"""Semantic task routing before retrieval; IDs and origins are validated locally."""

import json
import re
from functools import lru_cache

from pydantic import Field

from imperial_thermo_ai.parser import _json_object
from imperial_thermo_ai.graph_search import normalize

from .function_registry import model_spec
from .models import Contract

# Discovery vocabulary; scientific validity is checked by the function validator.
CUES = [
    "adiabatic flame temperature|equilibrium products",
    "lewis number|thermal diffusivity|mass diffusivity",
    "stoichiometric mixture fraction|flame sheet radius",
    "heat release|oxygen consumption",
    "opposed flow|against airflow|against the airflow|upstream flame spread",
    "concurrent flow|with the airflow|downstream flame spread",
    "blowoff|blow off|damkohler",
    "richardson number|mixed convection|buoyancy driven flow",
    "spalding|b number|gasification",
    "droplet regression|burning constant|squared diameter",
    "two stage|cool flame transition",
    "multicomponent evaporation|preferential evaporation",
    "radiative quenching",
    "radiative heat fraction|radiative fraction",
    "soot inception",
    "time to ignition|solid heating|thermal penetration",
    "limiting oxygen|flammability limit",
    "suppression heat capacity|heat absorbed by suppressant|water mist",
    "cabin pressure rise|closed cabin|sealed compartment pressure",
    "smoke transport|aerosol transport|agglomeration",
]


class MissingSlot(Contract):
    id: str
    question: str
    reason_code: str = "missing_value"
    unit: str | None = None
    choices: list[str] = Field(default_factory=list)


class Route(Contract):
    intent: str = "discovery"
    model_ids: list[str] = Field(default_factory=list, max_length=4)
    reason: str = ""
    missing: list[MissingSlot] = Field(default_factory=list, max_length=3)


@lru_cache(maxsize=1)
def capabilities():
    from .function_registry import input_contract

    result = []
    for i in range(20):
        mid = f"THM-{i + 1:02}"
        contract = input_contract(mid)
        contract.pop("documentation", None)
        spec = model_spec(mid)
        result.append({
            "model_id": mid, "description": spec["description"],
            "cues": CUES[i].split("|"), "requires_evidence": spec["requires_evidence"],
            "input_contract": {key: contract[key] for key in ("required_inputs", "defaults")
                               if key in contract},
        })
    return result


def _route_once(prompt, generate=None, context=None):
    explicit = list(
        dict.fromkeys(re.findall(r"\bTHM-(?:0[1-9]|1[0-9]|20)\b", prompt.upper()))
    )
    if generate:
        raw = generate(
            [
                {
                    "role": "system",
                    "content": "Classify the scientific request. Return JSON matching schema: "
                    + json.dumps(Route.model_json_schema())
                    + " Infer a THM model from the requested physical quantity without requiring its ID in the question. "
                    "intent must be calculation, explanation, discovery, or chart. A numerical what-is/how-much/what-if "
                    "question needs calculation. A conceptual definition or question about which model to use needs explanation. "
                    "Select relevant models even if evidence is missing. At classification return missing=[]; "
                    "input readiness and clarification questions are handled by the subsequent function planner, "
                    "which has the full source and parameter contracts. Do not invent inputs or calibration. "
                    "Do not ask what a THM ID means. Explicit IDs constrain calculation selection. "
                    "Use context only to resolve follow-ups; never treat prior generated prose as measured inputs.",
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "question": prompt,
                            "context": {k: v for k, v in (context or {}).items()
                                        if v and not (k == "resolved_task" and v == prompt)},
                            "capabilities": capabilities(),
                        }, separators=(",", ":")
                    ),
                },
            ]
        )
        result = Route.model_validate(_json_object(raw))
        if result.intent not in {"calculation", "explanation", "discovery", "chart"}:
            raise ValueError("Invalid task routing intent")
        for mid in result.model_ids:
            model_spec(mid)
        if explicit and result.intent in {"calculation", "chart"}:
            result.model_ids = explicit
        return result
    quantitative = bool(
        re.search(
            r"\b(calculate|compute|estimate|predict|plot|how much|what if)\b|\d",
            prompt,
            re.IGNORECASE,
        )
    )
    conceptual = bool(
        re.search(
            r"\b(what.*means|meaning|define|definition|which model|what model)\b",
            prompt,
            re.IGNORECASE,
        )
    )
    normalized = prompt.casefold().replace("-", " ")
    mids = explicit or [
        f"THM-{i + 1:02}"
        for i, c in enumerate(CUES)
        if any(x in normalized for x in c.split("|"))
    ]
    return Route(
        intent="calculation"
        if quantitative and not conceptual and mids
        else "explanation"
        if conceptual
        else "discovery",
        model_ids=mids[:4],
        reason="Deterministic capability discovery",
    )


# Match unambiguous physical quantities, including common phrasing from the UI.
QUANTITIES = {
    "THM-01": r"adiabatic flame temperatures?|peak (?:flame )?temperatures?.{0,60}(?:fuel|oxidizer)|how hot.{0,60}flames?",
    "THM-02": r"lewis number|thermal diffusivity",
    "THM-03": r"stoichiometric mixture fraction",
    "THM-04": r"heat (?:release(?: rate)?|was released)|oxygen[- ]consumption (?:measurements|calorimetry)",
    "THM-07": r"damk[oö]hler number",
    "THM-08": r"richardson number",
    "THM-09": r"spalding (?:mass transfer )?b.?number",
    "THM-10": r"droplet burning constant|droplet regression rate",
    "THM-16": r"time to ignition|how long.{0,60}(?:to|before it) ignite",
    "THM-17": r"limiting oxygen concentration",
}


def quantity_route(prompt):
    if re.search(r"\b(?:THM-\d+|define|meaning|definition|means|how (?:do|does) .{0,40} work)\b", prompt, re.I):
        return None
    if not re.search(r"\b(?:calculate|compute|estimate|predict|figure out|work out|determine|plot|chart|how (?:hot|long|much)|what (?:is|would|are)|what .{1,32} would)\b", prompt, re.I):
        return None
    if re.fullmatch(
        r"\s*what (?:is|are)\s+(?:the\s+)?(?:"
        + "|".join(QUANTITIES.values()) + r")[?.\s]*", prompt, re.I
    ):
        return None
    text = " " + normalize(prompt) + " "
    matches = [
        f"THM-{index:02}"
        for index, cues in enumerate(CUES, 1)
        if any(" " + normalize(cue) + " " in text for cue in cues.split("|"))
    ]
    precise = [mid for mid, pattern in QUANTITIES.items()
               if re.search(r"\b(?:" + pattern + r")\b", prompt, re.I)]
    matches = sorted(set(precise or matches))
    if len(matches) != 1:
        return None
    if (matches == ["THM-02"] and re.search(r"\bISS\b", prompt, re.I)
            and not re.search(r"\b(?:PSI|dataset|CSV|from the|previous|same)\b", prompt, re.I)
            and not re.search(r"\d\s*(?:K\b|kPa\b|atm\b|psi\b|%)", prompt, re.I)):
        return Route(
            intent="calculation", model_ids=matches,
            reason="THM-02 requires an explicit thermodynamic state.",
            missing=[MissingSlot(
                id="lewis_mixture_state", reason_code="required_model_state",
                question="What gas temperature, pressure and methane/oxygen/nitrogen mole fractions "
                         "should THM-02 use? For a dilution comparison, give the second mixture too.",
            )],
        )
    return Route(intent="chart" if re.search(r"\b(?:plot|chart|graph)\b", prompt, re.I)
                 else "calculation", model_ids=matches,
                 reason="Matched the requested physical quantity to its Python model.")


def route(prompt, generate=None, context=None, *, function_planner=False):
    """One bounded schema repair; a technical failure never becomes science data."""
    from .intent import interpret

    spec = interpret(prompt)
    from .nist_calorimetry import nist_window

    if nist_window(prompt) is not None:
        return Route(intent="chart", model_ids=["THM-04"], reason="Matched the named NIST burner run.")
    from .flame_temperature import flame_temperature_inputs

    if flame_temperature_inputs(prompt) is not None:
        return Route(intent="calculation", model_ids=["THM-01"],
                     reason="All flame-temperature inputs are specified.")
    if any(r.model_id == "THM-05" for r in spec.requirements):
        from .calibrated_spread import pmma_comparison_inputs

        if pmma_comparison_inputs(spec) is not None:
            return Route(intent="calculation", model_ids=["THM-05"],
                         reason="Matched the calibrated BASS-II PMMA comparison.")
    quantity = quantity_route(prompt)
    if quantity is not None:
        return quantity
    kinds = {r.kind for r in spec.requirements}
    if kinds <= {"explanation", "document", "video", "image", "inspection"} and not re.search(
        r"\b(?:how much|how many|at\s+\d+|what if)\b", prompt, re.I
    ):
        return Route(
            intent="explanation" if "explanation" in kinds else "discovery",
            reason="Matched the requested output and model from the question.",
        )
    # The shared function planner can select the model and bind inputs in one pass.
    # Keep the separate router for ambiguous prose and for the legacy workflow.
    if function_planner and "calculation" in kinds:
        ids = list(dict.fromkeys(r.model_id for r in spec.requirements if r.model_id))
        return Route(intent="chart" if "chart" in kinds else "calculation", model_ids=ids,
                     reason="Use the registered function planner to select and bind the calculation.")
    if generate is None:
        return _route_once(prompt, None, context)
    failure = None
    for _ in range(2):

        def checked(messages, failure=failure):
            if failure:
                messages = messages + [
                    {
                        "role": "user",
                        "content": "Correct the JSON schema error: " + failure,
                    }
                ]
            return generate(messages)

        try:
            return _route_once(prompt, checked, context)
        except ValueError as exc:
            failure = str(exc)[:1000]
    raise ValueError("Could not validate scientific model routing: " + failure)
