# THM-18 · Suppression-agent heat capacity

Estimate a gas mixture's heat-sink capacity and dilution, or calculate how much heat a quantity of water mist absorbs under a specified evaporation assumption.

## Run

From the repository root in PowerShell, use the existing project Python or any Python 3.10 or later. This model uses the standard library.

```powershell
.\.venv\Scripts\python.exe src/Functions/THM-18/thm_18.py src/Functions/THM-18/THM-18_input.json
```

The CLI prints JSON. The backend can pass the parsed [input file](../../src/Functions/THM-18/THM-18_input.json) directly.

```python
from request_planner.function_registry import run_model

result = run_model("THM-18", payload)
```

The AI fills `request` with the scenario. Retrieval supplies the matching `evidence` records and their source links. The model accepts fresh records in this format.

## Input

Set `request.topic = "suppression"` and `request.analysis = "estimate_thermal_capacity"`. In `scenario`, set `profile_id`, `mode`, and `pressure_kPa`. Supply the corresponding profile under `evidence.profiles` with applicable pressure and property ranges.

| Mode | Scenario and matching evidence |
| --- | --- |
| `gas_dilution` | Supply `initial_temperature_K`, `target_temperature_K`, `agent_mole_fraction` as the final share added by dilution, and `base_gas_mole_fractions` summing to one. If the original gas already contains the agent, the output `final_agent_mole_fraction` includes both the original and added portions. The profile names `agent_species` and `oxygen_species`, and supplies `species` properties for each participating gas. Each record gives `cp_at_reference_J_mol_K`, `cp_reference_temperature_K`, `temperature_range_K`, and optionally `cp_slope_J_mol_K2`. The same format accepts nitrogen, helium, CO₂, or other supported diluents. |
| `water_mist` | Supply `water_mass_kg`, `inlet_water_temperature_K`, `liquid_endpoint_temperature_K`, and `evaporated_fraction`. The profile supplies `liquid_cp_J_kg_K`, `vaporization_enthalpy_J_kg`, and applicable liquid and phase-change temperature ranges. The bundled file contains both property profiles. |

Optional gas `conduction` evidence gives `agent_mole_fraction`, `area_m2`, `path_length_m`, and supplied `base_conductivity_W_m_K` and `mix_conductivity_W_m_K` at relevant conditions. The model reports conductive power when the requested fraction matches that property record. A backend can use mixture properties from THM-02 when they apply.

To try water mist, replace only the `request.scenario` object in the example input with this one and run the same command.

```json
{
  "profile_id": "water_at_373_15K",
  "mode": "water_mist",
  "pressure_kPa": 101.325,
  "water_mass_kg": 0.2,
  "inlet_water_temperature_K": 293.15,
  "liquid_endpoint_temperature_K": 373.15,
  "evaporated_fraction": 0.5
}
```

This case absorbs about **293 kJ** under the supplied evaporation assumption.

## Calculation and output

```text
Gas sensible heat per mole = ∫ Σ x_i cp_i(T) dT
Initial gas molar density  = P / (R T_initial)
O2 after dilution          = O2_base × (1 − added fraction)
Conductive power           = k × A × ΔT / length
Water heat absorbed        = m × cp_liquid × ΔT + m × evaporated_fraction × Δh_vap
```

Use `sweep` for heat absorbed and remaining oxygen versus agent fraction, or for mist energy versus evaporated fraction when the supplied latent heat is applicable. The gas example lowers oxygen from **21% to 14.7%** at a final added CO₂ mole fraction of **0.30**. These are thermodynamic budgets. Suppressant delivery, droplet evaporation rate, and flame extinction require additional data. [FLEX diluents](https://ntrs.nasa.gov/citations/20205008449), [NIST water properties](https://doi.org/10.6028/NIST.IR.5078), [NASA water-mist development](https://ntrs.nasa.gov/citations/20130011664).

Code, README, and example prepared with SI assistance from OpenAI Codex.
