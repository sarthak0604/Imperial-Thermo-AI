"""THM-13 optically thin radiative quench heat balance.

Run: python THM-13/thm_13.py THM-13/THM-13_input.json
Developed with SI assistance from OpenAI Codex.
"""

import argparse
import json
from math import fsum, isfinite
from pathlib import Path


MODEL_ID = "THM-13"


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


STEFAN_BOLTZMANN_W_M2_K4 = 5.670374419e-8
GAS_CONSTANT_J_MOL_K = 8.31446261815324


def covered(value, bounds, field, low=0, high=None):
    value = number(value, field, low, high)
    lower, upper = (number(v, f"{field} bound", low, high) for v in bounds)
    if not lower <= value <= upper:
        raise ValueError(f"{field} falls outside the profile range [{lower}, {upper}].")
    return value, lower, upper


def evaluate_radiative_quenching_extinction(scenario, profile):
    for key in ("material_id", "setup_id", "gravity", "flow_direction"):
        if profile[key] != scenario[key]:
            raise ValueError(f"Scenario and profile must agree on {key}.")
    validity = profile["validity"]
    speed, speed_lo, speed_hi = covered(
        scenario["u_flow_ms"], validity["u_flow_ms"], "u_flow_ms",
    )
    oxygen, oxygen_lo, oxygen_hi = covered(
        scenario["x_o2"], validity["x_o2"], "x_o2", high=1,
    )
    pressure, _, _ = covered(
        scenario["pressure_kpa"], validity["pressure_kpa"], "pressure_kpa",
    )
    inlet_temperature, _, _ = covered(
        scenario["t_amb_k"], validity["t_amb_k"], "t_amb_k",
    )
    number(pressure, "pressure", positive=True)
    number(inlet_temperature, "inlet temperature", positive=True)
    gas_temperature = number(profile["flame_temperature_k"], "flame temperature", positive=True)
    surface_temperature = number(profile["surface_temperature_k"], "surface temperature", positive=True)
    surroundings = number(
        scenario.get("surroundings_temperature_k", inlet_temperature),
        "surroundings temperature", positive=True,
    )
    if min(gas_temperature, surface_temperature) < surroundings:
        raise ValueError("The radiative-loss model requires gas and surface at or above surroundings temperature.")
    emissivity, _, _ = covered(
        scenario["surface_emissivity"], validity["surface_emissivity"], "surface_emissivity", high=1,
    )
    planck = profile["planck_mean_per_atm_m_inv"]
    gas_fractions = {}
    for field, species in (("co2_frac", "co2"), ("h2o_frac", "h2o")):
        gas_fractions[species], _, _ = covered(scenario[field], validity[field], field, high=1)
    if fsum(gas_fractions.values()) > 1:
        raise ValueError("CO2 and H2O mole fractions in the radiating gas must sum to at most one.")
    pressure_atm = pressure / 101.325
    by_species = {
        species: pressure_atm * fraction * number(planck[species], f"{species} Planck mean", 0)
        for species, fraction in gas_fractions.items()
    }
    soot = number(profile.get("soot_absorption_m_inv", 0), "effective soot absorption", 0)
    absorption = fsum((*by_species.values(), soot))
    beam_length = number(profile["optical_path_length_m"], "optical path length", positive=True)
    optical_depth = absorption * beam_length
    if optical_depth > 0.1:
        raise ValueError("Optical depth exceeds 0.1. Supply optically thin conditions for this model.")
    volume_per_area = number(profile["gas_volume_per_reference_area_m"], "gas volume per reference area", positive=True)
    area_ratio = number(profile.get("emitting_surface_to_reference_area", 1), "surface area ratio", 0)
    effectiveness = number(profile["oxygen_heat_coupling_factor"], "oxygen heat coupling factor", 0, 1, positive=True)
    heat = number(profile["heat_per_mol_oxygen_j"], "heat per mole of oxygen", positive=True)
    diffusion_speed = 0.0
    if "oxygen_diffusion" in profile:
        diffusion = profile["oxygen_diffusion"]
        diffusivity = number(diffusion["diffusivity_m2_s"], "oxygen diffusivity", positive=True)
        thickness = number(diffusion["length_m"], "oxygen diffusion length", positive=True)
        diffusion_speed = number(diffusivity / thickness, "oxygen diffusion equivalent speed", positive=True)

    coefficient = effectiveness * (pressure * 1000 / (GAS_CONSTANT_J_MOL_K * inlet_temperature)) * heat
    q_gas = (
        4 * STEFAN_BOLTZMANN_W_M2_K4 * absorption * volume_per_area
        * (gas_temperature ** 4 - surroundings ** 4)
    )
    q_surface = (
        emissivity * STEFAN_BOLTZMANN_W_M2_K4 * area_ratio
        * (surface_temperature ** 4 - surroundings ** 4)
    )
    q_other = number(profile.get("other_loss_w_m2", 0), "other loss", 0)
    q_loss = fsum((q_gas, q_surface, q_other))
    effective_speed = speed + diffusion_speed
    q_chem = coefficient * oxygen * effective_speed
    threshold_speed = q_loss / (coefficient * oxygen) - diffusion_speed if oxygen > 0 else None
    threshold_oxygen = q_loss / (coefficient * effective_speed) if effective_speed > 0 else None
    margin = q_chem - q_loss
    tolerance = 1e-12 * max(q_chem, q_loss)
    condition = "below_heat_balance" if margin < -tolerance else (
        "above_heat_balance" if margin > tolerance else "on_heat_balance"
    )
    speed_points = sorted({speed, speed_lo, speed_hi, *(
        speed_lo + (speed_hi - speed_lo) * (index / 100) for index in range(1, 100)
    )})
    # Clip the exported speed domain analytically to both oxygen bounds.
    branch = None
    branch_speed_range = None
    if q_loss > 0 and oxygen_hi > 0:
        start = max(speed_lo, q_loss / (coefficient * oxygen_hi) - diffusion_speed)
        end = min(speed_hi, q_loss / (coefficient * oxygen_lo) - diffusion_speed) if oxygen_lo > 0 else speed_hi
        if start < end:
            speeds = [start, *(u for u in speed_points if start < u < end), end]
            branch_speed_range = [start, end]
            branch = {
                "form": "table",
                "points": [
                    [u, 100 * min(oxygen_hi, max(oxygen_lo, q_loss / (coefficient * (u + diffusion_speed))))]
                    for u in speeds
                ],
            }
    speed_covered = threshold_speed is not None and speed_lo <= threshold_speed <= speed_hi
    oxygen_covered = threshold_oxygen is not None and oxygen_lo <= threshold_oxygen <= oxygen_hi
    return {
        "status": "model_estimate",
        "heat_balance_status": condition,
        "air_speed_m_s": speed,
        "inlet_oxygen_mole_fraction": oxygen,
        "optical_depth": optical_depth,
        "oxygen_diffusion_equivalent_speed_m_s": diffusion_speed,
        "species_absorption_m_inv": by_species,
        "effective_soot_absorption_m_inv": soot,
        "thermal_budget_w_m2": {
            "chemical_input": q_chem,
            "gas_radiation": q_gas,
            "surface_radiation": q_surface,
            "other_loss": q_other,
            "loss_total": q_loss,
            "net_margin": margin,
        },
        "critical_speed_m_s": threshold_speed if speed_covered else None,
        "critical_oxygen_mole_fraction": threshold_oxygen if oxygen_covered else None,
        "critical_speed_within_evidence": speed_covered,
        "critical_oxygen_within_evidence": oxygen_covered,
        "quench_branch": branch,
        "quench_speed_range_m_s": branch_speed_range,
        "plot_data": {
            "air_speed_m_s": speed_points,
            "chemical_input_w_m2": [coefficient * oxygen * (u + diffusion_speed) for u in speed_points],
            "heat_loss_w_m2": [q_loss for u in speed_points],
            "net_heat_margin_w_m2": [coefficient * oxygen * (u + diffusion_speed) - q_loss for u in speed_points],
        },
    }

def run_request(payload):
    request, evidence = payload["request"], payload["evidence"]
    if (request["topic"], request["analysis"]) != ("extinction", "estimate_radiative_quench"):
        raise ValueError("Expected extinction / estimate_radiative_quench.")
    scenario = request["scenario"]
    matches = [item for item in evidence["profiles"] if item["id"] == scenario["profile_id"]]
    if len(matches) != 1:
        raise ValueError("Provide one evidence record matching scenario.profile_id.")
    record = matches[0]
    result = evaluate_radiative_quenching_extinction(scenario, record)

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
