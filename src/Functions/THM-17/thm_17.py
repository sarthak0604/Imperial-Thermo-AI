"""THM-17 limiting oxygen estimate for established microgravity flame spread.

Run: python THM-17/thm_17.py THM-17/THM-17_input.json
Developed with SI assistance from OpenAI Codex.
"""

import argparse
import json
from math import exp, isfinite
from pathlib import Path


MODEL_ID = "THM-17"


def number(value, name, low=None, high=None, *, positive=False):
    try:
        valid = type(value) in (int, float) and isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(f"{name} must be a finite number.")
    if positive and value <= 0:
        raise ValueError(f"{name} must be positive.")
    if (low is not None and value < low) or (high is not None and value > high):
        raise ValueError(f"{name} is outside its allowed range.")
    return value

def branch_function(branch):
    form = branch["form"]
    if form == "linear":
        intercept = number(branch["intercept_pct"], "linear intercept")
        slope = number(branch["slope_pct_per_axis_unit"], "linear slope", 0)
        return lambda x: intercept + slope * x
    if form == "exponential":
        base = number(branch["base_pct"], "quench asymptote", 0, 100)
        amplitude = number(branch["amplitude_pct"], "quench amplitude", 0)
        decay = number(branch["decay_per_axis_unit"], "quench decay rate", 0)
        return lambda x: base + amplitude * exp(-decay * x)
    if form != "table":
        raise ValueError("Use a linear, exponential, or table boundary.")
    points = [
        (number(x, "boundary coordinate", 0), number(y, "boundary oxygen", 0, 100))
        for x, y in branch["points"]
    ]
    if len(points) < 2 or any(b[0] <= a[0] for a, b in zip(points, points[1:])):
        raise ValueError("A boundary table needs at least two points in increasing order.")

    def interpolate(x):
        if x < points[0][0] or x > points[-1][0]:
            raise ValueError("Boundary table does not cover the calibrated speed range.")
        for (left, y0), (right, y1) in zip(points, points[1:]):
            if x <= right:
                return y0 + (y1 - y0) * ((x - left) / (right - left))
        return points[-1][1]

    return interpolate


def predict_limiting_oxygen_index_0g(air_speed_m_s, profile):
    speed = number(air_speed_m_s, "air speed", 0)
    lo, hi = (number(value, "air speed bound", 0) for value in profile["air_speed_range_m_s"])
    if not lo <= speed <= hi:
        raise ValueError("Air speed falls outside the calibrated range.")
    scale = number(profile.get("axis_units_per_m_s", 1), "speed to boundary axis", positive=True)
    quench = branch_function(profile["quench"])
    blowoff = branch_function(profile["blowoff"])
    rule = profile["combination_rule"]
    if rule not in ("maximum", "shared_baseline_excess_sum"):
        raise ValueError("Choose maximum or shared_baseline_excess_sum.")
    baseline = (
        number(profile["shared_baseline_pct"], "shared baseline", 0, 100)
        if rule == "shared_baseline_excess_sum" else None
    )

    def at(u):
        x = u * scale
        q = number(quench(x), "quenching boundary", 0, 100)
        b = number(blowoff(x), "blowoff boundary", 0, 100)
        if baseline is None:
            limit = max(q, b)
        else:
            if min(q, b) < baseline:
                raise ValueError("Both branches must be at or above the shared baseline.")
            limit = number(q + b - baseline, "combined boundary", 0, 100)
        return q, b, limit

    q, b, limit = at(speed)
    speeds = sorted({speed, lo, hi, *(lo + (hi - lo) * index / 80 for index in range(1, 80))})
    quench_pct, blowoff_pct, loi_pct = (list(column) for column in zip(*(at(u) for u in speeds)))
    return {
        "status": "model_estimate",
        "limiting_oxygen_pct": limit,
        "air_speed_m_s": speed,
        "boundary_coordinate": speed * scale,
        "larger_branch": "quench" if q > b else "blowoff" if b > q else "equal",
        "sweep": {
            "air_speed_m_s": speeds, "quench_oxygen_pct": quench_pct,
            "blowoff_oxygen_pct": blowoff_pct, "limiting_oxygen_pct": loi_pct,
        },
        "limitations": [
            "The estimate applies to sustained propagation in the supplied geometry and pressure envelope.",
            "The estimated boundary does not resolve near-limit variability or predict ignition.",
        ],
    }


def run_request(payload):
    request, evidence = payload["request"], payload["evidence"]
    if (request["topic"], request["analysis"]) != ("flammability", "estimate_limiting_oxygen"):
        raise ValueError("Expected flammability / estimate_limiting_oxygen.")
    scenario = request["scenario"]
    matches = [item for item in evidence["calibrations"] if item["id"] == scenario["calibration_id"]]
    if len(matches) != 1:
        raise ValueError("Provide one evidence record matching scenario.calibration_id.")
    record = matches[0]

    for key in ("material_id", "setup_id", "flow_direction"):
        if scenario[key] != record[key]:
            raise ValueError(f"{key} must match the boundary calibration.")
    if scenario["gravity"] != record["gravity"]:
        raise ValueError("Gravity regime must match the microgravity boundary calibration.")
    pressure = number(scenario["pressure_kPa"], "pressure", positive=True)
    lo, hi = (number(value, "pressure bound", positive=True) for value in record["pressure_range_kPa"])
    if not lo <= pressure <= hi:
        raise ValueError("Pressure falls outside the calibrated range.")
    result = predict_limiting_oxygen_index_0g(scenario["air_speed_m_s"], record)
    if "reference_1g" in record:
        reference = record["reference_1g"]
        typical = number(reference["oxygen_pct"], "1g reference oxygen", 0, 100)
        result["reference_1g"] = dict(
            reference, estimate_minus_reference_percentage_points=result["limiting_oxygen_pct"] - typical,
        )
    if "ambient_oxygen_pct" in scenario:
        ambient = number(scenario["ambient_oxygen_pct"], "ambient oxygen", 0, 100)
        result["ambient_minus_limit_percentage_points"] = ambient - result["limiting_oxygen_pct"]

    return dict(
        result, model_id=MODEL_ID, evidence_id=record["id"],
        provenance=evidence["provenance"], sources=evidence["sources"],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSON file containing request and evidence")
    args = parser.parse_args()
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8-sig"))
        print(json.dumps(run_request(payload), indent=2, allow_nan=False))
    except (OSError, KeyError, TypeError, ValueError, AttributeError, ArithmeticError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
