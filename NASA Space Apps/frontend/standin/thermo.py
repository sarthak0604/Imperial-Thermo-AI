"""Adapt the Thermo workflow to Omri's frontend. SI-assisted with OpenAI Codex."""

from functools import lru_cache
import json
import re
from pathlib import Path
from threading import Lock

REPO = Path(__file__).resolve().parents[3]
MODEL_LOCK = Lock()


class ModelLoadError(RuntimeError):
    pass


def model_id(env):
    from imperial_thermo_ai.parser import DEFAULT_MODEL

    return env.get("PSI_PARSER_MODEL") or DEFAULT_MODEL


@lru_cache(maxsize=1)
def instruction_model(name):
    from imperial_thermo_ai.parser import QuestionParser

    return QuestionParser(model_id=name, max_new_tokens=1600)


def thm01_summary(result):
    """Present the THM-01 function's outputs and the inputs it actually used."""
    inputs, outputs = result["inputs"], result["outputs"]
    return (
        f"THM-01 estimates an adiabatic flame temperature of "
        f"{outputs['adiabatic_flame_temp_k']:,.2f} K ({outputs['adiabatic_flame_temp_c']:,.2f} °C) "
        f"for {inputs['fuel_species']} with {inputs['o2_mole_frac']:.1%} oxygen "
        f"at {inputs['pressure_kpa']:g} kPa and an initial temperature of {inputs['t_init_k']:g} K."
    )


# Recognize comparisons that vary only sheet thickness. Other scenario inputs
# still go through the planner and require evidence for the requested conditions.
THICKNESS_COMPARISON = re.compile(
    r"how (?:does|would) (?:increasing|changing) (?:acrylic|pmma) sheet thickness "
    r"from (\d+(?:\.\d+)?)\s*(?:mm\s*)?to (\d+(?:\.\d+)?)\s*mm "
    r"affect (?:the )?flame spread (?:rate )?(?:against (?:the )?airflow|in opposed flow) "
    r"in (?:orbital )?microgravity[?.]?",
    re.IGNORECASE,
)


def compare_acrylic_thickness(thicknesses_mm):
    from request_planner.function_registry import function_root, model_spec, run_model

    model = "THM-05"
    example = model_spec(model)["example"]
    payload = json.loads(function_root().joinpath(example).read_text(encoding="utf-8"))
    scenario = payload["request"]["scenario"]
    profile = payload["evidence"]["materials"][0]["calibrations"][0]
    source = {"psi_id": "PSI-25", "note": "BASS-II thin-sheet PMMA calibration, equations 2.11–2.12",
              "url": profile["source_url"]}
    low, high = (bound * 1000 for bound in profile["thickness_range_m"])
    meta = {"source": "live", "provider": "thermo", "model": model, "status": "completed"}
    if not all(low <= thickness <= high for thickness in thicknesses_mm):
        message = f"The bundled BASS-II calibration covers PMMA thicknesses from {low:g} to {high:g} mm."
        return {"summary": message, "answer": message, "evidence": [source], "blocks": [],
                "meta": {**meta, "status": "needs_input"}}

    rates = []
    for thickness in thicknesses_mm:
        scenario["specimen_thickness"]["value"] = thickness / 1000
        result = run_model(model, payload)
        rates.append(result["spread_rate_mm_s"])

    labels = [f"{thickness:.2f} mm" for thickness in thicknesses_mm]
    message = f"THM-05 estimates {rates[0]:.2f} mm/s at {labels[0]} and {rates[1]:.2f} mm/s at {labels[1]}."
    if rates[0] != rates[1]:
        direction = "decrease" if rates[1] < rates[0] else "increase"
        message += f" That is a {abs(rates[1] / rates[0] - 1):.0%} {direction}."
    air = scenario["ambient"]
    limitations = (
        f"The estimate holds opposed airflow at {air['air_speed']['value']:g} cm/s, "
        f"oxygen at {air['oxygen']['value']:g}%, and pressure at {air['pressure']['value']:g} kPa "
        "using the bundled BASS-II calibration. "
        "The published thickness-check points are approximate figure readings with unspecified individual airflow."
    )
    chart = {"type": "chart", "chart_type": "scatter", "title": "THM-05 opposed-flow spread estimates",
             "x": {"label": "Sheet thickness", "unit": "mm", "values": list(thicknesses_mm)},
             "series": [{"label": "Estimated flame spread rate", "unit": "mm/s", "values": rates}],
             "evidence_type": "model_estimate"}
    return {"summary": message, "answer": message, "evidence": [source], "limitations": limitations,
            "blocks": [chart], "meta": meta}


def ask(question, env):
    comparison = THICKNESS_COMPARISON.fullmatch(" ".join(question.split()))
    if comparison:
        return compare_acrylic_thickness(tuple(map(float, comparison.groups())))

    from request_planner.mini_graph import MiniGraph, search_graph
    from request_planner.planner import LocalPlanner
    from request_planner.service import run_workflow

    graph_path = Path(env.get("THERMO_GRAPH") or REPO / "examples" / "psi_graph.json")
    graph = MiniGraph.model_validate_json(graph_path.read_text(encoding="utf-8"))
    results = search_graph(graph, question)
    response = None
    message = "No files in the configured PSI graph matched this question."
    name = model_id(env)
    if results.files:
        with MODEL_LOCK:
            model = instruction_model(name)
            if model.model is None:
                try:
                    model._load()
                except (OSError, RuntimeError, ValueError) as exc:
                    raise ModelLoadError from exc
            planner = LocalPlanner(model.generate, timed_generate=model.generate)
            response = run_workflow(question, results, planner, planning_seconds=60)
        message = response.message or "The Thermo workflow returned no explanation."
        for block in response.blocks:
            if block["type"] == "calculation" and block.get("model_id") == "THM-01":
                message = block["result_summary"] = thm01_summary(block["data"])

    files = {file.file_id: file for file in results.files}
    evidence = [
        {"psi_id": source["investigation_id"], "note": source["title"],
         "url": source.get("source_page_url") or str(files[source["file_id"]].source_page_url or "")}
        for source in (response.sources if response else [])
        if source["file_id"] in files
    ]
    blocks = response.blocks if response else []
    return {
        "summary": message,
        "answer": message,
        "evidence": evidence,
        "limitations": "\n\n".join(response.warnings) if response else "",
        "blocks": blocks,
        "meta": {"source": "live", "provider": "thermo", "model": name,
                 "status": response.status if response else "no_match", "si_generated": True},
    }
