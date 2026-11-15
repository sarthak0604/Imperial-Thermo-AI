"""Bounded multi-operation programs for explicit scenarios and selected data tables."""

import json
import math
import re
import tempfile
from typing import Literal

from pydantic import Field

from imperial_thermo_ai.parser import _json_object

from .models import Contract, ExecutionLimits
from .operations import ScenarioTask, TableTask, table


class ProgramStep(Contract):
    id: str
    depends_on: list[str] = Field(default_factory=list)
    kind: Literal["scenario", "table"]
    scenario: ScenarioTask | None = None
    table: TableTask | None = None
    input_source_spans: dict[str, str] = Field(default_factory=dict)


class Program(Contract):
    steps: list[ProgramStep] = Field(max_length=8)
    missing_inputs: list[str] = Field(default_factory=list)


def propose(prompt, files, generate):
    from .function_registry import operation_catalog
    from .planner import _local_catalog

    messages = [
        {
            "role": "system",
            "content": "Plan a bounded scientific data program. Return JSON matching the schema. "
            "Use only exact supplied file IDs, column headers and verified quantity meanings. "
            "Do not invent evidence or calibration. For parameter-only legacy scenarios, copy only explicit user inputs. "
            "Every parameter needs an input_source_spans entry keyed by the parameter name quoting the prompt, "
            "including its exact value. Copy the shortest exact phrase containing the value directly from the question. input_origins values are the literal string user, NOT a source quote. "
            "For example scenario={model_id:THM-03, params:{fuel_formula:CH4,y_fuel_stream:1,y_ox_stream:0.232}, "
            "input_origins:{fuel_formula:user,y_fuel_stream:user,y_ox_stream:user}}; "
            "input_source_spans={fuel_formula:CH4,y_fuel_stream:fuel mass fraction 1,y_ox_stream:oxygen mass fraction 0.232}. "
            "Defaults are forbidden unless explicitly permitted by the user. "
            "Do not substitute an unrelated table. For filtered plots select the exact columns and row predicates, "
            "and keep missing=reject unless the user explicitly permits omissions. Do not join files. "
            "Use aggregate=none for raw plots. If no supported operation is possible, return steps=[] with missing_inputs. "
            "A scenario step has scenario filled and table=null; a table step has table filled and scenario=null. "
            "All other nonapplicable fields should be empty. Schema: "
            + json.dumps(Program.model_json_schema()),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "question": prompt,
                    "files": [
                        f.model_dump(mode="json", exclude_none=True,
                                     exclude={"retrieval_url", "source_page_url"})
                        for f in files
                    ],
                    "models": _local_catalog(prompt, operation_catalog()),
                }, separators=(",", ":")
            ),
        },
    ]
    for attempt in range(2):
        raw = generate(messages)
        try:
            candidate = Program.model_validate(_json_object(raw))
            for step in candidate.steps:
                if step.kind == "scenario":
                    validate_origins(step, prompt)
            return candidate
        except (ValueError, TypeError) as exc:
            if attempt:
                raise
            words = list(re.finditer(r"\S+", prompt))
            choices = list(dict.fromkeys(
                prompt[first.start():last.end()]
                for size in range(1, 6)
                for first, last in zip(words, words[size - 1:])
            ))
            context = json.loads(messages[1]["content"])
            context["exact_source_span_choices"] = choices
            messages[1]["content"] = json.dumps(context, separators=(",", ":"))
            messages.extend(
                [
                    {"role": "assistant", "content": raw},
                    {
                        "role": "user",
                        "content": "Return the complete corrected program JSON. Fix this validation error without inventing inputs: "
                        + str(exc)[:1600],
                    },
                ]
            )


def _scalars(value):
    if isinstance(value, dict):
        for v in value.values():
            yield from _scalars(v)
    elif isinstance(value, list):
        for v in value:
            yield from _scalars(v)
    else:
        yield value


def validate_origins(step, prompt):
    task = step.scenario
    if task is None or step.table is not None:
        raise ValueError("Scenario step must contain exactly one scenario task.")
    if task.allowed_defaults:
        raise ValueError(
            "Generated programs cannot invent permitted defaults; use the explicit typed scenario API."
        )
    from imperial_thermo_ai.quantities import user_quantity_spans

    for key, value in task.params.items():
        span = step.input_source_spans.get(key, "")
        if (
            not span
            or span.casefold() not in prompt.casefold()
            or task.input_origins.get(key) != "user"
        ):
            raise ValueError(
                f"input_source_spans[{key!r}]={span!r} is not an exact user quote or its origin is not user. "
                "Copy a literal substring from the question, without adding labels. "
                f"The actual user question is: {prompt}"
            )
        for scalar in _scalars(value):
            if isinstance(scalar, bool) or scalar is None:
                raise ValueError(
                    "Generated scenario inputs require explicit scientific values."
                )
            if isinstance(scalar, (int, float)):
                quantities = user_quantity_spans(key, span)
                nums = [number for number, _ in quantities] or [
                    float(n)
                    for n in re.findall(
                        r"(?<![\w.+-])[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?", span
                    )
                ]
                if not math.isfinite(scalar) or not any(
                    math.isclose(scalar, n, rel_tol=1e-12) for n in nums
                ):
                    raise ValueError(
                        "Scenario value differs from the quoted user value. Use explicit registered conversions."
                    )
            elif str(scalar).casefold() not in span.casefold():
                raise ValueError(
                    "Scenario species/material differs from the quoted user value."
                )


def execute(program, prompt, files, *, limits=None, client=None, url_validator=None):
    from .execution import ExecutionSession, present_result
    from .function_registry import model_spec

    program = Program.model_validate(program)
    if len({step.id for step in program.steps}) != len(program.steps):
        raise ValueError("Program step IDs must be unique.")
    records = {f.file_id: f for f in files}
    blocks, done, trace = [], set(), []
    options = {"url_validator": url_validator} if url_validator else {}
    with tempfile.TemporaryDirectory(prefix="thermo-program-") as directory:
        session = ExecutionSession(
            directory, limits or ExecutionLimits(), client=client, **options
        )
        for step in program.steps:
            session.remaining()
            if not set(step.depends_on).issubset(done):
                raise ValueError(
                    "Program dependencies must reference earlier completed steps."
                )
            if step.kind == "scenario":
                validate_origins(step, prompt)
                if model_spec(step.scenario.model_id)["requires_evidence"]:
                    raise ValueError(
                        "Scenario-only execution cannot supply missing model evidence."
                    )
                result = session.calculate(
                    step.scenario.model_id, {"params": step.scenario.params}
                )
                produced = present_result(step.scenario.model_id, result)
                for block in produced:
                    block["source_file_ids"] = []
                blocks.extend(produced)
                from .function_registry import input_contract

                contract = input_contract(step.scenario.model_id)
                trace.append(
                    {
                        "step_id": step.id,
                        "inputs": step.scenario.params,
                        "origins": step.scenario.input_origins,
                        "model_defaults": {
                            k: v
                            for k, v in contract.get("defaults", {}).items()
                            if k not in step.scenario.params
                        },
                    }
                )
            else:
                if (
                    step.table is None
                    or step.scenario is not None
                    or step.table.file_id not in records
                ):
                    raise ValueError(
                        "Table step requires exactly one known source file."
                    )
                file = records[step.table.file_id]
                if file.media_type != "text/csv" or file.role != "measurement":
                    raise ValueError("Table operations require a measurement CSV.")
                if step.table.missing != "reject" and not re.search(
                    r"\b(drop|omit|skip)\b.*\b(missing|invalid)\b",
                    prompt,
                    re.IGNORECASE,
                ):
                    raise ValueError(
                        "Omitting selected rows requires explicit user permission."
                    )
                for predicate in step.table.predicates:
                    if str(predicate.value).casefold() not in prompt.casefold() and (
                        not isinstance(predicate.value, (int, float))
                        or not any(
                            math.isclose(float(n), predicate.value)
                            for n in re.findall(r"(?<![\w.])-?\d+(?:\.\d+)?", prompt)
                        )
                    ):
                        raise ValueError(
                            "A row predicate must preserve an explicit user value."
                        )
                if step.table.aggregate != "none" and not re.search(
                    r"\b(mean|average|min(?:imum)?|max(?:imum)?|sum|total|count)\b",
                    prompt,
                    re.IGNORECASE,
                ):
                    raise ValueError("Aggregations must be explicitly requested.")
                result = table(
                    session.fetch(file), file, step.table, remaining=session.remaining
                )
                trace.append({"step_id": step.id, **result})
                if len(step.table.columns) == 2 and step.table.aggregate == "none":
                    x, y = step.table.columns
                    units = {v.name: v.unit for v in file.variables or []}
                    if not units.get(x) or not units.get(y):
                        raise ValueError(
                            "Plot axes need verified units before plotting selected data."
                        )
                    blocks.append(
                        {
                            "type": "chart",
                            "chart_type": "scatter",
                            "title": file.title,
                            "x": {
                                "label": x,
                                "unit": step.table.conversions.get(x, units[x]),
                                "values": [r["values"][x] for r in result["rows"]],
                            },
                            "series": [
                                {
                                    "label": y,
                                    "unit": step.table.conversions.get(y, units[y]),
                                    "values": [r["values"][y] for r in result["rows"]],
                                }
                            ],
                            "evidence_type": "measured",
                            "source_file_ids": [file.file_id],
                        }
                    )
                else:
                    blocks.append(
                        {
                            "type": "inspection",
                            "file_id": file.file_id,
                            "kind": "json",
                            "preview": result,
                            "note": "Explicit row selection and aggregate; source indices are retained.",
                        }
                    )
            done.add(step.id)
        return blocks, list(session.sources.values()), trace
