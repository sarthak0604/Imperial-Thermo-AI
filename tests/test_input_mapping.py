"""Verify that raw-data assembly reaches every registered thermo solver."""

import json
from unittest import TestCase

import httpx

from request_planner.function_registry import function_root, model_spec
from request_planner.input_contracts import contract_for
from request_planner.input_sources import MappingError, convert, pointer_parts
from request_planner.planner import LocalPlanner
from request_planner.service import execute_request, run_workflow


def leaves(data, pattern, prefix=()):
    if not pattern:
        yield prefix, data
        return
    key, *rest = pattern
    if key == "#" and isinstance(data, list):
        children = enumerate(data)
    elif key == "*" and isinstance(data, dict):
        children = data.items()
    elif isinstance(data, dict) and key in data:
        children = [(key, data[key])]
    elif key.isdecimal() and isinstance(data, list) and int(key) < len(data):
        children = [(key, data[int(key)])]
    else:
        return
    for index, child in children:
        yield from leaves(child, rest, prefix + (str(index),))


def search_record(file_id, media_type, role="measurement", variables=None):
    return {"file_id": file_id, "title": f"Assembly test source {file_id}",
            "investigation_id": "checked-assembly-fixture", "role": role, "media_type": media_type,
            "retrieval_url": f"https://data.example/{file_id}", "variables": variables}


def assignment(target, kind, **source):
    return {"target": target, "source": {"kind": kind, **source}}


def config(target, value):
    return assignment(target, "config", value=value)


def make_mapping(model_id, items, files):
    return {
        "action": "calculate", "selected_file_ids": files, "requested_asset_ids": [],
        "operation": {"name": "run_thermo_model", "file_id": files[0], "parameters": {
            "model_id": model_id, "request_json": json.dumps({"input_mapping": {"assignments": items}}),
            "template_file_id": None, "bindings": [],
        }},
        "explanation": "Assemble the requested model input.", "warnings": [],
    }


class RawAssemblyTests(TestCase):
    def execute(self, model_id, items, records, raw_files, prompt=None):
        plan = make_mapping(model_id, items, [record["file_id"] for record in records])
        return self.run_saved(plan, records, raw_files, prompt)

    def run_saved(self, plan, records, raw_files, prompt=None):
        built = {}

        def fake_download(request):
            return httpx.Response(200, stream=httpx.ByteStream(raw_files[request.url.path[1:]]))

        with httpx.Client(transport=httpx.MockTransport(fake_download)) as client:
            response = execute_request({"query_id": "assembly", "plan": plan},
                                       {"query_id": "assembly", "files": records},
                                       prompt=prompt, client=client, url_validator=lambda url: None,
                                       on_model_input=lambda model, payload: built.update({model: payload}))
        return response, built

    def test_every_entrypoint_runs_with_its_fields_populated_from_source_values(self):
        for index in range(1, 21):
            model_id = f"THM-{index:02}"
            with self.subTest(model=model_id):
                spec = model_spec(model_id)
                raw = json.loads(function_root().joinpath(spec["example"]).read_text(encoding="utf-8-sig"))
                original = raw.get("example_request", raw)
                if model_id == "THM-02":
                    original["params"]["mole_fracs"] = original["params"].pop("gas_composition")
                if model_id == "THM-08":
                    original["params"]["gravity_g"] = 0.16
                if model_id == "THM-10":
                    scenario = original["request"]["scenario"]
                    del scenario["endpoint_diameter_mm"]
                    scenario["time_limit_s"] = 2
                items, data = [], {}
                for pattern, (role, _) in contract_for(model_id).items():
                    for path, value in leaves(original, pointer_parts(pattern)):
                        if value is None:
                            continue
                        target = "/" + "/".join(path)
                        if role in {"C", "B", "I"}:
                            items.append(config(target, value))
                            continue
                        key = f"datum_{len(data)}"
                        if role.startswith("Q"):
                            data[key] = value
                        elif role == "S":
                            data[key] = value
                        else:
                            data[key] = {"value": value, "unit": "1" if role == "D" else role}
                        items.append(assignment(target, "json", file_id="values", pointer=f"/{key}"))
                inputs = {"values": json.dumps(data).encode()}
                response, built = self.execute(model_id, items, [search_record("values", "application/json")], inputs)
                self.assertEqual(response.status, "completed", response.message)
                block = next(block for block in response.blocks if block["type"] == "calculation")
                self.assertEqual(block["model_id"], model_id)
                provenance = block["data"]["assembled_input_provenance"]["field_sources"]
                self.assertTrue(provenance)
                if model_id == "THM-10":
                    self.assertEqual(provenance["/evidence/profiles/0/method"]["value"], "measured_rate")
                    self.assertTrue(any("0 mm" in text for text in block["data"]["assumptions"]))
                    self.assertTrue(any("101 points" in text for text in block["data"]["assumptions"]))
                    self.assertEqual(block["data"]["plot_data"]["time_s"][-1], 2)
                self.assertIn(model_id, built)

    def test_csv_mapping_converts_and_aligns_a_complete_series(self):
        samples = "/evidence/runs/0/samples/#/"
        items = [
            config("/request/scenario/run_id", "r1"),
            config("/evidence/runs/0/id", "r1"),
            config("/evidence/runs/0/measurement_method", "paired_oxygen_mass_flow"),
            *[assignment(samples + field, "csv", file_id="csv", column=column,
                         where={"column": "run", "equals": "r1"})
              for field, column in (("time_s", "elapsed"), ("inlet_o2_kg_s", "inlet"),
                                    ("outlet_o2_kg_s", "outlet"))],
        ]
        sources = {"csv": b"run,elapsed,inlet,outlet\nr1,0,2,1\nr2,0,4,3\nr1,1000,2,1\n"}
        record = search_record("csv", "text/csv", variables=[
            {"name": "elapsed", "unit": "ms"}, {"name": "inlet", "unit": "g/s"},
            {"name": "outlet", "unit": "g/s"},
        ])
        response, built = self.execute("THM-04", items, [record], sources)
        self.assertEqual(response.status, "completed", response.message)
        rows = built["THM-04"]["evidence"]["runs"][0]["samples"]
        self.assertEqual(rows[1], {"time_s": 1, "inlet_o2_kg_s": .002, "outlet_o2_kg_s": .001})
        self.assertEqual(response.blocks[0]["data"]["hrr_W"], [13100, 13100])
        items[-1]["source"]["where"]["equals"] = "r2"
        response, built = self.execute("THM-04", items, [record], sources)
        self.assertEqual(response.status, "needs_input")
        self.assertIn("same source and row selection", response.message)
        self.assertFalse(built)

    def test_json_bulk_mapping_reads_an_array_of_records(self):
        src_columns = {"time_s": "elapsed", "inlet_o2_kg_s": "oxygen_in", "outlet_o2_kg_s": "oxygen_out"}
        items = [
            config("/request/scenario/run_id", "r1"),
            config("/evidence/runs/0/id", "r1"),
            config("/evidence/runs/0/measurement_method", "paired_oxygen_mass_flow"),
            *[assignment(f"/evidence/runs/0/samples/#/{field}", "json", file_id="series",
                         pointer=f"/records/#/{key}") for field, key in src_columns.items()],
        ]
        samples = [{"elapsed": {"value": clock, "unit": "ms"}, "oxygen_in": {"value": 2, "unit": "g/s"},
                    "oxygen_out": {"value": 1, "unit": "g/s"}} for clock in (0, 1000)]
        files = [search_record("series", "application/json")]
        result, built = self.execute("THM-04", items, files, {"series": json.dumps({"records": samples}).encode()})
        self.assertEqual(result.status, "completed", result.message)
        self.assertEqual(built["THM-04"]["evidence"]["runs"][0]["samples"][1]["time_s"], 1)
        self.assertEqual(result.blocks[0]["data"]["hrr_W"], [13100, 13100])

    def test_csv_header_units_are_verified_without_search_metadata(self):
        items = [
            assignment("/params/pressure_kpa", "csv", file_id="sample", column="Pressure [atm]", unit="atm"),
            assignment("/params/temp_k", "csv", file_id="sample", column="Temperature (degC)", unit="degC"),
            assignment("/params/mole_fracs/O2", "csv", file_id="sample", column="O2; vol%", unit="vol%"),
            assignment("/params/mole_fracs/N2", "csv", file_id="sample", column="N2; vol%", unit="vol%"),
        ]
        files = {"sample": b"Pressure [atm],Temperature (degC),O2; vol%,N2; vol%\n1,20,21,79\n"}
        records = [search_record("sample", "text/csv")]
        result, built = self.execute("THM-02", items, records, files)
        self.assertEqual(result.status, "completed", result.message)
        self.assertAlmostEqual(built["THM-02"]["params"]["temp_k"], 293.15)
        items[-1]["source"]["unit"] = "wt%"
        result, built = self.execute("THM-02", items, records, files)
        self.assertEqual(result.status, "needs_input")
        self.assertFalse(built)

    def test_units_distinguish_grams_gravity_and_composition_basis(self):
        self.assertEqual(convert(5, "g", "kg"), .005)
        self.assertAlmostEqual(convert(1.62, "m/s2", "g"), .1651940265)
        with self.assertRaises(MappingError):
            convert(25, "wt%", "mf")

    def test_document_and_prompt_quotes_assemble_and_reject_fabricated_values(self):
        items = [
            assignment("/params/pressure_kpa", "quote", file_id="report",
                       quote="Chamber pressure: 0.5 atm.", token="0.5", unit="atm"),
            assignment("/params/mole_fracs/O2", "quote", file_id="report",
                       quote="Chamber oxygen: 21%.", token="21", unit="%"),
            assignment("/params/mole_fracs/N2", "quote", file_id="report",
                       quote="Chamber nitrogen: 79%.", token="79", unit="%"),
            assignment("/params/temp_k", "prompt", quote="300 K", token="300", unit="K"),
        ]
        records = [search_record("report", "text/plain", role="documentation")]
        files = {"report": b"Chamber pressure: 0.5 atm. Chamber oxygen: 21%. Chamber nitrogen: 79%."}
        response, built = self.execute("THM-02", items, records, files, "Compute properties at 300 K.")
        self.assertEqual(response.status, "completed", response.message)
        self.assertAlmostEqual(built["THM-02"]["params"]["pressure_kpa"], 50.6625)
        self.assertAlmostEqual(built["THM-02"]["params"]["mole_fracs"]["O2"], 0.21)
        items[1]["source"]["token"] = "31"
        response, built = self.execute("THM-02", items, records, files, "Compute properties at 300 K.")
        self.assertEqual(response.status, "needs_input")
        self.assertIn("value token is not in", response.message)
        self.assertFalse(built)

    def test_document_preview_reaches_the_planner_before_calculation(self):
        report = 'Chamber pressure: 1 atm. Oxygen: 21%. Nitrogen: 79%.'
        records = [search_record('report', 'text/plain', role='documentation')]
        items = [
            assignment('/params/pressure_kpa', 'quote', file_id='report',
                       quote='Chamber pressure: 1 atm.', token='1', unit='atm'),
            assignment('/params/mole_fracs/O2', 'quote', file_id='report', quote='Oxygen: 21%.', token='21', unit='%'),
            assignment('/params/mole_fracs/N2', 'quote', file_id='report', quote='Nitrogen: 79%.', token='79', unit='%'),
            assignment('/params/temp_k', 'prompt', quote='300 K', token='300', unit='K'),
        ]
        def generate(messages):
            context = json.loads(messages[1]["content"])
            self.assertEqual(len(context["input_mapping_contracts"]), 20)
            if not context["inspection"]:
                return json.dumps({"action": "inspect_files", "operation": None, "selected_file_ids": ["report"],
                                   "requested_asset_ids": [], "explanation": "Read the report", "warnings": []})
            self.assertIn(report, str(context["inspection"][0]["preview"]["pages"]))
            plan = make_mapping("THM-02", items, ["report"])
            parameters = plan["operation"]["parameters"]
            parameters["request_json"] = json.loads(parameters["request_json"])
            return json.dumps(plan)

        def download(_request):
            return httpx.Response(200, stream=httpx.ByteStream(report.encode()))

        with httpx.Client(transport=httpx.MockTransport(download)) as client:
            result = run_workflow('Compute mixture properties at 300 K.', {'query_id': 'preview', 'files': records},
                                  LocalPlanner(generate), client=client, url_validator=lambda url: None)
        self.assertEqual(result.status, 'completed', result.message)
        self.assertEqual([block['type'] for block in result.blocks], ['inspection', 'calculation'])

    def test_missing_fields_are_reported_before_the_worker(self):
        item = assignment("/params/pressure_kpa", "json", file_id="data", pointer="/pressure")
        response, built = self.execute("THM-02", [item], [search_record("data", "application/json")],
                                       {"data": b'{"pressure":{"value":100,"unit":"kPa"}}'})
        self.assertEqual(response.status, "needs_input")
        self.assertIn("/params/mole_fracs/*", response.message)
        self.assertIn("/params/temp_k", response.message)
        self.assertFalse(built)
