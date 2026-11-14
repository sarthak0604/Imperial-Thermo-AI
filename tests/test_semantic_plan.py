"""Compiler regression tests. SI assistance: OpenAI Codex."""
import unittest
from imperial_thermo_ai.semantic_plan import compile_expression, compile_plan


class RouteTests(unittest.TestCase):
    def test_flat_criteria_compile_without_filtering_optional_airflow(self):
        plan = {'queries': [{'label': 'flames', 'return_type': 'Experiment', 'criteria': [
            {'node_type': 'Concept', 'field': 'name', 'operator': 'eq', 'value': 'flame spread', 'source_text': 'flame spread'}]}],
            'requested_fields': [{'node_type': 'Experiment', 'field': 'conditions.airflow', 'stage': None, 'optional': True}]}
        result = compile_plan(plan)
        self.assertEqual(len(result['queries'][0]['where']['items']), 1)
        self.assertEqual(result['queries'][0]['where']['items'][0]['edge'], 'STUDIES')
        self.assertEqual(result['requested_fields'], plan['requested_fields'])

    def test_topic_is_not_an_experiment_property(self):
        predicate = {'kind': 'filter', 'field': 'name', 'operator': 'eq', 'value': 'flame spread', 'source_text': 'flame spread'}
        result = compile_expression({'kind': 'on', 'node_type': 'Concept', 'where': predicate}, 'Experiment')
        self.assertEqual(result, {'kind': 'relation', 'edge': 'STUDIES', 'direction': 'out', 'where': predicate})

    def test_resource_to_variable_route(self):
        result = compile_expression({'kind': 'on', 'node_type': 'Variable', 'where': {'kind': 'all', 'items': []}}, 'Resource')
        self.assertEqual((result['edge'], result['direction']), ('HAS_RESOURCE', 'in'))
        self.assertEqual(result['where']['edge'], 'MEASURES')

    def test_same_resource_binding_and_negation(self):
        expr = {'kind': 'all', 'items': [
            {'kind': 'filter', 'field': key, 'operator': 'eq', 'value': value, 'source_text': value}
            for key, value in [('file_format', 'pdf'), ('resource_type', 'dataset')]]}
        result = compile_expression({'kind': 'not', 'item': {'kind': 'on', 'node_type': 'Resource', 'where': expr}}, 'Experiment')
        self.assertEqual(result['kind'], 'not')
        self.assertEqual(result['item']['edge'], 'HAS_RESOURCE')
        self.assertEqual(result['item']['where'], expr)

    def test_model_cannot_supply_routes(self):
        with self.assertRaises(ValueError):
            compile_expression({'kind': 'relation', 'edge': 'FAKE'}, 'Experiment')
