"""THM-14 radiant heat release from radiometer flux and geometry.

Run: python THM-14/thm_14.py THM-14/THM-14_input.json
Developed with SI assistance from OpenAI Codex.
"""

import argparse
import json
from math import cos, fsum, isfinite, pi, radians
from pathlib import Path


MODEL_ID = "THM-14"
STEFAN_BOLTZMANN_W_M2_K4 = 5.670374419e-8


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


def compute_radiative_heat_flux_fraction(samples, geometry):
    mode = geometry["method"]
    transmission = number(geometry.get("transmission", 1), "path transmission", 0, 1, positive=True)
    if mode == "view_factor":
        area = number(geometry["detector_area_m2"], "detector active area", positive=True)
        view_factor = number(
            geometry["view_factor_f12"], "source-to-detector view factor", 0, 1, positive=True,
        )
        effective_area = area / (view_factor * transmission)
    elif mode == "isotropic_point_source":
        distance = number(geometry["source_distance_m"], "source distance", positive=True)
        angle = number(geometry["incidence_angle_deg"], "detector incidence angle", 0)
        if angle >= 90:
            raise ValueError("The detector incidence angle must be below 90 degrees.")
        effective_area = 4 * pi * distance ** 2 / (cos(radians(angle)) * transmission)
    else:
        raise ValueError("Choose view_factor or isotropic_point_source.")
    number(effective_area, "flux-to-power factor", positive=True)
    if not samples:
        raise ValueError("Supply at least one synchronized radiometer and HRR sample.")

    base_background = number(geometry.get("background_flux_w_m2", 0), "background flux", 0)
    times = []
    net_fluxes = []
    hrrs = []
    powers = []
    fractions = []
    flags = []
    for sample in samples:
        time = number(sample["time_s"], "sample time")
        if times and time <= times[-1]:
            raise ValueError("Sample times must be strictly increasing.")
        hrr = number(sample["total_hrr_w"], "total heat release rate", 0)
        reading = number(sample["radiometer_flux_w_m2"], "radiometer flux")
        background = number(sample.get("background_flux_w_m2", base_background), "background flux", 0)
        flux = reading - background
        power = number(flux * effective_area, "radiant power")
        fraction = number(power / hrr, "radiative fraction") if hrr > 0 else None
        sample_flags = []
        if power < 0:
            sample_flags.append("negative_net_flux")
        if fraction is None:
            sample_flags.append("zero_total_hrr")
        elif fraction > 1:
            sample_flags.append("radiative_fraction_above_one")
        times.append(time)
        net_fluxes.append(flux)
        hrrs.append(hrr)
        powers.append(power)
        fractions.append(fraction)
        flags.append(sample_flags)

    radiant_energy = total_energy = integrated_fraction = None
    if len(times) > 1:
        intervals = [b - a for a, b in zip(times, times[1:])]
        radiant_energy = fsum((0.5 * a + 0.5 * b) * dt for a, b, dt in zip(powers, powers[1:], intervals))
        total_energy = fsum((0.5 * a + 0.5 * b) * dt for a, b, dt in zip(hrrs, hrrs[1:], intervals))
        if total_energy > 0:
            integrated_fraction = number(radiant_energy / total_energy, "integrated radiative fraction")
    return {
        "status": "model_estimate" if all(not row for row in flags) else "model_estimate_with_flags",
        "gray_body_net_exchange_w": gray_body_exchange(geometry["gray_body"]) if "gray_body" in geometry else None,
        "geometry_method": mode,
        "flux_to_power_m2": effective_area,
        "radiant_energy_j": radiant_energy,
        "total_released_energy_j": total_energy,
        "integrated_radiative_fraction": integrated_fraction,
        "sample_flags": flags,
        "plot_data": {
            "time_s": times,
            "net_radiometer_flux_w_m2": net_fluxes,
            "radiant_power_w": powers,
            "total_hrr_w": hrrs,
            "radiative_fraction": fractions,
        },
    }

def gray_body_exchange(properties):
    area = number(properties["emitting_area_m2"], "gray-body area", positive=True)
    emissivity = number(properties["emissivity"], "gray-body emissivity", 0, 1)
    temperature = number(properties["temperature_k"], "gray-body temperature", positive=True)
    surroundings = number(properties["surroundings_temperature_k"], "gray-body surroundings", positive=True)
    return number(
        emissivity * STEFAN_BOLTZMANN_W_M2_K4 * area * (temperature ** 4 - surroundings ** 4),
        "gray-body net exchange",
    )


def run_request(payload):
    request, evidence = payload["request"], payload["evidence"]
    if (request["topic"], request["analysis"]) != ("heat_release", "estimate_radiative_fraction"):
        raise ValueError("Expected heat_release / estimate_radiative_fraction.")
    scenario = request["scenario"]
    matches = [item for item in evidence["runs"] if item["id"] == scenario["run_id"]]
    if len(matches) != 1:
        raise ValueError("Provide one evidence record matching scenario.run_id.")
    record = matches[0]
    result = compute_radiative_heat_flux_fraction(record["samples"], record["geometry"])

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
