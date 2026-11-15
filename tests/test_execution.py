"""Offline workflow integration using synthetic files and real THM calculations."""

import json
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import httpx
from openai import OpenAI

from request_planner.execution import ExecutionError, ExecutionSession, public_url
from request_planner.function_registry import function_root, model_spec, operation_catalog
from request_planner.models import ExecutionLimits, Plan, SearchResults, ServiceRequest
from request_planner.planner import LocalPlanner, OpenAIPlanner, PlanningError
from request_planner.service import execute_request, run_workflow


def file_record(file_id="dataset", media_type="application/json", **updates):
    return {"file_id": file_id, "investigation_id": "synthetic-study", "run_ids": ["run-1"],
            "title": "Synthetic test input", "role": "measurement", "media_type": media_type,
            "retrieval_url": f"https://data.example/{file_id}", **updates}


def thermo_plan(model_id="THM-03", **parameters):
    return Plan.model_validate({
        "action": "calculate", "selected_file_ids": ["dataset"], "requested_asset_ids": [],
        "operation": {"name": "run_thermo_model", "file_id": "dataset", "parameters": {
            "model_id": model_id, "request_json": None, "template_file_id": None, "bindings": [], **parameters}},
        "explanation": "Calculate from the selected synthetic input.", "warnings": ["Synthetic test data."],
    })


class ExecutionTests(unittest.TestCase):
    def client(self, payloads):
        self.fetched = []

        def handler(request):
            self.fetched.append(request.url.path)
            return httpx.Response(200, stream=httpx.ByteStream(payloads[request.url.path]))

        client = httpx.Client(transport=httpx.MockTransport(handler))
        self.addCleanup(client.close)
        return client

    def run_saved(self, plan, records, payloads, **kwargs):
        results = SearchResults(query_id="test", files=records)
        request = ServiceRequest(query_id="test", plan=plan)
        return execute_request(request, results, client=self.client(payloads),
                               url_validator=lambda url: None, **kwargs)

    def test_json_download_calls_real_registered_function_and_cleans_up(self):
        payload = json.dumps({"params": {"fuel_formula": "CH4", "y_fuel_stream": 1, "y_ox_stream": 0.232}}).encode()
        with tempfile.TemporaryDirectory() as directory:
            response = self.run_saved(thermo_plan(), [file_record()], {"/dataset": payload}, temp_dir=directory)
            self.assertEqual(response.status, "completed", response.model_dump())
            self.assertEqual(list(Path(directory).iterdir()), [])
        result = response.blocks[0]
        self.assertEqual(result["model_id"], "THM-03")
        self.assertTrue(result["data"])
        self.assertEqual(response.sources[0]["size_bytes"], len(payload))
        self.assertEqual(len(response.sources[0]["sha256"]), 64)
        self.assertNotIn("/tmp/", response.model_dump_json())

    def test_named_thm05_plot_runs_folder_function_and_returns_chart(self):
        payload = (Path(__file__).resolve().parents[1] /
                   "src/Functions/THM-05/THM-05_input.json").read_bytes()
        plan = thermo_plan("THM-05")
        response = run_workflow(
            "Plot THM-05 flame spread against acrylic sheet thickness",
            SearchResults(query_id="test", files=[file_record()]),
            LocalPlanner(lambda _: plan.model_dump_json()),
            client=self.client({"/dataset": payload}),
            url_validator=lambda url: None,
        )
        self.assertEqual(response.status, "completed", response.message)
        self.assertEqual([block["type"] for block in response.blocks], ["calculation", "chart"])
        chart = response.blocks[1]
        self.assertEqual(chart["x"]["label"], "sample_thickness_m")
        self.assertEqual(chart["series"][0]["unit"], "mm/s")
        self.assertEqual(chart["source_file_ids"], ["dataset"])

    def test_inspect_then_llm_request_then_csv_function_and_supporting_media(self):
        csv = b"clock,inlet,outlet\n0,0.002,0.001\n1,0.002,0.001\n2,0.002,0.001\n"
        template = {"request": {"topic": "heat_release", "analysis": "estimate_hrr", "scenario": {"run_id": "run-1"}},
                    "evidence": {"runs": [{"id": "run-1", "measurement_method": "paired_oxygen_mass_flow",
                                            "samples": [{"time_s": 0, "inlet_o2_kg_s": 0, "outlet_o2_kg_s": 0}],
                                            "source_url": "https://data.example/dataset", "source_locator": "Synthetic CSV"}],
                                 "provenance": {"illustrative": True}}}
        plan = thermo_plan("THM-04", template_file_id="template", bindings=[{
            "target": "/evidence/runs/0/samples", "mode": "records", "row": None, "columns": [
                {"column": "clock", "field": "time_s", "unit": "s"},
                {"column": "inlet", "field": "inlet_o2_kg_s", "unit": "kg/s"},
                {"column": "outlet", "field": "outlet_o2_kg_s", "unit": "kg/s"},
            ]}])
        plan.selected_file_ids.append("template")
        plan.requested_asset_ids = ["video", "paper"]
        inspect = Plan(action="inspect_files", selected_file_ids=["dataset", "template"], requested_asset_ids=[],
                       operation=None, explanation="Inspect measurements and evidence", warnings=[])
        records = [file_record(media_type="text/csv", variables=[
            {"name": "clock", "unit": "s"}, {"name": "inlet", "unit": "kg/s"}, {"name": "outlet", "unit": "kg/s"}]),
            file_record("template"), file_record("video", "video/mp4", role="video"),
            file_record("paper", "application/pdf", role="documentation")]
        plans = iter([inspect, plan])

        def llm_handler(request):
            body = json.loads(request.content)
            context = json.loads(body["input"][0]["content"])
            self.assertNotIn("https://data.example", body["input"][0]["content"])
            current = next(plans)
            if current.action == "calculate":
                self.assertEqual(context["inspection"][0]["row_count"], 3)
                self.assertTrue(context["graph_search_results"]["files"][0]["variables"][0]["numeric"])
            self.assertEqual(len(context["thermo_functions"]), 20)
            return httpx.Response(200, json={
                "id": "resp_synthetic", "object": "response", "created_at": 0, "model": "test", "status": "completed",
                "output": [{"id": "msg_synthetic", "type": "message", "role": "assistant", "status": "completed",
                            "content": [{"type": "output_text", "text": current.model_dump_json(), "annotations": []}]}],
            })

        with OpenAI(api_key="synthetic", max_retries=0,
                    http_client=httpx.Client(transport=httpx.MockTransport(llm_handler))) as sdk:
            response = run_workflow("Calculate HRR and show the video and paper", {"query_id": "test", "files": records},
                                    OpenAIPlanner("test", sdk), client=self.client({"/dataset": csv, "/template": json.dumps(template).encode()}),
                                    url_validator=lambda url: None)
        self.assertEqual(response.status, "completed", response.model_dump())
        result = next(b for b in response.blocks if b["type"] == "calculation")
        self.assertEqual(result["data"]["time_s"], [0, 1, 2])
        self.assertEqual(result["data"]["hrr_W"], [13100, 13100, 13100])
        self.assertTrue(result["illustrative"])
        self.assertTrue(any(b["type"] == "chart" for b in response.blocks))
        self.assertTrue(any(b["type"] == "video" for b in response.blocks))
        self.assertTrue(any(b["type"] == "document" for b in response.blocks))
        self.assertEqual(self.fetched, ["/dataset", "/template"])

    def test_repeated_inspection_returns_missing_inputs_without_a_third_plan(self):
        inspect = Plan(action="inspect_files", selected_file_ids=["dataset"], requested_asset_ids=[],
                       operation=None, explanation="Mixture temperature is missing.", warnings=[])

        class RepeatedInspection:
            calls = 0

            def propose(self, prompt, results, limits):
                self.calls += 1
                return inspect

            def with_context(self, inspection):
                return self

        planner = RepeatedInspection()
        response = run_workflow("Calculate a Lewis number.",
                                {"query_id": "test", "files": [file_record(media_type="text/csv")]},
                                planner, client=self.client({"/dataset": b"oxygen\n0.21\n"}),
                                url_validator=lambda url: None)
        self.assertEqual(response.status, "needs_input")
        self.assertIn("Mixture temperature is missing", response.message)
        self.assertEqual(planner.calls, 2)
        self.assertEqual(self.fetched, ["/dataset"])
        self.assertEqual([block["type"] for block in response.blocks], ["inspection"])

    def test_csv_can_supply_legacy_params_without_calibration_template(self):
        plan = thermo_plan(request_json=json.dumps({"fuel_formula": "CH4", "y_fuel_stream": 1, "y_ox_stream": 0}),
                           bindings=[{"target": "/params/y_ox_stream", "mode": "scalar", "row": 0,
                                      "columns": [{"column": "oxygen mass fraction", "field": "y_ox_stream", "unit": "1"}]}])
        record = file_record(media_type="text/csv", variables=[{"name": "oxygen mass fraction", "numeric": True, "unit": "1"}])
        response = self.run_saved(plan, [record], {"/dataset": b"oxygen mass fraction\n0.232\n"})
        self.assertEqual(response.status, "completed", response.model_dump())

    def test_unknown_unit_does_not_become_dimensionless(self):
        inspect = Plan(action="inspect_files", selected_file_ids=["dataset"], requested_asset_ids=[],
                       operation=None, explanation="Inspect", warnings=[])

        class Once:
            def propose(self, *args):
                return inspect

        response = run_workflow("Inspect", {"query_id": "test", "files": [file_record(media_type="text/csv")]}, Once(),
                                client=self.client({"/dataset": b"x\n1\n"}), url_validator=lambda url: None)
        self.assertEqual(response.status, "completed")
        self.assertIsNone(response.blocks[0]["columns"][0]["unit"])

    def test_byte_cap_cleans_up_and_reports_error(self):
        request = ServiceRequest(query_id="test", plan=thermo_plan(), limits=ExecutionLimits(max_download_bytes=5))
        with tempfile.TemporaryDirectory() as directory:
            response = execute_request(request, SearchResults(query_id="test", files=[file_record()]),
                                       client=self.client({"/dataset": b"too many bytes"}),
                                       url_validator=lambda url: None, temp_dir=directory)
            self.assertEqual(response.status, "error")
            self.assertIn("byte budget", response.message)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_invalid_function_input_is_frontend_diagnostic(self):
        response = self.run_saved(thermo_plan("THM-10"), [file_record()], {"/dataset": b'{"request": {}, "evidence": {}}'})
        self.assertEqual(response.status, "needs_input")
        self.assertTrue(response.errors)

    def test_registry_has_all_modules_and_contracts(self):
        self.assertEqual(len(operation_catalog()), 20)
        for n in range(1, 21):
            spec = model_spec(f"THM-{n:02}")
            self.assertTrue(function_root().joinpath(spec["module"]).is_file())
        with self.assertRaises(ValueError):
            model_spec("../../evil")

    def test_worker_timeout_is_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            session = ExecutionSession(directory, ExecutionLimits())
            with patch("request_planner.execution.subprocess.run", side_effect=subprocess.TimeoutExpired("worker", 1)):
                with self.assertRaisesRegex(ExecutionError, "runtime"):
                    session.calculate("THM-03", {})

    def test_query_id_mismatch_is_rejected(self):
        with self.assertRaises(PlanningError):
            execute_request(ServiceRequest(query_id="other", plan=thermo_plan()), SearchResults(query_id="test", files=[]))

    def test_public_destination_policy_and_redirect_revalidation(self):
        addresses = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
        with patch("request_planner.execution.socket.getaddrinfo", return_value=addresses):
            with self.assertRaisesRegex(ExecutionError, "public"):
                public_url("https://local.example/data")
        for url in ("file:///etc/passwd", "http://user:password@example.com/data", "http://example.com:9000/data"):
            with self.assertRaises(ExecutionError):
                public_url(url)
        checked = []

        def policy(url):
            checked.append(url)
            if "127.0.0.1" in url:
                raise ExecutionError("Private redirect rejected")

        with httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(302, headers={"location": "http://127.0.0.1/private"}))) as client:
            response = execute_request(ServiceRequest(query_id="test", plan=thermo_plan()),
                                       SearchResults(query_id="test", files=[file_record()]), client=client, url_validator=policy)
        self.assertEqual(response.status, "error")
        self.assertEqual(len(checked), 2)

    def test_no_match_never_downloads(self):
        plan = Plan(action="no_match", selected_file_ids=[], requested_asset_ids=[], operation=None,
                    explanation="No sourced inputs", warnings=[])
        response = self.run_saved(plan, [], {})
        self.assertEqual(response.status, "no_match")
        self.assertEqual(self.fetched, [])

    def test_plot_returns_exact_measured_arrays_without_matplotlib(self):
        plan = Plan(action="calculate", selected_file_ids=["dataset"], requested_asset_ids=[],
                    operation={"name": "plot_relationship", "file_id": "dataset", "parameters": {"x": "x", "y": "y"}},
                    explanation="Plot measured values", warnings=[])
        record = file_record(media_type="text/csv", variables=[{"name": "x", "unit": "s", "numeric": True},
                                                              {"name": "y", "unit": "K", "numeric": True}])
        response = self.run_saved(plan, [record], {"/dataset": b"x,y\n0,290\n1,300\n"})
        self.assertEqual(response.status, "completed")
        self.assertEqual(response.blocks[0]["x"]["values"], [0, 1])
        self.assertEqual(response.blocks[0]["series"][0]["values"], [290, 300])
        self.assertEqual(response.blocks[0]["evidence_type"], "measured")

    def test_media_only_returns_display_links_without_downloading(self):
        plan = Plan(action="retrieve_assets", selected_file_ids=[], requested_asset_ids=["video"],
                    operation=None, explanation="Show experiment video", warnings=[])
        response = self.run_saved(plan, [file_record("video", "video/mp4", role="video")], {})
        self.assertEqual(response.status, "completed")
        self.assertEqual(response.blocks[0]["type"], "video")
        self.assertFalse(response.sources[0]["downloaded"])
        self.assertEqual(self.fetched, [])

    def test_destination_unit_contract_is_independent_of_model_and_graph_labels(self):
        plan = thermo_plan(request_json=json.dumps({"fuel_formula": "CH4", "y_fuel_stream": 1, "y_ox_stream": 0}),
                           bindings=[{"target": "/params/y_ox_stream", "mode": "scalar", "row": 0,
                                      "columns": [{"column": "oxygen", "field": "y_ox_stream", "unit": "K"}]}])
        record = file_record(media_type="text/csv", variables=[{"name": "oxygen", "numeric": True, "unit": "K"}])
        response = self.run_saved(plan, [record], {"/dataset": b"oxygen\n0.232\n"})
        self.assertEqual(response.status, "error")
        self.assertIn("destination unit", response.message)

    def test_cross_run_template_is_rejected_before_download(self):
        plan = thermo_plan("THM-04", template_file_id="template", bindings=[{
            "target": "/evidence/runs/0/samples", "mode": "records", "row": None,
            "columns": [{"column": "clock", "field": "time_s", "unit": "s"}]}])
        plan.selected_file_ids.append("template")
        records = [file_record(media_type="text/csv"), file_record("template", run_ids=["different-run"])]
        response = self.run_saved(plan, records, {})
        self.assertEqual(response.status, "needs_input")
        self.assertIn("verified run IDs", response.message)
        self.assertEqual(self.fetched, [])

    def test_unknown_size_and_corrupt_numeric_data_fail_without_silent_cleaning(self):
        plan = thermo_plan(request_json=json.dumps({"fuel_formula": "CH4", "y_fuel_stream": 1, "y_ox_stream": 0}),
                           bindings=[{"target": "/params/y_ox_stream", "mode": "scalar", "row": 0,
                                      "columns": [{"column": "oxygen", "field": "y_ox_stream", "unit": "1"}]}])
        record = file_record(media_type="text/csv", variables=[{"name": "oxygen", "numeric": True, "unit": "1"}])
        response = self.run_saved(plan, [record], {"/dataset": b"oxygen\n0.232\nNaN\n"})
        self.assertEqual(response.status, "error")
        self.assertIn("nonnumeric", response.message)
        self.assertTrue(any("Unknown size" in w for w in response.warnings))

    def test_bundled_frontend_example_is_reproducible(self):
        root = Path(__file__).resolve().parents[1] / "examples"
        request = ServiceRequest.model_validate_json((root / "thermo_request.json").read_text())
        records = SearchResults.model_validate_json((root / "thermo_search_results.json").read_text())

        def transport(req):
            name = "thermo_measurements.csv" if req.url.path.endswith(".csv") else "thermo_input_template.json"
            return httpx.Response(200, stream=httpx.ByteStream((root / name).read_bytes()))

        with httpx.Client(transport=httpx.MockTransport(transport)) as client:
            actual = execute_request(request, records, client=client, url_validator=lambda url: None)
        expected = json.loads((root / "thermo_frontend_response.json").read_text())
        self.assertEqual(actual.model_dump(mode="json"), expected)


if __name__ == "__main__":
    unittest.main()
