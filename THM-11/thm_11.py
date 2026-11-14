"""THM-11 reduced model for two-stage n-alkane droplet burning.

Run from the repository root with Python 3.10+ (standard library only):
    python THM-11/thm_11.py THM-11/THM-11_request.json THM-11/THM-11_evidence.json

Each stage follows D^2(t) = D^2(start) - K * (t - start). The hot-stage
endpoint is supplied by the evidence. Cool extinction uses the approximate
D_ce^2 / K_c ~ C_O2^(-3/2) scaling of Nayagam et al., NASA NTRS 20140006750,
section 3.4. D_ce^2 / K_c is an extinction timescale, not the elapsed
cool-stage duration. For matched ambient temperatures, the ideal-gas
oxygen concentration ratio is the ratio of oxygen partial pressures.

This conditional model requires evidence that the two-stage regime applies.
Code developed with SI assistance from OpenAI Codex.
"""

import argparse
import json
from math import isclose, isfinite, sqrt
from pathlib import Path


MODEL_ID = "THM-11"
COOL_EXTINCTION_EXPONENT = -1.5


def finite_number(value, name):
    try:
        if type(value) in (int, float) and isfinite(value):
            return value
    except OverflowError:
        pass
    raise ValueError(f"{name} must be a finite number.")


def positive(value, name):
    value = finite_number(value, name)
    if value <= 0:
        raise ValueError(f"{name} must be positive.")
    return value


def quantity(record, key, unit):
    item = record[key]
    if item["unit"] != unit:
        raise ValueError(f"{key} must be in {unit}.")
    return finite_number(item["value"], key)


def model_two_stage_cool_flame_kinetics(
    d0_mm,
    hot_burning_rate_mm2_s,
    cool_burning_rate_mm2_s,
    hot_extinction_diameter_squared_mm2,
    cool_extinction_timescale_s,
):
    """Return the droplet trajectory, conditional on two quasi-steady stages."""
    d0_mm = positive(d0_mm, "initial_diameter_mm")
    hot_rate = positive(hot_burning_rate_mm2_s, "hot_burning_rate_mm2_s")
    cool_rate = positive(cool_burning_rate_mm2_s, "cool_burning_rate_mm2_s")
    hot_end = positive(
        hot_extinction_diameter_squared_mm2, "hot_extinction_diameter_squared_mm2"
    )
    scale = positive(cool_extinction_timescale_s, "cool_extinction_timescale_s")

    initial_squared = d0_mm * d0_mm
    cool_end = cool_rate * scale
    if not isfinite(initial_squared) or not 0 < cool_end < hot_end < initial_squared:
        raise ValueError("Expected decreasing, positive droplet sizes across both stages.")

    hot_duration = (initial_squared - hot_end) / hot_rate
    cool_duration = (hot_end - cool_end) / cool_rate
    total_duration = hot_duration + cool_duration
    if not isfinite(total_duration) or not 0 < hot_duration < total_duration:
        raise ValueError("Burning rates and diameters must yield finite, distinct stage times.")

    time_s = []
    diameter_squared_mm2 = []
    phase = []
    intervals = 60
    stages = (
        ("hot_flame", 0.0, hot_duration, initial_squared, hot_end),
        ("cool_flame", hot_duration, total_duration, hot_end, cool_end),
    )
    for label, start_time, end_time, start_squared, end_squared in stages:
        for index in range(intervals):
            fraction = index / intervals
            time_s.append(start_time + fraction * (end_time - start_time))
            diameter_squared_mm2.append(
                start_squared + fraction * (end_squared - start_squared)
            )
            phase.append(label)
    time_s.append(total_duration)
    diameter_squared_mm2.append(cool_end)
    phase.append("cool_flame")

    return {
        "model_id": MODEL_ID,
        "hot_extinction_time_s": hot_duration,
        "hot_extinction_diameter_mm": sqrt(hot_end),
        "cool_stage_duration_s": cool_duration,
        "cool_extinction_time_s": total_duration,
        "cool_extinction_diameter_mm": sqrt(cool_end),
        "hot_burning_rate_mm2_s": hot_rate,
        "cool_burning_rate_mm2_s": cool_rate,
        "cool_extinction_timescale_s": scale,
        "time_s": time_s,
        "diameter_squared_mm2": diameter_squared_mm2,
        "diameter_mm": [sqrt(value) for value in diameter_squared_mm2],
        "phase": phase,
    }


def matches_conditions(profile, setup_id, pressure, oxygen, diameter):
    low, high = profile["initial_diameter_range_mm"]
    return (
        profile["setup_id"] == setup_id
        and isclose(profile["pressure_kPa"], pressure, rel_tol=0, abs_tol=1e-8)
        and isclose(profile["oxygen_pct"], oxygen, rel_tol=0, abs_tol=1e-8)
        and low <= diameter <= high
    )


def run_request(request, evidence):
    """Run the dashboard request with matching, externally supplied evidence."""
    if request["topic"] != "droplet_combustion" or request["analysis"] != "estimate_cool_flame":
        raise ValueError("Expected a droplet_combustion / estimate_cool_flame request.")
    scenario = request["scenario"]
    setup_id = scenario["setup_id"]
    materials = scenario["materials"]
    if not isinstance(materials, list) or len(materials) != 1:
        raise ValueError("Provide one alkane material ID in scenario.materials.")
    setups = [item for item in evidence["setups"] if item["id"] == setup_id]
    fuels = [item for item in evidence["materials"] if item["id"] == materials[0]]
    if len(setups) != 1 or setups[0]["model"] != MODEL_ID or len(fuels) != 1:
        raise ValueError("Provide one matching THM-11 setup and alkane material.")
    setup, fuel = setups[0], fuels[0]
    if scenario.get("gravity", setup["gravity_regime"]) != setup["gravity_regime"]:
        raise ValueError("The gravity regime must match the evidence setup.")

    air = scenario["ambient"]
    pressure = positive(quantity(air, "pressure", "kPa"), "pressure")
    oxygen = positive(quantity(air, "oxygen", "%"), "oxygen")
    diameter = positive(
        quantity(scenario, "initial_diameter", "mm"), "initial_diameter"
    )
    diluent = air["additional_diluent"]
    if oxygen >= 100:
        raise ValueError("Oxygen must be below 100 percent.")
    if diluent != setup["additional_diluent"]:
        raise ValueError("The additional diluent must match the setup.")

    profiles = [
        item for item in fuel["calibrations"]
        if matches_conditions(item, setup_id, pressure, oxygen, diameter)
    ]
    references = [
        item for item in fuel["cool_extinction_references"] if item["setup_id"] == setup_id
    ]
    if len(profiles) != 1 or len(references) != 1:
        raise ValueError(
            "Need one matching two-stage calibration and one cool extinction reference "
            "within the evidence-supported fuel, size and ambient conditions."
        )
    profile, reference = profiles[0], references[0]

    hot_end = positive(
        profile["hot_extinction_diameter_squared_mm2"], "hot extinction diameter squared"
    )
    hot_duration = positive(profile["hot_extinction_time_s"], "hot extinction time")
    reference_initial = positive(profile["observed_initial_diameter_mm"], "reference size")
    effective_hot_rate = (reference_initial * reference_initial - hot_end) / hot_duration
    reference_scale = positive(
        reference["diameter_squared_mm2"], "reference cool extinction diameter squared"
    ) / positive(reference["cool_burning_rate_mm2_s"], "reference cool burning rate")
    reference_pressure = positive(reference["pressure_kPa"], "reference pressure")
    reference_oxygen = positive(reference["oxygen_pct"], "reference oxygen")
    partial_pressure_ratio = (pressure / reference_pressure) * (oxygen / reference_oxygen)
    cool_scale = reference_scale * partial_pressure_ratio ** COOL_EXTINCTION_EXPONENT

    result = model_two_stage_cool_flame_kinetics(
        diameter, effective_hot_rate, profile["cool_burning_rate_mm2_s"], hot_end, cool_scale
    )
    is_reference_run = profile["id"] == reference["run_id"]
    result.update(
        status="calibration_reconstruction" if is_reference_run else "conditional_estimate",
        evidence_boundary="Semi-Empirical Correlation",
        material_id=fuel["id"],
        setup_id=setup_id,
        calibration_id=profile["id"],
        cool_extinction_reference_run_id=reference["run_id"],
        oxygen_partial_pressure_ratio=partial_pressure_ratio,
        illustrative=bool(evidence["provenance"]["illustrative"]),
        sources=[
            {
                "role": "stage_inputs",
                "run_id": profile["id"],
                "url": profile["source_url"],
                "locator": profile["source_locator"],
            },
            {
                "role": "cool_extinction_reference",
                "run_id": reference["run_id"],
                "url": reference["source_url"],
                "locator": reference["source_locator"],
            },
            {
                "role": "extinction_correlation",
                "url": "https://ntrs.nasa.gov/api/citations/20140006750/downloads/20140006750.pdf#page=7",
                "locator": "Nayagam et al., section 3.4 and Fig. 4b",
            },
        ],
        limitations=[
            "The evidence supplies the hot-flame endpoint and cool burning rate.",
            "The scaling assumes comparable ambient temperature and gas transport properties.",
            "The trajectory starts with established burning and ends at cool-flame extinction.",
            "The model requires evidence of two-stage burning for the requested conditions.",
        ],
    )
    check = profile.get("held_out_cool_extinction")
    if check is not None and not is_reference_run and diameter == reference_initial:
        observed_time = positive(check["time_s"], "observed cool extinction time")
        result["held_out_check"] = {
            "run_id": profile["id"],
            "observed_cool_extinction_time_s": observed_time,
            "model_minus_observed_s": result["cool_extinction_time_s"] - observed_time,
            "source_url": profile["source_url"],
            "method": check["method"],
            "scope": "Only the cool extinction endpoint was held out.",
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path)
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    try:
        request = json.loads(args.request.read_text(encoding="utf-8"))
        evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
        output = run_request(request, evidence)
        print(json.dumps(output, allow_nan=False, indent=2))
    except (OSError, KeyError, ValueError, TypeError, ArithmeticError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
