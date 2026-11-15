"""End-to-end source inputs, dependency execution, and report regressions."""

import hashlib
import json
import unittest
from unittest.mock import patch

import httpx

from request_planner.methods import method_details
from request_planner.models import FileRecord, FrontendResponse
from request_planner.thm_pipeline import FunctionPlan, execute_functions, order_tasks


def chained_plan():
    return {
        "tasks": [
            {
                "id": "blowoff",
                "model_id": "THM-07",
                "purpose": "Estimate blowoff using the predicted temperature",
                "params": {"u_flow_ms": 0.15, "x_o2": 0.21, "flame_temp_k": 0},
                "input_source_spans": {"u_flow_ms": "flow 0.15", "x_o2": "oxygen 0.21"},
                "results": [
                    {
                        "task_id": "temperature",
                        "source_pointer": "/outputs/adiabatic_flame_temp_k",
                        "target_pointer": "/params/flame_temp_k",
                        "unit": "K",
                    }
                ],
            },
            {
                "id": "temperature",
                "model_id": "THM-01",
                "purpose": "Estimate equilibrium flame temperature",
                "params": {
                    "fuel_species": "CH4",
                    "o2_mole_frac": 0.21,
                    "pressure_kpa": 101.325,
                    "t_init_k": 298.15,
                },
                "input_source_spans": {
                    "fuel_species": "CH4",
                    "o2_mole_frac": "oxygen 0.21",
                    "pressure_kpa": "pressure 101.325",
                    "t_init_k": "temperature 298.15",
                },
            },
        ]
    }


PROMPT = "Calculate CH4 flame temperature and blowoff with oxygen 0.21, pressure 101.325, temperature 298.15, and flow 0.15"


class THMPipelineTests(unittest.TestCase):
    def test_real_dependency_uses_generated_upstream_output(self):
        plan = FunctionPlan.model_validate(chained_plan())
        self.assertEqual([t.id for t in order_tasks(plan)], ["temperature", "blowoff"])
        blocks, _, trace = execute_functions(plan, PROMPT, [])
        self.assertEqual([t["status"] for t in trace], ["completed", "completed"])
        self.assertEqual(
            trace[1]["input_json"]["params"]["flame_temp_k"],
            trace[0]["output_json"]["outputs"]["adiabatic_flame_temp_k"],
        )
        self.assertTrue(
            any(p["kind"] == "computed_result" for p in trace[1]["provenance"])
        )
        response = FrontendResponse(
            query_id="test", status="completed", message="", blocks=blocks
        )
        calculations = [b for b in response.blocks if b["type"] == "calculation"]
        self.assertEqual(calculations[1]["depends_on"], ["temperature"])
        self.assertIn("input_json", calculations[0])

    def test_cycle_and_unknown_dependency_rejected(self):
        data = chained_plan()
        data["tasks"][1]["depends_on"] = ["blowoff"]
        with self.assertRaises(ValueError):
            order_tasks(FunctionPlan.model_validate(data))
        data["tasks"][1]["depends_on"] = ["unknown"]
        with self.assertRaises(ValueError):
            order_tasks(FunctionPlan.model_validate(data))

    def test_invalid_dependency_blocks_only_downstream(self):
        data = chained_plan()
        data["tasks"][1]["params"]["fuel_species"] = "invented"
        blocks, _, trace = execute_functions(data, PROMPT, [])
        self.assertEqual([t["status"] for t in trace], ["needs_input", "blocked"])
        self.assertFalse(blocks)

    def test_unregistered_link_is_rejected(self):
        data = chained_plan()
        data["tasks"][0]["results"][0]["unit"] = "C"
        _, _, trace = execute_functions(data, PROMPT, [])
        self.assertEqual(trace[1]["status"], "needs_input")

    def test_nasa_csv_values_generate_solver_json_and_check_hash(self):
        raw = b"oxygen mole fraction\n0.21\n"
        file = FileRecord(
            file_id="source",
            investigation_id="PSI-69",
            title="Verified test fixture",
            role="measurement",
            media_type="text/csv",
            retrieval_url="https://example.org/data.csv",
            size_bytes=len(raw),
            variables=[{"name": "oxygen mole fraction", "unit": "1", "numeric": True}],
        )
        task = {
            "tasks": [
                {
                    "id": "temperature",
                    "model_id": "THM-01",
                    "purpose": "Use measured oxygen",
                    "params": {
                        "fuel_species": "CH4",
                        "o2_mole_frac": 0,
                        "pressure_kpa": 101.325,
                    },
                    "input_source_spans": {
                        "fuel_species": "CH4",
                        "pressure_kpa": "pressure 101.325",
                    },
                    "sources": [
                        {
                            "file_id": "source",
                            "binding": {
                                "target": "/params/o2_mole_frac",
                                "mode": "scalar",
                                "row": 0,
                                "columns": [
                                    {
                                        "column": "oxygen mole fraction",
                                        "field": "o2_mole_frac",
                                        "unit": "1",
                                    }
                                ],
                            },
                        }
                    ],
                }
            ]
        }
        client = httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, stream=httpx.ByteStream(raw))
            )
        )
        with client:
            blocks, sources, trace = execute_functions(
                task,
                "Calculate CH4 temperature at pressure 101.325 using the first row",
                [file],
                client=client,
                url_validator=lambda u: u,
                trusted_source_hashes={"source": hashlib.sha256(raw).hexdigest()},
            )
        self.assertEqual(trace[0]["status"], "completed", trace[0])
        self.assertEqual(trace[0]["input_json"]["params"]["o2_mole_frac"], 0.21)
        self.assertEqual(sources[0]["file_id"], "source")
        self.assertEqual(blocks[0]["source_file_ids"], ["source"])

    def test_methods_cover_actual_twenty_functions(self):
        for i in range(1, 21):
            method = method_details(f"THM-{i:02}")
            self.assertTrue(method["summary"])
            self.assertTrue(method["equations"])

    def test_missing_calibration_retains_task_and_does_not_fabricate_json(self):
        _, _, trace = execute_functions(
            {
                "tasks": [
                    {
                        "id": "spread",
                        "model_id": "THM-05",
                        "purpose": "Predict opposed spread",
                    }
                ]
            },
            "Predict spread",
            [],
        )
        self.assertEqual(trace[0]["status"], "needs_input")
        self.assertIsNone(trace[0]["input_json"])

    def test_all_base_json_files_exist_before_first_solver(self):
        from request_planner.execution import ExecutionSession

        original = ExecutionSession.calculate
        counts = []

        def observed(session, model, payload):
            counts.append(len(list(session.directory.glob("*.input.json"))))
            return original(session, model, payload)

        with patch.object(ExecutionSession, "calculate", observed):
            _, _, trace = execute_functions(chained_plan(), PROMPT, [])
        self.assertEqual(counts, [2, 2])
        self.assertTrue(all(t["status"] == "completed" for t in trace))

    def test_backend_routes_selected_functions_to_json_pipeline(self):
        from request_planner.backend import answer
        from request_planner.task_router import Route

        result = answer(
            PROMPT,
            function_generator=lambda _: json.dumps(chained_plan()),
            routing_decision=Route(
                intent="calculation", model_ids=["THM-01", "THM-07"]
            ),
        )
        self.assertEqual(result.status, "completed", result.message)
        frontend = result.frontend()
        self.assertEqual(len(frontend["function_pipeline"]), 2)
        calculations = [b for b in frontend["blocks"] if b["type"] == "calculation"]
        self.assertEqual([b["model_id"] for b in calculations], ["THM-01", "THM-07"])
        self.assertTrue(all(b.get("method", {}).get("equations") for b in calculations))
        self.assertTrue(any(b["type"] == "chart" for b in frontend["blocks"]))

    def test_planner_repairs_invented_defaults_before_running(self):
        from unittest.mock import Mock

        from request_planner.thm_pipeline import propose_functions

        invalid = chained_plan()
        invalid["tasks"][1]["params"]["diluent_gas"] = "N2"
        generate = Mock(side_effect=[json.dumps(invalid), json.dumps(chained_plan())])
        plan = propose_functions(PROMPT, [], generate, ["THM-01", "THM-07"])
        self.assertEqual(generate.call_count, 2)
        self.assertNotIn("diluent_gas", plan.tasks[1].params)
        self.assertIn("diluent_gas", generate.call_args.args[0][-1]["content"])

    def test_computed_value_cannot_also_be_a_user_input(self):
        from unittest.mock import Mock

        from request_planner.thm_pipeline import propose_functions

        invalid = chained_plan()
        invalid["tasks"][0]["user_inputs"] = [
            {
                "target_pointer": "/params/flame_temp_k",
                "value": 0,
                "quote": "invented upstream temperature",
                "unit": "K",
            }
        ]
        generate = Mock(side_effect=[json.dumps(invalid), json.dumps(chained_plan())])
        plan = propose_functions(PROMPT, [], generate, ["THM-01", "THM-07"])
        self.assertFalse(plan.tasks[0].user_inputs)
        self.assertIn("Remove user_inputs", generate.call_args.args[0][-1]["content"])
