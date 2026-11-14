# Flame in Freefall · THM-05 opposed-flow flame spread

THM-05 estimates how fast an established flame moves along a solid sheet **against** ventilation. It evaluates the de Ris thermally thin and thick limits and selects the applicable limit using the full sample thickness.

## Run the example

Open PowerShell at the repo root. With the project Python environment from the [THM-16 setup instructions](THM-16.md#run-the-example), run:

```powershell
.\.venv\Scripts\python.exe src/Functions/THM-05/thm_05.py src/Functions/THM-05/THM-05_input.json
```

Python 3.10 or later is sufficient for this model. You can also use `py -3` in place of the project interpreter. The command prints JSON.

The BASS-II example gives **1.11 mm/s** for a **0.20 mm** PMMA sheet. Figure 2.21 shows approximately **1.1 mm/s** at that thickness. The flame coefficient comes from the separate **0.10 mm** measurement. The plotted thickness checks have limited precision and the figure does not specify the exact gas speed at each point. [NASA BASS-II report, Eq. 2.12 and Fig. 2.21](https://ntrs.nasa.gov/api/citations/20210011385/downloads/TM-20210011385.pdf#page=50)

## Inputs for the dashboard

The AI and backend assemble **one** [input JSON](../../src/Functions/THM-05/THM-05_input.json). Its `request` section describes the scenario. Its `evidence` section carries retrieved measurements, model parameters and sources. Feed the entire parsed JSON object to the Python entry point from the repo root.

```python
from request_planner.function_registry import run_model

result = run_model("THM-05", payload)
```

- Set `request.topic` to `"flame_spread"` and `request.analysis` to `"estimate_spread_rate"`. Give `scenario.materials` with one material ID, `setup_id`, `gravity`, and `flow_direction: "opposed"`.
- Use `{"value": number, "unit": "…"}` quantities. Provide `ambient.air_speed` in `cm/s`, `ambient.pressure` in `kPa`, `ambient.oxygen` in `%`, and `sample_width` and `specimen_thickness` in `m`. Enter a positive speed and the full sheet thickness.
- Provide matching entries in `evidence.setups` and `evidence.materials`. The selected material's `calibrations` each specify `setup_id`, `air_speed_range_m_s`, `pressure_range_kPa`, `oxygen_range_pct`, `thickness_range_m`, `width_range_m`, `source_url`, `source_locator`, and a `thermal` block. Equal endpoints represent a single supported condition. Exactly one calibration must apply.
- In `thermal`, supply `solid` and `gas` with `conductivity_W_m_K`, `density_kg_m3`, and `specific_heat_J_kg_K` in both. Supply representative properties at the relevant conditions. Optional `gas.density_reference_pressure_kPa` enables ideal-gas density scaling with pressure at fixed reference gas temperature and composition. Alternatively supply published coefficients in `thermal.prefactors.thin_m2_s` and `thermal.prefactors.thick_dimensionless`.
- Supply `thermal.flame_coefficient` from a relevant source or give `thermal.ambient_temperature_K`, `thermal.vaporization_temperature_K`, and `thermal.effective_flame_temperature_K` to calculate it. Oxygen selects the applicable evidence. A different oxygen condition needs a supported coefficient or appropriate temperatures. THM-01 can provide a suitable flame-temperature estimate if its assumptions apply. THM-02 or a property source can provide relevant gas inputs. The backend can pass those values in the evidence block.
- Set `evidence.provenance.illustrative` and add any relevant notes. Optional `spread_rate_checks` can compare against same-setup, same-atmosphere measurements with `thickness_m`, `spread_rate_mm_s`, and source information. Include `air_speed_m_s` for thick-limit comparisons.

The bundled example checks only the thin branch under the BASS-II conditions supplied. Feed in other materials and conditions by supplying compatible properties and evidence for the thermal regime.

For an input or evidence mismatch, the Python call raises an error and the CLI returns a usage error. The backend can use that message to request the missing or compatible data.

## Equations

Let `d` be full sheet thickness and `τ = d/2` for symmetric two-sided heating. The calculation uses the published thin correction `π/4` and equates the two limiting rates to get the transition.

```text
Flame coefficient           F = (T_flame − T_vaporization) / (T_vaporization − T_ambient)
Thin prefactor (m²/s)       A = (π/4) × k_g / (ρ_s × cp_s)
Thick prefactor              B = (k_g × ρ_g × cp_g) / (k_s × ρ_s × cp_s)
Thin spread rate             V_thin = A × F / τ
Thick spread rate            V_thick = B × U × F²
Full transition thickness   d_transition = 2 × A × F / V_thick
```

Use the thin rate at or below the transition and the thick rate above. In the thin limit, the heat flux and preheat length have opposing effects as airflow changes, so the expression has no explicit speed term. In the thick limit, the rate scales with opposing speed. The estimate assumes steady, thermally controlled burning and excludes ignition and extinction. Use separate applicable evidence or THM-07/THM-13 when screening for blowoff and quenching. [NASA BASS-II analysis, Eqs. 2.9–2.14](https://ntrs.nasa.gov/api/citations/20210011385/downloads/TM-20210011385.pdf#page=49)

## Output for plots

- Use `spread_rate_mm_s`, `thermal_regime`, and `transition_thickness_m` for the scenario summary. The two limiting rates are also returned.
- `sweeps` provides spread rate versus speed and versus thickness within the chosen evidence bounds, varying one at a time. A fixed input gives a single point. Plot `spread_rate_checks` as measured markers with their conditions and residuals.
- When comparing opposed and concurrent results, use a consistent spread-rate definition, units, specimen geometry, and applicable conditions. Check each model's sources and evidence bounds before putting results on a shared plot.

Code, README and example JSON prepared with SI assistance from OpenAI Codex.
