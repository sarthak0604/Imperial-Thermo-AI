"""THM-19 sealed, well-mixed cabin response to a prescribed fire.

Run: python THM-19/thm_19.py THM-19/THM-19_input.json
Developed with SI assistance from OpenAI Codex.
"""

import argparse
import json
from math import expm1, fsum, isfinite
from pathlib import Path


MODEL_ID = "THM-19"


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
MOLE_MASS = {"oxygen": 0.031998, "carbon_dioxide": 0.044009, "carbon_monoxide": 0.028010}


def series(record, name, size, *, low=None):
    values = record[name]
    if not isinstance(values, list) or len(values) != size:
        raise ValueError(f"{name} must contain one value per timestamp.")
    return [number(value, name, low) for value in values]


def thermal_weights(z):
    if z < 1e-3:
        return (
            1 - z / 2 + z**2 / 6 - z**3 / 24 + z**4 / 120,
            0.5 - z / 6 + z**2 / 24 - z**3 / 120 + z**4 / 720,
        )
    constant = -expm1(-z) / z
    return constant, (1 - constant) / z


def integrate_moles(time, initial, rates, name):
    moles = [initial]
    for left, right, start, stop in zip(time, time[1:], rates, rates[1:]):
        duration = right - left
        before = moles[-1]
        after = before + duration * (start + stop) / 2
        minimum = min(before, after)
        if start < 0 < stop:
            minimum = min(minimum, before - duration * start**2 / (2 * (stop - start)))
        if minimum < -1e-12:
            raise ValueError(f"{name} inventory would become negative inside the simulation.")
        moles.append(max(0, after))
    return moles


def model_closed_cabin_first_law_pressure_rise(cabin, fire):
    time = [number(v, "time_s") for v in fire["time_s"]]
    if len(time) < 2 or any(b <= a for a, b in zip(time, time[1:])):
        raise ValueError("Supply two or more strictly increasing timestamps.")
    hrr = series(fire, "hrr_W", len(time), low=0)
    volume = number(cabin["volume_m3"], "cabin volume", positive=True)
    pressure0 = number(cabin["initial_pressure_kPa"], "initial pressure", positive=True)
    temp0 = number(cabin["initial_temperature_K"], "initial temperature", positive=True)
    wall_temp = number(cabin["wall_temperature_K"], "wall temperature", positive=True)
    ua = number(cabin["wall_ua_W_K"], "wall UA", 0)
    cv = number(cabin["effective_molar_cv_J_mol_K"], "effective molar Cv", positive=True)
    fraction_to_gas = number(cabin["fire_heat_fraction_to_gas"], "heat fraction to gas", 0, 1)
    n0 = pressure0 * 1000 * volume / (R * temp0)

    gas_rates = fire.get("species")
    assumptions = []
    tracked = {}
    if gas_rates is None:
        total_moles = [n0] * len(time)
        assumptions.append("Initial total gas moles are held constant because no species budget was supplied.")
    else:
        inputs = (
            ("oxygen", "oxygen_consumption_kg_s", -1),
            ("carbon_dioxide", "co2_production_kg_s", 1),
            ("carbon_monoxide", "co_production_kg_s", 1),
        )
        initial = cabin["initial_mole_fractions"]
        initial_moles = {
            name: n0 * number(initial[name], f"initial {name} mole fraction", 0, 1)
            for name, _, _ in inputs
        }
        if fsum(initial_moles.values()) > n0:
            raise ValueError("Tracked initial mole fractions must sum to at most one.")
        for name, channel, sign in inputs:
            rates = [sign * v / MOLE_MASS[name] for v in series(gas_rates, channel, len(time), low=0)]
            tracked[name] = integrate_moles(time, initial_moles[name], rates, name)
        other = integrate_moles(
            time, n0 - fsum(initial_moles.values()),
            series(gas_rates, "other_net_gas_mol_s", len(time)), "remaining gas",
        )
        total_moles = [fsum(values) for values in zip(other, *tracked.values())]
        if any(value <= 0 for value in total_moles):
            raise ValueError("The simulation must retain a positive total gas inventory.")

    heat_capacity = n0 * cv
    temperature = [temp0]
    heat_to_gas = [0.0]
    for t0, t1, q0, q1 in zip(time, time[1:], hrr, hrr[1:]):
        dt = t1 - t0
        z = ua / heat_capacity * dt
        w0, w1 = thermal_weights(z)
        q_start, q_end = fraction_to_gas * q0, fraction_to_gas * q1
        temperature.append(
            temperature[-1] + (wall_temp - temperature[-1]) * (-expm1(-z))
            + dt / heat_capacity * (w0 * q_start + w1 * (q_end - q_start))
        )
        heat_to_gas.append(heat_to_gas[-1] + dt * (q_start + q_end) / 2)
    pressure = [n * R * temp / (1000 * volume) for n, temp in zip(total_moles, temperature)]
    pressure[0] = pressure0
    changes = [value - pressure0 for value in pressure]
    output = {
        "time_s": time, "hrr_W": hrr, "temperature_K": temperature, "pressure_kPa": pressure,
        "pressure_change_kPa": changes, "total_gas_moles": total_moles,
        "sampled_peak_pressure_change_kPa": max(changes),
        "sampled_peak_temperature_K": max(temperature),
        "cumulative_fire_heat_to_gas_kJ": [value / 1000 for value in heat_to_gas],
        "cumulative_wall_heat_loss_kJ": [
            (heat - heat_capacity * (temp - temp0)) / 1000
            for heat, temp in zip(heat_to_gas, temperature)
        ],
        "assumptions": assumptions,
    }
    for species in MOLE_MASS:
        fractions = [a / b for a, b in zip(tracked[species], total_moles)] if tracked else None
        output[f"{species}_mole_fraction"] = fractions
        output[f"{species}_partial_pressure_kPa"] = (
            [x * p for x, p in zip(fractions, pressure)] if fractions is not None else None
        )
    return output


def run_request(payload):
    request, evidence = payload["request"], payload["evidence"]
    if (request["topic"], request["analysis"]) != ("cabin_fire", "estimate_cabin_response"):
        raise ValueError("Expected cabin_fire / estimate_cabin_response.")
    scenario = request["scenario"]
    matches = [item for item in evidence["fires"] if item["id"] == scenario["fire_id"]]
    if len(matches) != 1:
        raise ValueError("Provide one evidence record matching scenario.fire_id.")
    record = matches[0]

    result = model_closed_cabin_first_law_pressure_rise(scenario["cabin"], record)
    result.update(
        status="model_estimate",
        limitations=[
            "Rigid sealed cabin, uniform conditions and constant effective heat capacity based on initial moles.",
            "Wall temperature and UA are fixed. Fire heat and species source terms are prescribed.",
            "Gas chemistry, condensation and fire feedback are outside the balance. The provided other-gas rate controls additional gas accumulation.",
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
