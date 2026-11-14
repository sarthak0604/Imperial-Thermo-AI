"""Tests for meaningful semantic scoring. SI assistance: OpenAI Codex."""

import unittest

from evaluate_v2 import check_plan


class EvaluationTests(unittest.TestCase):
    def plan(self, where):
        return {"intent": "find", "queries": [{"return_type": "Experiment", "where": where}]}

    def atom(self, field, value, operator="eq"):
        return {"kind": "filter", "field": field, "operator": operator, "value": value}

    def test_or_is_not_scored_as_and(self):
        atoms = [self.atom("file_format", "csv"), self.atom("file_format", "pdf")]
        expected = {"alternative_values": {"field": "file_format", "values": ["csv", "pdf"]}}
        self.assertTrue(check_plan(self.plan({"kind": "all", "items": atoms}), expected))
        self.assertEqual(check_plan(self.plan({"kind": "any", "items": atoms}), expected), [])

    def test_negative_filter_is_not_counted_as_invented_positive(self):
        plan = self.plan({"kind": "not", "item": self.atom("conditions.gravity", "microgravity")})
        self.assertEqual(check_plan(plan, {"forbidden_filters": [{"field": "conditions.gravity", "value": "microgravity"}]}), [])

    def test_units_and_boundaries_are_scored(self):
        plan = self.plan(self.atom("conditions.oxygen_concentration", 21, "lt"))
        self.assertTrue(check_plan(plan, {"filters": [{"field": "conditions.oxygen_concentration", "value": 21, "operator": "lte"}]}))
        self.assertTrue(check_plan(plan, {"filters": [{"field": "conditions.oxygen_concentration", "unit": "%"}]}))

    def test_optional_final_oxygen_is_not_a_required_filter(self):
        plan = self.plan(self.atom("conditions.oxygen_concentration", 21, "lte"))
        plan["requested_fields"] = [{"field": "conditions.oxygen_concentration", "stage": "final", "optional": True}]
        expected = {"requested_fields": [{"field": "conditions.oxygen_concentration", "stage": "final", "optional": True}],
                    "forbidden_filters": [{"field": "conditions.oxygen_concentration", "stage": "final"}]}
        self.assertEqual(check_plan(plan, expected), [])

    def test_original_question_alone_cannot_satisfy_preserved_details(self):
        plan = self.plan({"kind": "all", "items": []})
        plan["original_question"] = "Kevlar mesh spark"
        self.assertTrue(check_plan(plan, {"required_terms": ["mesh", "spark"]}))


if __name__ == "__main__":
    unittest.main()
