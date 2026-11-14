"""THM-04 oxygen-consumption calorimetry for a sampled duct fire.

Run from the repository root:
    python THM-04/thm_04.py THM-04/THM-04_input.json

See README.md for sensor modes, corrections and data provenance.
Developed with SI assistance from OpenAI Codex.
"""

import argparse
import json
from bisect import bisect_left
from math import fsum, isfinite
from pathlib import Path


MODEL_ID = "THM-04"


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

M_O2 = 0.031998   # kg/mol
M_CO = 0.028010
M_CO2 = 0.044009
M_C = 0.012011
HEAT_PER_KG_O2_J = 13.1e6
CO_OXIDATION_PER_KG_O2_J = 17.69e6
CARBON_OXIDATION_PER_KG_O2_J = 12.30e6
METHOD_URL = "https://doi.org/10.6028/NIST.TN.2077"
SOOT_METHOD_URL = "https://doi.org/10.1016/j.applthermaleng.2010.09.010"


def gas_fractions(record):
    oxygen = number(record["o2_vol_frac"], "dry O2 fraction", minimum=0, maximum=1)
    dioxide = number(record["co2_vol_frac"], "dry CO2 fraction", minimum=0, maximum=1)
    monoxide = number(record["co_vol_frac"], "dry CO fraction", minimum=0, maximum=1)
    residual = 1 - fsum((oxygen, dioxide, monoxide))
    if residual <= 0:
        raise ValueError("Dry gas fractions must leave a positive inert balance.")
    return oxygen, dioxide, monoxide, residual


def exhaust_balance(samples, inlet):
    """Use the dry inert balance and the wet-flow correction of NIST TN 2077."""
    oxygen_in, dioxide_in, monoxide_in, inert_in = gas_fractions(inlet)
    if oxygen_in <= 0:
        raise ValueError("Inlet oxygen fraction must be positive.")
    humidity = number(inlet["water_vapor_vol_frac"], "inlet water fraction", minimum=0)
    if humidity >= 1:
        raise ValueError("Inlet water fraction must be below one.")
    alpha = number(inlet["expansion_factor"], "combustion expansion factor", positive=True)
    molar_mass = number(inlet["gas_molar_mass_kg_mol"], "gas molar mass", positive=True)

    rows = []
    for sample in samples:
        oxygen, dioxide, monoxide, inert = gas_fractions(sample)
        mass_flow = number(sample["mass_flow_kg_s"], "wet exhaust mass flow", minimum=0)
        exit_to_inlet_dry = inert_in / inert
        depletion = (oxygen_in - exit_to_inlet_dry * oxygen) / oxygen_in
        expansion = 1 + depletion * (alpha - 1)
        if expansion <= 0:
            raise ValueError("Gas fractions and the expansion factor yield invalid inlet flow.")
        inlet_dry_mol_s = mass_flow * (1 - humidity) / (expansion * molar_mass)
        rows.append((
            M_O2 * inlet_dry_mol_s * oxygen_in * depletion,
            M_CO * inlet_dry_mol_s * (exit_to_inlet_dry * monoxide - monoxide_in),
            M_CO2 * inlet_dry_mol_s * (exit_to_inlet_dry * dioxide - dioxide_in),
        ))
    return rows


def optional_channel(samples, key, *, minimum=None):
    present = [key in sample for sample in samples]
    if not any(present):
        return [None] * len(samples)
    if not all(present):
        raise ValueError(f"Provide {key} for every sample or omit the channel.")
    return [number(sample[key], key, minimum=minimum) for sample in samples]


def paired_balance(samples):
    """Use measured inlet and outlet mass flows of oxygen."""
    oxygen = [
        number(sample["inlet_o2_kg_s"], "inlet oxygen mass flow", minimum=0)
        - number(sample["outlet_o2_kg_s"], "outlet oxygen mass flow", minimum=0)
        for sample in samples
    ]
    return list(zip(
        oxygen,
        optional_channel(samples, "net_co_kg_s"),
        optional_channel(samples, "net_co2_kg_s"),
    ))


def interpolate_row(times, rows, point):
    index = bisect_left(times, point)
    if times[index] == point:
        return rows[index]
    weight = (point - times[index - 1]) / (times[index] - times[index - 1])
    return tuple(
        None if left is None else (1 - weight) * left + weight * right
        for left, right in zip(rows[index - 1], rows[index])
    )


def select_window(times, rows, window):
    if window is None:
        return times, rows
    start, end = (number(t, "time window endpoint") for t in window)
    if not times[0] <= start < end <= times[-1]:
        raise ValueError("time_window_s must increase within the sampled time range.")
    inside = [i for i, t in enumerate(times) if start < t < end]
    return (
        [start, *(times[i] for i in inside), end],
        [interpolate_row(times, rows, start), *(rows[i] for i in inside),
         interpolate_row(times, rows, end)],
    )


def integral_kJ(times, watts):
    cumulative = [0.0]
    for index in range(1, len(times)):
        dt = times[index] - times[index - 1]
        energy = (watts[index - 1] / 2000 + watts[index] / 2000) * dt
        cumulative.append(cumulative[-1] + energy)
    return cumulative


def estimate_hrr_oxygen_consumption_calorimetry(
    samples, *, measurement_method, inlet=None, heat_per_kg_o2_J=HEAT_PER_KG_O2_J,
    time_window_s=None,
):
    """Return the heat release, species rates and an optional reference comparison."""
    if not isinstance(samples, list) or len(samples) < 2:
        raise ValueError("Provide at least two synchronized samples.")
    times = [number(sample["time_s"], "time_s") for sample in samples]
    if any(right <= left for left, right in zip(times, times[1:])):
        raise ValueError("Samples must be in strictly increasing timestamp order.")
    heat_per_kg_o2_J = number(heat_per_kg_o2_J, "heat per kg of O2", positive=True)

    if measurement_method == "exhaust_mass_flow" and inlet is not None:
        rates = exhaust_balance(samples, inlet)
    elif measurement_method == "paired_oxygen_mass_flow":
        rates = paired_balance(samples)
    else:
        raise ValueError(
            "Use exhaust_mass_flow with inlet conditions or paired_oxygen_mass_flow."
        )

    soot = optional_channel(samples, "soot_carbon_kg_s", minimum=0)
    reference = optional_channel(samples, "reference_hrr_W")
    rows = []
    for (oxygen, co, co2), carbon, expected in zip(rates, soot, reference):
        co_oxygen = (co or 0) * 0.5 * M_O2 / M_CO
        soot_oxygen = (carbon or 0) * M_O2 / M_C
        co_adjustment = (heat_per_kg_o2_J - CO_OXIDATION_PER_KG_O2_J) * co_oxygen
        soot_adjustment = (heat_per_kg_o2_J - CARBON_OXIDATION_PER_KG_O2_J) * soot_oxygen
        hrr = heat_per_kg_o2_J * oxygen + co_adjustment + soot_adjustment
        rows.append((hrr, oxygen, co, co2, co_adjustment, soot_adjustment, expected))

    times, rows = select_window(times, rows, time_window_s)
    hrr, oxygen, co, co2, co_correction, soot_correction, reference = (
        list(column) for column in zip(*rows)
    )
    if any(value is not None and not isfinite(value) for row in rows for value in row):
        raise ValueError("Inputs yielded a non-finite calorimetry result.")
    energy = integral_kJ(times, hrr)
    if not all(isfinite(value) for value in energy):
        raise ValueError("The integration window yielded a non-finite heat release.")
    peak = max(hrr)
    warnings = []
    if any(value < 0 for value in hrr):
        warnings.append("Signed negative HRR samples were retained. Check baseline and channel timing.")
    if co[0] is None:
        warnings.append("CO correction is unavailable for these inputs.")
    if soot[0] is None:
        warnings.append("Soot correction is unavailable for these inputs.")

    result = {
        "time_s": times,
        "hrr_W": hrr,
        "hrr_kW": [value / 1000 for value in hrr],
        "cumulative_heat_kJ": energy,
        "total_heat_release_kJ": energy[-1],
        "peak_hrr_W": peak,
        "peak_hrr_time_s": times[hrr.index(peak)],
        "oxygen_consumption_kg_s": oxygen,
        "co_production_kg_s": None if co[0] is None else co,
        "co2_production_kg_s": None if co2[0] is None else co2,
        "co_correction_W": None if co[0] is None else co_correction,
        "soot_correction_W": None if soot[0] is None else soot_correction,
        "heat_per_kg_o2_J": heat_per_kg_o2_J,
        "warnings": warnings,
    }
    if reference[0] is not None:
        reference_energy = integral_kJ(times, reference)[-1]
        if not isfinite(reference_energy):
            raise ValueError("The benchmark integration yielded a non-finite heat release.")
        result["benchmark_check"] = {
            "reference_hrr_W": reference,
            "reference_total_heat_kJ": reference_energy,
            "reference_peak_hrr_W": max(reference),
            "model_minus_reference_kJ": energy[-1] - reference_energy,
        }
    return result


def run_request(payload):
    request, evidence = payload["request"], payload["evidence"]
    if (request["topic"], request["analysis"]) != ("heat_release", "estimate_hrr"):
        raise ValueError("Expected a heat_release / estimate_hrr request.")
    scenario = request["scenario"]
    run_id = scenario["run_id"]
    matches = [item for item in evidence["runs"] if item["id"] == run_id]
    if len(matches) != 1:
        raise ValueError("Provide one evidence run matching scenario.run_id.")
    run = matches[0]
    method = run["measurement_method"]
    if method == "exhaust_mass_flow" and run["gas_basis"] != "dry":
        raise ValueError("Provide dry mole fractions for exhaust_mass_flow.")
    result = estimate_hrr_oxygen_consumption_calorimetry(
        run["samples"], measurement_method=method, inlet=run.get("inlet"),
        heat_per_kg_o2_J=run.get("heat_per_kg_o2_J", HEAT_PER_KG_O2_J),
        time_window_s=scenario.get("time_window_s"),
    )
    result.update(
        model_id=MODEL_ID,
        status="data_reduction",
        evidence_boundary="Oxygen consumption calorimetry",
        run_id=run_id,
        measurement_method=method,
        illustrative=evidence["provenance"]["illustrative"],
        provenance=evidence["provenance"],
        sources=[
            {"role": "measurements", "url": run["source_url"], "locator": run["source_locator"]},
            {"role": "calorimetry_method", "url": METHOD_URL, "locator": "Eqs. 4, 6, 9 and 12"},
        ],
        limitations=[
            "Use spatially representative, synchronized and calibrated measurements.",
            "The integration covers the returned time window.",
            "The exhaust balance treats the residual dry gas as conserved inert gas.",
        ],
    )
    if result["soot_correction_W"] is not None:
        result["sources"].append({"role": "soot_method", "url": SOOT_METHOD_URL})
    if "benchmark_check" in result:
        benchmark = run["benchmark"]
        result["benchmark_check"].update(
            source_url=benchmark["source_url"], source_locator=benchmark["source_locator"],
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
