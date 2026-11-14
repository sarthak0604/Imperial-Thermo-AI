"""THM-12 nonboiling multicomponent droplet vapor-liquid equilibrium.

Run: python THM-12/thm_12.py THM-12/THM-12_input.json
Developed with SI assistance from OpenAI Codex.
"""

import argparse
import json
from math import exp, expm1, fsum, isfinite
from pathlib import Path


MODEL_ID = "THM-12"


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


GAS_CONSTANT_J_MOL_K = 8.31446261815324


def evaporation_history(times, initial_moles, drives, uptake, min_moles, check_pressure):
    """Integrate a lumped inventory balance with nonnegative intermediate states."""
    time = 0.0
    amounts = initial_moles
    history = [(time, amounts)]
    largest_drive = max(drives)
    uptake_total = fsum(uptake)
    steps = 0

    def advance(inventory, total, step):
        result = []
        for amount, drive, supply in zip(inventory, drives, uptake):
            decay = drive / total
            if decay == 0:
                result.append(amount + supply * step)
            else:
                removed_fraction = -expm1(-decay * step)
                result.append(amount * (1 - removed_fraction) + supply * (removed_fraction / decay))
        return result

    for target in times[1:]:
        while time < target:
            total = fsum(amounts)
            step = target - time
            fastest = max(largest_drive, uptake_total)
            if fastest > 0:
                step = min(step, 0.002 * total / fastest)
            next_time = time + step
            steps += 1
            if steps > 50000 or next_time <= time:
                raise ValueError("The inventory solve exceeded its resolution limit. Shorten duration_s or raise min_total_moles.")
            midpoint = advance(amounts, total, 0.5 * step)
            check_pressure(midpoint)
            updated = advance(amounts, fsum(midpoint), step)
            updated_total = fsum(updated)
            if updated_total <= min_moles:
                portion = (total - min_moles) / (total - updated_total)
                endpoint = [a + portion * (b - a) for a, b in zip(amounts, updated)]
                check_pressure(endpoint)
                history.append((time + portion * step, endpoint))
                return history, "minimum_inventory"
            check_pressure(updated)
            amounts = updated
            time = next_time
        history.append((target, amounts))
    return history, "duration"


def calc_clausius_clapeyron_multicomponent_evap(scenario, profile):
    temperature = number(scenario["t_surface_k"], "surface temperature", positive=True)
    pressure = number(scenario["pressure_kpa"], "ambient pressure", positive=True)
    for field, value in (("t_surface_k", temperature), ("pressure_kpa", pressure)):
        lower, upper = (number(v, field, positive=True) for v in profile["validity"][field])
        if not lower <= value <= upper:
            raise ValueError(f"{field} falls outside the profile range [{lower}, {upper}].")
    components = profile["components"]
    ids = [component["id"] for component in components]
    if len(ids) < 2 or len(set(ids)) != len(ids):
        raise ValueError("Supply at least two uniquely identified liquid components.")
    fractions = scenario["liquid_fractions"]
    ambient = scenario["ambient_partial_pressures_kpa"]
    if set(ids) != set(fractions) or set(ids) != set(ambient):
        raise ValueError("Give a liquid mole fraction and gas partial pressure for every profile component.")
    fractions = [number(fractions[key], f"{key} liquid mole fraction", 0, 1) for key in ids]
    total_fraction = fsum(fractions)
    if abs(total_fraction - 1) > 1e-8:
        raise ValueError("Liquid mole fractions must sum to one.")
    fractions = [fraction / total_fraction for fraction in fractions]
    ambient = [number(ambient[key], f"{key} ambient partial pressure", 0, pressure) for key in ids]
    if fsum(ambient) > pressure:
        raise ValueError("Ambient component partial pressures exceed the chamber pressure.")

    saturation = []
    coefficients = []
    conductances = []
    for component, far_pressure in zip(components, ambient):
        name = component["id"]
        gamma = number(component["activity_coefficient"], f"{name} activity coefficient", positive=True)
        volatile = component.get("volatile", True)
        if type(volatile) is not bool:
            raise ValueError(f"{name} volatile must be a Boolean.")
        conductance = component.get("transfer_conductance_mol_s_kpa")
        if volatile:
            ref_temperature = number(component["reference_temperature_k"], f"{name} reference temperature", positive=True)
            ref_pressure = number(component["reference_vapor_pressure_kpa"], f"{name} reference vapor pressure", positive=True)
            enthalpy = number(component["vaporization_enthalpy_j_mol"], f"{name} vaporization enthalpy", positive=True)
            p_sat = ref_pressure * exp((enthalpy / GAS_CONSTANT_J_MOL_K) * (1 / ref_temperature - 1 / temperature))
        else:
            if far_pressure != 0 or conductance not in (None, 0):
                raise ValueError(f"Nonvolatile component {name} requires zero ambient partial pressure and conductance.")
            p_sat = 0.0
            conductance = 0.0
        if conductance is not None:
            conductance = number(conductance, f"{name} transfer conductance", 0)
        saturation.append(number(p_sat, f"{name} saturation pressure", 0))
        coefficients.append(number(p_sat * gamma, f"{name} activity-adjusted saturation pressure", 0))
        conductances.append(conductance)

    def at(liquid_fractions):
        partial = [fraction * coefficient for fraction, coefficient in zip(liquid_fractions, coefficients)]
        total_partial = fsum(partial)
        if total_partial >= pressure:
            raise ValueError("Vapor pressure reached chamber pressure. The nonboiling model is outside its regime.")
        driving = [surface - far for surface, far in zip(partial, ambient)]
        return [
            {
                "id": name,
                "liquid_mole_fraction": fraction,
                "saturation_pressure_kpa": saturated,
                "surface_partial_pressure_kpa": surface,
                "ambient_partial_pressure_kpa": far,
                "surface_gas_mole_fraction": surface / pressure,
                "vapor_only_mole_fraction": surface / total_partial if total_partial > 0 else None,
                "driving_pressure_kpa": delta,
                "transfer_direction": "evaporating" if delta > 0 else "condensing" if delta < 0 else "equilibrium",
                "net_outward_transfer_mol_s": conductance * delta if conductance is not None else None,
            }
            for name, fraction, saturated, surface, far, delta, conductance
            in zip(ids, liquid_fractions, saturation, partial, ambient, driving, conductances)
        ]

    state = at(fractions)
    result = {
        "status": "model_estimate",
        "components": state,
        "surface_vapor_pressure_kpa": fsum(row["surface_partial_pressure_kpa"] for row in state),
        "liquid_mass_peclet": None,
        "plot_data": {
            "component_id": ids,
            "surface_partial_pressure_kpa": [row["surface_partial_pressure_kpa"] for row in state],
            "ambient_partial_pressure_kpa": ambient,
            "net_outward_transfer_mol_s": [row["net_outward_transfer_mol_s"] for row in state],
        },
    }
    mixing = scenario.get("liquid_transport")
    if mixing is not None:
        radius = number(mixing["radius_m"], "liquid radius", positive=True)
        velocity = number(mixing["circulation_speed_m_s"], "liquid circulation speed", 0)
        diffusivity = number(mixing["mass_diffusivity_m2_s"], "liquid mass diffusivity", positive=True)
        result["liquid_mass_peclet"] = velocity * radius / diffusivity

    evolution = scenario.get("time_evolution")
    if evolution is not None:
        if any(value is None for value in conductances):
            raise ValueError("Time evolution requires a transfer conductance for every volatile component.")
        initial = number(evolution["initial_total_moles"], "initial total moles", positive=True)
        minimum = number(evolution.get("min_total_moles", initial * 1e-4), "minimum total moles", positive=True)
        if minimum >= initial:
            raise ValueError("Minimum inventory must be below the initial inventory.")
        duration = number(evolution["duration_s"], "duration", positive=True)
        count = evolution.get("plot_points", 101)
        if type(count) is not int or not 2 <= count <= 2001:
            raise ValueError("plot_points must be an integer from 2 to 2001.")
        targets = [duration * (index / (count - 1)) for index in range(count)]
        def check_pressure(amounts):
            surface_pressure = fsum(amount * p for amount, p in zip(amounts, coefficients)) / fsum(amounts)
            if surface_pressure >= pressure:
                raise ValueError("Vapor pressure reached chamber pressure during the inventory solve.")

        history, stop = evaporation_history(
            targets, [initial * fraction for fraction in fractions],
            [g * p for g, p in zip(conductances, coefficients)],
            [g * p for g, p in zip(conductances, ambient)], minimum, check_pressure,
        )
        series = {"time_s": [], "total_liquid_moles": [], "by_component": {
            key: {"liquid_mole_fraction": [], "liquid_moles": [], "net_outward_transfer_mol_s": []}
            for key in ids
        }}
        for time, amounts in history:
            total = fsum(amounts)
            series["time_s"].append(time)
            series["total_liquid_moles"].append(total)
            for amount, row in zip(amounts, at([amount / total for amount in amounts])):
                column = series["by_component"][row["id"]]
                column["liquid_mole_fraction"].append(row["liquid_mole_fraction"])
                column["liquid_moles"].append(amount)
                column["net_outward_transfer_mol_s"].append(row["net_outward_transfer_mol_s"])
        result["stop_reason"] = stop
        result["plot_data"]["evolution"] = series
    return result

def run_request(payload):
    request, evidence = payload["request"], payload["evidence"]
    if (request["topic"], request["analysis"]) != ("droplet_evaporation", "estimate_multicomponent_evaporation"):
        raise ValueError("Expected droplet_evaporation / estimate_multicomponent_evaporation.")
    scenario = request["scenario"]
    matches = [item for item in evidence["profiles"] if item["id"] == scenario["profile_id"]]
    if len(matches) != 1:
        raise ValueError("Provide one evidence record matching scenario.profile_id.")
    record = matches[0]
    result = calc_clausius_clapeyron_multicomponent_evap(scenario, record)

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
