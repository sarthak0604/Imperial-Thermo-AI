"""Vector-seeded local and repository-wide global graph retrieval.

SI assistance: OpenAI Codex. Vectors rank metadata; they do not verify science.
Global means all-investigation retrieval, not community-summary GraphRAG.
"""
import hashlib
import json
import math
from collections import deque
from .graph_search import GraphIndex, evaluate
from .semantic_plan import route
from .query_plan import validate_plan
from .file_contract import SearchResults

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
        result[key] = '\n'.join(json.dumps({'type': n['type'], 'properties': {
            k: v for k, v in n['properties'].items()
            if k in {'name', 'title', 'summary', 'description', 'keywords', 'synonyms',
                     'conditions', 'methods', 'variables', 'filename', 'resource_type', 'file_format', 'material'}
        }}, ensure_ascii=False) for n in selected)
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
            inputs = self.tokenizer(batch, padding=True, truncation=False, return_tensors='pt')
            if inputs.input_ids.shape[1] > 8192:
                raise ValueError('Embedding document exceeds 8192 tokens; chunk it before indexing.')
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
    return {'graph_fingerprint': fingerprint(graph), 'model_id': embedder.model_id,
            'vectors': dict(zip(docs, vectors))}


class VectorGraphSearch:
    def __init__(self, graph, index):
        self.graph = GraphIndex(graph)
        if index.get('graph_fingerprint') != fingerprint(graph):
            raise ValueError('Index belongs to a different graph snapshot; rebuild it.')
        self.model_id = index['model_id']
        if set(index['vectors']) != set(self.graph.nodes):
            raise ValueError('Index must cover exactly the graph nodes.')
        self.vectors = {key: unit_vector(v) for key, v in index['vectors'].items()}
        dimensions = {len(v) for v in self.vectors.values()}
        if len(dimensions) > 1:
            raise ValueError('Index vector dimensions differ.')
        self.dimension = next(iter(dimensions), None)

    def _scores(self, query_vector, model_id):
        if model_id != self.model_id:
            raise ValueError('Query and index must use the same embedding model.')
        vector = unit_vector(query_vector)
        if self.dimension is not None and len(vector) != self.dimension:
            raise ValueError('Query and index vector dimensions differ.')
        return {key: sum(a * b for a, b in zip(vector, value)) for key, value in self.vectors.items()}

    def _provenance(self, file_id):
        experiments = [e['source'] for e in self.graph.incoming[file_id] if e['type'] == 'HAS_RESOURCE']
        investigations = {e['source'] for exp in experiments for e in self.graph.incoming[exp] if e['type'] == 'CONTAINS'}
        if len(investigations) != 1:
            raise ValueError(f'{file_id}: exactly one source investigation is required for the file contract.')
        return next(iter(investigations)), experiments

    def _record(self, file_id, reason):
        node = self.graph.nodes[file_id]
        props = node['properties']
        inv_id, experiments = self._provenance(file_id)
        inv = self.graph.nodes[inv_id]['properties']
        fmt = str(props.get('file_format', '')).lower().lstrip('.')
        mime = props.get('media_type') or {
            'csv': 'text/csv', 'tsv': 'text/tab-separated-values', 'pdf': 'application/pdf',
            'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'gif': 'image/gif',
            'mp4': 'video/mp4', 'webm': 'video/webm', 'txt': 'text/plain', 'json': 'application/json',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        }.get(fmt, 'application/octet-stream')
        role = ('video' if mime.startswith('video/') else 'image' if mime.startswith('image/') else
                'documentation' if props.get('resource_type') == 'paper' else
                'measurement' if props.get('resource_type') == 'dataset' else
                'documentation' if mime == 'application/pdf' else 'other')
        notes = list(props.get('data_notes') or [])
        url = props.get('retrieval_url') or props.get('download_url')
        if not url:
            notes.append('Download URL unknown; a landing page is not a file download. Planner cannot select this file yet.')
        if not props.get('columns_verified'):
            variables = None
        else:
            variables = props.get('column_metadata')
        # Never promote graph Variable names or Resource.variables tags to inspected column headers.
        if variables is None:
            notes.append('Column headers, units and numeric suitability have not been verified.')
        # Only explicitly file-level facts are exported, never inherited run conditions.
        conditions = props.get('file_conditions') or {}
        run_ids = props.get('run_ids', []) if props.get('run_ids_verified') else []
        path_edges = [e for exp in experiments for e in self.graph.incoming[exp] + self.graph.outgoing[exp]
                      if e['type'] == 'CONTAINS' or e['target'] == file_id]
        if any(e.get('properties', {}).get('origin') == 'illustrative' or
               e.get('properties', {}).get('verification_status') == 'needs_review' for e in path_edges):
            notes.append('Graph provenance is illustrative or needs review; this is not verified experimental evidence.')
        return {'file_id': file_id, 'investigation_id': inv.get('investigation_id') or inv_id.removeprefix('inv:'),
                'title': props.get('title') or props.get('filename') or file_id,
                'role': role, 'media_type': mime, 'retrieval_url': url,
                'source_page_url': props.get('source_page_url') or props.get('source_url') or inv.get('source_url'),
                'size_bytes': props.get('size_bytes'), 'run_ids': run_ids, 'variables': variables,
                'encoding': props.get('encoding'), 'conditions': conditions, 'data_notes': notes,
                'related_file_ids': props.get('related_file_ids') or [], 'match_reason': reason}

    def _finish(self, ranked, query_id, plan, top_k, include_unknown):
        if type(top_k) is not int or not 1 <= top_k <= 1000:
            raise ValueError('top_k must be 1..1000.')
        if plan is not None:
            plan = validate_plan(plan, graph=self.graph.graph)
        files = []
        for file_id, score, reason in sorted(ranked, key=lambda row: (-row[1], row[0])):
            if plan is not None:
                evaluations = [evaluate(self.graph, file_id, route('Resource', q['return_type'], q['where']))
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
                     hops=2, top_k=20, min_score=0.3, plan=None, include_unknown=True):
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
            while queue:
                current, distance = queue.popleft()
                if self.graph.nodes[current]['type'] == 'Resource':
                    score = 0.7 * scores[current] + 0.3 * scores[seed] - 0.03 * distance
                    if current not in found or score > found[current][1]:
                        found[current] = (current, score, f'Local semantic match via node {seed}; graph distance {distance}.')
                if distance < hops:
                    for edge in self.graph.outgoing[current] + self.graph.incoming[current]:
                        other = edge['target'] if edge['source'] == current else edge['source']
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
            inv, _ = self._provenance(key)
            ranked.append((key, 0.85 * scores[key] + 0.15 * scores[inv],
                           f'Global semantic file match within investigation {inv}; searched across all investigations.'))
        return self._finish(ranked, query_id, plan, top_k, include_unknown)
