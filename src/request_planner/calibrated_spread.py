"""SI-assisted routing for the bundled BASS-II PMMA calibration."""

import json
import re
import tempfile
import uuid

from .backend_models import AnswerResult, RetrievalBundle
from .execution import ExecutionError, ExecutionSession
from .function_registry import function_root, model_spec
from .models import ExecutionLimits, FrontendResponse
from .model_presentation import model_highlights


NUMBER = r"(?<![\w.+-])(\d+(?:\.\d+)?)"
THICKNESSES = re.compile(
    rf"\bfrom\s+{NUMBER}\s*(?:mm\s*)?to\s+{NUMBER}\s*mm\b", re.I
)
CONDITIONS = {
    "air_speed": rf"{NUMBER}\s*cm/s\s+(?:opposed\s+)?airflow\b",
    "oxygen": rf"{NUMBER}\s*%\s+oxygen\b",
    "pressure": rf"{NUMBER}\s*kPa(?:\s+pressure)?\b",
    "sample_width": rf"{NUMBER}\s*mm\s+(?:sheet|sample)\s+width\b",
}


def pmma_comparison_inputs(spec):
    prompt = spec.original_prompt
    models = {r.model_id for r in spec.requirements if r.model_id}
    if (models != {"THM-05"} or spec.clarifications
            or set(spec.investigations) - {"PSI-25"}
            or "PSI-25" in spec.excluded_investigations
            or any(r.kind not in {"calculation", "chart", "explanation"} for r in spec.requirements)
            or not re.search(r"\b(?:acrylic|pmma)\b", prompt, re.I)
            or not re.search(r"\bmicrogravity\b", prompt, re.I)
            or not re.search(r"\b(?:oppos\w*|against (?:the )?airflow)\b", prompt, re.I)
            or re.search(r"\b(?:without|exclude|instead|concurrent|normal gravity|lunar|martian|csv|dataset|measured)\b", prompt, re.I)):
        return None
    thicknesses = list(THICKNESSES.finditer(prompt))
    conditions = {key: list(re.finditer(pattern, prompt, re.I))
                  for key, pattern in CONDITIONS.items()}
    if len(thicknesses) != 1 or any(len(values) > 1 for values in conditions.values()):
        return None
    # Additional numerical inputs could specify a different or conflicting scenario.
    unparsed = prompt
    for match in sorted([thicknesses[0], *(v[0] for v in conditions.values() if v)],
                        key=lambda m: m.start(), reverse=True):
        unparsed = unparsed[:match.start()] + unparsed[match.end():]
    if re.search(r"\d", re.sub(r"\b(?:THM-05|PSI-25)\b", "", unparsed, flags=re.I)):
        return None

    values = [float(n) for n in thicknesses[0].groups()]
    if values[0] == values[1]:
        return None
    return values, {key: float(matches[0].group(1)) for key, matches in conditions.items() if matches}


def answer_pmma_comparison(spec, graph_id):
    inputs = pmma_comparison_inputs(spec)
    if inputs is None:
        return None
    values, conditions = inputs
    model_id = "THM-05"
    payload = json.loads(function_root().joinpath(model_spec(model_id)["example"]).read_text())
    scenario = payload["request"]["scenario"]
    for key, number in conditions.items():
        slot = scenario if key == "sample_width" else scenario["ambient"]
        slot[key]["value"] = number / 1000 if key == "sample_width" else number

    query_id = uuid.uuid4().hex
    bundle = RetrievalBundle(query_id=query_id, graph_id=graph_id, files=[])
    response = FrontendResponse(query_id=query_id, status="completed", message="")
    try:
        with tempfile.TemporaryDirectory(prefix="thermo-pmma-") as directory:
            worker = ExecutionSession(directory, ExecutionLimits())
            results = []
            for thickness in values:
                scenario["specimen_thickness"]["value"] = thickness / 1000
                results.append(worker.calculate(model_id, payload))
    except ExecutionError as exc:
        response.status = "needs_input"
        response.message = f"The BASS-II calibration does not cover this request or could not run. {exc}"
    else:
        source_id = "bass-ii-pmma-thermal-calibration"
        rates = [r["spread_rate_mm_s"] for r in results]
        bundle.diagnostics.append({'function_pipeline':[
            {'task_id':f'spread-{i+1}','model_id':model_id,'purpose':f'Predict spread for {values[i]} mm sheet',
             'status':'completed','depends_on':[],'input_json':getattr(r,'input_payload',{}),
             'output_json':r,'provenance':[]} for i,r in enumerate(results)]})
        calibration = results[0]["sources"][0]
        response.sources = [{"file_id": source_id, "investigation_id": "PSI-25",
                             "title": calibration["locator"], "source_page_url": calibration["url"]}]
        response.blocks = [
            {"type": "calculation", "model_id": model_id, "evidence_type": "model_estimate",
             "illustrative": False, "source_file_ids": [source_id],
             "input_json": {f"case_{i+1}": r.input_payload for i, r in enumerate(results)},
             "task_id": "pmma-thickness-comparison",
             "data": {"thicknesses_mm": values, "rates_mm_s": rates,
                      "calibration_id": results[0]["calibration_id"],
                      "ambient": results[0]["ambient"], "sample_width_m": results[0]["sample_width_m"],
                      "opposed_gas_speed_m_s": results[0]["opposed_gas_speed_m_s"]}},
        ]
        response.blocks[0]["headline_metrics"] = model_highlights(model_id, response.blocks[0]["data"])
        if any(r.kind == "chart" for r in spec.requirements):
            response.blocks.append({
                "type": "chart", "chart_type": "scatter", "title": "THM-05 predicted PMMA flame spread",
                "x": {"label": "Sheet thickness", "unit": "mm", "values": values},
                "series": [{"label": "Predicted spread speed", "unit": "mm/s", "values": rates}],
                "evidence_type": "model_estimate", "source_file_ids": [source_id],
            })
        response.warnings = list(results[0]["limitations"])
        omitted = [key for key in CONDITIONS if key not in conditions]
        if omitted:
            notes = []
            for key in omitted:
                value = scenario[key] if key == "sample_width" else scenario["ambient"][key]
                notes.append(f"{key.replace('_', ' ')} {value['value']:g} {value['unit']}")
            assumption = "Used bundled BASS-II conditions for unspecified inputs: " + ", ".join(notes) + "."
            response.warnings.append(assumption)
            response.blocks[0]["input_provenance"] = [{"kind": "scenario_assumption", "assumption": assumption}]
        response.message = (
            f"Using the BASS-II calibration, THM-05 predicts {rates[0]:.3f} mm/s "
            f"at {values[0]:.2f} mm and {rates[1]:.3f} mm/s at {values[1]:.2f} mm."
        )

    completed = response.status == "completed"
    result_status = "completed" if completed else "needs_input"
    return AnswerResult(
        trace_id=query_id, status=result_status, message=response.message,
        request=spec, retrieval=bundle, result=response,
        fulfilment=[
            {"id": r.id, "kind": r.kind, "satisfied": completed,
             "missing": None if completed else response.message}
            for r in spec.requirements
        ],
    )
