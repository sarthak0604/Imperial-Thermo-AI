"""Semantic task routing before retrieval; IDs and origins are validated locally."""

import json
import re
from functools import lru_cache

from pydantic import Field

from imperial_thermo_ai.parser import _json_object

from .function_registry import model_spec
from .models import Contract

# Discovery vocabulary; scientific validity is checked by the function validator.
CUES = [
    "adiabatic flame temperature|equilibrium products",
    "lewis number|thermal diffusivity|mass diffusivity",
    "stoichiometric mixture fraction|flame sheet radius",
    "heat release|oxygen consumption",
    "opposed flow|against airflow|against the airflow",
    "concurrent flow|with the airflow",
    "blowoff|blow off|damkohler",
    "richardson|buoyancy|mixed convection",
    "spalding|b number|gasification",
    "droplet regression|burning constant|squared diameter",
    "two stage|cool flame transition",
    "multicomponent evaporation|preferential evaporation",
    "radiative quenching",
    "radiative heat fraction|radiative fraction",
    "soot inception",
    "time to ignition|solid heating|thermal penetration",
    "limiting oxygen|flammability limit",
    "suppression heat|suppressant|water mist",
    "cabin pressure|closed cabin",
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
        result.append(
            dict(model_spec(mid), cues=CUES[i].split("|"), input_contract=contract)
        )
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
                    "Select relevant models even if evidence is missing. Ask at most three essential, user-answerable "
                    "questions with stable missing slot IDs, units and choices. Do not invent inputs or calibration. "
                    "Do not ask what a THM ID means. Explicit IDs constrain calculation selection. "
                    "Use context only to resolve follow-ups; never treat prior generated prose as measured inputs.",
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "question": prompt,
                            "context": context or {},
                            "capabilities": capabilities(),
                        }
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


def route(prompt, generate=None, context=None):
    """One bounded schema repair; a technical failure never becomes science data."""
    from .intent import interpret

    spec = interpret(prompt)
    if any(r.model_id == "THM-05" for r in spec.requirements):
        from .calibrated_spread import pmma_comparison_inputs

        if pmma_comparison_inputs(spec) is not None:
            return Route(intent="calculation", model_ids=["THM-05"],
                         reason="Matched the calibrated BASS-II PMMA comparison.")
    kinds = {r.kind for r in spec.requirements}
    if kinds <= {"explanation", "document", "video", "image", "inspection"} and not re.search(
        r"\b(?:how much|how many|at\s+\d+|what if)\b", prompt, re.I
    ):
        return Route(
            intent="explanation" if "explanation" in kinds else "discovery",
            reason="Matched the requested output and model from the question.",
        )
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
