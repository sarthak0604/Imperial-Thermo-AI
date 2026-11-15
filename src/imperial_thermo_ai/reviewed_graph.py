"""Indexed lexical retrieval over the reviewed PSI graph. SI: OpenAI Codex."""

import argparse
from collections import defaultdict
from functools import lru_cache
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys

import reviewed_knowledge_graph

from .graph_files import GraphFileRecords, file_kind
from .graph_search import GraphIndex, stringify, tokens
from request_planner.models import SearchResults


def default_graph_path():
    return Path(os.environ.get("THERMO_GRAPH") or Path(reviewed_knowledge_graph.__file__).parent
                / "output" / "knowledge_graph.json")


class ReviewedGraphSearch(GraphFileRecords):
    """Index direct and owning-experiment text without traversing shared concepts.

    Lexical scores express discovery relevance, not satisfaction of requested
    numerical conditions. The planner must inspect files before calculating.
    """

    def __init__(self, graph):
        self.graph = GraphIndex(graph)
        self.direct = defaultdict(set)
        self.context = defaultdict(set)
        self.owners = {}
        self.investigations = {}
        self.roles = {}
        self.statuses = {}
        self.aliases = {}
        for key, node in self.graph.nodes.items():
            if node['type'] == 'Investigation':
                self.investigations[key.removeprefix('inv:')] = key
            elif node['type'] == 'Experiment':
                title = node['properties'].get('title', '')
                if node['properties'].get('conditions', {}).get('record_kind') == 'investigation_campaign':
                    alias = title.split(' — ')[0]
                    parents = [e['source'] for e in self.graph.incoming[key] if e['type'] == 'CONTAINS']
                    if alias and len(parents) == 1:
                        self.aliases[alias] = parents[0].removeprefix('inv:')
                nearby = [node]
                nearby.extend(self.graph.nodes[e['source']] for e in self.graph.incoming[key]
                              if e['type'] == 'CONTAINS')
                nearby.extend(self.graph.nodes[e['target']] for e in self.graph.outgoing[key]
                              if e['type'] in {'STUDIES', 'MEASURES'})
                for term in tokens(' '.join(stringify(n['properties']) for n in nearby)):
                    self.context[term].add(key)
            elif node['type'] == 'Resource':
                provenance = self._provenance(key)
                if provenance is None:
                    continue
                self.owners[key] = provenance
                props = node['properties']
                text = ' '.join(stringify(props.get(field)) for field in
                                ('title', 'filename', 'summary', 'keywords', 'variables', 'resource_type'))
                # Underscores are filename separators, not part of a search word.
                self.roles[key] = file_kind(props)[1]
                for term in tokens(text.replace('_', ' ') + ' ' + self.roles[key]):
                    self.direct[term].add(key)
                self.statuses[key] = props.get('access_status')

    def crosslinks(self, investigations, excluded=(), limit=3):
        """Rank shared graph concepts and measurements, favoring specific links."""
        relations = {}
        for psi_id, key in self.investigations.items():
            relations[psi_id] = {
                (edge["type"], edge["target"])
                for member in self.graph.outgoing[key] if member["type"] == "CONTAINS"
                for edge in self.graph.outgoing[member["target"]]
                if edge["type"] in {"STUDIES", "MEASURES"}
            }
        frequency = defaultdict(int)
        for terms in relations.values():
            for term in terms:
                frequency[term] += 1
        anchors = set(investigations) & relations.keys() - set(excluded)
        if not anchors:
            return []
        targets = anchors if len(anchors) > 1 else relations.keys() - set(excluded)
        ranked = []
        for left in sorted(anchors):
            for right in sorted(targets - {left}):
                if right in anchors and right < left:
                    continue
                shared = sorted(relations[left] & relations[right],
                                key=lambda item: (frequency[item], item))
                reasons = []
                for relation, key in shared:
                    properties = self.graph.nodes[key]["properties"]
                    label = properties.get("name") or properties.get("title")
                    if label:
                        reasons.append({"kind": "measurement" if relation == "MEASURES" else "topic",
                                        "label": label, "node_id": key})
                if reasons:
                    score = sum(1 / frequency[term] for term in shared[:3])
                    ranked.append((score, left, right, reasons[:3]))
        ranked.sort(key=lambda row: (-row[0], row[1], row[2]))
        return [{"from": left, "to": right, "shared": reasons}
                for _, left, right, reasons in ranked[:limit]]

    def search(self, query, *, investigation_id=None, role=None, limit=6, query_id=None):
        if not isinstance(query, str) or not query.strip():
            raise ValueError('Search query must not be empty')
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError('Search limit must be 1..1000')
        if role and role not in {'measurement', 'documentation', 'image', 'video', 'other'}:
            raise ValueError('Unknown file role')
        if investigation_id and investigation_id not in self.investigations:
            raise ValueError(f'Unknown investigation: {investigation_id}')
        # An exact PSI ID in the question scopes retrieval, including unknown IDs.
        scopes = {re.sub(r'\s+', '', s.upper()) for s in re.findall(r'\bPSI\s*-\s*\d+\b', query, re.I)}
        if investigation_id:
            if scopes and investigation_id not in scopes:
                return SearchResults(query_id=query_id or self.query_id(query, investigation_id, role, limit), files=[])
            scopes = {investigation_id}
        if not scopes:
            remaining = query
            for alias in sorted(self.aliases, key=len, reverse=True):
                pattern = r'(?<![\w-])' + re.escape(alias) + r'(?![\w-])'
                if re.search(pattern, remaining, re.I):
                    scopes.add(self.aliases[alias])
                    remaining = re.sub(pattern, '', remaining, flags=re.I)
        excluded = {m.group(1).upper().replace(' ', '') for m in re.finditer(
            r'(?:excluding|except|without|not)\s+(PSI\s*-\s*\d+)', query, re.I)}
        scopes -= excluded
        if excluded and any(self.aliases.get(alias) in excluded and re.search(
                r'(?<![\w-])' + re.escape(alias) + r'(?![\w-])', query, re.I)
                for alias in self.aliases):
            return SearchResults(query_id=query_id or self.query_id(query, investigation_id, role, limit), files=[])
        terms = tokens(query.replace('_', ' '))
        terms -= {'psi', *re.findall(r'\b\d+\b', query)}
        preferred_roles = set()
        query_words = set(re.findall(r'\w+', query.casefold()))
        for words, kind in (({'video', 'videos'}, 'video'), ({'image', 'images', 'photo'}, 'image'),
                            ({'report', 'reports', 'pdf'}, 'documentation'),
                            ({'measurement', 'measurements', 'table', 'csv'}, 'measurement')):
            if words & query_words:
                preferred_roles.add(kind)
        # Entity names constrain scope; they are not evidence of topic relevance.
        meaningful = re.sub(r'\bPSI\s*-\s*\d+\b', '', query, flags=re.I)
        for alias in sorted(self.aliases, key=len, reverse=True):
            meaningful = re.sub(r'(?<![\w-])' + re.escape(alias) + r'(?![\w-])', '', meaningful, flags=re.I)
        meaningful_terms = tokens(meaningful) - {'excluding', 'except', 'without', 'not'}
        scores = defaultdict(float)
        exp_scores = defaultdict(float)
        for term in terms:
            for key in self.direct.get(term, ()):
                scores[key] += 3 * math.log1p(len(self.owners) / max(1, len(self.direct[term])))
            for key in self.context.get(term, ()):
                exp_scores[key] += 1
        inherited = defaultdict(float)
        for exp, score in exp_scores.items():
            for edge in self.graph.outgoing[exp]:
                if edge['type'] == 'HAS_RESOURCE':
                    # A table linked to many rows gets its strongest context,
                    # rather than an artificial boost for every duplicate path.
                    inherited[edge['target']] = max(inherited[edge['target']], score)
        ranked = []
        for key, (inv, experiments) in self.owners.items():
            if inv.removeprefix('inv:') in excluded:
                continue
            if scopes and inv.removeprefix('inv:') not in scopes:
                continue
            if role and self.roles[key] != role:
                continue
            score = scores.get(key, 0) + inherited.get(key, 0)
            if meaningful_terms and not any(key in self.direct.get(t, ()) or any(
                    exp in self.context.get(t, ()) for exp in experiments) for t in meaningful_terms):
                continue
            if score <= 0 and not scopes:
                continue
            if self.roles[key] in preferred_roles:
                score += 12
            # Prefer reviewed sources on equal relevance; large raw inventories
            # must not bury experiment tables or reports behind thousands of files.
            reviewed = self.statuses[key] in {'reviewed_selected_sections', 'structured_table_reviewed'}
            ranked.append((key, score, reviewed))
        ranked.sort(key=lambda row: (-row[1], -row[2], row[0]))
        # Round robin investigation groups so a large inventory cannot starve a comparison.
        if len(scopes) > 1:
            groups = {scope: [r for r in ranked if self.owners[r[0]][0].removeprefix('inv:') == scope] for scope in sorted(scopes)}
            ranked = [rows[i] for i in range(max((len(v) for v in groups.values()), default=0))
                      for rows in groups.values() if i < len(rows)]
        records = []
        for key, score, reviewed in ranked[:limit]:
            inv = self.owners[key][0]
            records.append(self._record(key,
                f'Lexical discovery through {inv} --CONTAINS--> Experiment --HAS_RESOURCE--> {key}. '
                'Requested numerical conditions are not verified by text relevance. '
                'Campaign membership does not establish a shared physical run.'))
        return SearchResults.model_validate({'query_id': query_id or self.query_id(query, investigation_id, role, limit),
                                             'files': records})

    def query_id(self, query, investigation_id, role, limit):
        value = [self.graph.graph.get('graph_id'), query, investigation_id, role, limit]
        return 'psi-reviewed-' + hashlib.sha256(json.dumps(value).encode()).hexdigest()[:12]


def read_graph(path):
    """Read the snapshot and attach separately retained file inspection facts."""
    graph = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    metadata_path = Path(__file__).with_name('reviewed_file_metadata.json')
    metadata = json.loads(metadata_path.read_text()) if metadata_path.is_file() else {}
    for node in graph.get('nodes', []):
        profile = metadata.get(node.get('id'))
        props = node.get('properties', {})
        if (node.get('type') == 'Resource' and profile
                and props.get('source_url') == profile['source_url']
                and props.get('size_bytes') == profile['size_bytes']):
            props.update(profile_sha256=profile['sha256'], encoding=profile['encoding'], columns_verified=True,
                         column_metadata=profile['column_metadata'],
                         data_notes=[*props.get('data_notes', []), *profile['data_notes'],
                                     'Profiled source SHA-256: ' + profile['sha256']])
    quality_path = Path(path).with_name('source_quality_issues.json')
    issues = defaultdict(set)
    if quality_path.is_file():
        for item in json.loads(quality_path.read_text()):
            issues[(item.get('study'), item.get('filename'))].update(item.get('issues', []))
    for node in graph.get('nodes', []):
        if node.get('type') == 'Resource':
            props = node['properties']
            study = node['id'].split(':')[1] if ':' in node['id'] else None
            notes = sorted(issues.get((study, props.get('filename')), ()))
            if notes:
                props['data_notes'] = [*props.get('data_notes', []),
                                       *('Source quality issue: ' + note for note in notes)]
    from .quantities import normalize_graph
    normalize_graph(graph)
    return graph


@lru_cache(maxsize=1)
def _load(path, mtime_ns, size):
    return ReviewedGraphSearch(read_graph(path))


def load_graph(path=None):
    path = Path(path or default_graph_path()).resolve()
    stat = path.stat()
    return _load(str(path), stat.st_mtime_ns, stat.st_size)


def main():
    cli = argparse.ArgumentParser(description='Search the reviewed NASA PSI knowledge graph')
    cli.add_argument('--graph', type=Path, default=default_graph_path())
    cli.add_argument('--query', required=True)
    cli.add_argument('--query-id')
    cli.add_argument('--investigation')
    cli.add_argument('--role', choices=['measurement', 'documentation', 'video', 'image', 'other'])
    cli.add_argument('--limit', type=int, default=6)
    cli.add_argument('--output', type=Path)
    args = cli.parse_args()
    try:
        results = load_graph(args.graph).search(args.query, investigation_id=args.investigation,
                    role=args.role, limit=args.limit, query_id=args.query_id)
        output = results.model_dump_json(indent=2) + '\n'
        if args.output:
            args.output.write_text(output, encoding='utf-8')
        else:
            sys.stdout.write(output)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f'Search failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
