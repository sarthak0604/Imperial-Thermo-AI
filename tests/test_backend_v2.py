"""Regression tests for audited correctness flaws and the shared backend."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from imperial_thermo_ai.graph_search import GraphIndex, evaluate
from imperial_thermo_ai.quantities import normalize_graph
from imperial_thermo_ai.semantic_plan import compile_plan
from imperial_thermo_ai.vector_search import MODEL_ID, VectorGraphSearch, fingerprint
from request_planner.backend import answer
from request_planner.execution import ExecutionError, ExecutionSession, apply_bindings, present_result
from request_planner.intent import interpret
from request_planner.models import (
    DatasetBinding,
    ExecutionLimits,
    FileRecord,
    Plan,
    SearchResults,
)
from request_planner.operations import scenario, table
from request_planner.planner import LocalPlanner
from request_planner.service import run_workflow


def graph_fixture():
    nodes = [
        {"id": "inv:a", "type": "Investigation", "properties": {}},
        {
            "id": "exp:a",
            "type": "Experiment",
            "properties": {"conditions": {"gravity": "microgravity"}},
        },
        {
            "id": "exp:b",
            "type": "Experiment",
            "properties": {"conditions": {"gravity": "normal gravity"}},
        },
        {"id": "topic", "type": "Concept", "properties": {"name": "ignition"}},
        {
            "id": "csv",
            "type": "Resource",
            "properties": {
                "title": "csv",
                "file_format": "csv",
                "resource_type": "dataset",
            },
        },
        {
            "id": "pdf",
            "type": "Resource",
            "properties": {"title": "pdf", "file_format": "pdf"},
        },
    ]
    rows = [
        ("a", "inv:a", "exp:a", "CONTAINS"),
        ("b", "inv:a", "exp:b", "CONTAINS"),
        ("c", "exp:b", "topic", "STUDIES"),
        ("d", "exp:a", "csv", "HAS_RESOURCE"),
        ("e", "exp:b", "csv", "HAS_RESOURCE"),
        ("f", "exp:a", "pdf", "HAS_RESOURCE"),
    ]
    return {
        "nodes": nodes,
        "edges": [
            {"id": i, "source": s, "target": t, "type": k, "properties": {}}
            for i, s, t, k in rows
        ],
    }


class BackendV2Tests(unittest.TestCase):
    def test_plain_language_thickness_comparison_requests_thm05_and_chart(self):
        request = interpret(
            "How does increasing acrylic sheet thickness from 0.20 to 0.30 mm "
            "affect flame spread against airflow in microgravity?"
        )
        self.assertEqual(
            [(r.kind, r.model_id) for r in request.requirements],
            [("explanation", None), ("chart", None), ("calculation", "THM-05")],
        )

    def test_named_model_plot_requires_its_calculation(self):
        request = interpret("Plot THM-05 flame spread against sheet thickness")
        self.assertEqual(
            [(r.kind, r.model_id) for r in request.requirements],
            [("chart", None), ("calculation", "THM-05")],
        )

    def test_thickness_comparison_allows_unit_on_both_values(self):
        request = interpret(
            "How does increasing acrylic thickness from 0.20 mm to 0.30 mm "
            "affect flame spread against the airflow?"
        )
        self.assertIn(("calculation", "THM-05"),
                      [(r.kind, r.model_id) for r in request.requirements])

    def test_modern_thm_without_sourced_json_reports_missing_evidence(self):
        result = answer(
            "Plot THM-05 flame spread against acrylic sheet thickness",
            program_generator=lambda _: self.fail("A model plan cannot replace sourced calibration"),
        )
        self.assertIn(result.status, {"needs_input", "partial"})
        self.assertTrue(any("sourced JSON calibration" in text
                            for text in result.request.clarifications))
        self.assertFalse(any(block["type"] == "calculation" for block in result.result.blocks))

    def test_thm05_calibrated_sweep_is_a_renderable_chart(self):
        from request_planner.function_registry import run_model

        payload = json.loads(
            (Path(__file__).resolve().parents[1] / "src/Functions/THM-05/THM-05_input.json").read_text()
        )
        result = run_model("THM-05", payload)
        charts = [block for block in present_result("THM-05", result) if block["type"] == "chart"]
        self.assertEqual(len(charts), 1)
        self.assertEqual(charts[0]["x"]["label"], "sample_thickness_m")
        self.assertEqual(charts[0]["x"]["unit"], "m")
        self.assertEqual(charts[0]["series"][0]["unit"], "mm/s")
        self.assertEqual(len(charts[0]["x"]["values"]), len(charts[0]["series"][0]["values"]))
        self.assertEqual(charts[0]["evidence_type"], "model_estimate")

    def test_wrong_action_cannot_complete_calculation_prompt(self):
        files = SearchResults(
            query_id="test",
            files=[
                FileRecord(
                    file_id="pdf",
                    investigation_id="study",
                    title="Report",
                    role="documentation",
                    media_type="application/pdf",
                    retrieval_url="https://example.org/a.pdf",
                )
            ],
        )
        plan = Plan(
            action="retrieve_assets",
            selected_file_ids=[],
            requested_asset_ids=["pdf"],
            operation=None,
            explanation="Report",
            warnings=[],
        )
        r = run_workflow(
            "Calculate flame spread and plot it",
            files,
            LocalPlanner(lambda _: plan.model_dump_json()),
        )
        self.assertEqual(r.status, "needs_input")
        self.assertTrue(any("calculation" in w for w in r.warnings))

    def test_conditions_cannot_use_different_experiments(self):
        g = graph_fixture()
        plan = compile_plan(
            {
                "queries": [
                    {
                        "label": "test",
                        "return_type": "Resource",
                        "criteria": [
                            {
                                "node_type": "Experiment",
                                "field": "conditions.gravity",
                                "operator": "eq",
                                "value": "microgravity",
                                "source_text": "microgravity",
                            },
                            {
                                "node_type": "Concept",
                                "field": "name",
                                "operator": "eq",
                                "value": "ignition",
                                "source_text": "ignition",
                            },
                        ],
                    }
                ]
            }
        )
        result = evaluate(GraphIndex(g), "csv", plan["queries"][0]["where"])
        self.assertIsNot(result.state, True)

    def test_sibling_pdf_does_not_make_csv_a_pdf(self):
        g = graph_fixture()
        plan = compile_plan(
            {
                "original_question": "Find PDF files",
                "normalized_question": "Find PDF files",
                "language": "en",
                "intent": "find",
                "search_text": "PDF",
                "queries": [
                    {
                        "label": "pdf",
                        "return_type": "Experiment",
                        "criteria": [
                            {
                                "node_type": "Resource",
                                "field": "file_format",
                                "operator": "eq",
                                "value": "pdf",
                                "source_text": "PDF",
                            }
                        ],
                    }
                ],
            }
        )
        ix = {
            "model_id": MODEL_ID,
            "graph_fingerprint": fingerprint(g),
            "vectors": {n["id"]: [1, 0] for n in g["nodes"]},
        }
        r = VectorGraphSearch(g, ix).global_search([1, 0], query_id="test", plan=plan)
        self.assertEqual([f["file_id"] for f in r["files"]], ["pdf"])

    def test_mole_fraction_cannot_bind_to_mass_fraction(self):
        f = FileRecord(
            file_id="x",
            investigation_id="test",
            title="Oxygen",
            role="measurement",
            media_type="text/csv",
            variables=[{"name": "oxygen mole fraction", "unit": "1", "numeric": True}],
        )
        b = DatasetBinding(
            target="/params/y_ox_stream",
            mode="scalar",
            row=0,
            columns=[
                {"column": "oxygen mole fraction", "field": "y_ox_stream", "unit": "1"}
            ],
        )
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.csv"
            p.write_text("oxygen mole fraction\n0.21\n")
            with self.assertRaisesRegex(ExecutionError, "basis"):
                apply_bindings({"params": {"y_ox_stream": 0}}, p, f, [b])

    def test_same_size_changed_source_rejects_profile(self):
        f = FileRecord(
            file_id="x",
            investigation_id="test",
            title="x",
            role="measurement",
            media_type="text/csv",
            retrieval_url="https://example.org/data",
            size_bytes=4,
            data_notes=[
                "Profiled source SHA-256: " + hashlib.sha256(b"x\n1\n").hexdigest()
            ],
        )
        with (
            tempfile.TemporaryDirectory() as d,
            httpx.Client(
                transport=httpx.MockTransport(
                    lambda r: httpx.Response(200, stream=httpx.ByteStream(b"x\n2\n"))
                )
            ) as c,
            self.assertRaisesRegex(ExecutionError, "checksum"),
        ):
            ExecutionSession(
                d, ExecutionLimits(), client=c, url_validator=lambda u: None
            ).fetch(f)

    def test_table_selection_and_conversion_preserve_rows(self):
        f = FileRecord(
            file_id="x",
            investigation_id="test",
            title="x",
            role="measurement",
            media_type="text/csv",
            variables=[{"name": "pressure", "unit": "atm", "numeric": True}],
        )
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.csv"
            p.write_text("oxygen,pressure\n21,1\n30,2\n")
            r = table(
                p,
                f,
                {
                    "file_id": "x",
                    "columns": ["pressure"],
                    "predicates": [{"column": "oxygen", "operator": "eq", "value": 30}],
                    "conversions": {"pressure": "kPa"},
                },
            )
        self.assertEqual(r["rows"][0]["row_index"], 1)
        self.assertEqual(r["rows"][0]["values"]["pressure"], 202.65)

    def test_normalized_oxygen_retains_stage_basis_and_original(self):
        g = {
            "nodes": [
                {
                    "type": "Experiment",
                    "properties": {
                        "conditions": {
                            "Calibrated initial O2 % by vol": "22.2",
                            "source_row": 2,
                        }
                    },
                }
            ]
        }
        normalize_graph(g)
        p = g["nodes"][0]["properties"]
        self.assertEqual(p["conditions"]["Calibrated initial O2 % by vol"], "22.2")
        self.assertEqual(p["normalized"]["oxygen_initial"]["basis"], "volume")
        self.assertEqual(p["normalized"]["oxygen_initial"]["value"], 22.2)

    def test_long_prompt_is_rejected_without_slicing(self):
        with self.assertRaises(ValueError):
            interpret("a" * 12001)

    def test_negated_scope_and_unknown_group_are_explicit(self):
        r = answer("Find BASS-II videos excluding PSI-25")
        self.assertEqual(r.status, "needs_input")
        self.assertFalse(r.retrieval.files)
        r = answer("Find tables for PSI-25 and PSI-99999")
        self.assertNotEqual(r.status, "completed")
        self.assertFalse(r.retrieval.coverage["PSI-99999"]["known"])

    def test_scoped_irrelevant_prompt_has_no_fallback(self):
        r = answer("PSI-25 quantum banana zebra")
        self.assertEqual(r.status, "no_evidence")
        self.assertFalse(r.retrieval.files)

    def test_explicit_scenario_has_input_origins(self):
        r = scenario(
            {
                "model_id": "THM-03",
                "params": {
                    "fuel_formula": "CH4",
                    "y_fuel_stream": 1,
                    "y_ox_stream": 0.232,
                },
                "input_origins": {
                    "fuel_formula": "user",
                    "y_fuel_stream": "user",
                    "y_ox_stream": "user",
                },
            }
        )
        self.assertTrue(r["result"])
        with self.assertRaisesRegex(ValueError, "sourced"):
            scenario({"model_id": "THM-04", "params": {}, "input_origins": {}})

    def test_program_scenario_reaches_shared_backend_without_unrelated_data(self):
        program = {
            "steps": [
                {
                    "id": "first",
                    "kind": "scenario",
                    "scenario": {
                        "model_id": "THM-03",
                        "params": {
                            "fuel_formula": "CH4",
                            "y_fuel_stream": 1,
                            "y_ox_stream": 0.232,
                        },
                        "input_origins": {
                            "fuel_formula": "user",
                            "y_fuel_stream": "user",
                            "y_ox_stream": "user",
                        },
                    },
                    "input_source_spans": {
                        "fuel_formula": "CH4",
                        "y_fuel_stream": "fuel mass fraction 1",
                        "y_ox_stream": "oxygen mass fraction 0.232",
                    },
                }
            ]
        }
        r = answer(
            "Calculate THM-03 for CH4 with fuel mass fraction 1 and oxygen mass fraction 0.232",
            program_generator=lambda messages: json.dumps(program),
        )
        self.assertEqual(r.status, "completed", r.message)
        self.assertEqual(r.result.blocks[0]["model_id"], "THM-03")
        self.assertEqual(r.result.sources, [])
        self.assertTrue(
            any("Model defaults" in warning for warning in r.result.warnings)
        )

    def test_named_title_matches_terms_without_inventing_exact_filename(self):
        from imperial_thermo_ai.graph_search import evaluate_filter

        node = {
            "id": "report",
            "type": "Resource",
            "properties": {"title": "PSI-39_Reports_CFI Science Final Report.pdf"},
        }
        result = evaluate_filter(
            node,
            {
                "field": "title",
                "operator": "contains",
                "value": "PSI-39 CFI final science report",
            },
        )
        self.assertTrue(result.state)

    def test_generated_scenario_cannot_invent_user_inputs(self):
        from request_planner.program import ProgramStep, validate_origins

        step = ProgramStep(
            id="x",
            kind="scenario",
            scenario={
                "model_id": "THM-03",
                "params": {"y_ox_stream": 0.9},
                "input_origins": {"y_ox_stream": "user"},
            },
            input_source_spans={"y_ox_stream": "oxygen 0.21"},
        )
        with self.assertRaisesRegex(ValueError, "differs"):
            validate_origins(step, "oxygen 0.21")

    def test_composition_rejects_invented_citations_and_numbers(self):
        from request_planner.backend_models import EvidenceItem
        from request_planner.composition import compose

        e = EvidenceItem(
            id="a",
            file_id="f",
            investigation_id="i",
            title="Report",
            text="The measured rate is 1.1 Hz.",
            locator="page 2",
            source_url="https://example.org/report",
            sha256="x",
            review_status="reviewed_selected_sections",
        )
        with self.assertRaisesRegex(ValueError, "missing source"):
            compose(
                "Explain",
                [e],
                lambda _: json.dumps(
                    {"claims": [{"text": "A fact", "evidence_ids": ["invented"]}]}
                ),
            )
        with self.assertRaisesRegex(ValueError, "number"):
            compose(
                "Explain",
                [e],
                lambda _: json.dumps(
                    {
                        "claims": [
                            {"text": "Measured rate is 5 Hz.", "evidence_ids": ["a"]}
                        ]
                    }
                ),
            )

    def test_comparison_requires_both_cited_investigations(self):
        from request_planner.backend_models import EvidenceItem

        items = [
            EvidenceItem(
                id=eid,
                file_id="source-" + eid,
                investigation_id=study,
                title=("BASS-II" if study == "PSI-25" else "FLEX")
                + " flame comparison",
                text="A source finding about flame behaviour.",
                locator="page 1",
                source_url="https://example.org/" + eid,
                sha256=eid,
                review_status="text_extracted_unreviewed",
            ).model_dump()
            for eid, study in [("a", "PSI-25"), ("b", "PSI-69")]
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.json"
            path.write_text(json.dumps({"items": items}))
            result = answer(
                "Compare BASS-II with FLEX",
                evidence_path=path,
                answer_generator=lambda _: json.dumps(
                    {
                        "claims": [
                            {
                                "text": "A source finding about flame behaviour.",
                                "evidence_ids": ["a"],
                            }
                        ]
                    }
                ),
            )
        self.assertEqual(result.status, "partial")
        self.assertTrue(
            any(
                row["id"] == "group-PSI-69" and not row["satisfied"]
                for row in result.fulfilment
            )
        )

    def test_model_loading_has_hard_outer_deadline(self):
        import subprocess
        import sys

        from request_planner.model_worker import ModelWorker

        original = subprocess.Popen

        def stalled(*args, **kwargs):
            return original(
                [sys.executable, "-c", "import time;time.sleep(30)"], **kwargs
            )

        worker = ModelWorker("unused")
        try:
            with (
                patch(
                    "request_planner.model_worker.subprocess.Popen", side_effect=stalled
                ),
                self.assertRaisesRegex(ValueError, "deadline"),
            ):
                worker.generate([], max_time=0.05)
            self.assertIsNone(worker.process)
        finally:
            worker.close()


if __name__ == "__main__":
    unittest.main()
