"""THM-15 soot inception screening for diffusion flames.

Run: python THM-15/thm_15.py THM-15/THM-15_input.json
Developed with SI assistance from OpenAI Codex.
"""

import argparse
import json
from math import isfinite, log
from pathlib import Path


MODEL_ID = "THM-15"


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

def threshold_curve(points):
    curve = [
        (
            number(point["residence_time_s"], "threshold residence time", positive=True),
            number(point["threshold_temperature_K"], "threshold temperature", positive=True),
        )
        for point in points
    ]
    if not curve or any(right[0] <= left[0] for left, right in zip(curve, curve[1:])):
        raise ValueError("Threshold points must be ordered by strictly increasing residence time.")
    return curve


def threshold_at(residence, curve):
    if not curve[0][0] <= residence <= curve[-1][0]:
        raise ValueError("Residence time falls outside the supplied threshold curve.")
    for (t0, temp0), (t1, temp1) in zip(curve, curve[1:]):
        if residence <= t1:
            weight = log(residence / t0) / log(t1 / t0)
            return temp0 + weight * (temp1 - temp0)
    return curve[-1][1]


def calc_soot_inception_temperature_threshold(scenario, profile):
    """Compare co-located fuel-side temperature and C/O with an evidence threshold."""
    temperature = number(scenario["flame_temperature_K"], "local temperature", positive=True)
    gradient = number(scenario["temperature_gradient_K_m"], "outward temperature gradient")
    residence = number(scenario["residence_time_s"], "residence time", positive=True)
    carbon_oxygen = number(scenario["carbon_to_oxygen_atomic_ratio"], "local atomic C/O", 0)
    min_co = number(profile["min_carbon_to_oxygen_atomic_ratio"], "threshold atomic C/O", positive=True)
    margin_band = number(profile.get("temperature_margin_band_K", 0), "margin band", 0)
    curve = threshold_curve(profile["threshold_curve"])
    threshold = threshold_at(residence, curve)
    margin = temperature - threshold
    if carbon_oxygen < min_co or margin < -margin_band:
        screening = "below_inception_criteria"
    elif margin <= margin_band:
        screening = "near_threshold"
    else:
        screening = "inception_possible"

    viscosity = number(profile["kinematic_viscosity_m2_s"], "kinematic viscosity", positive=True)
    coefficient = number(profile["thermophoretic_coefficient"], "thermophoretic coefficient", 0)
    gas_speed = number(scenario["radial_gas_velocity_m_s"], "outward gas velocity")
    drift = -coefficient * viscosity * gradient / temperature
    return {
        "status": "screening_estimate",
        "inception_screen": screening,
        "threshold_temperature_K": threshold,
        "temperature_margin_K": margin,
        "carbon_to_oxygen_margin": carbon_oxygen - min_co,
        "thermophoretic_velocity_m_s": drift,
        "net_radial_particle_velocity_m_s": gas_speed + drift,
        "threshold_curve": profile["threshold_curve"],
        "limitations": [
            "Use co-located fuel-side values, with temperature and residence time defined by the calibration.",
            "Thermophoretic drift is reported alongside the threshold screen. Residence time remains the supplied input.",
            "A soot inception screen alone cannot establish visible flame color, soot emission, or detector response.",
        ],
    }


def run_request(payload):
    request, evidence = payload["request"], payload["evidence"]
    if (request["topic"], request["analysis"]) != ("soot", "screen_soot_inception"):
        raise ValueError("Expected soot / screen_soot_inception.")
    scenario = request["scenario"]
    matches = [item for item in evidence["calibrations"] if item["id"] == scenario["calibration_id"]]
    if len(matches) != 1:
        raise ValueError("Provide one evidence record matching scenario.calibration_id.")
    record = matches[0]

    for key in ("fuel_id", "setup_id", "gravity"):
        if scenario[key] != record[key]:
            raise ValueError(f"{key} must match the threshold calibration.")
    pressure = number(scenario["pressure_kPa"], "pressure", positive=True)
    lo, hi = (number(value, "pressure bound", positive=True) for value in record["pressure_range_kPa"])
    if not lo <= pressure <= hi:
        raise ValueError("Pressure falls outside the supplied threshold calibration.")
    result = calc_soot_inception_temperature_threshold(scenario, record)

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
