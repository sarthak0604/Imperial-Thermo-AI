"""THM-20 one-dimensional aerosol transport and coagulation screening.

Run: python THM-20/thm_20.py THM-20/THM-20_input.json
Developed with SI assistance from OpenAI Codex.
"""

import argparse
import json
from math import erfc, exp, expm1, isfinite, pi, sqrt
from pathlib import Path


MODEL_ID = "THM-20"


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

K_B = 1.380649e-23


def arrival_fraction(time, length, drift, diffusivity):
    """First-passage CDF for a point packet with constant drift and diffusion."""
    if time == 0:
        return 0.0
    if diffusivity == 0:
        return float(drift > 0 and time >= length / drift)
    scale = sqrt(4 * diffusivity * time)
    direct = 0.5 * erfc((length - drift * time) / scale)
    tail = (length + drift * time) / scale
    if tail < 25:
        reflected = (
            exp(-((length - drift * time) / scale)**2)
            * (0.5 * erfc(tail) * exp(tail**2))
        )
    else:
        # Large-tail erfc expansion with the drift exponent combined analytically.
        inverse = 0.5 / tail / tail
        reflected = (
            exp(-((length - drift * time) / scale)**2)
            / (2 * sqrt(pi) * tail) * (1 - inverse + 3 * inverse**2 - 15 * inverse**3)
        )
    return min(1.0, max(0.0, direct + reflected))


def model_aerosol_thermophoretic_coagulation_transport(scenario, profile):
    length = number(scenario["duct_length_m"], "duct length", positive=True)
    area = number(scenario["duct_area_m2"], "duct area", positive=True)
    speed = number(scenario["air_speed_m_s"], "carrier gas speed", positive=True)
    gradient = number(scenario["axial_temperature_gradient_K_m"], "axial temperature gradient")
    smoke_rate = number(scenario["smoke_mass_rate_kg_s"], "smoke mass rate", 0)
    duration = number(scenario["duration_s"], "analysis duration", positive=True)
    temperature = number(profile["gas_temperature_K"], "representative gas temperature", positive=True)
    viscosity = number(profile["gas_dynamic_viscosity_Pa_s"], "dynamic viscosity", positive=True)
    density = number(profile["gas_density_kg_m3"], "gas density", positive=True)
    diameter = number(profile["source_particle_diameter_m"], "source particle diameter", positive=True)
    particle_density = number(profile["particle_density_kg_m3"], "particle density", positive=True)
    coefficient = number(profile["thermophoretic_coefficient"], "thermophoretic coefficient", 0)
    diffusivity = number(profile["axial_dispersion_m2_s"], "axial dispersion", 0)
    loss = number(profile.get("wall_loss_rate_s_inv", 0), "wall loss rate", 0)
    if "collision_kernel_m3_s" in profile:
        kernel = number(profile["collision_kernel_m3_s"], "collision kernel", 0)
    else:
        mean_path = number(profile["gas_mean_free_path_m"], "mean free path", positive=True)
        if 2 * mean_path / diameter > 0.1:
            raise ValueError("Supply a collision kernel for particles outside the continuum/slip limit.")
        slip = number(profile["cunningham_slip_factor"], "Cunningham factor", 1)
        brownian = 8 * K_B * temperature * slip / (3 * viscosity)
        shear = number(profile.get("laminar_shear_rate_s_inv", 0), "laminar shear rate", 0)
        kernel = brownian + 4 / 3 * shear * diameter**3

    thermophoresis = -coefficient * (viscosity / density) * gradient / temperature
    drift = speed + thermophoresis
    if drift <= 0:
        raise ValueError("The particle drift must remain downstream for this duct model.")
    mass0 = smoke_rate / (drift * area)
    number0 = mass0 / (pi / 6 * particle_density * diameter**3)
    travel = length / drift

    def evolve(time):
        reduction = exp(-loss * time)
        exposure = -expm1(-loss * time) / loss if loss else time
        collisions = 1 + 0.5 * kernel * number0 * exposure
        return number0 * reduction / collisions, mass0 * reduction, diameter * collisions**(1 / 3)

    times = sorted({*(duration * i / 100 for i in range(101)), min(duration, travel)})
    count, mass, size = (list(col) for col in zip(*(evolve(time) for time in times)))
    at_detector = evolve(travel)
    return {
        "status": "transport_estimate",
        "thermophoretic_velocity_m_s": thermophoresis,
        "effective_particle_velocity_m_s": drift,
        "mean_advective_travel_time_s": travel,
        "collision_kernel_m3_s": kernel,
        "number_concentration_at_mean_arrival_m3": at_detector[0],
        "mass_concentration_at_mean_arrival_kg_m3": at_detector[1],
        "equivalent_diameter_at_mean_arrival_m": at_detector[2] if number0 else None,
        "time_s": times,
        "parcel_number_concentration_m3": count,
        "parcel_mass_concentration_kg_m3": mass,
        "parcel_equivalent_diameter_m": size if number0 else None,
        "packet_transport_arrival_fraction": [
            arrival_fraction(time, length, drift, diffusivity) for time in times
        ] if number0 else [0.0] * len(times),
        "limitations": [
            "Uniform straight duct with positive axial particle drift and a constant collision kernel.",
            "Equivalent size assumes compact particles. The solver returns a bulk size and count, with no resolved size distribution.",
            "Arrival fraction describes kinematic first passage, independent of wall loss and coagulation.",
            "Outputs describe transport at the detector location. An alarm estimate needs a detector response calibration.",
        ],
    }


def run_request(payload):
    request, evidence = payload["request"], payload["evidence"]
    if (request["topic"], request["analysis"]) != ("smoke", "estimate_aerosol_transport"):
        raise ValueError("Expected smoke / estimate_aerosol_transport.")
    scenario = request["scenario"]
    matches = [item for item in evidence["profiles"] if item["id"] == scenario["profile_id"]]
    if len(matches) != 1:
        raise ValueError("Provide one evidence record matching scenario.profile_id.")
    record = matches[0]

    if scenario["setup_id"] != record["setup_id"]:
        raise ValueError("Setup must match the aerosol transport profile.")
    for key, value_range in record["scenario_bounds"].items():
        lo, hi = (number(v, f"{key} bound") for v in value_range)
        if not lo <= number(scenario[key], key) <= hi:
            raise ValueError(f"{key} falls outside the calibrated range.")
    result = model_aerosol_thermophoretic_coagulation_transport(scenario, record)

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
