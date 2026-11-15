"""THM-10 isolated spherical droplet d-squared regression.

Run: python THM-10/thm_10.py THM-10/THM-10_input.json
Developed with SI assistance from OpenAI Codex.
"""

import argparse
import json
from math import isfinite, log1p, pi, sqrt
from pathlib import Path


MODEL_ID = "THM-10"


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


def model_droplet_d2_vaporization_combustion(scenario, profile):
    diameter = number(scenario["d0_mm"], "initial diameter", positive=True)
    oxygen = number(scenario["x_o2"], "oxygen mole fraction", 0, 1)
    pressure = number(scenario["pressure_kpa"], "ambient pressure", positive=True)
    temperature = number(scenario["t_amb_k"], "ambient temperature", positive=True)
    process = scenario["process"]
    if process not in ("combustion", "evaporation"):
        raise ValueError("Choose combustion or evaporation.")
    if process == "combustion" and oxygen == 0:
        raise ValueError("Combustion requires oxygen.")
    if (profile["fuel_type"], profile["process"]) != (scenario["fuel_type"], process):
        raise ValueError("Fuel and process must match the supplied profile.")
    for key, value in (
        ("d0_mm", diameter), ("x_o2", oxygen),
        ("pressure_kpa", pressure), ("t_amb_k", temperature),
    ):
        lower, upper = (number(v, f"{key} range") for v in profile["validity"][key])
        if not lower <= value <= upper:
            raise ValueError(f"{key} falls outside the profile range [{lower}, {upper}].")

    method = profile["method"]
    density = profile.get("liquid_density_kg_m3")
    if density is not None:
        density = number(density, "liquid density", positive=True)
    transfer_number = None
    if method == "measured_rate":
        rate = number(profile["regression_rate_mm2_s"], "measured regression rate", positive=True)
    elif method == "heat_transfer":
        density = number(density, "liquid density", positive=True)
        conductivity = number(profile["gas_conductivity_w_m_k"], "gas conductivity", positive=True)
        heat_capacity = number(profile["gas_cp_j_kg_k"], "gas specific heat", positive=True)
        if "spalding_heat_transfer_number" in profile:
            transfer_number = number(profile["spalding_heat_transfer_number"], "transfer number", 0)
        elif process == "evaporation":
            surface_temperature = number(profile["surface_temperature_k"], "surface temperature", positive=True)
            latent_heat = number(profile["effective_vaporization_heat_j_kg"], "vaporization heat", positive=True)
            transfer_number = max(0.0, heat_capacity * (temperature - surface_temperature) / latent_heat)
        else:
            raise ValueError("Heat-transfer combustion requires a supplied Spalding heat-transfer number.")
        rate = 1e6 * (8 * conductivity / (density * heat_capacity)) * log1p(transfer_number)
    else:
        raise ValueError("Choose measured_rate or heat_transfer.")

    rate = number(rate, "computed regression rate", 0)
    endpoint = scenario.get("endpoint_diameter_mm")
    if endpoint is not None:
        endpoint = number(endpoint, "endpoint diameter", 0)
        if not 0 < endpoint < diameter:
            raise ValueError("A supplied endpoint diameter must be strictly between zero and d0_mm.")
    duration = None if rate == 0 else (diameter ** 2 - (endpoint or 0) ** 2) / rate
    time_limit = scenario.get("time_limit_s")
    if time_limit is not None:
        time_limit = number(time_limit, "time limit", positive=True)
    if duration is None and time_limit is None:
        raise ValueError("Provide time_limit_s when the profile yields no positive regression.")
    stop = time_limit if duration is None else min(duration, time_limit or duration)
    reached = duration is not None and stop == duration
    end_reason = "time_limit"
    if reached:
        end_reason = "supplied_diameter" if endpoint is not None else "formal_zero_diameter"

    count = scenario.get("plot_points", 101)
    if type(count) is not int or not 2 <= count <= 2001:
        raise ValueError("plot_points must be an integer from 2 to 2001.")
    times = [stop * (i / (count - 1)) for i in range(count)]
    squares = [max(0.0, diameter ** 2 - rate * time) for time in times]
    if reached:
        squares[-1] = (endpoint or 0) ** 2
    diameters = [sqrt(value) for value in squares]
    series = {"time_s": times, "diameter_squared_mm2": squares, "diameter_mm": diameters}
    if density is not None:
        series["droplet_mass_kg"] = [density * (pi / 6) * (d * 1e-3) ** 3 for d in diameters]
    result = {
        "status": "model_estimate",
        "process": process,
        "method": method,
        "regression_rate_mm2_s": rate,
        "spalding_heat_transfer_number": transfer_number,
        "modeled_endpoint_time_s": duration,
        "modeled_endpoint_diameter_mm": (endpoint or 0.0) if duration is not None else None,
        "stop_reason": end_reason,
        "plot_data": series,
    }
    if process == "combustion":
        result["burning_rate_mm2_s"] = rate
    if "comparison_rate_mm2_s" in profile:
        observed = number(profile["comparison_rate_mm2_s"], "comparison rate", positive=True)
        result["rate_comparison"] = {
            "reference_rate_mm2_s": observed,
            "model_minus_reference_mm2_s": rate - observed,
        }
    return result

def run_request(payload):
    request, evidence = payload["request"], payload["evidence"]
    if (request["topic"], request["analysis"]) != ("droplet_combustion", "estimate_droplet_regression"):
        raise ValueError("Expected droplet_combustion / estimate_droplet_regression.")
    scenario = request["scenario"]
    matches = [item for item in evidence["profiles"] if item["id"] == scenario["profile_id"]]
    if len(matches) != 1:
        raise ValueError("Provide one evidence record matching scenario.profile_id.")
    record = matches[0]
    result = model_droplet_d2_vaporization_combustion(scenario, record)

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
