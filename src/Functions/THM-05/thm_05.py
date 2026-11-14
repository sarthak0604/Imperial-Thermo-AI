"""THM-05 de Ris thermal-regime estimates for opposed flame spread.

Run from the repository root:
    python THM-05/thm_05.py THM-05/THM-05_input.json

Properties and bounds come from the input evidence. See NASA/TM-20210011385,
Eqs. 2.11 and 2.14, for the two limits and their intersection.
Developed with SI assistance from OpenAI Codex.
"""

import argparse
import json
from math import isfinite, pi
from pathlib import Path


MODEL_ID = "THM-05"


def number(value, name, *, minimum=None, maximum=None, positive=False):
    try:
        finite = type(value) in (int, float) and isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError(f"{name} must be a finite number.")
    if positive and value <= 0:
        raise ValueError(f"{name} must be positive.")
    if (minimum is not None and value < minimum) or (maximum is not None and value > maximum):
        raise ValueError(f"{name} is outside its permitted range.")
    return value

METHOD_URL = "https://ntrs.nasa.gov/api/citations/20210011385/downloads/TM-20210011385.pdf#page=49"


def quantity(record, key, unit):
    entry = record[key]
    if entry["unit"] != unit:
        raise ValueError(f"{key} must use {unit}.")
    return number(entry["value"], key, positive=True)


def bounds(calibration, name, *, maximum=None):
    lower, upper = (
        number(limit, name, positive=True, maximum=maximum)
        for limit in calibration[name]
    )
    if lower > upper:
        raise ValueError(f"{name} bounds must be in ascending order.")
    return lower, upper


def thermal_prefactors(thermal, pressure_kPa):
    """Read published prefactors or calculate them from SI material and gas properties."""
    if "prefactors" in thermal:
        published = thermal["prefactors"]
        return (
            number(published["thin_m2_s"], "thin prefactor", positive=True),
            number(published["thick_dimensionless"], "thick prefactor", positive=True),
        )
    solid = thermal["solid"]
    gas = thermal["gas"]
    gas_conductivity = number(gas["conductivity_W_m_K"], "gas conductivity", positive=True)
    solid_capacity = (
        number(solid["density_kg_m3"], "solid density", positive=True)
        * number(solid["specific_heat_J_kg_K"], "solid specific heat", positive=True)
    )
    thick = (
        gas_conductivity
        * number(gas["density_kg_m3"], "gas density", positive=True)
        * number(gas["specific_heat_J_kg_K"], "gas specific heat", positive=True)
        / (solid_capacity * number(solid["conductivity_W_m_K"], "solid conductivity", positive=True))
    )
    if "density_reference_pressure_kPa" in gas:
        reference_pressure = number(
            gas["density_reference_pressure_kPa"], "gas density reference pressure", positive=True
        )
        thick *= number(pressure_kPa, "pressure", positive=True) / reference_pressure
    return pi / 4 * gas_conductivity / solid_capacity, thick


def flame_coefficient(thermal):
    if "flame_coefficient" in thermal:
        return number(thermal["flame_coefficient"], "flame coefficient", positive=True)
    ambient = number(thermal["ambient_temperature_K"], "ambient temperature", positive=True)
    vaporization = number(
        thermal["vaporization_temperature_K"], "vaporization temperature", positive=True
    )
    flame = number(thermal["effective_flame_temperature_K"], "flame temperature", positive=True)
    if not ambient < vaporization < flame:
        raise ValueError("Expected ambient < vaporization < effective flame temperature.")
    return (flame - vaporization) / (vaporization - ambient)


def model_opposed_flow_flame_spread_deris(
    air_speed_m_s, thickness_m, *, thermal, pressure_kPa=None
):
    """Return a steady rate conditioned on established, thermally controlled spread."""
    speed = number(air_speed_m_s, "opposed gas speed", positive=True)
    thickness = number(thickness_m, "full sample thickness", positive=True)
    thin_prefactor, thick_prefactor = thermal_prefactors(thermal, pressure_kPa)
    coefficient = flame_coefficient(thermal)
    thin_rate = thin_prefactor * coefficient / (thickness / 2)
    thick_rate = thick_prefactor * speed * coefficient**2
    transition = 2 * thin_prefactor * coefficient / thick_rate
    if not all(isfinite(value) and value > 0 for value in (thin_rate, thick_rate, transition)):
        raise ValueError("The thermal properties must yield finite positive rates and thickness.")
    thin = thickness <= transition
    spread = thin_rate if thin else thick_rate
    return {
        "spread_rate_mm_s": 1000 * spread,
        "spread_rate_m_s": spread,
        "thin_limit_mm_s": 1000 * thin_rate,
        "thick_limit_mm_s": 1000 * thick_rate,
        "transition_thickness_m": transition,
        "thermal_regime": "thermally_thin" if thin else "thermally_thick",
        "flame_coefficient": coefficient,
        "opposed_gas_speed_m_s": speed,
        "sample_thickness_m": thickness,
    }


def run_request(payload):
    request, evidence = payload["request"], payload["evidence"]
    if (request["topic"], request["analysis"]) != ("flame_spread", "estimate_spread_rate"):
        raise ValueError("Expected a flame_spread / estimate_spread_rate request.")
    scenario = request["scenario"]
    materials, setup_id = scenario["materials"], scenario["setup_id"]
    if not isinstance(materials, list) or len(materials) != 1:
        raise ValueError("Provide one material ID in scenario.materials.")
    setups = [item for item in evidence["setups"] if item["id"] == setup_id]
    fuels = [item for item in evidence["materials"] if item["id"] == materials[0]]
    if len(fuels) != 1 or len(setups) != 1 or setups[0]["model"] != MODEL_ID:
        raise ValueError("Provide one matching THM-05 setup and material.")
    setup, fuel = setups[0], fuels[0]
    if (
        scenario["gravity"] != setup["gravity_regime"]
        or scenario["flow_direction"] != "opposed"
        or setup["flow_direction"] != "opposed"
    ):
        raise ValueError("THM-05 requires opposed flow and the gravity regime of the setup.")

    air = scenario["ambient"]
    speed = quantity(air, "air_speed", "cm/s") / 100
    pressure = quantity(air, "pressure", "kPa")
    oxygen = number(quantity(air, "oxygen", "%"), "oxygen percentage", maximum=100)
    thickness = quantity(scenario, "specimen_thickness", "m")
    width = quantity(scenario, "sample_width", "m")
    conditions = (
        ("air_speed_range_m_s", speed, None),
        ("pressure_range_kPa", pressure, None),
        ("oxygen_range_pct", oxygen, 100),
        ("thickness_range_m", thickness, None),
        ("width_range_m", width, None),
    )
    profiles = []
    for item in fuel["calibrations"]:
        if item["setup_id"] != setup_id:
            continue
        ranges = [bounds(item, key, maximum=maximum) for key, _, maximum in conditions]
        if all(low <= value <= high for (_, value, _), (low, high) in zip(conditions, ranges)):
            profiles.append((item, ranges))
    if len(profiles) != 1:
        raise ValueError("Provide one calibration covering the requested speed, atmosphere and sample geometry.")
    profile, ranges = profiles[0]
    thermal = profile["thermal"]
    result = model_opposed_flow_flame_spread_deris(speed, thickness, thermal=thermal, pressure_kPa=pressure)

    sweep = []
    for key, (low, high) in (("air_speed_m_s", ranges[0]), ("sample_thickness_m", ranges[3])):
        axis = [low] if low == high else [low + (high - low) * i / 40 for i in range(41)]
        axis[-1] = high
        rates = []
        for value in axis:
            sweep_speed = value if key == "air_speed_m_s" else speed
            sweep_thickness = value if key == "sample_thickness_m" else thickness
            curve = model_opposed_flow_flame_spread_deris(sweep_speed, sweep_thickness, thermal=thermal, pressure_kPa=pressure)
            rates.append(curve["spread_rate_mm_s"])
        sweep.append({key: axis, "spread_rate_mm_s": rates})

    comparisons = []
    for check in profile.get("spread_rate_checks", []):
        check_thickness = number(check["thickness_m"], "check thickness", positive=True)
        check_speed = number(check.get("air_speed_m_s", speed), "check speed", positive=True)
        if not ranges[0][0] <= check_speed <= ranges[0][1] or not ranges[3][0] <= check_thickness <= ranges[3][1]:
            raise ValueError("A spread-rate check lies outside the calibration bounds.")
        prediction = model_opposed_flow_flame_spread_deris(check_speed, check_thickness, thermal=thermal, pressure_kPa=pressure)
        if "air_speed_m_s" not in check and prediction["thermal_regime"] != "thermally_thin":
            raise ValueError("A thermally thick spread-rate check needs its measured air speed.")
        observed = number(check["spread_rate_mm_s"], "observed spread rate", positive=True)
        comparisons.append(dict(
            check, model_spread_rate_mm_s=prediction["spread_rate_mm_s"],
            model_minus_observed_mm_s=prediction["spread_rate_mm_s"] - observed,
        ))

    result.update(
        model_id=MODEL_ID,
        status="model_estimate",
        evidence_boundary="Thermally controlled, opposed-flow spread",
        setup_id=setup_id,
        material_id=fuel["id"],
        calibration_id=profile["id"],
        illustrative=evidence["provenance"]["illustrative"],
        provenance=evidence["provenance"],
        ambient={"pressure_kPa": pressure, "oxygen_pct": oxygen},
        sample_width_m=width,
        sweeps=sweep,
        evidence_bounds={
            key: list(interval) for (key, _, _), interval in zip(conditions, ranges)
        },
        spread_rate_checks=comparisons,
        sources=[
            {"role": "model_inputs", "url": profile["source_url"], "locator": profile["source_locator"]},
            {"role": "method", "url": METHOD_URL, "locator": "Eqs. 2.11 and 2.14"},
        ],
        limitations=[
            "The rate assumes established flame spread in the thermal regime.",
            "The two limiting laws exclude radiative quenching, kinetic blowoff and ignition.",
            "The thin branch assumes symmetric heating from both faces.",
            "The properties and flame coefficient apply within the supplied calibration bounds.",
            "Oxygen concentration selects the evidence profile and its flame coefficient.",
        ],
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSON file containing request and evidence")
    args = parser.parse_args()
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8-sig"))
        print(json.dumps(run_request(payload), indent=2, allow_nan=False))
    except (OSError, KeyError, TypeError, AttributeError, ValueError, ArithmeticError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
