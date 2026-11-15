"""Vector-seeded local and repository-wide global graph retrieval.

SI assistance: OpenAI Codex. Vectors rank metadata; they do not verify science.
Global means all-investigation retrieval, not community-summary GraphRAG.
"""
import hashlib
import json
import math
from collections import deque
from .graph_search import GraphIndex, evaluate
from .semantic_plan import route, resource_expression
from .query_plan import validate_plan
from .file_contract import SearchResults
from .graph_files import GraphFileRecords

MODEL_ID = 'Qwen/Qwen3-Embedding-0.6B'
INSTRUCTION = 'Given a space fire-safety research question, retrieve relevant NASA PSI combustion investigations, experiments, and files.'


def unit_vector(values):
    if not isinstance(values, (list, tuple)) or not values:
        raise ValueError('Expected a nonempty vector list.')
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
        raise ValueError('Vector components must be finite numbers.')
    norm = math.sqrt(sum(v * v for v in values))
    if not math.isfinite(norm) or norm == 0:
        raise ValueError('Vector must have a finite nonzero norm.')
    return [v / norm for v in values]


def fingerprint(graph):
    return hashlib.sha256(json.dumps(graph, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def documents(graph):
    index = GraphIndex(graph)
    result = {}
    # Resource descriptions inherit only their own experiment/investigation context.
    # Do not expand through shared concepts into unrelated experiments.
    for key, node in index.nodes.items():
        selected = [node]
        if node['type'] == 'Resource':
            for edge in index.incoming[key]:
                exp = index.nodes[edge['source']]
                selected.append(exp)
                selected.extend(index.nodes[e['target']] for e in index.outgoing[exp['id']]
                                if e['type'] in {'STUDIES', 'MEASURES'})
                selected.extend(index.nodes[e['source']] for e in index.incoming[exp['id']]
                                if e['type'] == 'CONTAINS')
        # A table can link hundreds of source-row experiments. Deduplicate their
        # common investigation and bound ranking text; constraint evaluation
        # still uses the complete original graph.
        unique = {n['id']: n for n in selected}
        result[key] = '\n'.join(json.dumps({'type': n['type'], 'properties': {
            k: v for k, v in n['properties'].items()
            if k in {'name', 'title', 'summary', 'description', 'keywords', 'synonyms',
                     'conditions', 'methods', 'variables', 'filename', 'resource_type', 'file_format', 'material'}
        }}, ensure_ascii=False) for n in unique.values())[:24000]
    return result


class QwenEmbedder:
    def __init__(self, model_id=MODEL_ID):
        import torch
        from transformers import AutoModel, AutoTokenizer
        self.model_id = model_id
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, padding_side='left', local_files_only=True)
        self.model = AutoModel.from_pretrained(model_id, device_map='auto', dtype='auto', local_files_only=True).eval()

    def encode(self, texts, *, query=False, batch_size=4):
        import torch
        import torch.nn.functional as F
        output = []
        for offset in range(0, len(texts), batch_size):
            batch = texts[offset:offset + batch_size]
            if query:
                batch = [f'Instruct: {INSTRUCTION}\nQuery: {text}' for text in batch]
            inputs = self.tokenizer(batch, padding=True, truncation=True, max_length=8192, return_tensors='pt')
            inputs = inputs.to(self.model.device)
            with torch.inference_mode():
                hidden = self.model(**inputs).last_hidden_state[:, -1, :]
                output.extend(F.normalize(hidden.float(), p=2, dim=-1).cpu().tolist())
        return output


def build_index(graph, embedder):
    docs = documents(graph)
    vectors = embedder.encode(list(docs.values()))
    if len(vectors) != len(docs):
        raise ValueError('Embedding count differs from node count.')
    return {'document_version': '2.0-bounded-context', 'query_instruction': INSTRUCTION,
            'model_revision': getattr(embedder, 'revision', 'local-cache'),
            'graph_fingerprint': fingerprint(graph), 'model_id': embedder.model_id,
            'vectors': dict(zip(docs, vectors))}


class VectorGraphSearch(GraphFileRecords):
    def __init__(self, graph, index):
        self.graph = GraphIndex(graph)
        if index.get('graph_fingerprint') != fingerprint(graph):
            raise ValueError('Index belongs to a different graph snapshot; rebuild it.')
        self.model_id = index['model_id']
        if set(index['vectors']) != set(self.graph.nodes):
            raise ValueError('Index must cover exactly the graph nodes.')
        self.keys = list(index['vectors'])
        vectors = [unit_vector(index['vectors'][key]) for key in self.keys]
        dimensions = {len(v) for v in vectors}
        if len(dimensions) > 1:
            raise ValueError('Index vector dimensions differ.')
        self.dimension = next(iter(dimensions), None)
        import numpy as np
        self.matrix = np.asarray(vectors, dtype=np.float32)

    def _scores(self, query_vector, model_id):
        if model_id != self.model_id:
            raise ValueError('Query and index must use the same embedding model.')
        vector = unit_vector(query_vector)
        if self.dimension is not None and len(vector) != self.dimension:
            raise ValueError('Query and index vector dimensions differ.')
        if not self.keys:
            return {}
        import numpy as np
        values = self.matrix @ np.asarray(vector, dtype=np.float32)
        return {key: float(value) for key, value in zip(self.keys, values)}

    def _finish(self, ranked, query_id, plan, top_k, include_unknown):
        if type(top_k) is not int or not 1 <= top_k <= 1000:
            raise ValueError('top_k must be 1..1000.')
        if plan is not None:
            plan = validate_plan(plan, graph=self.graph.graph)
        files = []
        for file_id, score, reason in sorted(ranked, key=lambda row: (-row[1], row[0])):
            if self._provenance(file_id) is None:
                continue
            if plan is not None:
                evaluations = [evaluate(self.graph, file_id, resource_expression(q['return_type'], q['where']))
                               for q in plan['queries']]
                if not evaluations:
                    continue
                if any(e.state is True for e in evaluations):
                    reason += ' Requested graph metadata conditions match.'
                elif include_unknown and any(e.state is None and not any(
                        detail.get('status') == 'conflicting' for detail in e.details) for e in evaluations):
                    reason += ' Candidate only: some requested conditions cannot be verified from graph metadata.'
                else:
                    continue
            files.append(self._record(file_id, reason))
            if len(files) == top_k:
                break
        return SearchResults.model_validate({'query_id': query_id, 'files': files}).model_dump()

    def local_search(self, query_vector, *, query_id, model_id=MODEL_ID, seed_k=5,
                     hops=2, top_k=20, min_score=0.3, plan=None, include_unknown=True, max_nodes=5000):
        """Rank seed nodes, expand bounded neighborhoods, then return linked files."""
        if type(seed_k) is not int or seed_k < 1 or type(hops) is not int or not 0 <= hops <= 4:
            raise ValueError('seed_k must be positive; hops must be 0..4.')
        scores = self._scores(query_vector, model_id)
        if not math.isfinite(min_score) or not -1 <= min_score <= 1:
            raise ValueError('min_score must be finite and between -1 and 1.')
        seeds = sorted((k for k, v in scores.items() if v >= min_score), key=lambda k: (-scores[k], k))[:seed_k]
        found = {}
        for seed in seeds:
            queue, seen = deque([(seed, 0)]), {seed}
            while queue and len(seen) <= max_nodes:
                current, distance = queue.popleft()
                if self.graph.nodes[current]['type'] == 'Resource':
                    score = 0.7 * scores[current] + 0.3 * scores[seed] - 0.03 * distance
                    if current not in found or score > found[current][1]:
                        found[current] = (current, score, f'Local semantic match via node {seed}; graph distance {distance}.')
                if distance < hops:
                    for edge in self.graph.outgoing[current] + self.graph.incoming[current]:
                        other = edge['target'] if edge['source'] == current else edge['source']
                        if len(seen) >= max_nodes:
                            break
                        if other not in seen:
                            seen.add(other)
                            queue.append((other, distance + 1))
        return self._finish(list(found.values()), query_id, plan, top_k, include_unknown)

    def global_search(self, query_vector, *, query_id, model_id=MODEL_ID, top_k=20,
                      min_score=0.3, plan=None, include_unknown=True):
        """Score every file, with a small investigation relevance contribution."""
        scores = self._scores(query_vector, model_id)
        if not math.isfinite(min_score) or not -1 <= min_score <= 1:
            raise ValueError('min_score must be finite and between -1 and 1.')
        ranked = []
        for key, node in self.graph.nodes.items():
            if node['type'] != 'Resource' or scores[key] < min_score:
                continue
            provenance = self._provenance(key)
            if provenance is None:
                continue
            inv, _ = provenance
            ranked.append((key, 0.85 * scores[key] + 0.15 * scores[inv],
                           f'Global semantic file match within investigation {inv}; searched across all investigations.'))
        return self._finish(ranked, query_id, plan, top_k, include_unknown)


def save_index(index, path):
    """Compact numeric storage; JSON remains supported for existing fixtures."""
    from pathlib import Path
    import numpy as np
    path = Path(path)
    if path.suffix == '.npz':
        metadata = {k:v for k,v in index.items() if k != 'vectors'}
        keys = list(index['vectors'])
        np.savez_compressed(path, metadata=json.dumps(metadata), keys=np.asarray(keys),
                            vectors=np.asarray([index['vectors'][k] for k in keys], dtype=np.float32))
    else:
        path.write_text(json.dumps(index, allow_nan=False))


def load_index(path):
    from pathlib import Path
    import numpy as np
    path = Path(path)
    if path.suffix != '.npz':
        return json.loads(path.read_text())
    with np.load(path, allow_pickle=False) as data:
        metadata = json.loads(str(data['metadata']))
        vectors = data['vectors']
        metadata['vectors'] = {str(k):v.tolist() for k,v in zip(data['keys'], vectors)}
        return metadata
