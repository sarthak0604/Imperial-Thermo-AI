"""Typed, auditable v2 operations. No code generation or implicit row cleaning."""

import csv
import math
import operator
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import Field

from .models import Contract, ExecutionLimits


class ScenarioTask(Contract):
    model_id: str
    params: dict
    input_origins: dict[str, Literal["user", "default"]]
    allowed_defaults: dict = Field(default_factory=dict)


class RowPredicate(Contract):
    column: str
    operator: Literal["eq", "ne", "lt", "lte", "gt", "gte"]
    value: float | str


class TableTask(Contract):
    file_id: str
    columns: list[str] = Field(min_length=1)
    predicates: list[RowPredicate] = Field(default_factory=list)
    aggregate: Literal["none", "mean", "min", "max", "sum", "count"] = "none"
    missing: Literal["reject", "omit_selected"] = "reject"
    # Conversion is explicit: source -> destination with a registered linear map.
    conversions: dict[str, str] = Field(default_factory=dict)


CONVERSIONS = {
    ("mmHg", "kPa"): (0.133322387415, 0),
    ("atm", "kPa"): (101.325, 0),
    ("C", "K"): (1, 273.15),
    ("mm", "m"): (0.001, 0),
    ("cm/s", "m/s"): (0.01, 0),
}


def scenario(task, *, limits=None, prompt=None):
    from .execution import ExecutionSession
    from .function_registry import model_spec

    task = ScenarioTask.model_validate(task)
    if model_spec(task.model_id)["requires_evidence"]:
        raise ValueError(
            "This model requires sourced calibration/evidence; scenario-only execution is unavailable."
        )
    if set(task.params) != set(task.input_origins):
        raise ValueError("Every scenario input needs an origin.")
    for name, origin in task.input_origins.items():
        if origin == "default" and task.allowed_defaults.get(name) != task.params[name]:
            raise ValueError("A default must be explicitly permitted with its value.")
    # User inputs originate in the explicit typed task, never in a model-generated evidence block.
    with tempfile.TemporaryDirectory(prefix="thermo-scenario-") as directory:
        result = ExecutionSession(directory, limits or ExecutionLimits()).calculate(
            task.model_id, {"params": task.params}
        )
    from .function_registry import input_contract

    defaults = {
        k: v
        for k, v in input_contract(task.model_id).get("defaults", {}).items()
        if k not in task.params
    }
    return {
        "model_defaults": defaults,
        "model_id": task.model_id,
        "evidence_type": "model_estimate",
        "inputs": task.params,
        "input_origins": task.input_origins,
        "assumptions": task.allowed_defaults,
        "result": result,
    }


def table(path, file, task, *, remaining=None):
    task = TableTask.model_validate(task)
    if file.file_id != task.file_id:
        raise ValueError("Table task source differs from the selected file.")
    with Path(path).open(encoding=file.encoding or "utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        required = set(task.columns) | {p.column for p in task.predicates}
        if len(set(headers)) != len(headers) or not required.issubset(headers):
            raise ValueError("Use exact unique column headers for selections.")
        rows, omitted = [], []
        for index, raw in enumerate(reader):
            if remaining is not None:
                remaining()
            if None in raw or any(v is None for v in raw.values()):
                raise ValueError("Ragged CSV rows cannot be selected.")
            keep = True
            for pred in task.predicates:
                observed = raw[pred.column]
                if isinstance(pred.value, (int, float)):
                    try:
                        observed = float(observed)
                    except ValueError as exc:
                        raise ValueError("Selection column is not numeric.") from exc
                    if not math.isfinite(observed):
                        raise ValueError("Selection column is nonfinite.")
                checks = {
                    "eq": operator.eq,
                    "ne": operator.ne,
                    "lt": operator.lt,
                    "lte": operator.le,
                    "gt": operator.gt,
                    "gte": operator.ge,
                }
                keep &= checks[pred.operator](observed, pred.value)
            if not keep:
                continue
            try:
                values = {column: float(raw[column]) for column in task.columns}
                if not all(math.isfinite(v) for v in values.values()):
                    raise ValueError("Nonfinite values")
            except ValueError:
                if task.missing == "omit_selected":
                    omitted.append(index)
                    continue
                raise ValueError(
                    "Selected numeric cells contain missing or nonfinite values."
                )
            for column, destination in task.conversions.items():
                source = next(
                    (v.unit for v in file.variables or [] if v.name == column), None
                )
                if column not in values or (source, destination) not in CONVERSIONS:
                    raise ValueError("No registered conversion for selected column.")
                scale, offset = CONVERSIONS[source, destination]
                values[column] = values[column] * scale + offset
            rows.append(
                {"row_index": index, "source_line": index + 2, "values": values}
            )
    if not rows:
        raise ValueError("No rows satisfy the requested selection.")
    aggregate = {}
    for column in task.columns:
        values = [row["values"][column] for row in rows]
        if task.aggregate != "none":
            operations = {
                "mean": sum(values) / len(values),
                "min": min(values),
                "max": max(values),
                "sum": sum(values),
                "count": len(values),
            }
            aggregate[column] = operations[task.aggregate]
    return {
        "file_id": file.file_id,
        "rows": rows,
        "omitted_row_indices": omitted,
        "aggregate": aggregate,
        "task": task.model_dump(),
    }
