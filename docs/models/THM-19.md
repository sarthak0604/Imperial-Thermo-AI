# THM-19 · Cabin pressure, temperature, and species

Estimate the bulk response of a rigid, sealed, well-mixed cabin to a prescribed fire history. The bundled example uses Saffire VI context and illustrative fire, species, and wall inputs. [NASA Saffire VI report](https://ntrs.nasa.gov/citations/20240002981).

## Run

From the repository root in PowerShell, use the existing project Python or any Python 3.10 or later. This model uses the standard library.

```powershell
.\.venv\Scripts\python.exe src/Functions/THM-19/thm_19.py src/Functions/THM-19/THM-19_input.json
```

The CLI prints JSON. The backend can pass the parsed [input file](../../src/Functions/THM-19/THM-19_input.json) directly.

```python
from request_planner.function_registry import run_model

result = run_model("THM-19", payload)
```

The AI fills `request` with the scenario. Retrieval supplies the matching `evidence` records and their source links. The model accepts fresh records in this format.

## Input

Set `request.topic = "cabin_fire"` and `request.analysis = "estimate_cabin_response"`. In `scenario`, set `fire_id` and provide `cabin.volume_m3`, `initial_pressure_kPa`, `initial_temperature_K`, `wall_temperature_K`, `wall_ua_W_K`, `effective_molar_cv_J_mol_K`, and `fire_heat_fraction_to_gas`. The heat fraction accounts for the share of the input HRR deposited directly in bulk gas. Account for wall heating separately when choosing that fraction and fixed wall state.

Supply one matching fire under `evidence.fires` with increasing `time_s` and aligned nonnegative `hrr_W`. Optional `species` supplies aligned net source histories `oxygen_consumption_kg_s`, `co2_production_kg_s`, `co_production_kg_s`, and `other_net_gas_mol_s`. The first three are positive rates in the directions named. Other gas is a signed rate including net water vapor or other products as applicable. When using species, supply cabin `initial_mole_fractions` for `oxygen`, `carbon_dioxide`, and `carbon_monoxide`. Their sum may be less than one.

**THM-04 handoff.** The backend can copy `time_s` and `hrr_W` into the fire record from THM-04 or use a sourced HRR. A series with signed analyzer noise needs an explicitly documented baseline treatment before use as physical fire power. Copy the available O₂, CO₂ and CO channels only if they describe valid net source terms for the cabin case. The remaining gas rate must be provided separately for a species run. Keep the upstream sources with the derived history.

## Calculation and output

```text
Initial moles             n0 = P0 V / (R T0)
Gas sensible heat balance n0 Cv dT/dt = heat_fraction × HRR(t) − UA(T − T_wall)
Species balances          dn_i/dt = supplied net rate, converted to mol/s
Total and partial pressure P = n_total R T / V,   P_i = x_i P
```

The solution integrates linearly interpolated power exactly on each interval for constant wall parameters and heat capacity. Species moles integrate the supplied rates. If species data are absent, total moles stay fixed and species curves are null.

Plot `temperature_K`, `pressure_kPa`, and partial pressures against `time_s`. The reported peaks are maxima of the returned samples. The energy curves report heat to the bulk gas and heat transferred to the wall. Condensation, ventilation, local concentrations, and fire feedback require a different balance. [NASA ideal-gas relation](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/equation-of-state/).

Code, README, and example prepared with SI assistance from OpenAI Codex.
