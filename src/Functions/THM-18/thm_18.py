"""THM-18 gas dilution and fine-water-mist heat-sink estimates.

Run: python THM-18/thm_18.py THM-18/THM-18_input.json
Developed with SI assistance from OpenAI Codex.
"""

import argparse
import json
from math import fsum, isfinite
from pathlib import Path


MODEL_ID = "THM-18"


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

R = 8.314462618


def heat_capacity_integral(species, cold, hot):
    lo, hi = (number(v, "heat capacity temperature bound", positive=True) for v in species["temperature_range_K"])
    if not lo <= cold <= hot <= hi:
        raise ValueError("Temperatures fall outside a species heat capacity range.")
    cp = number(species["cp_at_reference_J_mol_K"], "reference molar heat capacity", positive=True)
    reference = number(species["cp_reference_temperature_K"], "heat capacity reference T", positive=True)
    slope = number(species.get("cp_slope_J_mol_K2", 0), "heat capacity slope")
    cp_start = cp + slope * (cold - reference)
    cp_end = cp + slope * (hot - reference)
    if min(cp_start, cp_end) <= 0:
        raise ValueError("Molar heat capacity must stay positive across the interval.")
    return (cp_start + cp_end) / 2 * (hot - cold)


def calc_inert_suppressant_thermal_capacity(scenario, record):
    pressure = number(scenario["pressure_kPa"], "pressure", positive=True)
    cold = number(scenario["initial_temperature_K"], "initial temperature", positive=True)
    hot = number(scenario["target_temperature_K"], "target temperature", positive=True)
    fraction = number(scenario["agent_mole_fraction"], "added agent mole fraction", 0, 1)
    if hot <= cold:
        raise ValueError("Target temperature must exceed initial temperature.")
    composition = scenario["base_gas_mole_fractions"]
    base = {name: number(x, f"{name} mole fraction", 0, 1) for name, x in composition.items()}
    if abs(fsum(base.values()) - 1) > 1e-9:
        raise ValueError("Base mole fractions must sum to one.")
    agent = record["agent_species"]
    oxygen = record["oxygen_species"]
    if agent == oxygen:
        raise ValueError("An inert agent must be a different species from oxygen.")
    species = record["species"]
    added_agent_heat = heat_capacity_integral(species[agent], cold, hot)
    base_heat = fsum(
        x * heat_capacity_integral(species[name], cold, hot) for name, x in base.items() if x
    )
    mixture_heat = (1 - fraction) * base_heat + fraction * added_agent_heat
    base_oxygen = base.get(oxygen, 0)
    base_agent = base.get(agent, 0)
    moles_per_m3 = pressure * 1000 / (R * cold)
    result = {
        "final_agent_mole_fraction": (1 - fraction) * base_agent + fraction,
        "oxygen_mole_fraction": (1 - fraction) * base_oxygen,
        "oxygen_partial_pressure_kPa": pressure * (1 - fraction) * base_oxygen,
        "mixture_sensible_heat_kJ_mol": mixture_heat / 1000,
        "mixture_sensible_heat_kJ_per_initial_m3": mixture_heat * moles_per_m3 / 1000,
        "change_from_base_kJ_per_initial_m3": (mixture_heat - base_heat) * moles_per_m3 / 1000,
        "initial_molar_density_mol_m3": moles_per_m3,
    }
    if "conduction" in record:
        cond = record["conduction"]
        calibrated_fraction = number(cond["agent_mole_fraction"], "conductivity agent fraction", 0, 1)
        if abs(fraction - calibrated_fraction) <= 1e-9:
            area_over_length = (
                number(cond["area_m2"], "conduction area", positive=True)
                / number(cond["path_length_m"], "conduction path", positive=True)
            )
            base_k = number(cond["base_conductivity_W_m_K"], "base conductivity", positive=True)
            mix_k = number(cond["mix_conductivity_W_m_K"], "mixture conductivity", positive=True)
            result["conduction"] = {
                "base_heat_transfer_W": base_k * area_over_length * (hot - cold),
                "mixture_heat_transfer_W": mix_k * area_over_length * (hot - cold),
            }
    sweep = sorted({fraction, *(index / 20 for index in range(21))})
    result["sweep"] = {
        "agent_mole_fraction": sweep,
        "final_agent_mole_fraction": [(1 - x) * base_agent + x for x in sweep],
        "oxygen_mole_fraction": [(1 - x) * base_oxygen for x in sweep],
        "mixture_sensible_heat_kJ_per_initial_m3": [
            ((1 - x) * base_heat + x * added_agent_heat) * moles_per_m3 / 1000 for x in sweep
        ],
    }
    return result


def water_mist_heat_sink(scenario, record):
    mass = number(scenario["water_mass_kg"], "water mass", 0)
    inlet = number(scenario["inlet_water_temperature_K"], "water inlet T", positive=True)
    final = number(scenario["liquid_endpoint_temperature_K"], "liquid endpoint T", positive=True)
    evaporation = number(scenario["evaporated_fraction"], "evaporated fraction", 0, 1)
    lo, hi = (number(v, "liquid temperature bound", positive=True) for v in record["liquid_temperature_range_K"])
    if not lo <= inlet <= final <= hi:
        raise ValueError("The water heating interval is outside the supplied properties.")
    phase_lo, phase_hi = (
        number(v, "phase change temperature bound", positive=True)
        for v in record["phase_change_temperature_range_K"]
    )
    latent_applicable = phase_lo <= final <= phase_hi
    if evaporation and not latent_applicable:
        raise ValueError("The evaporation enthalpy must apply at the liquid endpoint temperature.")
    cp = number(record["liquid_cp_J_kg_K"], "water heat capacity", positive=True)
    latent = number(record["vaporization_enthalpy_J_kg"], "water enthalpy of evaporation", positive=True)
    sensible = mass * cp * (final - inlet) / 1000
    latent_energy = mass * evaporation * latent / 1000
    result = {
        "sensible_heat_kJ": sensible,
        "latent_heat_kJ": latent_energy,
        "total_water_heat_sink_kJ": sensible + latent_energy,
        "evaporated_water_kg": mass * evaporation,
    }
    if latent_applicable:
        sweep = sorted({evaporation, *(index / 20 for index in range(21))})
        result["sweep"] = {
            "evaporated_fraction": sweep,
            "total_water_heat_sink_kJ": [sensible + mass * fraction * latent / 1000 for fraction in sweep],
        }
    return result


def run_request(payload):
    request, evidence = payload["request"], payload["evidence"]
    if (request["topic"], request["analysis"]) != ("suppression", "estimate_thermal_capacity"):
        raise ValueError("Expected suppression / estimate_thermal_capacity.")
    scenario = request["scenario"]
    matches = [item for item in evidence["profiles"] if item["id"] == scenario["profile_id"]]
    if len(matches) != 1:
        raise ValueError("Provide one evidence record matching scenario.profile_id.")
    record = matches[0]

    pressure = number(scenario["pressure_kPa"], "pressure", positive=True)
    lo, hi = (number(v, "pressure bound", positive=True) for v in record["pressure_range_kPa"])
    if not lo <= pressure <= hi or scenario["mode"] != record["mode"]:
        raise ValueError("Provide a profile matching the mode and pressure conditions.")
    if record["mode"] == "gas_dilution":
        result = calc_inert_suppressant_thermal_capacity(scenario, record)
    elif record["mode"] == "water_mist":
        result = water_mist_heat_sink(scenario, record)
    else:
        raise ValueError("Choose gas_dilution or water_mist.")
    result.update(
        status="thermal_budget", mode=record["mode"],
        limitations=[
            "Heat capacity and conductive transfer estimates do not predict extinction or discharge performance.",
            "Gas dilution assumes ideal mixing at fixed final pressure. Water evaporation fraction is a supplied scenario input.",
        ],
    )

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
