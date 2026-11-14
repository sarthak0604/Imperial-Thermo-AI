# THM-10 · Droplet vaporization and combustion

From the repository root in PowerShell, run:

```powershell
python .\THM-10\thm_10.py .\THM-10\THM-10_input.json
```

Use Python 3.10+ with the standard library. If your project virtual environment is active, `python` uses that environment.

## What it calculates

This model estimates regression of an isolated, approximately spherical droplet over a phase with a constant regression rate. The AI selects a phase and fetches a compatible measurement or property set.

- `D²(t) = D₀² − Kt`. The output uses mm and mm²/s.
- In `measured_rate` mode, `K` comes from the selected evidence record.
- In `heat_transfer` mode, `K = 8 k_g ln(1 + B_T) / (ρ_l c_{p,g})` in m²/s, then converted to mm²/s. Supply gas conductivity, liquid density and gas specific heat. For combustion, also supply the dimensionless Spalding heat-transfer number for the selected conditions. For evaporation, the model can use a supplied transfer number or estimate it as `max(0, c_{p,g}(T_∞ − T_s)/L_eff)` for a simplified heat-driven evaporation closure. Supply the surface temperature and effective vaporization enthalpy in J/kg for that closure.
- The integration stops at a supplied physical diameter, a requested time limit, or the mathematical zero diameter. Formal zero is a model lifetime, and hot-flame extinction can occur sooner.

The stagnant-film approximation assumes fixed properties and adequate isolation from other droplets. Flow effects, startup transients, wet bulb temperature, low-temperature flames and physical extinction need separate evidence. Pressure and oxygen select a covered property set. A measured rate and supplied transfer number are held fixed within their evidence range.

## JSON and backend handoff

Send one object with `request` and `evidence`. Set `request.topic` to `droplet_combustion` and `request.analysis` to `estimate_droplet_regression`. Set `request.scenario.profile_id` to the matching `evidence.profiles[].id`. The scenario also includes `fuel_type`, `process`, `d0_mm`, `x_o2` (mole fraction), `pressure_kpa` and `t_amb_k`. Each profile specifies a method, fuel, process and pairs of validity bounds for those four numeric scenario inputs. Include `evidence.provenance` and `evidence.sources`. Optional scenario fields are `endpoint_diameter_mm`, `time_limit_s` and `plot_points` (default 101). A zero-rate case needs `time_limit_s`.

The backend can call `run_request(payload)` and receive a dictionary. Plot `plot_data.time_s` against `diameter_mm` or `diameter_squared_mm2`. With a supplied liquid density, the series also contains `droplet_mass_kg`. The scalar `modeled_endpoint_time_s` is based on the selected constant rate and may lie beyond the supplied time limit.

When chaining to THM-11, use the same physical droplet and phase. THM-11 calculates its hot-phase rate from three evidence fields, `observed_initial_diameter_mm`, `hot_extinction_diameter_squared_mm2` and `hot_extinction_time_s`. A compatible THM-10 run can reconstruct that phase as a cross-check. To reuse a modeled endpoint where its evidence supports the handoff, square `modeled_endpoint_diameter_mm`, use `modeled_endpoint_time_s`, and mark the values as derived with the same time origin. THM-10's formal zero time cannot stand in for the observed extinction time.

The example reconstructs the FLEX-002 hot-phase slope of 0.60 mm²/s from published values. Running from the reported igniter-on diameter of 1.86 mm to 0.94 mm gives 4.293 s under constant regression. The published burn time is 5 s. The constant-rate reconstruction uses the reported diameters and slope across a single modeled phase, and the regression fit starts after ignition. A second run, FLEX-003, had 0.58 mm²/s and differs in initial diameter and chamber pressure. The difference of 0.02 mm²/s is a comparison between the reported rates.

[Princeton droplet combustion overview](https://www.princeton.edu/~fldryer/nasa.dir/backgrnd.htm) · [NASA FLEX report, Table IX](https://ntrs.nasa.gov/api/citations/20150023456/downloads/20150023456.pdf?attachment=true)
