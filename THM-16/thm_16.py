"""THM-16: one-dimensional transient conduction with solid pyrolysis.

Install NumPy and SciPy, then run the example from the repository root:

    python THM-16/thm_16.py THM-16/THM-16_request.json THM-16/THM-16_evidence.json

The example inputs are synthetic. This solver was developed with SI assistance
from OpenAI Codex.
"""

import argparse
import json
from math import isfinite
from pathlib import Path


def number(value):
    try:
        return type(value) in (int, float) and isfinite(value)
    except OverflowError:
        return False


def model_solid_pyrolysis_transient_conduction(
    q_ext_wm2, k_s, rho_s, c_s, thickness_m, t_ign_k, *,
    duration_s, ambient_temperature_k, h_front_wm2k, h_back_wm2k, emissivity,
    pyrolysis_pre_exponential_s_inv, pyrolysis_activation_energy_j_mol,
    heat_of_pyrolysis_j_kg, nodes=41,
):
    """Return a pre-ignition slab simulation in SI units.

    q_ext_wm2 is the absorbed heat flux entering the front face before surface
    losses. The flux is constant over the requested exposure. A threshold
    crossing ends the pre-ignition simulation.
    """
    import numpy as np
    from scipy.integrate import solve_ivp
    from scipy.sparse import bmat, diags

    positive = {
        "k_s": k_s, "rho_s": rho_s, "c_s": c_s, "thickness_m": thickness_m,
        "t_ign_k": t_ign_k, "duration_s": duration_s, "ambient_temperature_k": ambient_temperature_k,
        "pyrolysis_pre_exponential_s_inv": pyrolysis_pre_exponential_s_inv,
        "pyrolysis_activation_energy_j_mol": pyrolysis_activation_energy_j_mol,
        "heat_of_pyrolysis_j_kg": heat_of_pyrolysis_j_kg,
    }
    for name, value in positive.items():
        if not number(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive.")
    for name, value in {"q_ext_wm2": q_ext_wm2, "h_front_wm2k": h_front_wm2k,
                        "h_back_wm2k": h_back_wm2k, "emissivity": emissivity}.items():
        if not number(value) or value < 0:
            raise ValueError(f"{name} must be finite and nonnegative.")
    if emissivity > 1 or t_ign_k <= ambient_temperature_k:
        raise ValueError("Emissivity must be at most 1 and the ignition threshold must exceed ambient temperature.")
    if type(nodes) is not int or not 3 <= nodes <= 401:
        raise ValueError("nodes must be an integer between 3 and 401.")

    x = np.linspace(0, thickness_m, nodes)
    dx = x[1]
    # Surface nodes represent half-width control volumes.
    weights = np.full(nodes, dx)
    weights[[0, -1]] = dx / 2
    diffusivity = k_s / (rho_s * c_s)
    radiation = emissivity * 5.670374419e-8
    ambient = ambient_temperature_k
    ambient_fourth = ambient ** 4
    activation_temperature = pyrolysis_activation_energy_j_mol / 8.314462618

    def reaction_rate(temperature, fraction):
        return pyrolysis_pre_exponential_s_inv * np.exp(-activation_temperature / temperature) * fraction

    def heat_balance(_time, state):
        temperature = state[:nodes]
        remaining = np.clip(state[nodes:], 0, 1)
        rate = reaction_rate(temperature, remaining)
        d_temperature = -heat_of_pyrolysis_j_kg / c_s * rate

        # Heat flux is positive in the direction of increasing depth.
        internal_flux = -k_s * np.diff(temperature) / dx
        front_loss = h_front_wm2k * (temperature[0] - ambient) + radiation * (temperature[0] ** 4 - ambient_fourth)
        back_loss = h_back_wm2k * (temperature[-1] - ambient) + radiation * (temperature[-1] ** 4 - ambient_fourth)
        flux = np.r_[q_ext_wm2 - front_loss, internal_flux, back_loss]
        d_temperature -= np.diff(flux) / (rho_s * c_s * weights)
        return np.r_[d_temperature, -rate]

    def reaches_ignition(_time, state):
        return state[0] - t_ign_k

    reaches_ignition.direction = 1
    reaches_ignition.terminal = True
    local = diags(np.ones(nodes), format="csc")
    conduction = diags([np.ones(nodes - 1), np.ones(nodes), np.ones(nodes - 1)], [-1, 0, 1], format="csc")
    solution = solve_ivp(
        heat_balance, (0, duration_s), np.r_[np.full(nodes, ambient), np.ones(nodes)],
        method="BDF", jac_sparsity=bmat([[conduction, local], [local, local]], format="csc"),
        dense_output=True, events=reaches_ignition, rtol=1e-7, atol=1e-9,
    )
    if not solution.success:
        raise ValueError(f"THM-16 solver failed: {solution.message}")

    ignition_time = float(solution.t_events[0][0]) if solution.t_events[0].size else None
    time = np.linspace(0, solution.t[-1], 121)
    states = solution.sol(time)
    temperature = states[:nodes]
    remaining = np.clip(states[nodes:], 0, 1)
    mass_flux = rho_s * (weights @ reaction_rate(temperature, remaining))
    penetration = [penetration_depth(x, profile, ambient) for profile in temperature.T]
    return {
        "model_id": "THM-16", "time_to_ignition_s": ignition_time,
        "criterion_reached": ignition_time is not None,
        "evidence_boundary": "Theoretical / Partial-g Bound",
        "ignition_criterion_K": t_ign_k, "requested_exposure_s": duration_s,
        "absorbed_heat_flux_W_m2": q_ext_wm2,
        "time_s": time.tolist(), "depth_m": x.tolist(),
        "surface_temperature_K": temperature[0].tolist(),
        "back_temperature_K": temperature[-1].tolist(),
        "temperature_by_depth_K": temperature.tolist(),
        "thermal_penetration_depth_m": penetration,
        "fourier_number": (diffusivity * time / thickness_m ** 2).tolist(),
        "pyrolysis_mass_flux_kg_m2_s": mass_flux.tolist(),
    }


def penetration_depth(depth, temperature, ambient):
    """Locate where the temperature rise falls to 1% of the front-face rise."""
    rise = temperature[0] - ambient
    if rise <= 1e-6:
        return 0.0
    threshold = ambient + 0.01 * rise
    for index in range(1, len(depth)):
        if temperature[index] <= threshold:
            fraction = (temperature[index - 1] - threshold) / (temperature[index - 1] - temperature[index])
            return float(depth[index - 1] + fraction * (depth[index] - depth[index - 1]))
    return float(depth[-1])


def read_quantity(record, key, unit):
    quantity = record[key]
    if quantity["unit"] != unit or not number(quantity["value"]):
        raise ValueError(f"{key} must be a finite number in {unit}.")
    return quantity["value"]


def run_request(request, evidence):
    """Run one THM-16 scenario in the units used by the bundled JSON example."""
    if request["topic"] != "ignition" or request["analysis"] != "estimate_ignition":
        raise ValueError("Expected an ignition estimate request.")
    scenario = request["scenario"]
    setup_id = scenario["setup_id"]
    material_ids = scenario["materials"]
    if not isinstance(material_ids, list) or len(material_ids) != 1:
        raise ValueError("Provide one material ID in scenario.materials.")
    setups = [item for item in evidence["setups"] if item["id"] == setup_id]
    materials = [item for item in evidence["materials"] if item["id"] == material_ids[0]]
    if len(setups) != 1 or setups[0]["model"] != "THM-16" or len(materials) != 1:
        raise ValueError("Provide one matching THM-16 setup and material.")
    setup, material = setups[0], materials[0]
    air, exposure = scenario["ambient"], scenario["exposure"]
    if scenario.get("gravity", setup["gravity_regime"]) != setup["gravity_regime"]:
        raise ValueError("The gravity regime must match the setup.")
    pressure = read_quantity(air, "pressure", "kPa")
    oxygen = read_quantity(air, "oxygen", "%")
    speed = read_quantity(air, "air_speed", "cm/s") / 100
    temperature = read_quantity(air, "temperature", "K")
    incident_flux = read_quantity(exposure, "heat_flux", "kW/m2")
    duration = read_quantity(exposure, "heating_time", "s")
    profiles = []
    for profile in material["calibrations"]:
        if profile["setup_id"] != setup_id or profile["pressure_kPa"] != pressure or profile["oxygen_pct"] != oxygen:
            continue
        bounds = (
            (profile["speed_range_m_s"], speed),
            (profile["ambient_temperature_range_K"], temperature),
            (profile["flux_range_kW_m2"], incident_flux),
        )
        if all(low <= value <= high for (low, high), value in bounds) and 0 < duration <= profile["max_heating_time_s"]:
            profiles.append(profile)
    if len(profiles) != 1:
        raise ValueError("The scenario needs one matching calibration within its supported conditions.")
    profile = profiles[0]
    props = material["properties"]
    if "specimen_thickness" in scenario:
        thickness = read_quantity(scenario, "specimen_thickness", "m")
        if thickness != props["thickness_m"]:
            raise ValueError("Specimen thickness must match the material record.")
    absorptivity = props["absorptivity"]
    if not number(absorptivity) or not 0 < absorptivity <= 1:
        raise ValueError("Absorptivity must be greater than zero and at most one.")
    front_h = setup["h_W_m2K"]
    result = model_solid_pyrolysis_transient_conduction(
        incident_flux * 1000 * absorptivity,
        props["conductivity_W_mK"], props["density_kg_m3"], props["cp_J_kgK"],
        props["thickness_m"], profile["t_ign_k"],
        duration_s=duration, ambient_temperature_k=temperature,
        h_front_wm2k=front_h, h_back_wm2k=setup.get("h_back_W_m2K", front_h),
        emissivity=props["emissivity"],
        pyrolysis_pre_exponential_s_inv=props["pyrolysis_pre_exponential_s_inv"],
        pyrolysis_activation_energy_j_mol=props["pyrolysis_activation_energy_j_mol"],
        heat_of_pyrolysis_j_kg=props["heat_of_pyrolysis_j_kg"],
    )
    result.update(
        material_id=material["id"], setup_id=setup_id, calibration_id=profile["id"],
        illustrative=profile.get("illustrative", False),
        source_locator=profile["source_locator"], source_url=profile.get("source_url"),
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path)
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    try:
        request = json.loads(args.request.read_text(encoding="utf-8"))
        evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
        print(json.dumps(run_request(request, evidence), allow_nan=False, indent=2))
    except (OSError, KeyError, ValueError, TypeError, ImportError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
