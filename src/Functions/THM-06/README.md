# Flame in Freefall · THM-06 concurrent-flow flame spread

THM-06 estimates how an established flame moves **with** ventilation over a thermally thin solid. A reduced laminar heat-transfer model links the downstream heat flux, pyrolyzing length, and spread rate. The burning length can start below its limiting value, grow, and approach quasi-steady advance.

## Run the example

Open PowerShell at the repo root. With the project Python environment from the [THM-16 setup instructions](../THM-16/README.md#run-the-example), run:

```powershell
.\.venv\Scripts\python.exe THM-06/thm_06.py THM-06/THM-06_input.json
```

Python 3.10 or later is sufficient for this model. You can also use `py -3` in place of the project interpreter. The command prints JSON.

At **22.5 cm/s** tunnel inlet flow, the Saffire II SIBAL example gives a **limiting spread rate of 2.36 mm/s**. It is anchored to run II-5 at **2.1 mm/s** and checks against II-6 at **25 cm/s**, where the model gives **2.625 mm/s** and NASA reports **2.6 mm/s**. The specimens occupied different positions on the sample card. The check addresses the limiting rate. The growth curve and heat-flux estimates use illustrative inputs. [NASA Saffire II Table 1](https://ntrs.nasa.gov/api/citations/20180005168/downloads/20180005168.pdf#page=31)

## Inputs for the dashboard

The AI and backend assemble **one** [input JSON](THM-06_input.json). Its `request` section describes the scenario. Its `evidence` section carries retrieved measurements, model parameters and sources. Feed the entire parsed JSON object to the Python entry point from the repo root.

```python
from importlib import import_module

run_request = import_module("THM-06.thm_06").run_request
result = run_request(payload)
```

- Set `request.topic` to `"flame_spread"` and `request.analysis` to `"estimate_spread_rate"`. Provide one material ID in `scenario.materials`, `setup_id`, `gravity`, and `flow_direction: "concurrent"`.
- Use `{"value": number, "unit": "…"}` quantities. Provide `ambient.air_speed` in `cm/s`, `ambient.pressure` in `kPa`, `ambient.oxygen` in `%`, and `ambient.temperature` in `K`. Provide `sample_length`, `sample_width`, and `specimen_thickness` in `m`.
- Optional `initial_pyrolysis_length` and `initial_front_position` in `m` set the state of the already burning specimen. The initial zone must fit before the end of the sample. By default the model starts at its limiting burning length with the base at the start of the specimen. Optional `duration` in `s` caps the simulation time.
- Supply matching `evidence.setups` and `evidence.materials`. The material's `calibrations` must include one setup-specific profile matching all seven requested conditions in `bounds`. The profile contains `thermal` with `specific_heat_J_kg_K` and `pyrolysis_temperature_K`. Supply `areal_mass_kg_m2` for a fixed-thickness fabric, or `density_kg_m3` and `reference.sample_thickness_m` for a thickness-dependent areal mass. Supply `gas.kinematic_viscosity_ref_m2_s`, `gas.conductivity_W_m_K`, `gas.prandtl`, and `gas.effective_flame_temperature_K`.
- In this profile, `reference` gives the reference flow, pressure, oxygen, ambient temperature, limiting pyrolysis length, and its source. Supply either reference spread rate for fitting the effective heat feedback, or a documented `effective_heat_feedback_factor` in the calibration. `heated_to_pyrolysis_length_ratio`, `growth_length_m`, and `pyrolysis_length_flow_exponent` define the length closure. Use a `growth_length_m` at least equal to the initial deficit in pyrolysis length to keep the calculated burnout front monotone.
- Put sources and assumptions in `evidence.provenance` and the calibration's source fields. Optional `spread_rate_checks` supply observed rates with their run IDs, conditions, and sources. A check inherits unspecified conditions from the reference. Give reference geometry explicitly if it differs from the requested specimen. The measured limiting-length reference is from the Saffire II analysis. [Urban et al., Fig. 8 and Sec. 3.1](https://doi.org/10.1016/j.combustflame.2018.10.012)

The calibrations and constants for a particular experiment live in the input. New evidence can describe other materials, geometries and atmospheres. Oxygen selects an applicable profile and its effective gas and flame properties. The backend may supply an applicable THM-01 flame temperature and THM-02 transport properties along with the remaining calibration data.

For an input or evidence mismatch, the Python call raises an error and the CLI returns a usage error. The backend can use that message to request the missing or compatible data.

## Equations

The model uses the average laminar flat-plate heat-transfer relation over the active pyrolysis length `L_p`, with inlet pressure adjustment of kinematic viscosity at fixed reference gas temperature and composition. `U` is forced flow speed, and `F_q` is a supplied or fitted effective heat-feedback multiplier.

```text
Reynolds number                  Re = U × L_p / ν
Average convection coefficient   h = 0.664 × k_g / L_p × √Re × Pr^(1/3)
Effective convective heat flux   q = F_q × h × (T_flame − T_p)
Heating energy per sample area   E_A = areal_mass × cp_s × (T_p − T_ambient)
Heated length ahead of front     L_h = heated_to_pyrolysis_length_ratio × L_p
Pyrolysis-front speed            dx_p/dt = V = q × L_h / E_A
Limiting pyrolysis length        L_limit = L_ref × (U / U_ref)^length_exponent
Growth closure                   dL_p/dx_p = (L_limit − L_p) / growth_length
Effective flame tip                x_f = x_p + L_h
```

The heat balance follows the forced-flow scaling in Thomsen et al. If you fit the heat feedback to a measured rate, the result at the reference conditions reproduces that rate. The profile's thermal and gas properties still set the effective flux. Use a sourced feedback factor to test sensitivity to those properties independently. The burning-length relaxation is an explicit reduced closure. It gives increasing spread rate from a short initial zone and constant spread when the zone reaches its limiting length. The effective flame tip is a heating-length proxy. The trajectory stops before a downstream edge invalidates the heat balance. This version covers laminar, heat-transfer-controlled spread over thin fuels. It uses evidence to establish that this regime applies. [Thomsen et al., Eqs. 1–5](https://pmc.ncbi.nlm.nih.gov/articles/PMC6907022/#S4)

## Output for plots

- Plot `pyrolysis_front_position_m`, `pyrolysis_base_position_m`, and `effective_flame_tip_position_m` against `time_s`. Show any `edge_influence_time_s` as the end of the modeled heating interval.
- Plot `pyrolysis_length_m`, `effective_flame_length_m`, or `spread_rate_series_mm_s` against `time_s` to show growth toward a limiting state. The scalar `spread_rate_mm_s` is the limiting rate. Use the series for actual model values over the returned interval.
- Plot `convective_heat_flux_W_m2` as an estimate from the supplied effective heat feedback. Keep `provenance`, `sources`, and `spread_rate_checks` visible with the curves. The bundled transient parameters and estimated heat flux still need experimental checks.

Code, README and example JSON prepared with SI assistance from OpenAI Codex.
