"""THM-06 reduced laminar-boundary-layer model for concurrent flame spread.

Run from the repository root:
    python THM-06/thm_06.py THM-06/THM-06_input.json

The heat-transfer closure follows the forced-flow limit of Thomsen et al.
The growth length, reference measurements and validity bounds are evidence inputs.
Developed with SI assistance from OpenAI Codex.
"""

import argparse
import json
from math import expm1, isfinite, log1p, sqrt, tanh
from pathlib import Path


MODEL_ID = "THM-06"


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

METHOD_URL = "https://pmc.ncbi.nlm.nih.gov/articles/PMC6907022/#S4"
BLASIUS_NUSSELT_COEFFICIENT = 0.664


def quantity(record, key, unit):
    entry = record[key]
    if entry["unit"] != unit:
        raise ValueError(f"{key} must use {unit}.")
    return number(entry["value"], key, positive=True)


def calibrated_conditions(profile, conditions):
    for key, value in conditions.items():
        low, high = (
            number(entry, f"{key} bound", positive=True)
            for entry in profile["bounds"][key]
        )
        if low > high:
            raise ValueError(f"{key} bounds must be in ascending order.")
        if not low <= value <= high:
            return False
    return True


def transfer_factors(gas, pressure_kPa, ref_pressure_kPa, speed, length):
    """Average flat-plate coefficient over the active pyrolysis length."""
    nu_ref = number(gas["kinematic_viscosity_ref_m2_s"], "kinematic viscosity", positive=True)
    conductivity = number(gas["conductivity_W_m_K"], "gas conductivity", positive=True)
    prandtl = number(gas["prandtl"], "Prandtl number", positive=True)
    nu = nu_ref * ref_pressure_kPa / pressure_kPa
    re = speed * length / nu
    if not isfinite(re) or re <= 0:
        raise ValueError("The inputs must yield a finite positive Reynolds number.")
    return re, BLASIUS_NUSSELT_COEFFICIENT * conductivity / length * sqrt(re) * prandtl**(1 / 3)


def model_concurrent_flow_boundary_layer_spread(
    air_speed_m_s, pressure_kPa, ambient_temperature_K, sample_length_m, *,
    thermal, gas, calibration, initial_pyrolysis_length_m=None,
    initial_front_position_m=None, duration_s=None, sample_thickness_m=None,
):
    """Model the established front until its heating zone approaches the sample edge."""
    speed = number(air_speed_m_s, "concurrent gas speed", positive=True)
    pressure = number(pressure_kPa, "pressure", positive=True)
    ambient = number(ambient_temperature_K, "ambient temperature", positive=True)
    sample_length = number(sample_length_m, "sample length", positive=True)

    pyrolysis_temp = number(thermal["pyrolysis_temperature_K"], "pyrolysis temperature", positive=True)
    flame_temp = number(gas["effective_flame_temperature_K"], "flame temperature", positive=True)
    if not ambient < pyrolysis_temp < flame_temp:
        raise ValueError("Expected ambient < pyrolysis < effective flame temperature.")
    cp = number(thermal["specific_heat_J_kg_K"], "solid specific heat", positive=True)
    ref = calibration["reference"]
    if "areal_mass_kg_m2" in thermal:
        areal_capacity = number(thermal["areal_mass_kg_m2"], "areal mass", positive=True) * cp
        reference_areal_capacity = areal_capacity
    else:
        density = number(thermal["density_kg_m3"], "solid density", positive=True)
        thickness = number(sample_thickness_m, "sample thickness", positive=True)
        reference_thickness = number(
            ref["sample_thickness_m"], "reference sample thickness", positive=True
        )
        areal_capacity = density * thickness * cp
        reference_areal_capacity = density * reference_thickness * cp
    energy_per_area = areal_capacity * (pyrolysis_temp - ambient)
    heating_ratio = number(
        calibration["heated_to_pyrolysis_length_ratio"], "heating length ratio", positive=True
    )
    growth_length = number(calibration["growth_length_m"], "growth length", positive=True)
    length_power = number(calibration["pyrolysis_length_flow_exponent"], "length exponent")
    ref_speed = number(ref["air_speed_m_s"], "reference speed", positive=True)
    ref_pressure = number(ref["pressure_kPa"], "reference pressure", positive=True)
    ref_length = number(ref["pyrolysis_length_m"], "reference pyrolysis length", positive=True)
    ref_ambient = number(ref["ambient_temperature_K"], "reference ambient temperature", positive=True)
    if ref_ambient >= pyrolysis_temp:
        raise ValueError("Reference ambient temperature must be below the pyrolysis temperature.")

    if "effective_heat_feedback_factor" in calibration:
        heat_feedback_factor = number(
            calibration["effective_heat_feedback_factor"], "heat feedback factor", positive=True
        )
    else:
        ref_rate = number(ref["spread_rate_mm_s"], "reference spread rate", positive=True) / 1000
        _, h_ref = transfer_factors(gas, ref_pressure, ref_pressure, ref_speed, ref_length)
        heat_flux_ref = h_ref * (flame_temp - pyrolysis_temp)
        heat_feedback_factor = (
            ref_rate * reference_areal_capacity * (pyrolysis_temp - ref_ambient)
            / (heating_ratio * ref_length * heat_flux_ref)
        )
    limit = ref_length * (speed / ref_speed) ** length_power
    if not isfinite(limit) or limit <= 0:
        raise ValueError("The calibration must yield a finite positive limiting pyrolysis length.")

    length0 = limit if initial_pyrolysis_length_m is None else number(
        initial_pyrolysis_length_m, "initial pyrolysis length", positive=True
    )
    front0 = length0 if initial_front_position_m is None else number(
        initial_front_position_m, "initial front position", positive=True
    )
    if not 0 < length0 <= min(front0, limit):
        raise ValueError("The initial burning length must fit behind the front and within the limit.")
    if limit - length0 > growth_length:
        raise ValueError("The growth length must be at least the initial deficit in pyrolysis length.")
    if front0 + heating_ratio * length0 >= sample_length:
        raise ValueError("The initial heating zone must fit before the downstream edge.")

    re_limit, h_limit = transfer_factors(gas, pressure, ref_pressure, speed, limit)
    flux_limit = heat_feedback_factor * h_limit * (flame_temp - pyrolysis_temp)
    rate_limit = heating_ratio * limit * flux_limit / energy_per_area
    if not all(isfinite(value) and value > 0 for value in (flux_limit, rate_limit)):
        raise ValueError("The supplied inputs did not yield a finite positive spread rate.")

    initial_ratio = sqrt(length0 / limit)
    initial_rate = rate_limit * initial_ratio

    def front_state(time):
        # Exact solution of dx/dt = V_inf sqrt(L_p/L_inf) and
        # dL_p/dx = (L_inf - L_p) / growth_length.
        z = time * rate_limit / (2 * growth_length)
        tanh_z = tanh(z)
        ratio = (initial_ratio + tanh_z) / (1 + initial_ratio * tanh_z)
        log_cosh_ratio = z + log1p(0.5 * (1 - initial_ratio) * expm1(-2 * z))
        front = front0 + 2 * growth_length * log_cosh_ratio
        return front, limit * ratio**2, rate_limit * ratio

    def flame_tip(time):
        front, length, _ = front_state(time)
        return front + heating_ratio * length

    # Bounded by the time the slower initial front alone would reach the edge.
    end = (sample_length - front0) / initial_rate
    if duration_s is not None:
        end = min(end, number(duration_s, "duration", positive=True))
    end = number(end, "trajectory end time", positive=True)
    reaches_edge = flame_tip(end) >= sample_length
    if reaches_edge:
        low, high = 0.0, end
        for _ in range(55):
            mid = (low + high) / 2
            if flame_tip(mid) >= sample_length:
                high = mid
            else:
                low = mid
        end = high

    times = [end * (i / 120) for i in range(121)]
    fronts, lengths, speeds = (
        list(column) for column in zip(*(front_state(time) for time in times))
    )
    heat_lengths = [heating_ratio * length for length in lengths]
    return {
        "spread_rate_mm_s": 1000 * rate_limit,
        "spread_rate_m_s": rate_limit,
        "initial_spread_rate_mm_s": 1000 * initial_rate,
        "limiting_pyrolysis_length_m": limit,
        "limiting_convective_heat_flux_W_m2": flux_limit,
        "limiting_reynolds_number": re_limit,
        "effective_heat_feedback_factor": heat_feedback_factor,
        "sample_length_m": sample_length,
        "end_reason": "heating_zone_reached_edge" if reaches_edge else "duration_elapsed",
        "edge_influence_time_s": end if reaches_edge else None,
        "time_s": times,
        "spread_rate_series_mm_s": [1000 * rate for rate in speeds],
        "pyrolysis_front_position_m": fronts,
        "pyrolysis_base_position_m": [front - length for front, length in zip(fronts, lengths)],
        "pyrolysis_length_m": lengths,
        "effective_flame_length_m": [length + heat for length, heat in zip(lengths, heat_lengths)],
        "effective_flame_tip_position_m": [front + heat for front, heat in zip(fronts, heat_lengths)],
        "convective_heat_flux_W_m2": [flux_limit * sqrt(limit / length) for length in lengths],
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
        raise ValueError("Provide one matching THM-06 setup and material.")
    setup, fuel = setups[0], fuels[0]
    if (
        scenario["gravity"] != setup["gravity_regime"]
        or scenario["flow_direction"] != "concurrent"
        or setup["flow_direction"] != "concurrent"
    ):
        raise ValueError("THM-06 requires concurrent flow and the gravity regime of the setup.")

    air = scenario["ambient"]
    conditions = {
        "air_speed_m_s": quantity(air, "air_speed", "cm/s") / 100,
        "pressure_kPa": quantity(air, "pressure", "kPa"),
        "oxygen_pct": number(quantity(air, "oxygen", "%"), "oxygen percentage", maximum=100),
        "ambient_temperature_K": quantity(air, "temperature", "K"),
        "sample_length_m": quantity(scenario, "sample_length", "m"),
        "sample_width_m": quantity(scenario, "sample_width", "m"),
        "sample_thickness_m": quantity(scenario, "specimen_thickness", "m"),
    }
    profiles = [
        item for item in fuel["calibrations"]
        if item["setup_id"] == setup_id and calibrated_conditions(item, conditions)
    ]
    if len(profiles) != 1:
        raise ValueError(
            "Provide one calibration that covers the airflow, atmosphere and sample geometry."
        )
    profile = profiles[0]
    ref = profile["reference"]
    thickness_range = profile["bounds"]["sample_thickness_m"]
    if "areal_mass_kg_m2" in profile["thermal"] and thickness_range[0] != thickness_range[1]:
        raise ValueError("Use density and a reference thickness for a variable-thickness profile.")
    reference_conditions = {
        **conditions,
        "air_speed_m_s": ref["air_speed_m_s"],
        "pressure_kPa": ref["pressure_kPa"],
        "ambient_temperature_K": ref["ambient_temperature_K"],
        "oxygen_pct": ref["oxygen_pct"],
        "sample_thickness_m": ref.get("sample_thickness_m", conditions["sample_thickness_m"]),
        "sample_width_m": ref.get("sample_width_m", conditions["sample_width_m"]),
        "sample_length_m": ref.get("sample_length_m", conditions["sample_length_m"]),
    }
    if not calibrated_conditions(profile, reference_conditions):
        raise ValueError("The reference conditions must lie within the calibrated envelope.")

    options = {}
    for key, unit, argument in (
        ("initial_pyrolysis_length", "m", "initial_pyrolysis_length_m"),
        ("initial_front_position", "m", "initial_front_position_m"),
        ("duration", "s", "duration_s"),
    ):
        if key in scenario:
            options[argument] = quantity(scenario, key, unit)
    result = model_concurrent_flow_boundary_layer_spread(
        conditions["air_speed_m_s"], conditions["pressure_kPa"],
        conditions["ambient_temperature_K"], conditions["sample_length_m"],
        thermal=profile["thermal"], gas=profile["gas"], calibration=profile,
        sample_thickness_m=conditions["sample_thickness_m"], **options,
    )
    comparisons = []
    for check in profile.get("spread_rate_checks", []):
        check_conditions = {key: check.get(key, value) for key, value in reference_conditions.items()}
        if not calibrated_conditions(profile, check_conditions):
            raise ValueError("A spread-rate check lies outside the calibration bounds.")
        check_result = model_concurrent_flow_boundary_layer_spread(
            check_conditions["air_speed_m_s"], check_conditions["pressure_kPa"],
            check_conditions["ambient_temperature_K"], check_conditions["sample_length_m"],
            thermal=profile["thermal"], gas=profile["gas"], calibration=profile,
            sample_thickness_m=check_conditions["sample_thickness_m"],
        )
        predicted = check_result["spread_rate_mm_s"]
        observed = number(check["spread_rate_mm_s"], "observed spread rate", positive=True)
        comparisons.append(dict(
            check, model_spread_rate_mm_s=predicted,
            model_minus_observed_mm_s=predicted - observed,
        ))

    result.update(
        model_id=MODEL_ID,
        status="model_estimate",
        evidence_boundary="Laminar, established concurrent flow over thin solid fuel",
        setup_id=setup_id,
        material_id=fuel["id"],
        calibration_id=profile["id"],
        illustrative=evidence["provenance"]["illustrative"],
        provenance=evidence["provenance"],
        conditions=conditions,
        evidence_bounds=profile["bounds"],
        spread_rate_checks=comparisons,
        sources=[
            {"role": "model_inputs", "url": profile["source_url"], "locator": profile["source_locator"]},
            {"role": "reference_conditions", "url": ref["source_url"], "locator": ref["source_locator"]},
            {"role": "method", "url": METHOD_URL, "locator": "Eqs. 1 to 5, forced-flow limit"},
        ] + profile.get("additional_sources", []),
        limitations=[
            "Use established flame spread over thermally thin material in laminar forced flow.",
            "The model uses an effective heat feedback factor and a prescribed flame-length closure.",
            "Oxygen selects the evidence profile and its effective flame temperature.",
            "The convective heat flux is an effective estimate under the radiation-balance approximation.",
            "The time origin is the supplied established front state.",
            "The trajectory ends before the downstream edge alters the heating zone.",
            "The result excludes ignition, blowoff, quenching, overshoot and burnout after the edge.",
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
