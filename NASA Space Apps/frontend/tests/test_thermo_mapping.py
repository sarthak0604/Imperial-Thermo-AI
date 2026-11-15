"""Check the reviewed example routing without downloading the report or loading Qwen."""

import json
from pathlib import Path
import sys
import unittest

from request_planner.mini_graph import MiniGraph, search_graph

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "standin"))
import thermo


class ReviewedDropletTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        graph_path = thermo.REPO / "examples" / "psi_graph.json"
        cls.graph = MiniGraph.model_validate_json(graph_path.read_text(encoding="utf-8"))

    def plan(self, question):
        return thermo.reviewed_r377_plan(question, search_graph(self.graph, question))

    def test_requested_duration_is_sourced_from_the_question(self):
        question = "How big would a burning fuel droplet be after 5 seconds in microgravity?"
        plan = self.plan(question)
        self.assertEqual(plan.operation.parameters.model_id, "THM-10")
        self.assertIn("n-decane", plan.warnings[0])
        bindings = json.loads(plan.operation.parameters.request_json)["input_mapping"]["assignments"]
        time = next(entry["source"] for entry in bindings if entry["target"].endswith("/time_limit_s"))
        self.assertEqual(time, {"kind": "prompt", "quote": "5 seconds", "token": "5", "unit": "seconds"})

    def test_methane_lewis_example_uses_real_solver_and_declares_its_assumptions(self):
        answer = thermo.ask("figure out the lewis number for a methane flame in a nitrogen diluted ISS environment", {})
        self.assertEqual(answer["meta"]["model"], "THM-02")
        calc, chart = answer["blocks"]
        baseline = calc["data"]
        self.assertEqual(baseline["inputs"]["target_species"], "CH4")
        self.assertAlmostEqual(baseline["inputs"]["normalized_mole_fracs"]["CH4"], 0.21 / 2.21, places=6)
        self.assertAlmostEqual(baseline["inputs"]["pressure_kpa"], 101.3)
        self.assertEqual(chart["x"]["values"], [21, 18, 15])
        self.assertEqual(chart["series"][0]["values"][0], baseline["dimensionless_numbers"]["lewis_number"])
        self.assertTrue(any("illustrative" in text for text in baseline["assumptions"]))

    def test_other_fuelling_or_phase_questions_go_to_the_general_planner(self):
        self.assertIsNone(self.plan("How does a methanol droplet shrink in 10 seconds in space?"))
        self.assertEqual(self.plan("How much does a burning fuel droplet shrink in 20 seconds in space?").action,
                         "no_match")


if __name__ == "__main__":
    unittest.main()
