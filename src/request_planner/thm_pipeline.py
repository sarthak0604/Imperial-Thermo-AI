"""Source-grounded THM task graphs with prepared JSON and bounded execution."""

import copy
import json
import math
import re
import tempfile
from pathlib import Path

import httpx
from pydantic import AliasChoices, Field, StrictFloat, StrictStr

from imperial_thermo_ai.parser import _json_object
from imperial_thermo_ai.quantities import user_quantity_spans

from .execution import (
    ExecutionSession,
    apply_bindings,
    present_result,
    strict_json,
)
from .function_registry import (
    function_root,
    input_contract,
    model_spec,
    operation_catalog,
)
from .models import Contract, DatasetBinding, ExecutionLimits
from .operations import ScenarioTask
from .program import ProgramStep, validate_origins
from .reference_inputs import (
    fill_properties,
    is_iss_methane_lewis,
    iss_methane_state,
    reference_origin,
    scenario_origin,
)
from .reference_inputs import (
    records as property_records,
)


class SourceBinding(Contract):
    file_id: str
    binding: DatasetBinding


class ResultBinding(Contract):
    source_task_id: str = Field(
        validation_alias=AliasChoices("source_task_id", "task_id")
    )

    @property
    def task_id(self):
        return self.source_task_id

    source_pointer: str
    target_pointer: str
    unit: str


class UserBinding(Contract):
    target_pointer: str
    value: float | str
    quote: str
    unit: str | None = None


class AssumedInput(Contract):
    target_pointer: str
    value: StrictFloat | StrictStr | dict[str, StrictFloat]
    unit: str | None = None
    reason: str = Field(min_length=4, max_length=240)


class FunctionTask(Contract):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    model_id: str
    purpose: str
    scenario_id: str = "requested-scenario"
    depends_on: list[str] = Field(default_factory=list)
    template_file_id: str | None = None
    package_id: str | None = None
    params: dict = Field(default_factory=dict)
    input_source_spans: dict[str, str] = Field(default_factory=dict)
    user_inputs: list[UserBinding] = Field(default_factory=list)
    sources: list[SourceBinding] = Field(default_factory=list)
    results: list[ResultBinding] = Field(default_factory=list)
    assumptions: list[AssumedInput] = Field(default_factory=list, max_length=20)


class FunctionPlan(Contract):
    tasks: list[FunctionTask] = Field(default_factory=list, max_length=20)
    missing_inputs: list[str] = Field(default_factory=list, max_length=20)


# Scientific substitutions require explicit reviewed adapters. These are optional
# estimates, not automatic claims that equilibrium and observed temperatures agree.
RESULT_LINKS = {
    ("THM-01", "/outputs/adiabatic_flame_temp_k", "THM-07", "/params/flame_temp_k"): (
        "K",
        "Uses adiabatic equilibrium temperature as the flame-temperature estimate; heat loss may change blowoff.",
    ),
}


def order_tasks(plan):
    tasks = {t.id: t for t in plan.tasks}
    if len(tasks) != len(plan.tasks):
        raise ValueError("THM task IDs must be unique.")
    for task in plan.tasks:
        model_spec(task.model_id)
        dependencies = set(task.depends_on) | {r.task_id for r in task.results}
        if not dependencies <= tasks.keys():
            raise ValueError("Dependency refers to an unknown THM task.")
    ordered, done = [], set()
    while len(done) < len(tasks):
        ready = [
            t
            for t in plan.tasks
            if t.id not in done
            and (set(t.depends_on) | {r.task_id for r in t.results}) <= done
        ]
        if not ready:
            raise ValueError("THM dependency graph contains a cycle.")
        for task in ready:
            ordered.append(task)
            done.add(task.id)
    return ordered


def pointer(value, path):
    if not path.startswith("/"):
        raise ValueError("Expected an absolute JSON pointer.")
    for key in path[1:].split("/"):
        key = key.replace("~1", "/").replace("~0", "~")
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def set_pointer(value, path, resolved):
    parent_path, _, key = path.rpartition("/")
    parent = pointer(value, parent_path) if parent_path else value
    key = key.replace("~1", "/").replace("~0", "~")
    if isinstance(parent, list):
        parent[int(key)] = resolved
    else:
        if key not in parent:
            raise ValueError("Binding must reference an existing declared input slot.")
        parent[key] = resolved


def reviewed_function_plan(prompt):
    """Handle deliberately scoped reference examples without a provider call."""
    text = " ".join(prompt.split())
    if re.search(r"\b(?:THM-(?:0[13-9]|1\d|20)|define|definition|means)\b", text, re.IGNORECASE):
        methane = False
    else:
        methane = is_iss_methane_lewis(prompt)
    if methane:
        return FunctionPlan(tasks=[
            FunctionTask(id="methane-iss", model_id="THM-02",
                         purpose="Estimate methane Lewis number at nominal ISS conditions."),
            FunctionTask(id="methane-iss-diluted", model_id="THM-02", scenario_id="nitrogen-sensitivity",
                         purpose="Compare an illustrative nitrogen-enriched oxidizer."),
        ])
    match = re.fullmatch(
        r"(?:(?:run|calculate|test|show|try)\s+)?(THM-(?:0[1-9]|1\d|20))(?:\s+(?:example|demo))?[?.]?",
        text, re.IGNORECASE,
    )
    if match:
        model = match[1].upper()
        return FunctionPlan(tasks=[FunctionTask(
            id="bundled-example", model_id=model, package_id="example-" + model.lower(),
            purpose="Run the model's bundled worked example.",
        )])
    from .droplet_snapshot import snapshot_bindings

    bindings = snapshot_bindings(prompt)
    if bindings:
        return FunctionPlan(tasks=[FunctionTask(
            id="droplet-snapshot", model_id="THM-12", package_id="methanol_water_snapshot",
            purpose="Compare surface and ambient vapour pressures for each droplet component.",
            user_inputs=[UserBinding.model_validate(binding) for binding in bindings],
        )])
    blowoff = blowoff_function_plan(prompt)
    if blowoff:
        return blowoff
    from .reviewed_scenarios import match_scenario

    reviewed = match_scenario(prompt)
    if reviewed:
        scenario, bindings = reviewed
        if scenario.package_id is None:
            inputs = {b["target_pointer"].removeprefix("/params/"): b for b in bindings}
            return FunctionPlan(tasks=[FunctionTask(
                id="reviewed-scenario", model_id=scenario.model_id,
                purpose="Compute the requested quantity from the supplied fuel and oxidizer.",
                params={name: b["value"] for name, b in inputs.items()},
                input_source_spans={name: b["quote"] for name, b in inputs.items()},
            )])
        return FunctionPlan(tasks=[FunctionTask(
            id="reviewed-scenario", model_id=scenario.model_id, package_id=scenario.package_id,
            purpose="Run the matched scenario with the stated conditions and reviewed reference inputs.",
            user_inputs=[UserBinding.model_validate(binding) for binding in bindings],
        )])
    return None


# The demo is selected by intent. Its kinetics come from the registered
# THM-07 example while the prompt supplies any requested operating conditions.
BLOWOFF_REQUEST = re.compile(
    r"\b(?:blow[-\s]?off|damk[oö]hler number|blow (?:the |a )?flame (?:out|off)|"
    r"(?:flame|flames)\s+(?:blows? out|go(?:es)? out)|"
    r"airflow.{0,35}(?:flame extinguishes|extinguish(?:es)? (?:a |the )?flame))\b",
    re.I,
)
DEMO_REQUEST = re.compile(
    r"\b(?:demo|example|illustrative)\s+(?:kinetics|parameters|inputs|settings|values)\b"
    r"|\b(?:using|use|with)\s+(?:the\s+)?(?:bundled\s+)?(?:demo|example)\b",
    re.I,
)


def blowoff_function_plan(prompt):
    from .intent import refers_to_prior_turn

    explicit = {m.upper() for m in re.findall(r"\bTHM-\d+\b", prompt, re.I)}
    if (explicit - {"THM-07"} or not (explicit or BLOWOFF_REQUEST.search(prompt))
            or refers_to_prior_turn(prompt)
            or re.search(r"\b(?:definition|define|means|measured|dataset|experiment|csv|"
                         r"PSI-\d+|mass fraction|weight percent|by mass|wt\s*%|sweep|"
                         r"flame temperature|flame spread|limiting oxygen|and ignition)\b", prompt, re.I)):
        return None

    values, quotes, spans = {}, {}, []
    for field in ("x_o2", "pressure_kpa", "u_flow_ms", "activation_energy_j"):
        matches = user_quantity_spans(field, prompt)
        if len(matches) > 1:
            return None
        if matches:
            values[field], (start, end) = matches[0]
            quotes[field] = prompt[start:end]
            spans.append((start, end))

    remaining = prompt
    for start, end in sorted(spans, reverse=True):
        remaining = remaining[:start] + " " + remaining[end:]
    if re.search(r"\d", re.sub(r"\b(?:THM-07|O2|N2)\b", "", remaining, flags=re.I)):
        return None

    use_demo = bool(DEMO_REQUEST.search(prompt))
    if use_demo:
        if not values:
            return None
        units = {"x_o2": "1", "pressure_kpa": "kPa", "u_flow_ms": "m/s", "activation_energy_j": "J/mol"}
        return FunctionPlan(tasks=[FunctionTask(
            id="blowoff", model_id="THM-07", package_id="example-thm-07",
            purpose="Estimate the blowoff limit using the bundled demo kinetics.",
            user_inputs=[
                UserBinding(target_pointer=f"/params/{field}", value=value,
                            quote=quotes[field], unit=units[field])
                for field, value in values.items()
            ],
        )])
    if not {"x_o2", "u_flow_ms"} <= values.keys():
        return None
    return FunctionPlan(tasks=[FunctionTask(
        id="blowoff", model_id="THM-07",
        purpose="Estimate the blowoff limit and compare the requested airflow.",
        params=values, input_source_spans=quotes,
    )])


ASSUMPTION_UNITS = {
    "mole_fracs": "mol/mol", "pressure_kpa": "kPa", "temp_k": "K", "t_init_k": "K",
    "t_amb_k": "K", "flame_temp_k": "K", "t_film_k": "K", "delta_t_k": "K", "t_vap_k": "K",
    "o2_mole_frac": "1", "x_o2": "1", "y_o2_amb": "1", "y_fuel_stream": "1", "y_ox_stream": "1",
    "x_fuel_stream": "1", "x_ox_stream": "1", "gravity_g": "g", "equivalence_ratio": "1",
    "u_flow_ms": "m/s", "u_forced_ms": "m/s", "char_length_m": "m", "burner_radius_mm": "mm",
    "total_flow_rate_sccm": "sccm", "activation_energy_j": "J/mol",
    "heat_combustion_jkg": "J/kg", "heat_pyrolysis_jkg": "J/kg",
}


SCENARIO_UNIT_SUFFIXES = (
    ("_kg_s", "kg/s"), ("_m_s", "m/s"), ("_m2", "m2"), ("_m3", "m3"), ("_kpa", "kPa"),
    ("_mm", "mm"), ("_kg", "kg"), ("_pct", "%"), ("_k", "K"), ("_s", "s"), ("_m", "m"),
)


def validate_user_binding(task, user, prompt):
    if task.package_id:
        from .reviewed_scenarios import match_scenario

        reviewed = match_scenario(prompt)
        if reviewed:
            scenario, bindings = reviewed
            if (task.model_id, task.package_id) == (scenario.model_id, scenario.package_id):
                if user.model_dump() in bindings:
                    return
    if task.model_id == "THM-12" and task.package_id == "methanol_water_snapshot":
        from .droplet_snapshot import snapshot_bindings

        if user.model_dump() in snapshot_bindings(prompt):
            return
    key = user.target_pointer.rsplit("/", 1)[-1]
    expected_unit = ASSUMPTION_UNITS.get(key)
    if expected_unit and user.unit and user.unit.casefold() != expected_unit.casefold():
        raise ValueError(f"User binding {key} needs units of {expected_unit}.")
    validate_origins(
        ProgramStep(
            id=task.id,
            kind="scenario",
            scenario=ScenarioTask(
                model_id=task.model_id,
                params={key: user.value},
                input_origins={key: "user"},
            ),
            input_source_spans={key: user.quote},
        ),
        prompt,
    )


def apply_assumptions(task, payload, item):
    """Accept labelled scenario estimates while preserving retrieved and explicit values."""
    if not task.assumptions:
        return
    locked = ["/params/" + key for key in task.params]
    for p in item["provenance"]:
        path = p.get("target_pointer") or p.get("mapping", {}).get("target")
        if path:
            locked.append(path)
    locked += [binding.target_pointer for binding in task.results]
    contract = input_contract(task.model_id)
    allowed = set(contract.get("required_inputs", [])) | set(contract.get("defaults", {}))
    allowed -= {"psi_citations", "investigation_context"}
    for assumption in task.assumptions:
        path, value = assumption.target_pointer, assumption.value
        unit = assumption.unit
        if any(path == key or path.startswith(key + "/") or key.startswith(path + "/") for key in locked):
            raise ValueError("An assumption must not replace a supplied value at " + path)
        values = value.values() if isinstance(value, dict) else [value]
        if any(type(v) in (int, float) and not math.isfinite(v) for v in values):
            raise ValueError("An assumption must be finite at " + path)
        if path.startswith("/params/") and path.count("/") == 2:
            name = path.rsplit("/", 1)[-1]
            if name not in allowed or not isinstance(payload.get("params"), dict):
                raise ValueError("Unknown model assumption field " + path)
            if isinstance(value, dict) and name != "mole_fracs":
                raise ValueError("Only a gas composition may be supplied as an assumption object.")
            if name == "mole_fracs" and (
                not isinstance(value, dict) or not value or any(v < 0 or v > 1 for v in value.values())
                or not math.isclose(sum(value.values()), 1, abs_tol=1e-6)
            ):
                raise ValueError("Assumed gas mole fractions must be between 0 and 1 and sum to 1.")
            expected = ASSUMPTION_UNITS.get(name)
            if expected and unit and unit.casefold() != expected.casefold():
                raise ValueError(f"Assumed {name} needs {expected}; received {unit}.")
            if expected and not isinstance(value, str):
                unit = expected
            if payload["params"].get(name) is not None:
                raise ValueError("An assumption must not replace a sourced value at " + path)
            payload["params"][name] = value
        else:
            keys = path.split("/")
            if (not path.startswith("/request/scenario/") or type(value) not in (int, float)
                    or any(key in {"evidence", "setup_id", "materials", "id", "unit", "source_url"}
                           or key.endswith("_id") for key in keys)):
                raise ValueError("Assumptions can fill numeric scenario inputs only: " + path)
            parent_path, _, key = path.rpartition("/")
            key = key.replace("~1", "/").replace("~0", "~")
            try:
                parent = pointer(payload, parent_path)
                if not isinstance(parent, dict):
                    raise TypeError("Scenario assumptions require a named input.")
                if key not in parent:
                    example = strict_json(function_root().joinpath(model_spec(task.model_id)["example"])
                                          .read_text(encoding="utf-8-sig"))
                    if type(pointer(example, path)) not in (int, float):
                        raise TypeError("Scenario slot is not a numeric input.")
            except (KeyError, IndexError, TypeError) as exc:
                raise ValueError("No declared scenario slot for assumption " + path) from exc
            if parent.get(key) is not None:
                raise ValueError("An assumption must not replace a sourced value at " + path)
            expected = parent.get("unit") if key == "value" else next(
                (u for suffix, u in SCENARIO_UNIT_SUFFIXES if key.lower().endswith(suffix)), None
            )
            if (key == "value" and (not unit or not expected)) or (
                    expected and unit and unit.casefold() != expected.casefold()
            ):
                raise ValueError("Assumed quantity must match the declared units at " + path)
            unit = expected or unit
            parent[key] = value
        locked.append(path)
        item["provenance"].append(scenario_origin(
            path, value, unit,
            f"AI assumption for {path}: {json.dumps(value)}{(' ' + unit) if unit else ''}. "
            + assumption.reason.strip(),
        ))


def propose_functions(
    prompt, files, generate, selected_models=(), packages=(), inspection=()
):
    from .planner import _local_catalog

    expanded = set(selected_models)
    for source, _, target, _ in RESULT_LINKS:
        if target in expanded:
            expanded.add(source)
    catalogue = _local_catalog(
        prompt + " " + " ".join(sorted(expanded)), operation_catalog()
    )
    messages = [
        {
            "role": "system",
            "content": "Select THM functions that answer the user and necessary prerequisites. Return JSON matching "
            + json.dumps(FunctionPlan.model_json_schema())
            + " Every task needs a scientific purpose tied to the question. Never run all functions by default. "
            "Legacy params contain ONLY explicit user inputs, with exact input_source_spans quoting their values. "
            "For unspecified scenario inputs prefer supplied sources, compatible library properties and solver defaults. "
            "For remaining gaps use task.assumptions: [{target_pointer,value,unit,reason}]. Choose physically "
            "plausible values in model units and describe why. Assumptions are forecasts for illustrative "
            "scenarios and must never provide measurements, calibrations, sample identity or user quotes. "
            "When missing a calibration, a bundled package can provide an explicitly illustrative baseline "
            "for a compatible question. Match requested material, test setup and phase. Preserve explicit "
            "user conditions. If the user requests measured results for a specific experiment and its data "
            "are unavailable, say what is needed. Do not quietly substitute an unrelated example. "
            "For CSV/result bindings, create a numeric placeholder in params and omit its source span; the executor fills it. "
            "For evidence-dependent functions choose a supplied compatible downloaded JSON template or approved package. "
            "Never generate an evidence section. Select a listed package ID to use its reviewed baseline. Sources map exact verified CSV headers/units "
            "through DatasetBinding. Do not combine incompatible investigations or unverified runs. "
            "Only use supplied registered result links; declare dependencies. Keep the same scenario_id for linked tasks. "
            "Do not set params when using a sourced template/package; use user_inputs with exact quotes and matching units for scenario changes. "
            "If facts/calibration are unavailable, list precise missing_inputs and retain independent supported tasks. "
            "Do not substitute another function for the explicitly requested one. "
            "A template/package scenario must match the user request; if it differs and no safe binding exists, ask for input.",
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "question": prompt,
                    "selected_models": list(selected_models),
                    "files": [
                        f.model_dump(
                            mode="json", exclude_none=True, exclude={"retrieval_url", "source_page_url"}
                        )
                        for f in files
                    ],
                    "models": catalogue,
                    "packages": list(packages),
                    "inspection": list(inspection),
                    "result_links": [
                        {
                            "source_model": k[0],
                            "source_pointer": k[1],
                            "target_model": k[2],
                            "target_pointer": k[3],
                            "unit": v[0],
                            "assumption": v[1],
                        }
                        for k, v in RESULT_LINKS.items()
                    ],
                }
            ),
        },
    ]
    messages[0]["content"] += (
        " Put result bindings INSIDE the downstream task.results list, never at plan level or in user_inputs. "
        "For example a downstream task has params={u_flow_ms:0.15,x_o2:0.21,flame_temp_k:0}, "
        "results=[{source_task_id:temperature,source_pointer:/outputs/adiabatic_flame_temp_k,"
        "target_pointer:/params/flame_temp_k,unit:K}], "
        "input_source_spans={u_flow_ms:<exact flow quote>,x_o2:<exact oxygen quote>}. "
        "Keep built-in diluent_gas, equivalence_ratio and other supported defaults omitted unless the user specifies them; "
        "omit them and let the actual solver apply its documented defaults, which will be disclosed. "
        "user_inputs is ONLY for literal user-provided scalar changes to a sourced template, "
        "not for placeholders or calculated upstream values. For pressure, oxygen mole fraction, "
        "airflow and activation energy, convert recognized prompt units to the stated solver units. "
        "Keep the original amount and units in the exact quote. Missing input messages must be natural-language "
        "questions, not JSON pointers. A registered dependency value is not a missing user input."
    )
    if not selected_models or len(expanded) > len(selected_models) or len(selected_models) > 1:
        messages[0]["content"] += (
            " results are INPUT LINKS ENTERING the task that owns them. source_task_id is the upstream producer. For THM-01 -> THM-07 the THM-01 task has results=[] and only THM-07 has the result link. Never ask the user to resolve a graph error invented by your plan. Correct it using the registered link direction. Example structure: "
            + json.dumps(
                {
                    "tasks": [
                        {
                            "id": "temperature",
                            "model_id": "THM-01",
                            "purpose": "Compute temperature",
                            "params": {
                                "fuel_species": "CH4",
                                "o2_mole_frac": 0.21,
                                "pressure_kpa": 101.325,
                            },
                            "input_source_spans": {
                                "fuel_species": "CH4",
                                "o2_mole_frac": "oxygen 0.21",
                                "pressure_kpa": "pressure 101.325",
                            },
                            "results": [],
                        },
                        {
                            "id": "blowoff",
                            "model_id": "THM-07",
                            "purpose": "Use upstream temperature",
                            "params": {"u_flow_ms": 0.15, "x_o2": 0.21, "flame_temp_k": 0},
                            "input_source_spans": {
                                "u_flow_ms": "flow 0.15",
                                "x_o2": "oxygen 0.21",
                            },
                            "results": [
                                {
                                    "source_task_id": "temperature",
                                    "source_pointer": "/outputs/adiabatic_flame_temp_k",
                                    "target_pointer": "/params/flame_temp_k",
                                    "unit": "K",
                                }
                            ],
                        },
                    ]
                }
            )
            + " This is a structure example only: copy actual values and spans from the current question."
        )
    for attempt in range(3):
        raw = generate(messages)
        try:
            plan = FunctionPlan.model_validate(_json_object(raw))
            by_id = {t.id: t for t in plan.tasks}
            for target in plan.tasks:
                for link in target.results:
                    if link.source_task_id not in by_id:
                        raise ValueError(
                            "Unknown source_task_id " + link.source_task_id
                        )
                    key = (
                        by_id[link.source_task_id].model_id,
                        link.source_pointer,
                        target.model_id,
                        link.target_pointer,
                    )
                    if key not in RESULT_LINKS:
                        raise ValueError(
                            "Backwards or unregistered result link on task "
                            + target.id
                            + ". Result links belong inside the DOWNSTREAM consumer task, and source_task_id must identify the UPSTREAM producer. Use the supplied registered direction."
                        )
            order_tasks(plan)
            for task in plan.tasks:
                result_targets = {b.target_pointer for b in task.results}
                for user in task.user_inputs:
                    if user.target_pointer in result_targets:
                        raise ValueError(
                            "Remove user_inputs for "
                            + user.target_pointer
                            + "; it is filled by task.results, not a user quote. Put a zero placeholder in params instead."
                        )
                    validate_user_binding(task, user, prompt)
                if not task.template_file_id and not task.package_id:
                    for binding in task.results:
                        try:
                            pointer({"params": task.params}, binding.target_pointer)
                        except KeyError as exc:
                            raise ValueError(
                                "Add a numeric zero placeholder at "
                                + binding.target_pointer
                                + " inside params; the registered result binding replaces it before execution."
                            ) from exc
                if (
                    not task.template_file_id
                    and not task.package_id
                    and not model_spec(task.model_id)["requires_evidence"]
                ):
                    bound = {b.target_pointer for b in task.results} | {
                        b.binding.target for b in task.sources
                    }
                    explicit = {
                        k: v
                        for k, v in task.params.items()
                        if "/params/" + k not in bound
                    }
                    validate_origins(
                        ProgramStep(
                            id=task.id,
                            kind="scenario",
                            scenario=ScenarioTask(
                                model_id=task.model_id,
                                params=explicit,
                                input_origins=dict.fromkeys(explicit, "user"),
                            ),
                            input_source_spans=task.input_source_spans,
                        ),
                        prompt,
                    )
            return plan
        except (ValueError, TypeError) as exc:
            if attempt == 2:
                raise
            messages += [
                {"role": "assistant", "content": raw},
                {
                    "role": "user",
                    "content": "Repair the plan without inventing scientific data: "
                    + str(exc)[:1200],
                },
            ]


def execute_functions(
    plan,
    prompt,
    files,
    *,
    limits=None,
    client=None,
    url_validator=None,
    trusted_source_hashes=None,
    package_registry=None,
):
    """Prepare independent JSONs first, then finalize dependent JSONs in topological order."""
    plan = FunctionPlan.model_validate(plan)
    ordered = order_tasks(plan)
    records = {f.file_id: f for f in files}
    tasks = {t.id: t for t in plan.tasks}
    blocks, trace, outputs, prepared, failed = [], [], {}, {}, set()
    package_sources = {}
    options = {"url_validator": url_validator} if url_validator else {}
    with tempfile.TemporaryDirectory(prefix="thermo-functions-") as directory:
        session = ExecutionSession(
            directory,
            limits or ExecutionLimits(),
            client=client,
            trusted_source_hashes=trusted_source_hashes,
            **options,
        )
        for task in ordered:
            item = {
                "task_id": task.id,
                "model_id": task.model_id,
                "purpose": task.purpose,
                "depends_on": sorted(
                    set(task.depends_on) | {b.task_id for b in task.results}
                ),
                "status": "prepared",
                "input_json": None,
                "output_json": None,
                "provenance": [],
            }
            trace.append(item)
            try:
                spec = model_spec(task.model_id)
                if task.template_file_id and task.package_id:
                    raise ValueError("Select a single evidence template or package.")
                if task.template_file_id:
                    file = records[task.template_file_id]
                    if file.media_type != "application/json":
                        raise ValueError(
                            "THM template must be a JSON measurement resource."
                        )
                    payload = strict_json(
                        session.fetch(file).read_text(
                            encoding=file.encoding or "utf-8-sig"
                        )
                    )
                    payload = copy.deepcopy(payload.get("example_request", payload))
                    item["provenance"].append(
                        {
                            "kind": "nasa_json",
                            "file_id": file.file_id,
                            "sha256": session.sources[file.file_id]["sha256"],
                        }
                    )
                elif task.package_id:
                    if package_registry is None:
                        raise ValueError(
                            "No approved evidence package registry configured."
                        )
                    package, payload = package_registry.load(
                        task.package_id, task.model_id
                    )
                    payload = copy.deepcopy(payload)
                    item["provenance"].append(
                        {
                            "kind": "evidence_package",
                            "id": package.id,
                            "sha256": package.sha256,
                            "sources": package.provenance,
                            "illustrative": package.illustrative,
                            "notes": package.notes,
                            "bundled": package.bundled,
                            "investigation_id": package.investigation_id,
                        }
                    )
                else:
                    if spec["requires_evidence"]:
                        raise ValueError(
                            task.model_id
                            + " needs compatible sourced evidence; supply a calibration/package."
                        )
                    bound = {b.target_pointer for b in task.results} | {
                        s.binding.target for s in task.sources
                    }
                    explicit = {
                        k: v
                        for k, v in task.params.items()
                        if "/params/" + k not in bound
                    }
                    validate_origins(
                        ProgramStep(
                            id=task.id,
                            kind="scenario",
                            scenario=ScenarioTask(
                                model_id=task.model_id,
                                params=explicit,
                                input_origins=dict.fromkeys(explicit, "user"),
                            ),
                            input_source_spans=task.input_source_spans,
                        ),
                        prompt,
                    )
                    payload = {"params": copy.deepcopy(task.params)}
                    item["provenance"] += [
                        {
                            "kind": "user",
                            "parameter": k,
                            "quote": task.input_source_spans[k],
                        }
                        for k in explicit
                    ]
                if (task.template_file_id or task.package_id) and task.params:
                    raise ValueError(
                        "Evidence requests accept verified bindings, not generated payload overrides."
                    )
                if (
                    payload.get("model_id", task.model_id) != task.model_id
                    or payload.get("function_id", task.model_id) != task.model_id
                ):
                    raise ValueError("Source payload identifies a different THM model.")
                if spec["requires_evidence"] and not isinstance(
                    payload.get("evidence"), dict
                ):
                    raise ValueError("Sourced calibration evidence is absent.")
                for user in task.user_inputs:
                    if not user.target_pointer.startswith(
                        ("/params/", "/request/scenario/")
                    ) or any(
                        key in user.target_pointer.split("/")
                        for key in (
                            "evidence",
                            "setup_id",
                            "materials",
                            "id",
                            "unit",
                            "source_url",
                        )
                    ):
                        raise ValueError(
                            "User bindings may modify scenario quantities, not source identity or evidence."
                        )
                    validate_user_binding(task, user, prompt)
                    existing = pointer(payload, user.target_pointer)
                    if type(existing) not in (str, int, float):
                        raise ValueError(
                            "User bindings require a scalar scientific input slot."
                        )
                    if user.target_pointer.endswith("/value"):
                        parent = pointer(payload, user.target_pointer.rsplit("/", 1)[0])
                        if not user.unit or parent.get("unit") != user.unit:
                            raise ValueError(
                                "User quantity and sourced input must have identical verified units."
                            )
                    set_pointer(payload, user.target_pointer, user.value)
                    item["provenance"].append({"kind": "user", **user.model_dump()})
                scalar_rows = {
                    s.binding.row for s in task.sources if s.binding.mode == "scalar"
                }
                if len(scalar_rows) > 1:
                    raise ValueError(
                        "A scenario cannot mix scalar values from different measurement rows."
                    )
                source_records = [records[s.file_id] for s in task.sources]
                if len({f.file_id for f in source_records}) > 1:
                    first = source_records[0]
                    if not first.run_ids or any(
                        f.investigation_id != first.investigation_id
                        or set(f.run_ids) != set(first.run_ids)
                        for f in source_records
                    ):
                        raise ValueError(
                            "Multiple input files need matching verified investigation/run identity."
                        )
                for source in task.sources:
                    file = records[source.file_id]
                    if file.media_type != "text/csv" or file.role != "measurement":
                        raise ValueError(
                            "CSV bindings require an inspected measurement file."
                        )
                    if task.template_file_id:
                        template = records[task.template_file_id]
                        if (
                            template.investigation_id != file.investigation_id
                            or not file.run_ids
                            or set(file.run_ids) != set(template.run_ids)
                        ):
                            raise ValueError(
                                "Template and CSV need identical verified investigation/run identity."
                            )
                    if task.package_id:
                        raise ValueError(
                            "Package-to-CSV run mapping requires a registered source adapter."
                        )
                    apply_bindings(payload, session.fetch(file), file, [source.binding])
                    item["provenance"].append(
                        {
                            "kind": "nasa_csv",
                            "file_id": file.file_id,
                            "sha256": session.sources[file.file_id]["sha256"],
                            "mapping": source.binding.model_dump(),
                        }
                    )
                if (task.model_id == "THM-02" and not task.template_file_id and not task.package_id
                        and not task.sources and not task.user_inputs and not task.assumptions
                        and not task.params and is_iss_methane_lewis(prompt)):
                    iss_methane_state(payload, item["provenance"], diluted=task.id == "methane-iss-diluted")
                apply_assumptions(task, payload, item)
                if spec["requires_evidence"]:
                    fill_properties(task.model_id, payload, item["provenance"])
                    if task.package_id and package.bundled:
                        bindings = payload["evidence"].get("provenance", {}).get("property_bindings", {})
                        for path, binding in bindings.items():
                            record = property_records().get(binding.get("property_record_id"))
                            if record:
                                origin = reference_origin(record, path, pointer(payload, path))
                                if origin not in item["provenance"]:
                                    item["provenance"].append(origin)
                for binding in task.results:
                    upstream = tasks[binding.task_id]
                    key = (
                        upstream.model_id,
                        binding.source_pointer,
                        task.model_id,
                        binding.target_pointer,
                    )
                    contract = RESULT_LINKS.get(key)
                    if (
                        not contract
                        or contract[0] != binding.unit
                        or upstream.scenario_id != task.scenario_id
                    ):
                        raise ValueError(
                            "Unregistered or incompatible THM output/input dependency."
                        )
                    pointer(payload, binding.target_pointer)
                prepared[task.id] = payload
                item["input_json"] = copy.deepcopy(payload)
                # Materialize every base input before executing any solver.
                Path(directory, task.id + ".input.json").write_text(
                    json.dumps(payload, allow_nan=False)
                )
            except httpx.HTTPError:
                item.update(
                    status="error",
                    message="Source transfer failed; check NASA source availability.",
                )
                failed.add(task.id)
            except (ValueError, KeyError, TypeError, OSError) as exc:
                item.update(status="needs_input", message=str(exc))
                failed.add(task.id)
        output_bytes = 0
        for task, item in zip(ordered, trace):
            if task.id in failed:
                continue
            dependencies = set(task.depends_on) | {b.task_id for b in task.results}
            if dependencies & failed:
                item.update(
                    status="blocked",
                    message="A prerequisite function did not produce a valid result.",
                )
                failed.add(task.id)
                continue
            try:
                payload = prepared[task.id]
                for binding in task.results:
                    value = pointer(outputs[binding.task_id], binding.source_pointer)
                    if type(value) not in (float, int) or not math.isfinite(value):
                        raise ValueError(
                            "Dependent scientific value must be finite and numeric."
                        )
                    set_pointer(payload, binding.target_pointer, value)
                    item["provenance"].append(
                        {
                            "kind": "computed_result",
                            **binding.model_dump(),
                            "assumption": RESULT_LINKS[
                                (
                                    tasks[binding.task_id].model_id,
                                    binding.source_pointer,
                                    task.model_id,
                                    binding.target_pointer,
                                )
                            ][1],
                        }
                    )
                path = Path(directory, task.id + ".input.json")
                path.write_text(json.dumps(payload, allow_nan=False))
                item["input_json"] = json.loads(path.read_text())
                for binding in task.results:
                    upstream_payload = prepared[binding.task_id].get("params", {})
                    downstream_payload = payload.get("params", {})
                    source_defaults = input_contract(
                        tasks[binding.task_id].model_id
                    ).get("defaults", {})
                    target_defaults = input_contract(task.model_id).get("defaults", {})
                    for source_key, target_key in (
                        ("pressure_kpa", "pressure_kpa"),
                        ("o2_mole_frac", "x_o2"),
                        ("t_init_k", "t_amb_k"),
                    ):
                        a = upstream_payload.get(
                            source_key, source_defaults.get(source_key)
                        )
                        b = downstream_payload.get(
                            target_key, target_defaults.get(target_key)
                        )
                        if a is not None and b is not None and a != b:
                            raise ValueError(
                                "Dependent THM scenarios have conflicting " + source_key
                            )
                result = session.calculate(task.model_id, item["input_json"])
                encoded_output = json.dumps(result, allow_nan=False)
                output_bytes += len(encoded_output.encode("utf-8"))
                if output_bytes > 10_000_000:
                    raise ValueError(
                        "The selected output JSONs exceed the dashboard response budget; narrow the request."
                    )
                Path(directory, task.id + ".output.json").write_text(encoded_output)
                outputs[task.id] = result
                item.update(status="completed", output_json=result)
                produced = present_result(task.model_id, result)
                source_ids = [
                    p["file_id"] for p in item["provenance"] if "file_id" in p
                ]
                baseline = next((p for p in item["provenance"]
                                 if p["kind"] == "evidence_package" and p.get("bundled")), None)
                if baseline:
                    for index, source in enumerate(result.get("sources") or baseline["sources"]):
                        if not isinstance(source, dict) or not str(source.get("url", "")).startswith("https://"):
                            continue
                        source_id = f"{baseline['id']}-{index + 1}"
                        package_sources[source_id] = {
                            "file_id": source_id, "investigation_id": baseline.get("investigation_id"),
                            "title": source.get("locator") or baseline["id"],
                            "source_page_url": source["url"],
                        }
                        source_ids.append(source_id)
                for dependency in task.results:
                    prior = next(t for t in trace if t["task_id"] == dependency.task_id)
                    source_ids += [
                        p["file_id"] for p in prior["provenance"] if p.get("file_id")
                    ]
                source_ids = list(dict.fromkeys(source_ids))
                defaults = input_contract(task.model_id).get("defaults", {})
                item["model_defaults"] = {k: v for k, v in defaults.items() if k not in payload.get("params", {})}
                for block in produced:
                    block["source_file_ids"] = source_ids
                    if any(p.get("illustrative") for p in item["provenance"]):
                        block["illustrative"] = True
                    if block["type"] == "calculation":
                        block.update(
                            task_id=task.id,
                            input_json=item["input_json"],
                            input_provenance=item["provenance"],
                            depends_on=item["depends_on"],
                            model_defaults=item["model_defaults"],
                        )
                blocks.extend(produced)
            except (ValueError, KeyError, TypeError, OSError) as exc:
                item.update(status="needs_input", message=str(exc))
                failed.add(task.id)
    return blocks, [*session.sources.values(), *package_sources.values()], trace


def _answer_functions(
    spec,
    graph,
    bundle,
    generate,
    *,
    answer_generator=None,
    selected_models=(),
    limits=None,
    client=None,
    url_validator=None,
    package_registry=None,
    deadline=None,
    reviewed_plan=None,
):
    import uuid

    from .backend_models import AnswerResult
    from .composition import compose_results
    from .intent import fulfilment, summarize_result
    from .models import FrontendResponse

    packages = []
    if package_registry:
        packages = [
            p.model_dump(exclude={"payload_path"})
            for p in package_registry.packages
            if p.review_status == "approved" and model_spec(p.model_id)["requires_evidence"]
            and (not selected_models or p.model_id in selected_models)
        ]
    plan = reviewed_plan if reviewed_plan is not None else propose_functions(
        spec.original_prompt, bundle.files, generate, selected_models, packages
    )
    if selected_models and not set(selected_models) <= {t.model_id for t in plan.tasks}:
        plan.missing_inputs.append(
            "Not all requested models have valid input tasks: "
            + ", ".join(sorted(set(selected_models) - {t.model_id for t in plan.tasks}))
        )
    if selected_models:
        by_id = {t.id: t for t in plan.tasks}
        needed = {t.id for t in plan.tasks if t.model_id in selected_models}
        frontier = list(needed)
        while frontier:
            task = by_id[frontier.pop()]
            for dep in set(task.depends_on) | {b.task_id for b in task.results}:
                if dep not in needed:
                    needed.add(dep)
                    frontier.append(dep)
        if any(t.id not in needed for t in plan.tasks):
            raise ValueError(
                "The function plan includes models unrelated to selected outputs or prerequisites."
            )
    # File records reaching the generator already have inspected column metadata
    # where available. Unverified columns are rejected by apply_bindings.
    if deadline is not None:
        import time

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError(
                "Request deadline exceeded while preparing the function plan."
            )
        configured = limits or ExecutionLimits()
        limits = ExecutionLimits(
            max_runtime_seconds=max(
                1, min(configured.max_runtime_seconds, int(remaining))
            ),
            max_download_bytes=configured.max_download_bytes,
        )
    blocks, sources, trace = execute_functions(
        plan,
        spec.original_prompt,
        bundle.files,
        limits=limits,
        client=client,
        url_validator=url_validator,
        trusted_source_hashes=bundle.trusted_source_hashes,
        package_registry=package_registry,
    )
    if reviewed_plan and {t.id for t in reviewed_plan.tasks} == {"methane-iss", "methane-iss-diluted"}:
        comparison = [b for b in blocks if b["type"] == "calculation"]
        if len(comparison) == 2:
            from .reference_inputs import ISS_METHANE_DILUTION

            blocks = comparison + [{
                "type": "chart", "chart_type": "bar", "title": "THM-02 nitrogen-dilution comparison",
                "categories": ["Nominal ISS oxidizer", f"{ISS_METHANE_DILUTION:.0%} oxygen in nitrogen"],
                "x": {"label": "Oxidizer condition", "unit": None, "values": [0, 1]},
                "series": [{"label": "Lewis number", "unit": None,
                            "values": [b["data"]["dimensionless_numbers"]["lewis_number"] for b in comparison]}],
                "evidence_type": "model_estimate", "illustrative": True, "source_file_ids": [],
            }]
    bundle.diagnostics.append({"function_pipeline": trace})
    warnings = plan.missing_inputs + [
        t["message"] for t in trace if t["status"] != "completed"
    ]
    warnings += [
        "Model defaults: " + json.dumps(t["model_defaults"])
        for t in trace
        if t.get("model_defaults")
    ]
    warnings += [
        p["assumption"] for t in trace for p in t["provenance"] if p.get("assumption")
    ]
    warnings += [
        p.get("notes") or f"{t['model_id']} used an illustrative baseline."
        for t in trace for p in t["provenance"]
        if p["kind"] == "evidence_package" and (p.get("notes") or p["illustrative"])
    ]
    response = FrontendResponse(
        query_id=bundle.query_id,
        status="completed" if blocks else "needs_input",
        message="",
        blocks=blocks,
        sources=sources,
        warnings=warnings,
    )
    claims = []
    if blocks and answer_generator:
        try:
            claims = compose_results(spec.original_prompt, blocks, answer_generator)
        except ValueError:
            warnings.append(
                "The explanation could not be verified; executed results are shown."
            )
    rows = fulfilment(spec, response, claims=claims, files=bundle.files)
    selected_investigations = {s.get("investigation_id") for s in sources}
    for inv in spec.investigations:
        rows.append(
            {
                "id": "group-" + inv,
                "kind": "investigation",
                "satisfied": inv in selected_investigations,
                "missing": None
                if inv in selected_investigations
                else "No executed input comes from requested investigation " + inv,
            }
        )
    status = (
        "completed"
        if blocks
        and not plan.missing_inputs
        and all(t["status"] == "completed" for t in trace)
        and all(r["satisfied"] for r in rows)
        else "partial"
        if blocks
        else "needs_input"
    )
    message = "\n\n".join(c["text"] for c in claims) or summarize_result(response)
    if warnings:
        message += "\n\n" + " ".join(
            plan.missing_inputs
            + [t["message"] for t in trace if t["status"] != "completed"]
        )
    if not message.strip():
        message = "The selected functions need additional scientific inputs before they can run."
    spec.clarifications.extend(
        plan.missing_inputs
        + [t["message"] for t in trace if t["status"] != "completed"]
    )
    return AnswerResult(
        trace_id=uuid.uuid4().hex,
        status=status,
        message=message.strip(),
        request=spec,
        retrieval=bundle,
        result=response,
        fulfilment=rows,
        claims=claims,
    )


def answer_functions(spec, graph, bundle, generate, **options):
    import uuid

    from .backend_models import AnswerResult
    from .intent import fulfilment
    from .model_worker import InferenceError
    from .models import FrontendResponse

    try:
        return _answer_functions(spec, graph, bundle, generate, **options)
    except (ValueError, TypeError, KeyError) as exc:
        if isinstance(exc, InferenceError):
            raise
        response = FrontendResponse(
            query_id=bundle.query_id,
            status="error",
            message="The scientific function plan could not be validated.",
            errors=[{"code": "invalid_function_plan", "message": str(exc)[:500]}],
        )
        return AnswerResult(
            trace_id=uuid.uuid4().hex,
            status="error",
            message=response.message,
            request=spec,
            retrieval=bundle,
            result=response,
            fulfilment=fulfilment(spec, response),
        )
