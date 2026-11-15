"""Temporary retrieval, deterministic input mapping, and frontend presentation."""

import copy
import csv
import hashlib
import ipaddress
import json
import math
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.parse import urljoin, urlsplit

import httpx

from .flex_input import build_flex_input, supports_flex_table
from .function_registry import model_spec
from .input_mapping import build_model_input, mapping_from_request
from .input_sources import MappingError, Sources, TEXT_MEDIA
from .models import SearchResults, ThermoOperation, Variable
from .planner import PlanningError, validate_plan
from .plotting import numeric_pairs


class ExecutionError(ValueError):
    pass


def public_url(url):
    """Check destinations including every redirect before opening a connection."""
    parsed = urlsplit(str(url))
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username or parsed.password or parsed.port not in {None, 80, 443}):
        raise ExecutionError("Download requires a public HTTP(S) URL on a standard port")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80),
                                       type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ExecutionError("Download host could not be resolved") from exc
    if not addresses or any(not ipaddress.ip_address(address[4][0]).is_global for address in addresses):
        raise ExecutionError("Download destination must have only public IP addresses")


def strict_json(text):
    def reject(value):
        raise ExecutionError(f"Non-finite JSON value: {value}")
    return json.loads(text, parse_constant=reject)


class UnsupportedCSVHeader(ExecutionError):
    """The CSV layout requires an explicit header mapping."""


def csv_columns(path, file):
    with path.open(encoding=file.encoding or "utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        if not header or any(not name for name in header) or len(header) != len(set(header)):
            raise UnsupportedCSVHeader("CSV needs nonempty unique column headers")
        numeric = dict.fromkeys(header, True)
        count = 0
        preview = []
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ExecutionError("CSV contains a row with the wrong number of cells")
            count += 1
            if len(preview) < 3:
                preview.append(row)
            for name, value in row.items():
                try:
                    numeric[name] = numeric[name] and bool(value.strip()) and math.isfinite(float(value))
                except ValueError:
                    numeric[name] = False
        if not count:
            raise ExecutionError("CSV contains no data rows")
    known = {v.name: v.unit for v in file.variables or []}
    variables = [Variable(name=name, numeric=bool(numeric[name]), unit=known.get(name)) for name in header]
    return variables, {"kind": "table", "row_count": count,
                       "columns": [v.model_dump() for v in variables], "preview": preview}


def preview_json(value, depth=0):
    if depth > 10:
        return "<nested content omitted>"
    if isinstance(value, dict):
        return {k: preview_json(v, depth + 1) for k, v in list(value.items())[:60]}
    if isinstance(value, list):
        return [preview_json(v, depth + 1) for v in value[:3]]
    if isinstance(value, str):
        return value[:1000]
    return value


class ExecutionSession:
    """One bounded workflow; the caller owns a TemporaryDirectory for its lifetime."""

    def __init__(self, directory, limits, client=None, url_validator=public_url, *, on_model_input=None, raw_prompt=""):
        self.directory = Path(directory)
        self.deadline = time.monotonic() + min(limits.max_runtime_seconds, 60)
        self.budget = min(limits.max_download_bytes, 100_000_000)
        self.client = client
        self.on_model_input = on_model_input
        self.raw_prompt = raw_prompt
        self.input_sources = Sources({}, self.fetch, self.remaining)
        self.url_validator = url_validator
        self.downloads = {}
        self.inspection = []
        self.sources = {}

    def remaining(self):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise ExecutionError("Execution runtime limit exceeded")
        return remaining

    def fetch(self, file):
        if file.file_id in self.downloads:
            previous, path = self.downloads[file.file_id]
            if previous != file.model_dump(mode="json"):
                # Inspection can enrich variable metadata without changing content identity.
                for field in ("retrieval_url", "investigation_id", "size_bytes", "media_type"):
                    if previous[field] != file.model_dump(mode="json")[field]:
                        raise ExecutionError("Source record changed during execution")
            return path
        self.remaining()
        path = self.directory / f"source-{len(self.downloads)}"
        if file.retrieval_url is None:
            raise ExecutionError("Selected source has no download URL")
        if file.size_bytes is not None and file.size_bytes > self.budget:
            raise ExecutionError("Selected source exceeds the remaining byte budget")
        if self.client is None:
            with httpx.Client(trust_env=False) as client:
                self._stream(client, str(file.retrieval_url), path)
        else:
            self._stream(self.client, str(file.retrieval_url), path)
        size = path.stat().st_size
        if file.size_bytes is not None and size != file.size_bytes:
            raise ExecutionError("Downloaded size differs from search metadata; refresh the source")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.downloads[file.file_id] = (file.model_dump(mode="json"), path)
        self.sources[file.file_id] = {
            "file_id": file.file_id, "investigation_id": file.investigation_id,
            "title": file.title, "source_page_url": str(file.source_page_url) if file.source_page_url else None,
            "run_ids": file.run_ids, "sha256": digest, "size_bytes": size,
        }
        return path

    def _stream(self, client, url, path):
        for _ in range(6):
            self.url_validator(url)
            with client.stream("GET", url, follow_redirects=False,
                               headers={"Accept-Encoding": "identity"},
                               timeout=min(10, self.remaining())) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise ExecutionError("Download redirect has no destination")
                    url = urljoin(url, location)
                    continue
                if response.status_code != 200:
                    raise ExecutionError(f"Source download failed (HTTP {response.status_code})")
                if response.headers.get("content-encoding", "identity").lower() != "identity":
                    raise ExecutionError("Compressed HTTP transfers are unsupported; request raw file bytes")
                length = response.headers.get("content-length")
                if length and int(length) > self.budget:
                    raise ExecutionError("Download exceeds the remaining byte budget")
                with path.open("wb") as handle:
                    for chunk in response.iter_raw():
                        self.remaining()
                        if len(chunk) > self.budget:
                            raise ExecutionError("Download exceeds the remaining byte budget")
                        self.budget -= len(chunk)
                        handle.write(chunk)
                return
        raise ExecutionError("Too many download redirects")

    def inspect(self, files):
        enriched, blocks = [], []
        for file in files:
            path = self.fetch(file)
            if file.media_type == "text/csv":
                try:
                    variables, content = csv_columns(path, file)
                except UnsupportedCSVHeader:
                    content = {"kind": "unsupported", "message": (
                        "CSV needs nonempty unique column headers. Provide a file with "
                        "one header row before calculating.")}
                else:
                    file = file.model_copy(update={"variables": variables})
            elif file.media_type == "application/json":
                payload = strict_json(path.read_text(encoding=file.encoding or "utf-8-sig"))
                if isinstance(payload, (dict, list)):
                    content = {"kind": "json", "preview": preview_json(payload),
                               "note": "Preview arrays contain at most three items; execution uses the full file."}
                else:
                    content = {"kind": "unsupported", "message": "Function input JSON must contain an object."}
            elif file.media_type in TEXT_MEDIA:
                try:
                    excerpts = self.input_sources.preview_document(file.file_id, self.raw_prompt)
                except (MappingError, UnicodeError) as exc:
                    excerpts = []
                    message = str(exc)
                else:
                    message = "The source has no extractable text in the inspected pages."
                if excerpts:
                    content = {"kind": "json", "preview": {"pages": excerpts},
                               "note": "Cite exact quotes with the one-based PDF page if present."}
                else:
                    content = {"kind": "unsupported", "message": message}
            else:
                content = {"kind": "unsupported", "media_type": file.media_type,
                           "message": "Provide CSV or a function-compatible JSON dataset for calculation."}
            block = {"type": "inspection", "file_id": file.file_id, **content}
            # Bound the context exposed to the planner; never truncate the downloaded data.
            if len(json.dumps(block)) > 24000:
                block = {"type": "inspection", "file_id": file.file_id, "kind": "unsupported",
                         "message": "JSON preview exceeds context limit; provide a smaller sourced model input."}
            blocks.append(block)
            enriched.append(file)
            self.remaining()
        self.inspection.extend(blocks)
        return enriched, blocks

    def execute(self, request, results):
        if request.query_id != results.query_id:
            raise PlanningError("Request query_id differs from search results")
        validate_plan(request.plan, results, request.limits)
        files = {file.file_id: file for file in results.files}
        self.input_sources.files = files
        plan = request.plan
        blocks = []
        if plan.action == "inspect_files":
            enriched, inspections = self.inspect([files[i] for i in plan.selected_file_ids])
            files.update({f.file_id: f for f in enriched})
            blocks.extend(inspections)
        elif plan.action == "calculate":
            operation = plan.operation
            file = files[operation.file_id]
            path = self.fetch(file)
            if isinstance(operation, ThermoOperation):
                payload = self.thermo_payload(operation, files, path)
                model_id = operation.parameters.model_id
                if self.on_model_input is not None:
                    self.on_model_input(model_id, copy.deepcopy(payload))
                result = self.calculate(model_id, payload)
                request_mapping = mapping_from_request(operation.parameters.request_json)
                if request_mapping is not None:
                    result["assembled_input_provenance"] = (
                        payload["evidence"]["provenance"] if "evidence" in payload
                        else payload["investigation_context"]
                    )
                presented = present_result(operation.parameters.model_id, result)
                for block in presented:
                    block["source_file_ids"] = plan.selected_file_ids
                blocks.extend(presented)
            else:
                xs, ys = numeric_pairs(path.read_bytes(), file.encoding or "utf-8-sig",
                                       operation.parameters.x, operation.parameters.y)
                units = {v.name: v.unit for v in file.variables or []}
                blocks.append({"type": "chart", "chart_type": "scatter", "title": file.title,
                               "x": {"label": operation.parameters.x, "unit": units[operation.parameters.x], "values": xs},
                               "series": [{"label": operation.parameters.y, "unit": units[operation.parameters.y], "values": ys}],
                               "evidence_type": "measured", "source_file_ids": [file.file_id]})
        for file_id in plan.requested_asset_ids:
            file = files[file_id]
            kind = "document" if file.media_type == "application/pdf" else file.role
            blocks.append({"type": kind, "file_id": file_id, "title": file.title,
                           "media_type": file.media_type, "url": str(file.retrieval_url),
                           "source_page_url": str(file.source_page_url) if file.source_page_url else None})
            self.sources.setdefault(file_id, {"file_id": file_id, "investigation_id": file.investigation_id,
                                              "title": file.title, "downloaded": False})
        self.remaining()
        return blocks, SearchResults(query_id=results.query_id, files=list(files.values()))

    def thermo_payload(self, operation, files, path):
        params = operation.parameters
        spec = model_spec(params.model_id)
        file = files[operation.file_id]
        mapping = mapping_from_request(params.request_json)
        if mapping is not None:
            try:
                return build_model_input(params.model_id, mapping, self.input_sources, self.raw_prompt)
            except MappingError as exc:
                raise ExecutionError(f"Function needs compatible inputs: {exc}") from exc
        if (not params.bindings and params.template_file_id is None
                and supports_flex_table(file, params.model_id)):
            values = strict_json(params.request_json) if params.request_json is not None else None
            try:
                return build_flex_input(params.model_id, values, path, file)
            except (ValueError, csv.Error, UnicodeError) as exc:
                raise ExecutionError(f"Function needs compatible inputs: {exc}") from exc
        if params.template_file_id:
            template = files[params.template_file_id]
            payload = strict_json(self.fetch(template).read_text(encoding=template.encoding or "utf-8-sig"))
        elif file.media_type == "application/json":
            payload = strict_json(path.read_text(encoding=file.encoding or "utf-8-sig"))
        else:
            payload = {}
        if not isinstance(payload, dict):
            raise ExecutionError("Function input JSON must be an object")
        if payload.get("model_id", params.model_id) != params.model_id:
            raise ExecutionError("Downloaded payload identifies a different THM model")
        payload = copy.deepcopy(payload.get("example_request", payload))
        if params.request_json is not None:
            values = strict_json(params.request_json)
            if spec["requires_evidence"]:
                if set(values) - {"topic", "analysis", "scenario"}:
                    raise ExecutionError("Modern THM request accepts topic, analysis, and scenario only")
                payload["request"] = values
            else:
                # Legacy adapters accept a params object. Evidence can only come from files.
                if any(k in values for k in ("evidence", "sources", "provenance", "psi_citations")):
                    raise ExecutionError("Model may not supply source evidence")
                payload["params"] = values
        if spec["requires_evidence"] and not isinstance(payload.get("evidence"), dict):
            raise ExecutionError("This function requires sourced evidence in the downloaded JSON")
        if params.bindings:
            apply_bindings(payload, path, file, params.bindings)
        if "function_id" in payload and payload["function_id"] != params.model_id:
            raise ExecutionError("Function ID differs from the selected model")
        return payload

    def calculate(self, model_id, payload):
        task_path = self.directory / "calculation-input.json"
        output_path = self.directory / "calculation-output.json"
        task_path.write_text(json.dumps({"model_id": model_id, "payload": payload}, allow_nan=False))
        try:
            completed = subprocess.run([sys.executable, "-m", "request_planner.worker",
                                        str(task_path), str(output_path)],
                                       timeout=self.remaining(), stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL, check=False)
        except subprocess.TimeoutExpired as exc:
            raise ExecutionError("Function exceeded the execution runtime limit") from exc
        if completed.returncode or not output_path.exists():
            raise ExecutionError("Function worker failed")
        if output_path.stat().st_size > 100_000_000:
            raise ExecutionError("Function output exceeds the response limit")
        output = strict_json(output_path.read_text())
        if "error" in output:
            raise ExecutionError(f"Function needs compatible inputs: {output['error']}")
        return output["result"]


def apply_bindings(payload, path, file, bindings):
    """Replace existing numeric slots; preserve calibration/source metadata verbatim."""
    variables, _ = csv_columns(path, file)
    numeric = {v.name: v.numeric for v in variables}
    with path.open(encoding=file.encoding or "utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    seen = []
    for binding in bindings:
        parts = [p.replace("~1", "/").replace("~0", "~") for p in binding.target[1:].split("/")]
        if (any(p in {"sources", "source_url", "source_locator", "provenance", "id", "unit", "units",
                       "validity", "bounds", "run_id", "setup_id", "material_id"} for p in parts)
                or any(parts[:len(other)] == other or other[:len(parts)] == parts for other in seen)):
            raise ExecutionError("Bindings cannot replace source metadata, validity bounds, or overlapping targets")
        seen.append(parts)
        parent = payload
        try:
            for part in parts[:-1]:
                parent = parent[int(part)] if isinstance(parent, list) else parent[part]
            key = int(parts[-1]) if isinstance(parent, list) else parts[-1]
            existing = parent[key]
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise ExecutionError("Binding must name an existing JSON input slot") from exc
        for column in binding.columns:
            if not numeric.get(column.column):
                raise ExecutionError(f"CSV column contains missing or nonnumeric data: {column.column}")
            target_field = column.field if binding.mode == "records" else parts[-1]
            expected_unit = INPUT_UNITS.get(target_field)
            if binding.mode == "scalar" and parts[-1] == "value" and isinstance(parent, dict):
                expected_unit = parent.get("unit")
            if expected_unit is None or column.unit != expected_unit:
                raise ExecutionError(f"No matching destination unit contract for {target_field}")
        if binding.mode == "scalar":
            if isinstance(existing, bool) or not isinstance(existing, (int, float)):
                raise ExecutionError("Scalar binding must replace an existing number")
            if binding.row >= len(rows):
                raise ExecutionError("Requested dataset row is out of range")
            value = float(rows[binding.row][binding.columns[0].column])
        elif binding.mode == "series":
            if not isinstance(existing, list) or not existing or any(type(v) not in (int, float) for v in existing):
                raise ExecutionError("Series binding must replace an existing numeric array")
            value = [float(row[binding.columns[0].column]) for row in rows]
        else:
            if not isinstance(existing, list) or not existing or not all(isinstance(v, dict) for v in existing):
                raise ExecutionError("Records binding must replace an existing sample table")
            # Every sample field must be populated; no unmeasured template values leak into results.
            fields = {column.field for column in binding.columns}
            if any(set(sample) != fields or any(type(v) not in (int, float) for v in sample.values())
                   for sample in existing):
                raise ExecutionError("CSV mapping must supply every sample field in the template")
            value = [{c.field: float(row[c.column]) for c in binding.columns} for row in rows]
        parent[key] = value


INPUT_UNITS = {
    "time_s": "s", "inlet_o2_kg_s": "kg/s", "outlet_o2_kg_s": "kg/s",
    "mass_flow_kg_s": "kg/s", "net_co_kg_s": "kg/s", "net_co2_kg_s": "kg/s",
    "soot_carbon_kg_s": "kg/s", "reference_hrr_W": "W", "hrr_W": "W",
    "radiometer_flux_w_m2": "W/m2", "total_hrr_w": "W", "background_flux_w_m2": "W/m2",
    "o2_vol_frac": "1", "co2_vol_frac": "1", "co_vol_frac": "1",
    "y_fuel_stream": "1", "y_ox_stream": "1", "x_o2": "1", "o2_mole_frac": "1", "d0_mm": "mm",
    "pressure_kpa": "kPa", "pressure_kPa": "kPa", "t_amb_k": "K", "t_surface_k": "K",
    "temp_k": "K", "air_speed_m_s": "m/s", "u_flow_ms": "m/s",
    "oxygen_consumption_kg_s": "kg/s", "co2_production_kg_s": "kg/s",
    "co_production_kg_s": "kg/s", "other_net_gas_mol_s": "mol/s",
}


def present_result(model_id, result):
    """Keep full model output and expose aligned arrays as renderable chart blocks."""
    evidence_type = "data_reduction" if result.get("status") == "data_reduction" else "model_estimate"
    illustrative = result.get("illustrative", result.get("provenance", {}).get("illustrative"))
    blocks = [{"type": "calculation", "model_id": model_id, "evidence_type": evidence_type,
               "illustrative": illustrative, "data": result}]

    def visit(value, path="result"):
        if not isinstance(value, dict):
            return
        arrays = {k: v for k, v in value.items() if isinstance(v, list) and len(v) > 1
                  and all(type(n) in (int, float) and math.isfinite(n) for n in v)}
        x_name = next((k for k in ("time_s", "air_speed_m_s", "diameter_mm", "thickness_m") if k in arrays), None)
        if x_name:
            series = [{"label": k, "unit": None, "values": v} for k, v in arrays.items()
                      if k != x_name and len(v) == len(arrays[x_name])]
            for item in series:
                blocks.append({"type": "chart", "chart_type": "line", "title": f"{model_id}: {path}",
                               "x": {"label": x_name, "unit": None, "values": arrays[x_name]},
                               "series": [item], "evidence_type": evidence_type, "illustrative": illustrative})
        for key, child in value.items():
            if isinstance(child, dict):
                visit(child, f"{path}.{key}")
    visit(result)
    return blocks
