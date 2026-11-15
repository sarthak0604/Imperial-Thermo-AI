"""Graph/search integration checks, offline. SI-assisted tests; see README.md."""

import json
from pathlib import Path
import unittest

from pydantic import ValidationError

from request_planner.__main__ import ReplayPlanner
from request_planner.mini_graph import MiniGraph, search_graph
from request_planner.planner import build_request


ROOT = Path(__file__).resolve().parents[1]


class MiniGraphTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / "examples/psi_graph.json").read_text())
        self.graph = MiniGraph.model_validate(self.data)

    def test_topic_traversal_finds_droplet_files(self):
        results = search_graph(self.graph, "extinguishment")
        self.assertEqual({file.file_id for file in results.files},
                         {"psi69-experimental-table", "nasa-cool-flame-report"})
        self.assertIn("Graph path: PSI-69 --has_file-->", results.files[0].match_reason)

    def test_droplet_question_finds_the_citable_r377_report(self):
        results = search_graph(self.graph, "How much does a burning fuel droplet shrink in 10 seconds in space?")
        report = results.files[0]
        self.assertEqual(report.run_ids, ["R377"])
        self.assertEqual(str(report.source_page_url), "https://ntrs.nasa.gov/citations/20140006750")

    def test_investigation_and_role_filters(self):
        results = search_graph(self.graph, "BASS-II", investigation_id="PSI-25", role="video")
        self.assertEqual([file.file_id for file in results.files], ["psi25-t23-video"])
        self.assertNotIn("psi69-experimental-table", results.files[0].related_file_ids)

    def test_no_unrelated_fallback_and_limit(self):
        self.assertEqual(search_graph(self.graph, "turbopump").files, [])
        self.assertEqual(len(search_graph(self.graph, "combustion", limit=2).files), 2)

    def test_unknown_investigation_and_invalid_limit(self):
        with self.assertRaisesRegex(ValueError, "Unknown investigation"):
            search_graph(self.graph, "airflow", investigation_id="PSI-999999")
        with self.assertRaisesRegex(ValueError, "positive"):
            search_graph(self.graph, "airflow", limit=0)

    def test_dangling_edge_and_conflicting_owner_are_rejected(self):
        self.data["edges"].append({"source": "PSI-25", "relation": "has_file", "target": "missing"})
        with self.assertRaisesRegex(ValidationError, "existing file"):
            MiniGraph.model_validate(self.data)
        self.data["edges"][-1]["target"] = "psi69-experimental-table"
        with self.assertRaisesRegex(ValidationError, "matching investigation owner"):
            MiniGraph.model_validate(self.data)

    def test_checked_in_results_are_reproducible(self):
        results = search_graph(self.graph, "BASS-II airflow calibration video",
                               investigation_id="PSI-25", limit=5)
        saved = json.loads((ROOT / "examples/psi_search_results.json").read_text())
        self.assertEqual(results.model_dump(mode="json"), saved)

    def test_real_search_results_feed_existing_planner_contract(self):
        results = search_graph(self.graph, "BASS-II airflow calibration video",
                               investigation_id="PSI-25", limit=5)
        request = build_request(
            "Find BASS-II airflow measurements, calibration and a test video",
            results,
            ReplayPlanner(ROOT / "examples/psi_inspection_plan.json"),
        )
        self.assertEqual(request.plan.action, "inspect_files")
        self.assertEqual(request.query_id, results.query_id)
        table = next(file for file in results.files if file.file_id == "psi25-experimental-table")
        column = next(var for var in table.variables if var.name == "Air display")
        self.assertIs(column.numeric, False)
        self.assertIsNone(column.unit)


if __name__ == "__main__":
    unittest.main()
