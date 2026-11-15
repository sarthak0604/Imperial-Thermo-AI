"""Synthetic vector retrieval and contract tests. SI: OpenAI Codex."""
import copy
import unittest
from imperial_thermo_ai.vector_search import VectorGraphSearch, documents, fingerprint, MODEL_ID
from imperial_thermo_ai.file_contract import SearchResults


def fixture():
    nodes = [
        {'id': 'inv:PSI-test', 'type': 'Investigation', 'properties': {'title': 'Synthetic', 'source_url': 'https://example.org/study'}},
        {'id': 'exp:a', 'type': 'Experiment', 'properties': {'conditions': {'gravity': 'microgravity'}}},
        {'id': 'c:a', 'type': 'Concept', 'properties': {'name': 'flame spread'}},
    ]
    edges = [dict(id='e1', source='inv:PSI-test', target='exp:a', type='CONTAINS', properties={}),
             dict(id='e2', source='exp:a', target='c:a', type='STUDIES', properties={})]
    for i, fmt in enumerate(['csv', 'pdf', 'png', 'mp4']):
        nodes.append({'id': f'file:{i}', 'type': 'Resource', 'properties': {
            'title': fmt, 'file_format': fmt, 'resource_type': 'dataset' if i == 0 else 'other',
            'variables': ['not_a_verified_column'], 'source_url': 'https://example.org/landing',
            'retrieval_url': f'https://example.org/file.{fmt}'}})
        edges.append(dict(id=f'r{i}', source='exp:a', target=f'file:{i}', type='HAS_RESOURCE', properties={}))
    graph = {'nodes': nodes, 'edges': edges}
    index = {'model_id': MODEL_ID, 'graph_fingerprint': fingerprint(graph),
             'vectors': {n['id']: [1.0, 0.0] for n in nodes}}
    return graph, index


class VectorTests(unittest.TestCase):
    def test_large_table_context_is_bounded_and_deduplicated(self):
        graph, _ = fixture()
        for i in range(30):
            key = f'exp:row:{i}'
            graph['nodes'].append({'id': key, 'type': 'Experiment', 'properties': {'summary': 'Source row ' * 300}})
            graph['edges'].extend([
                dict(id=f'contains:{i}', source='inv:PSI-test', target=key, type='CONTAINS', properties={}),
                dict(id=f'resource:{i}', source=key, target='file:0', type='HAS_RESOURCE', properties={}),
            ])
        text = documents(graph)['file:0']
        self.assertLessEqual(len(text), 24000)
        self.assertEqual(text.count('"title": "Synthetic"'), 1)

    def test_both_modes_emit_all_media_and_exact_contract(self):
        service = VectorGraphSearch(*fixture())
        for search in (service.local_search, service.global_search):
            result = search([1, 0], query_id='q')
            self.assertEqual(set(result), {'query_id', 'files'})
            self.assertEqual(len(result['files']), 4)
            self.assertEqual({f['role'] for f in result['files']}, {'measurement', 'documentation', 'image', 'video'})
            self.assertEqual(SearchResults.model_validate(result).query_id, 'q')
            for f in result['files']:
                self.assertIsNone(f['variables'])
                self.assertIsNone(f['size_bytes'])
                self.assertEqual(f['conditions'], {})
                self.assertEqual(f['run_ids'], [])
                self.assertNotIn('score', f)

    def test_no_matches(self):
        service = VectorGraphSearch(*fixture())
        for search in (service.local_search, service.global_search):
            self.assertEqual(search([-1, 0], query_id='q'), {'query_id': 'q', 'files': []})

    def test_local_scope_is_bounded(self):
        service = VectorGraphSearch(*fixture())
        self.assertEqual(service.local_search([1, 0], query_id='q', seed_k=1, hops=0)['files'], [])
        self.assertEqual(len(service.global_search([1, 0], query_id='q')['files']), 4)

    def test_compact_index_preserves_retrieval(self):
        import tempfile
        from pathlib import Path
        from imperial_thermo_ai.vector_search import save_index, load_index
        graph, index = fixture()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'index.npz'
            save_index(index, path)
            service = VectorGraphSearch(graph, load_index(path))
            result = service.global_search([1, 0], query_id='q')
        self.assertEqual(len(result['files']), 4)

    def test_stale_index_rejected(self):
        graph, index = fixture()
        graph['nodes'][0]['properties']['title'] = 'Changed'
        with self.assertRaises(ValueError):
            VectorGraphSearch(graph, index)

    def test_invalid_vectors_rejected(self):
        service = VectorGraphSearch(*fixture())
        for vector in ([0, 0], [1], [float('nan'), 0]):
            with self.assertRaises(ValueError):
                service.global_search(vector, query_id='q')
        with self.assertRaises(ValueError):
            service.global_search([1, 0], query_id='q', model_id='wrong')

    def test_landing_url_never_promoted(self):
        graph, index = fixture()
        for node in graph['nodes'][3:]:
            del node['properties']['retrieval_url']
        index['graph_fingerprint'] = fingerprint(graph)
        result = VectorGraphSearch(graph, index).global_search([1, 0], query_id='q')
        self.assertTrue(all(f['retrieval_url'] is None for f in result['files']))

    def test_duplicate_and_extra_fields_rejected(self):
        result = VectorGraphSearch(*fixture()).global_search([1, 0], query_id='q')
        bad = copy.deepcopy(result)
        bad['files'].append(bad['files'][0])
        with self.assertRaises(ValueError):
            SearchResults.model_validate(bad)
        result['score'] = 1
        with self.assertRaises(ValueError):
            SearchResults.model_validate(result)

    def test_known_conflicting_constraint_excludes_files(self):
        from imperial_thermo_ai.query_plan import validate_plan
        plan = {'original_question': 'normal gravity', 'language': 'en', 'normalized_question': 'normal gravity',
                'intent': 'find', 'search_text': 'flames', 'queries': [{'label': 'normal', 'return_type': 'Experiment',
                'where': {'kind': 'filter', 'field': 'conditions.gravity', 'operator': 'eq', 'value': 'normal gravity', 'source_text': 'normal gravity'}}]}
        plan = validate_plan(plan)
        service = VectorGraphSearch(*fixture())
        self.assertEqual(service.global_search([1, 0], query_id='q', plan=plan)['files'], [])


if __name__ == '__main__':
    unittest.main()
