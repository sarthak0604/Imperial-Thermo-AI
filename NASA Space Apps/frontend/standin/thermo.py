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

    return QuestionParser(model_id=name, max_new_tokens=3200)


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


ISS_LEWIS_QUESTION = re.compile(
    r"(?:figure out|calculate|estimate|what is) (?:the )?lewis number "
    r"(?:for|of) a methane flame in (?:a |an )?nitrogen[- ]diluted iss (?:environment|atmosphere)[?.]?",
    re.IGNORECASE,
)
ISS_ATMOSPHERE_SOURCE = "https://ntrs.nasa.gov/api/citations/20050185597/downloads/20050185597.pdf"


def methane_iss_lewis():
    """Run THM-02 on stoichiometric reactants at the cabin reference pressure."""
    from request_planner.function_registry import run_model

    temperature_k, pressure_kpa = 295.0, 101.3
    # Oxygen fractions describe the CH4-free oxidizer. Add one mole of fuel
    # for each two moles of O2, then express the reactants as mole fractions.
    scenario_results = []
    for oxygen_pct in (21, 18, 15):
        oxygen = oxygen_pct / 100
        methane = oxygen / 2
        total = 1 + methane
        mixture = {"CH4": methane / total, "O2": oxygen / total, "N2": (1 - oxygen) / total}
        evaluated = run_model("THM-02", {
            "params": {"mole_fracs": mixture, "target_species": "CH4",
                       "temp_k": temperature_k, "pressure_kpa": pressure_kpa},
            "psi_citations": [ISS_ATMOSPHERE_SOURCE],
            "investigation_context": {"source_scope": "ISS pressure and nominal oxidizer O2, NASA Table 1-1",
                                      "oxidizer_oxygen_pct": oxygen_pct},
        })
        scenario_results.append({"oxidizer_oxygen_pct": oxygen_pct, "result": evaluated})

    baseline = scenario_results[0]["result"]
    numbers = [entry["result"]["dimensionless_numbers"]["lewis_number"] for entry in scenario_results]
    summary = (f"THM-02 estimates methane's Lewis number at {numbers[0]:.3f} for the nominal ISS case "
               f"and {numbers[-1]:.3f} when nitrogen replaces oxygen down to 15% in the oxidizer. "
               "Values near 1 mean heat and methane diffuse at similar rates.")
    assumptions = [
        "NASA's nominal ISS reference supplies 101.3 kPa and 21% oxygen before methane is added. "
        "The remaining oxidizer is modeled as dry nitrogen.",
        "The calculation uses unburned, premixed reactants at 295 K and a stoichiometric fuel-to-oxygen ratio "
        "of 1 mole CH4 to 2 moles O2. Lewis number uses methane's mass diffusivity.",
        "The prompt gives no added nitrogen amount. The 18% and 15% oxygen points are illustrative "
        "replacements of oxygen by nitrogen at the same pressure and temperature.",
    ]
    data = dict(baseline, assumptions=assumptions, dilution_scenarios=scenario_results)
    calc = {"type": "calculation", "model_id": "THM-02", "evidence_type": "model_estimate",
            "illustrative": True, "data": data, "result_summary": summary}
    chart = {"type": "chart", "chart_type": "scatter", "title": "Methane Lewis number with added nitrogen dilution",
             "x": {"label": "Oxidizer oxygen before methane is added", "unit": "mol%",
                   "values": [entry["oxidizer_oxygen_pct"] for entry in scenario_results]},
             "series": [{"label": "Methane Lewis number", "unit": None, "values": numbers}],
             "evidence_type": "model_estimate", "illustrative": True}
    return {
        "summary": summary, "answer": summary, "blocks": [calc, chart],
        "evidence": [{"label": "NASA ISS cabin atmosphere", "note": "Table 1-1", "url": ISS_ATMOSPHERE_SOURCE}],
        "limitations": "These are transport estimates for the unburned mixture. Flame stability and extinction "
                       "also depend on chemistry, geometry, and flow.",
        "meta": {"source": "live", "provider": "thermo", "model": "THM-02", "status": "completed",
                 "si_generated": True},
    }


R377_TIME = re.compile(r"\b(\d+(?:\.\d+)?)\s+(s|secs?|seconds?)\b", re.IGNORECASE)
R377_QUESTION = re.compile(
    r"(?:how much does a burning fuel (?:droplet|drop) shrink in"
    r"|how big would a burning fuel (?:droplet|drop) be after"
    r"|can you show me how a burning fuel (?:droplet|drop) changes over the first)"
    r" <time> (?:in space|in (?:orbital )?microgravity)\??"
)
R377_REPORT = "https://ntrs.nasa.gov/api/citations/20140006750/downloads/20140006750.pdf"


def reviewed_r377_plan(question, results):
    """Offer a reviewed NASA case for ordinary droplet questions in its measured phase."""
    from request_planner.models import Plan

    duration = R377_TIME.search(question)
    if duration is None:
        return None
    pattern = " ".join((question[:duration.start()] + "<time>" + question[duration.end():]).lower().split())
    if not R377_QUESTION.fullmatch(pattern):
        return None
    report = next((file for file in results.files if file.file_id == "nasa-cool-flame-report"
                   and "R377" in file.run_ids and str(file.retrieval_url) == R377_REPORT), None)
    if report is None:
        return None
    if not 0 < float(duration[1]) <= 14.6:
        return Plan(action="no_match", selected_file_ids=[], requested_asset_ids=[], operation=None,
                    explanation="R377's hot-flame reconstruction covers a positive time up to about 14.6 seconds. "
                    "Ask about a shorter window or request the later cool-flame phase.", warnings=[])

    path = REPO / "examples" / "r377_report_request.json"
    plan = Plan.model_validate(json.loads(path.read_text(encoding="utf-8-sig"))["plan"])
    params = plan.operation.parameters
    mapping = json.loads(params.request_json)
    time_binding = next(item for item in mapping["input_mapping"]["assignments"]
                        if item["target"] == "/request/scenario/time_limit_s")
    time_binding["source"].update(quote=duration[0], token=duration[1], unit=duration[2])
    params.request_json = json.dumps(mapping)
    plan.explanation = "Estimate the change in droplet diameter during the hot-flame phase."
    plan.warnings = [
        "Scenario selected: NASA FLEX run R377, a burning n-decane droplet in microgravity. "
        "The initial conditions and hot-stage regression rate come from the NASA report.",
        "The report places visible flame extinction at about 14.6 seconds. The calculation covers the requested hot-phase window.",
    ]
    return plan


def thm10_summary(result):
    time = result["plot_data"]["time_s"]
    diameter = result["plot_data"]["diameter_mm"]
    return (
        f"The modeled droplet shrank by {diameter[0] - diameter[-1]:.3f} mm, "
        f"from {diameter[0]:.3f} mm to {diameter[-1]:.3f} mm after {time[-1]:g} seconds."
    )


def ask(question, env):
    normalized_question = " ".join(question.split())
    if ISS_LEWIS_QUESTION.fullmatch(normalized_question):
        return methane_iss_lewis()
    comparison = THICKNESS_COMPARISON.fullmatch(normalized_question)
    if comparison:
        return compare_acrylic_thickness(tuple(map(float, comparison.groups())))

    from request_planner.mini_graph import MiniGraph, search_graph
    from request_planner.planner import LocalPlanner
    from request_planner.service import execute_request, run_workflow

    graph_path = Path(env.get("THERMO_GRAPH") or REPO / "examples" / "psi_graph.json")
    graph = MiniGraph.model_validate_json(graph_path.read_text(encoding="utf-8"))
    results = search_graph(graph, question)
    response = None
    message = "No files in the configured PSI graph matched this question."
    name = model_id(env)
    reviewed = reviewed_r377_plan(question, results)
    if reviewed is not None:
        response = execute_request({"query_id": results.query_id, "plan": reviewed}, results, prompt=question)
        name = "reviewed R377 mapping"
    elif results.files:
        with MODEL_LOCK:
            model = instruction_model(name)
            if model.model is None:
                try:
                    model._load()
                except (OSError, RuntimeError, ValueError) as exc:
                    raise ModelLoadError from exc
            response = run_workflow(question, results, LocalPlanner(model.generate), planning_seconds=60)
    if response is not None:
        message = response.message or "The Thermo workflow returned no explanation."
        for block in response.blocks:
            if block["type"] == "calculation" and block.get("model_id") == "THM-01":
                message = block["result_summary"] = thm01_summary(block["data"])
            elif block["type"] == "calculation" and block.get("model_id") == "THM-10":
                message = block["result_summary"] = thm10_summary(block["data"])

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
