"""Real reviewed snapshot → planner → executor → frontend contract regressions."""

import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import httpx

from imperial_thermo_ai.graph_files import nasa_download_url
from imperial_thermo_ai.reviewed_graph import load_graph
from request_planner.models import ExecutionLimits, FrontendResponse, Plan
from request_planner.planner import LocalPlanner, OpenAIPlanner
from request_planner.service import run_workflow


ROOT = Path(__file__).resolve().parents[1]


class ReviewedWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.search = load_graph()

    def test_default_snapshot_and_all_investigations(self):
        self.assertEqual(len(self.search.investigations), 19)
        self.assertGreater(len(self.search.owners), 60_000)
        self.assertTrue(self.search.graph.graph['graph_id'].startswith('NASA-PSI-19-reviewed'))
        for study in self.search.investigations:
            files = self.search.search(f'{study} experimental table').files
            self.assertTrue(files, study)
            self.assertEqual({f.investigation_id for f in files}, {study})

    def test_acronyms_do_not_cross_investigations(self):
        for name, study in [('BASS-II', 'PSI-25'), ('BASS', 'PSI-26'),
                            ('FLEX', 'PSI-69'), ('FLEX-2', 'PSI-68')]:
            files = self.search.search(f'Find {name} measurements').files
            self.assertTrue(files)
            self.assertEqual({f.investigation_id for f in files}, {study})

    def test_explicit_filters_and_unknown_ids(self):
        result = self.search.search('experimental table', investigation_id='PSI-25', role='measurement')
        self.assertTrue(result.files)
        self.assertEqual({f.investigation_id for f in result.files}, {'PSI-25'})
        self.assertFalse(self.search.search('Find PSI-99999 data').files)
        self.assertFalse(self.search.search('Find PSI-25 data', investigation_id='PSI-69').files)
        with self.assertRaises(ValueError):
            self.search.search('data', investigation_id='PSI-99999')

    def test_downloads_reviews_and_unknown_metadata_survive_handoff(self):
        result = self.search.search('Find PSI-117 extinction diameter pressure data')
        self.assertIn('Extinction_Diameter_vs_pressure', result.files[0].title)
        for file in result.files:
            if file.retrieval_url:
                self.assertIn('/download?', str(file.retrieval_url))
            self.assertIsNone(file.variables)
            self.assertEqual(file.conditions, {})
            self.assertEqual(file.run_ids, [])
        notes = ' '.join(result.files[0].data_notes)
        self.assertIn('reviewed_selected_sections', notes)
        self.assertIn('unequal lengths', notes)

    def test_untrusted_landing_or_mismatched_resolver_is_not_a_download(self):
        node = {'id': 'res:PSI-25:a', 'properties': {'source_url':
            'https://psi.nasa.gov/geode-py/ws/studies/PSI-25/download?file=abc&version=1'}}
        self.assertIsNotNone(nasa_download_url(node))
        for url in ('https://example.com/paper',
                    'https://psi.nasa.gov/physci/repo/data/investigations/PSI-25',
                    'https://psi.nasa.gov/geode-py/ws/studies/PSI-69/download?file=abc&version=1'):
            node['properties']['source_url'] = url
            self.assertIsNone(nasa_download_url(node))

    def test_video_reaches_frontend_with_raw_recording_caveat(self):
        results = self.search.search('Show BASS-II video')
        video = next(f for f in results.files if f.role == 'video' and (f.size_bytes or 0) < 100_000_000)
        plan = Plan(action='retrieve_assets', selected_file_ids=[], requested_asset_ids=[video.file_id],
                    operation=None, explanation='Display the requested recording.', warnings=[])
        response = run_workflow('Show BASS-II video', results, LocalPlanner(lambda messages: plan.model_dump_json()))
        self.assertEqual(response.status, 'completed')
        self.assertEqual(response.blocks[0]['type'], 'video')
        self.assertIn('listed_public_unread', ' '.join(response.warnings))
        FrontendResponse.model_validate_json(response.model_dump_json())

    def test_api_planner_repairs_invalid_selection_within_same_deadline(self):
        results = self.search.search('PSI-25 experimental table')
        valid = Plan(action='inspect_files', selected_file_ids=[results.files[0].file_id], requested_asset_ids=[],
                     operation=None, explanation='Inspect the table.', warnings=[])
        invalid = valid.model_copy(update={'selected_file_ids': ['invented']})
        client = Mock()
        client.responses.parse.side_effect = [SimpleNamespace(status='completed', output_parsed=p)
                                              for p in (invalid, valid)]
        plan = OpenAIPlanner('test', client=client).propose('Inspect the table', results, ExecutionLimits())
        self.assertEqual(plan, valid)
        calls = client.responses.parse.call_args_list
        self.assertIn('Unknown file ID', calls[1].kwargs['input'][-1]['content'])
        self.assertLess(calls[1].kwargs['timeout'], calls[0].kwargs['timeout'])

    def test_flex_profile_preserves_encoding_and_limits_unit_claims(self):
        file = self.search.search('PSI-69 FLEX experimental table').files[0]
        self.assertEqual(file.encoding, 'cp1252')
        variables = {v.name: v for v in file.variables}
        self.assertEqual(variables['Ambient pressure; mmHg'].unit, 'mmHg')
        self.assertEqual(variables['O initial ambient composition; mole fraction'].unit, '1')
        self.assertIsNone(variables['Burning rate; mm'].unit)

    def test_inspection_replanning_and_temporary_cleanup(self):
        # Synthetic downloaded bytes test mechanics; metadata and IDs are from
        # the reviewed graph. This does not claim these are NASA measurements.
        results = self.search.search('PSI-25 experimental table')
        file = results.files[0]
        body = b'clock,value\n0,1\n1,2\n'
        file.size_bytes = len(body)
        inspected = Plan(action='inspect_files', selected_file_ids=[file.file_id], requested_asset_ids=[],
                         operation=None, explanation='Inspect the unknown columns.', warnings=[])
        stopped = Plan(action='no_match', selected_file_ids=[], requested_asset_ids=[], operation=None,
                       explanation='Units are unavailable; cannot calculate.', warnings=[])
        contexts = []

        def generate(messages):
            context = json.loads(messages[-1]['content'])
            contexts.append(context)
            return (stopped if context['inspection'] else inspected).model_dump_json()

        def transfer(request):
            return httpx.Response(200, stream=httpx.ByteStream(body))

        with tempfile.TemporaryDirectory() as directory, httpx.Client(transport=httpx.MockTransport(transfer)) as client:
            response = run_workflow('Inspect and calculate only with verified units', results, LocalPlanner(generate),
                                    client=client, url_validator=lambda url: None, temp_dir=directory)
            self.assertEqual(list(Path(directory).iterdir()), [])
        self.assertEqual([r.plan.action for r in response.requests], ['inspect_files', 'no_match'])
        self.assertEqual(response.blocks[0]['row_count'], 2)
        self.assertIsNone(contexts[1]['graph_search_results']['files'][0]['variables'][0]['unit'])
        self.assertEqual(len(response.sources), 1)
        self.assertFalse(any(b['type'] == 'calculation' for b in response.blocks))

    def test_frontend_uses_reviewed_graph_by_default(self):
        path = ROOT / 'NASA Space Apps/frontend/standin/thermo.py'
        spec = importlib.util.spec_from_file_location('reviewed_frontend_thermo', path)
        frontend = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(frontend)

        def generate(messages, **kwargs):
            context = json.loads(messages[-1]['content'])
            files = context['graph_search_results']['files']
            self.assertTrue(all(f['file_id'].startswith('res:PSI-102:') for f in files))
            selected = next(f for f in files if f['media_type'] == 'application/pdf')
            return Plan(action='retrieve_assets', selected_file_ids=[], requested_asset_ids=[selected['file_id']],
                        operation=None, explanation='Display the SAME report.', warnings=[]).model_dump_json()

        with patch.object(frontend, 'instruction_model', return_value=SimpleNamespace(model=True, generate=generate)):
            response = frontend.ask('Show PSI-102 smoke detector report PDF', {})
        self.assertEqual(response['meta']['status'], 'completed')
        self.assertEqual(response['blocks'][0]['type'], 'document')
        self.assertEqual(response['evidence'][0]['psi_id'], 'PSI-102')


if __name__ == '__main__':
    unittest.main()
