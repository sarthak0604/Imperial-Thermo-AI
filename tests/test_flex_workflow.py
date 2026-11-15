"""Exercise the search-result to FLEX CSV to worker path."""

from copy import deepcopy
import json
import unittest

import httpx

from request_planner.models import Plan, SearchResults, ServiceRequest
from request_planner.service import execute_request


URL = (
    "https://psi.nasa.gov/geode-py/ws/studies/PSI-69/download"
    "?file=PSI-69_Experimental%20table_FLEX.csv&version=1&redirect=true"
)
CSV_DATA = (
    "FLEX Test #,FLEX Identifier,Fuel,Ambient pressure; mmHg,"
    "O initial ambient composition; mole fraction,N initial ambient composition; mole fraction,"
    "CO initial ambient composition; mole fraction,He initial ambient composition; mole fraction,"
    "Droplet initial diameter; mm,Visible flame extinction diameter; mm,"
    "Burning rate; mm,Burn time; s,Test end\n"
    "2,20CAL10,Methanol,762,0.21,0.79,0,0,1.86,0.94,0.6,5,Extinction\n"
    "3,20CAL12,Methanol,764.2,0.21,0.79,0,0,1.61,0.92,0.58,3.2,Extinction\n"
    "4,30CAL02,Methanol,760,0.21,0.79,0,0,2.06,,0.6,7.64,Extinction\n"
).encode()


class FlexWorkflowTests(unittest.TestCase):
    def run_flex(self, model_id, selection, *, url=URL, body=CSV_DATA):
        results = SearchResults.model_validate({
            "query_id": "flex",
            "files": [{"file_id": "dataset", "investigation_id": "PSI-69", "title": "FLEX",
                       "role": "measurement", "media_type": "text/csv", "retrieval_url": url}],
        })
        plan = Plan.model_validate({
            "action": "calculate", "selected_file_ids": ["dataset"], "requested_asset_ids": [],
            "operation": {"name": "run_thermo_model", "file_id": "dataset",
                          "parameters": {"model_id": model_id, "request_json": json.dumps(selection),
                                         "template_file_id": None, "bindings": []}},
            "explanation": "Select one FLEX test.", "warnings": [],
        })
        payloads = {}
        calls = []

        def download(request):
            calls.append(str(request.url))
            return httpx.Response(200, stream=httpx.ByteStream(body))

        def capture(mid, payload):
            payloads[mid] = deepcopy(payload)
            payload.clear()

        with httpx.Client(transport=httpx.MockTransport(download)) as client:
            result = execute_request(ServiceRequest(query_id="flex", plan=plan), results,
                                     client=client, url_validator=lambda url: None,
                                     on_model_input=capture)
        return result, payloads, calls

    @staticmethod
    def droplet_selection(run_id):
        return {"topic": "droplet_combustion", "analysis": "estimate_droplet_regression",
                "scenario": {"run_id": run_id}}

    def test_selected_run_drives_thm10_payload_and_worker(self):
        result, payloads, calls = self.run_flex("THM-10", self.droplet_selection("FLEX-003"))
        self.assertEqual(result.status, "completed", result.model_dump())
        self.assertEqual(len(calls), 1)
        payload = payloads["THM-10"]
        scenario = payload["request"]["scenario"]
        self.assertEqual(scenario["d0_mm"], 1.61)
        self.assertIsNone(scenario["t_amb_k"])
        self.assertAlmostEqual(scenario["pressure_kpa"], 764.2 * 101.325 / 760)
        self.assertEqual(payload["evidence"]["provenance"]["run_id"], "FLEX-003")
        self.assertEqual(payload["evidence"]["provenance"]["reported_burn_time_s"], 3.2)
        output = result.blocks[0]["data"]
        self.assertAlmostEqual(output["modeled_endpoint_time_s"], (1.61 ** 2 - .92 ** 2) / .58)
        self.assertTrue(any("101 points" in text for text in output["assumptions"]))
        self.assertFalse(any("0 mm" in text for text in output["assumptions"]))
        self.assertEqual(result.blocks[0]["source_file_ids"], ["dataset"])
        self.assertTrue(any(block["type"] == "chart" for block in result.blocks))

    def test_missing_extinction_diameter_requests_input(self):
        result, payloads, _ = self.run_flex("THM-10", self.droplet_selection("FLEX-004"))
        self.assertEqual(result.status, "needs_input")
        self.assertIn("Visible flame extinction diameter", result.message)
        self.assertFalse(payloads)

    def test_unreviewed_table_version_uses_general_csv_validation(self):
        result, _, calls = self.run_flex("THM-10", self.droplet_selection("FLEX-002"),
                                        url=URL.replace("version=1", "version=2"))
        self.assertEqual(result.status, "needs_input")
        self.assertFalse(calls)

    def test_thm02_uses_the_selected_ambient_mixture_and_requested_temperature(self):
        result, inputs, _ = self.run_flex("THM-02", {"run_id": "FLEX-002", "temp_k": 310})
        self.assertEqual(result.status, "completed", result.model_dump())
        self.assertEqual(inputs["THM-02"]["params"]["temp_k"], 310)
        self.assertEqual(inputs["THM-02"]["params"]["mole_fracs"]["O2"], 0.21)
        self.assertGreater(result.blocks[0]["data"]["transport_properties"]["density_kg_m3"], 0)

    def test_thm02_requires_temperature_before_downloading(self):
        result, _, calls = self.run_flex("THM-02", {"run_id": "FLEX-002"})
        self.assertEqual(result.status, "needs_input")
        self.assertIn("temperature", result.message)
        self.assertFalse(calls)
