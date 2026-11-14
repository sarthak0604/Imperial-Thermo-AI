"""Offline contract and SDK-boundary checks. SI-assisted tests; see README.md."""

import json
from pathlib import Path
import unittest

import httpx
from openai import OpenAI
from pydantic import ValidationError

from request_planner.models import Plan, SearchResults
from request_planner.planner import OpenAIPlanner, PlanningError, build_request


ROOT = Path(__file__).resolve().parents[1]


class FixedPlanner:
    def __init__(self, plan):
        self.plan = plan

    def propose(self, prompt, results, limits):
        return self.plan


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.graph_data = json.loads((ROOT / "examples/graph_search.json").read_text())
        self.plan_data = json.loads((ROOT / "examples/plan.json").read_text())

    def request(self):
        return build_request(
            "Plot flame spread against airflow and show the video",
            SearchResults.model_validate(self.graph_data),
            FixedPlanner(Plan.model_validate(self.plan_data)),
        )

    def test_known_columns_produce_calculation_request_with_provenance(self):
        request = self.request()
        self.assertEqual(request.plan.operation.parameters.x, "airflow_speed")
        self.assertEqual(request.query_id, self.graph_data["query_id"])
        self.assertEqual(request.limits.max_download_bytes, 100_000_000)
        self.assertNotIn("https://", request.model_dump_json())

    def test_unknown_or_duplicate_ids_rejected(self):
        for selected in [["invented-file"], ["demo-measurements", "demo-measurements"]]:
            with self.subTest(selected=selected):
                self.plan_data["selected_file_ids"] = selected
                with self.assertRaises(PlanningError):
                    self.request()

    def test_missing_schema_numeric_type_or_unit_requires_inspection(self):
        for variables in [None, [], [{"name": "airflow_speed", "unit": "cm/s"}], [
            {"name": "airflow_speed", "numeric": True, "unit": "cm/s"},
            {"name": "flame_spread_rate", "numeric": True, "unit": None},
        ]]:
            with self.subTest(variables=variables):
                self.graph_data["files"][0]["variables"] = variables
                with self.assertRaisesRegex(PlanningError, "Inspect file first"):
                    self.request()

    def test_inspect_unknown_schema_without_guessing_columns(self):
        self.graph_data["files"][0]["variables"] = None
        self.plan_data.update(action="inspect_files", operation=None)
        self.assertEqual(self.request().plan.action, "inspect_files")

    def test_rejects_invented_column(self):
        self.plan_data["operation"]["parameters"]["y"] = "made_up"
        with self.assertRaisesRegex(PlanningError, "made_up"):
            self.request()

    def test_only_registered_operation_schema_is_accepted(self):
        self.plan_data["operation"]["name"] = "execute_python"
        with self.assertRaises(ValidationError):
            self.request()
        self.plan_data["operation"]["name"] = "plot_relationship"
        self.plan_data["operation"]["code"] = "arbitrary code"
        with self.assertRaises(ValidationError):
            self.request()

    def test_rejects_missing_url_large_download_and_non_csv_calculation(self):
        for field, value in [("retrieval_url", None), ("size_bytes", 100_000_001),
                             ("media_type", "application/zip")]:
            original = self.graph_data["files"][0][field]
            with self.subTest(field=field):
                self.graph_data["files"][0][field] = value
                with self.assertRaises(PlanningError):
                    self.request()
            self.graph_data["files"][0][field] = original

    def test_budget_includes_assets(self):
        self.graph_data["files"][0]["size_bytes"] = 99_000_000
        with self.assertRaisesRegex(PlanningError, "budget"):
            self.request()

    def test_unknown_size_is_preserved_and_warned(self):
        self.graph_data["files"][0]["size_bytes"] = None
        self.assertTrue(any("Unknown size" in warning for warning in self.request().plan.warnings))
        self.assertIsNone(self.graph_data["files"][0]["size_bytes"])

    def test_media_only_and_empty_search(self):
        self.plan_data.update(action="retrieve_assets", selected_file_ids=[], operation=None)
        self.assertEqual(self.request().plan.action, "retrieve_assets")
        self.graph_data["files"] = []
        self.plan_data.update(action="no_match", requested_asset_ids=[])
        self.assertEqual(self.request().plan.action, "no_match")

    def test_invalid_action_combinations(self):
        for changes in [
            {"action": "no_match"},
            {"action": "inspect_files"},
            {"action": "retrieve_assets"},
            {"selected_file_ids": ["demo-video"]},
            {"requested_asset_ids": ["demo-measurements"]},
            {"selected_file_ids": []},
        ]:
            original = self.plan_data.copy()
            with self.subTest(changes=changes):
                self.plan_data.update(changes)
                with self.assertRaises(PlanningError):
                    self.request()
            self.plan_data = original

    def test_duplicate_graph_file_ids_rejected(self):
        self.graph_data["files"].append(self.graph_data["files"][0])
        with self.assertRaises(ValidationError):
            self.request()

    def test_empty_prompt_rejected_before_model_call(self):
        class MustNotBeCalled:
            def propose(self, *args):
                raise AssertionError("Model should not be called")

        with self.assertRaisesRegex(PlanningError, "empty"):
            build_request(" ", SearchResults.model_validate(self.graph_data), MustNotBeCalled())

    def sdk_planner(self, output, status="completed"):
        def handler(request):
            payload = json.loads(request.content)
            self.assertEqual(request.url.path, "/v1/responses")
            self.assertEqual(payload["text"]["format"]["type"], "json_schema")
            self.assertTrue(payload["text"]["format"]["strict"])
            self.assertFalse(payload["store"])
            context = json.loads(payload["input"][0]["content"])
            self.assertEqual(context["user_prompt"], "Plot airflow")
            self.assertIs(context["graph_search_results"]["files"][0]["retrieval_url"], True)
            self.assertNotIn("https://example.org", payload["input"][0]["content"])
            return httpx.Response(200, json={
                "id": "resp_test", "object": "response", "created_at": 0,
                "model": "test-model", "status": status, "output": output,
            })

        client = OpenAI(api_key="test-key-not-real", http_client=httpx.Client(
            transport=httpx.MockTransport(handler),
        ))
        self.addCleanup(client.close)
        return OpenAIPlanner("test-model", client=client)

    def test_real_sdk_parses_mock_http_response(self):
        planner = self.sdk_planner([{
            "id": "msg_test", "type": "message", "role": "assistant", "status": "completed",
            "content": [{"type": "output_text", "text": json.dumps(self.plan_data), "annotations": []}],
        }])
        request = build_request("Plot airflow", SearchResults.model_validate(self.graph_data), planner)
        self.assertEqual(request.plan.action, "calculate")

    def test_model_refusal_does_not_create_executable_request(self):
        planner = self.sdk_planner([{
            "id": "msg_test", "type": "message", "role": "assistant", "status": "completed",
            "content": [{"type": "refusal", "refusal": "Cannot produce a plan"}],
        }])
        with self.assertRaisesRegex(PlanningError, "refusal"):
            build_request("Plot airflow", SearchResults.model_validate(self.graph_data), planner)

    def test_incomplete_response_does_not_create_executable_request(self):
        planner = self.sdk_planner([], status="incomplete")
        with self.assertRaisesRegex(PlanningError, "incomplete"):
            build_request("Plot airflow", SearchResults.model_validate(self.graph_data), planner)


if __name__ == "__main__":
    unittest.main()

