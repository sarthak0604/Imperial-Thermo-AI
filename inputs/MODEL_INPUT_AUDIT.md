# THM-01 through THM-20 input audit

This audit covers model JSON entry points under `src/Functions/` at `b86b29f` and on [Liem’s branch at `2855ca2`](https://github.com/sarthak0604/Imperial-Thermo-AI/tree/2855ca26795b1a5de04ed204a13cd7b89ef52618). Each section names the canonical input keys. Keys are case-sensitive. A row with several keys applies the same requirement and source rule to each listed key. Paths are relative to the object named in the first column.

- **Scenario** comes from the user, test metadata, or a named what-if selected for the request. Preserve explicit user inputs.
- **Reference** is a property or correlation reusable for a matching material, phase and state. Use measured or fitted values with sources and stated applicability.
- **Setup** needs the actual geometry, instrumentation, operating conditions, measured histories or a compatible calibration. Keep the setup identity and applicability with the values.
- **Derived** is a deterministic calculation or upstream model output. Record its source inputs, model and units.
- **Metadata** supplies identifiers or provenance. Store the originating URL, figure/table/run, and notes on assumptions. Where a parser accepts extra metadata, preserve it in the sidecar even if a model does not echo it.
- **Default** names what the current solver does when omitted. Physical defaults such as ambient conditions, kinetics, background corrections and heat transfer assumptions belong in the backend's result provenance. Numerical plot controls can be set by the application.

**Payload conventions.** THM-01/03/07/08/09 accept a single JSON with an `inputs` or `params` object (or flat keys). THM-02 accepts `params` or flat keys. They use `run_from_json_payload`. For Liem’s `THM-XX_example.json` files, pass their `example_request` object to that function. The outer `example_response` describes intended dashboard output. In THM-08’s branch example, `gravity_g=1.569` is inconsistent with its lunar label. Use `"Moon"` or a fraction near `0.165` for the described scenario. The other models use `run_request(payload)` with one JSON containing `request` and `evidence`. Set `request.topic`, `request.analysis`, and `request.scenario` for every envelope model. For THM-10/12/13/14/15/17/18/19/20, `evidence.provenance` and `evidence.sources` are required by code. THM-04/05/06/11 require `evidence.provenance.illustrative`; THM-16 reads provenance fields from its selected calibration. For the envelope models, provide exactly one matching setup/material record or profile as stated. The archive or citation for a calibration is separate from sources for general properties.

**Units.** A quantity field marked **Q** takes `{"value": number, "unit": "…"}` with the exact unit string in its row. Other numeric fields take a JSON number. Fraction means 0–1, percent means 0–100. A range is a two-element array in the stated units; equal endpoints represent one condition. Check oxygen basis (mole/volume versus mass), temperature, pressure and flow units before copying across models.

## THM-01 · Adiabatic flame temperature

`inputs` or `params`. Returns an ideal equilibrium flame temperature and product composition.

| Fields | Requirement and source |
|---|---|
| `fuel_species` | Required scenario fuel species. Use a species supported by the selected mechanism or fallback. |
| `o2_mole_frac`, `pressure_kpa` | Required scenario oxidizer oxygen mole fraction and absolute pressure in kPa. |
| `diluent_gas` | Scenario oxidizer balance species. Default `N2`. |
| `equivalence_ratio`, `t_init_k` | Scenario fuel-to-oxidizer equivalence ratio (default 1) and initial gas temperature in K (298.15). |
| Aliases and context | Fuel: `fuel`, `fuel_type`, `species`. Oxygen: `xo2`, `x_o2`, `o2_percent`. Pressure: `p_kpa`, `pressure_psi`, `pressure_pa`. Diluent: `diluent`. Equivalence ratio: `phi`. Temperature: `temp_k`, `t_amb_k`. Optional top-level `investigation_context`; optional `batch_scenarios` or `scenarios` array of like requests, with optional per-case `scenario_name` and `investigation_context`. |

Gas temperature is adiabatic. Downstream flame-edge or surface temperatures require a model or measurement relevant to that location.

## THM-02 · Gas transport and Lewis number

`params` or flat JSON. Evaluates gas-mixture properties at a specified state.

| Fields | Requirement and source |
|---|---|
| `mole_fracs` | Required map of supported species to gas mole fractions. Parser normalizes positive entries. Prefer a checked mixture summing to one. |
| `temp_k`, `pressure_kpa` | Required scenario temperature in K and absolute pressure in kPa. Select the reference state needed by the receiving model. |
| `target_species` | Optional species present in the mixture for mass diffusivity and Lewis number. Default chooses the least abundant recognized fuel if present, else oxygen in a multicomponent mixture, else the least abundant species. |
| Aliases and context | `gas_composition` or `species_mole_fractions`; `temperature_k`; `pressure_atm` or `pressure_psi`; `limiting_species`. Optional `psi_citations` at top level or in `params`. Optional top-level `investigation_context` or `data_slice`. `batch_scenarios[]` uses `mole_fracs`, `temp_k`, `pressure_kpa` and optional `target_species` under `params` or flat, plus optional per-case `psi_citations`, `scenario_name`. |

The mechanism and built-in transport reference data supply properties. Preserve which backend computed them. A Lewis number is a screening indicator for diffusion effects.

## THM-03 · Stoichiometric mixture fraction and spherical flame size

`inputs` or `params`. The size estimate assumes an idealized spherical diffusion flame.

| Fields | Requirement and source |
|---|---|
| `fuel_formula` | Required supported fuel formula. Aliases `fuel_species`, `fuel`. |
| `y_fuel_stream`, `y_ox_stream` | Scenario fuel and oxygen **mass fractions** in their respective feed streams. Defaults 1 and 0.232. |
| `x_fuel_stream`, `fuel_diluent` | Alternate fuel mole-fraction basis and its diluent (default `N2`). Backend should resolve the diluent explicitly if using the conversion. |
| `x_ox_stream` or `o2_mole_frac`, `ox_diluent` or `diluent_gas`, `o2_percent` | Alternate oxygen basis. With a mole fraction, diluent defaults to `N2`. The separate percentage shortcut uses `N2` in the code. |
| `burner_radius_mm`, `total_flow_rate_sccm`, `pressure_kpa`, `t_film_k` | Setup radius, standard volumetric feed, absolute pressure, representative gas-film temperature. Code defaults 3.2 mm, 250 sccm, 101.325 kPa, 1200 K. Record actual conditions for an experiment. |
| `flame_configuration` | `normal`, `inverse`, or `auto` (default, infers from feed fractions). Use the known burner direction when available. |
| Context | Optional `investigation_context`, `batch_scenarios` or `scenarios` and optional case `scenario_name` or `investigation_context`, as THM-01. |

## THM-04 · Oxygen-consumption calorimetry

Routing `heat_release / estimate_hrr`.

| Path and fields | Requirement and source |
|---|---|
| Scenario `run_id`, `time_window_s` | Run ID required. Optional analysis window in seconds, within observed samples. |
| `evidence.runs[]`: `id`, `measurement_method`, `samples`, `source_url`, `source_locator` | Required selected run. Methods: `exhaust_mass_flow` or `paired_oxygen_mass_flow`. At least two synchronized samples with increasing `time_s` in seconds. |
| Exhaust: `gas_basis`; `samples[].{mass_flow_kg_s,o2_vol_frac,co2_vol_frac,co_vol_frac}` | Required `gas_basis="dry"`. Gas analyzer fractions are dry volume fractions. Exhaust mass flow is the wet mass-flow rate. Use actual analyzer and flow measurements. |
| Exhaust `inlet.{o2_vol_frac,co2_vol_frac,co_vol_frac,water_vapor_vol_frac,expansion_factor,gas_molar_mass_kg_mol}` | Required dry inlet O₂, CO₂ and CO fractions, wet water fraction, expansion factor (dimensionless), and gas molar mass (kg/mol). Inlet humidity and expansion factor need setup evidence or an explicit assumption. Molar mass can be derived from the known composition. |
| Paired `samples[].{inlet_o2_kg_s,outlet_o2_kg_s,net_co_kg_s,net_co2_kg_s}` | First two required measured oxygen mass flows. Optional `net_co_kg_s` and `net_co2_kg_s` need full aligned channels when used. |
| Either `heat_per_kg_o2_J`, `samples[].soot_carbon_kg_s`, `samples[].reference_hrr_W`, `benchmark.{source_url,source_locator}` | Optional documented heat per kg O₂, default 13.1 MJ/kg O₂. Optional measured soot carbon, or independent HRR comparison. Supply each optional channel across all samples; benchmark source fields are required with the comparison channel. |
| `evidence.provenance.illustrative` | Required flag. Carry time alignment, fuel coefficient and baseline notes. |

## THM-05 · Opposed-flow flame spread

Routing `flame_spread / estimate_spread_rate`.

| Path and fields | Requirement and source |
|---|---|
| Scenario `materials`, `setup_id`, `gravity`, `flow_direction` | One material ID in an array, one setup ID, matching gravity and `opposed` flow. |
| `scenario.ambient.{air_speed,pressure,oxygen}` | Q in `cm/s`, `kPa`, `%`. Actual scenario or run conditions. |
| Scenario `specimen_thickness`, `sample_width` | Q in `m`. Full thickness and width from the test specimen. |
| `evidence.setups[].{id,model,gravity_regime,flow_direction}`, `evidence.materials[].{id,calibrations}` | Required matching setup and fuel, with `model="THM-05"`. |
| Calibration `id`, `setup_id`, `source_url`, `source_locator` | Required identity and source. |
| Calibration `air_speed_range_m_s`, `pressure_range_kPa`, `oxygen_range_pct`, `thickness_range_m`, `width_range_m` | Required coverage from the selected study or fit. |
| `thermal.prefactors.{thin_m2_s,thick_dimensionless}` | Published/model-calibrated coefficient route. Both required if using prefactors. |
| `thermal.solid` and `thermal.gas`: `conductivity_W_m_K`, `density_kg_m3`, `specific_heat_J_kg_K` | Alternative reference-property route, all six fields. Optional `thermal.gas.density_reference_pressure_kPa` for ideal-gas pressure correction at fixed temperature/composition. THM-02 can supply compatible gas properties. |
| `thermal.flame_coefficient` or `thermal.{ambient_temperature_K,vaporization_temperature_K,effective_flame_temperature_K}` | Required choice of calibrated coefficient or three compatible temperatures. Use a supported mapping before applying THM-01 to the effective flame temperature. |
| `spread_rate_checks[].{thickness_m,spread_rate_mm_s,air_speed_m_s}` | Optional comparison rows. First two required per row; default speed is scenario speed for the thin check (supply speed for thick checks). Carry `run_id`, `source_url`, `source_locator` and measurement notes where known. |
| `evidence.provenance.illustrative` | Required flag. |

## THM-06 · Concurrent-flow flame spread

Routing `flame_spread / estimate_spread_rate`.

| Path and fields | Requirement and source |
|---|---|
| Scenario `materials`, `setup_id`, `gravity`, `flow_direction` | One material ID in an array, one setup ID, matching gravity and `concurrent` flow. |
| `scenario.ambient.{air_speed,pressure,oxygen,temperature}` | Q in `cm/s`, `kPa`, `%`, `K`. Actual scenario or run conditions. |
| Scenario `sample_length`, `sample_width`, `specimen_thickness` | Q in `m`. Setup geometry. |
| Scenario `initial_pyrolysis_length`, `initial_front_position`, `duration` | Optional Q in `m`, `m`, `s`. Both lengths describe the already-burning specimen. Defaults to limiting burning length and front at that length, with duration ending at edge influence unless capped. |
| `evidence.setups[].{id,model,gravity_regime,flow_direction}`, `evidence.materials[].{id,calibrations}` | Required matching records, model `THM-06`. |
| Calibration `id`, `setup_id`, `source_url`, `source_locator`, `bounds` | Required metadata. Bounds keys: `air_speed_m_s`, `pressure_kPa`, `oxygen_pct`, `ambient_temperature_K`, `sample_length_m`, `sample_width_m`, `sample_thickness_m`. Apply to scenario and calibration reference. |
| `thermal.{specific_heat_J_kg_K,pyrolysis_temperature_K,areal_mass_kg_m2,density_kg_m3}` | Specific heat and supported effective pyrolysis temperature required; choose fixed-thickness areal mass or density plus `reference.sample_thickness_m` for the variable-thickness route. |
| `gas.{kinematic_viscosity_ref_m2_s,conductivity_W_m_K,prandtl,effective_flame_temperature_K}` | All required. Reference viscosity is at reference pressure. THM-02 supplies compatible transport, and an effective flame temperature needs a supported model/measurement. |
| `heated_to_pyrolysis_length_ratio`, `growth_length_m`, `pyrolysis_length_flow_exponent`, `effective_heat_feedback_factor` | First three required setup/fit inputs. Provide the heat-feedback factor or a reference measured spread rate. |
| `reference.{air_speed_m_s,pressure_kPa,oxygen_pct,ambient_temperature_K,pyrolysis_length_m,spread_rate_mm_s,source_url,source_locator}` | Required conditions, limiting pyrolysis length and source. Rate required if fitting the heat-feedback factor. Optional `sample_length_m`, `sample_width_m`, `sample_thickness_m` inherit specimen geometry when omitted; thickness required for the density route. Preserve `run_id` if known. |
| `spread_rate_checks[]`, `additional_sources[]`, `evidence.provenance.illustrative` | Checks optional, each needs `spread_rate_mm_s`, with condition overrides using keys in `bounds` and default reference conditions. Retain run ID and figure/table. Extra source entries optional; illustrative flag required. |

## THM-07 · Convective blowoff

`inputs` or `params`. Use material/setup calibration for engineering comparisons.

| Fields | Requirement and source |
|---|---|
| `u_flow_ms`, `x_o2` | Required flow in m/s and oxygen mole fraction. Aliases `u_flow_cms`, `flow_velocity_cms`, `airflow_cms`; `o2_mole_frac`, `o2_percent`. |
| `pressure_kpa`, `t_amb_k` | Scenario pressure (default 101.325 kPa; alias `pressure_psi`) and ambient temperature (298.15 K). |
| `activation_energy_j`, `pre_exp_factor`, `reaction_order_n`, `o2_order_m`, `da_critical` | Setup/model-kinetics values. Despite its name the activation energy is **J/mol**; default 125600. Effective pre-factor default 2.5e6 s⁻¹ under normalized pressure and O₂; exponents 1.75 and 1; threshold 1. These are physical assumptions. |
| `flame_temp_k` | Compatible effective leading-edge temperature in K; built-in approximation if omitted. |
| Context | Optional top-level `investigation_context`, `batch_scenarios` or `scenarios`, optional case `scenario_name` or `investigation_context`, as THM-01. |

## THM-08 · Mixed convection at different gravity

`inputs` or `params`. Partial-gravity outputs are theoretical scaling.

| Fields | Requirement and source |
|---|---|
| `gravity_g` | Required scenario gravity in Earth g, numeric string, or supported preset such as `ISS`, `Moon`, `Mars`, `Earth`. Aliases `gravity`, `environment`. |
| `u_forced_ms` | Forced-flow speed; default 0.10 m/s. Aliases `u_forced_cms`, `u_flow_ms`, `u_flow_cms`. |
| `char_length_m`, `delta_t_k` | Setup characteristic length (default 0.05 m; aliases `char_length_cm`, `char_length_mm`) and representative hot-to-ambient temperature difference (default 1400 K). |
| `pressure_kpa`, `t_amb_k` | Scenario pressure (default 101.325 kPa; alias `pressure_psi`) and ambient temperature (298.15 K). The code uses air-based property scaling. |
| Context | Optional top-level `investigation_context`, `batch_scenarios` or `scenarios`, optional case `scenario_name` or `investigation_context`, as THM-01. |

## THM-09 · Spalding mass-transfer number for solids

`inputs` or `params`. The solid-fuel preset can silently substitute values for omitted properties, even with an unknown material name.

| Fields | Requirement and source |
|---|---|
| `y_o2_amb` | Required oxygen **mass fraction**, or `x_o2`, `o2_mole_frac` or `o2_percent`. The alternate conversion assumes oxygen and nitrogen; pass the mass fraction for other mixtures. |
| `material_name`, `heat_combustion_jkg`, `heat_pyrolysis_jkg`, `t_vap_k`, `stoich_o2_fuel_mass_ratio`, `surface_emissivity` | Scenario material (alias `material`, code default PMMA); source material heats in J/kg, effective vaporization/pyrolysis temperature in K, kg O₂ per kg fuel, and dimensionless emissivity. Code supplies preset or generic values; explicitly supply matched properties for a real material. Heats accept `heat_combustion_mjkg`, `heat_pyrolysis_mjkg` as alternatives. |
| `u_flow_ms`, `char_length_m`, `pressure_kpa`, `t_amb_k` | Setup flow (0.15 m/s; alias `u_flow_cms`), length (0.05 m), pressure (101.325 kPa; alias `pressure_psi`), ambient temperature (298.15 K). |
| `cp_gas_jkgk`, `include_surface_radiation` | Reference film heat capacity in J/(kg K) (default 1150); Boolean radiation switch (default true). Use a JSON Boolean because parser truthiness applies to other types. |
| Context | Optional top-level `investigation_context`, `batch_scenarios` or `scenarios`, optional case `scenario_name` or `investigation_context`, as THM-01. |


## THM-10 · Isolated droplet regression

Routing `droplet_combustion / estimate_droplet_regression`. Selected `evidence.profiles[].id` matches `scenario.profile_id`.

| Path and fields | Requirement and source |
|---|---|
| Scenario `profile_id`, `fuel_type`, `process` | Required ID, fuel, and `combustion` or `evaporation`; evidence repeats fuel and process. |
| Scenario `d0_mm`, `x_o2`, `pressure_kpa`, `t_amb_k` | Required starting diameter, O₂ mole fraction, pressure and temperature. Profile `validity` requires bounds for all four with the same keys. |
| Scenario `endpoint_diameter_mm`, `time_limit_s`, `plot_points` | Optional measured or specified positive endpoint, time cap and sample count (default 101, 2–2001). A zero-regression case needs a time cap. An unspecified endpoint is a mathematical zero-diameter limit. |
| Profile `id`, `fuel_type`, `process`, `method` | Required selection. `method` is `measured_rate` or `heat_transfer`. |
| Measured profile `regression_rate_mm2_s`, `comparison_rate_mm2_s` | Measured regression required for `measured_rate`; optional independent comparison rate. Use compatible phase and run conditions. |
| Profile `liquid_density_kg_m3`, `gas_conductivity_w_m_k`, `gas_cp_j_kg_k` | Reference properties required for heat-transfer method. Density is optional in measured mode to also produce a mass curve. |
| Profile `spalding_heat_transfer_number`, `surface_temperature_k`, `effective_vaporization_heat_j_kg` | Supply a compatible Spalding number for combustion. For evaporation, choose a supplied number or both surface temperature and effective latent heat. Gas properties alone cannot supply a combustion transfer number. |

## THM-11 · Hot and cool droplet stages

Routing `droplet_combustion / estimate_cool_flame`.

| Path and fields | Requirement and source |
|---|---|
| Scenario `setup_id`, `materials`, `gravity`, `initial_diameter` | Matching setup, one fuel ID, optional gravity (defaults to setup), initial diameter Q in `mm`. |
| `scenario.ambient.{pressure,oxygen,additional_diluent}` | Q in `kPa` and `%`, plus diluent identifier matching the setup. Preserve oxygen basis and actual diluent. |
| `evidence.setups[].{id,model,gravity_regime,additional_diluent}` | Matched setup and `model="THM-11"`. |
| `evidence.materials[].{id,calibrations,cool_extinction_references}` | One selected material, and one compatible entry from each evidence list. |
| Calibration `id`, `setup_id`, `pressure_kPa`, `oxygen_pct`, `initial_diameter_range_mm`, `observed_initial_diameter_mm`, `hot_extinction_time_s`, `hot_extinction_diameter_squared_mm2`, `cool_burning_rate_mm2_s`, `source_url`, `source_locator` | Required actual-run evidence. The initial size, hot time and squared diameter determine the hot-stage regression rate. A compatible THM-10 reconstruction can provide a derived estimate with the same time origin and phase. |
| `cool_extinction_references[].{setup_id,run_id,pressure_kPa,oxygen_pct,diameter_squared_mm2,cool_burning_rate_mm2_s,source_url,source_locator}` | Required reference for final cool extinction. Use a separate matching reference where possible. |
| Calibration `held_out_cool_extinction.{time_s,method}`, `evidence.provenance.illustrative` | Optional comparison with both fields; flag required. Mark when an observed endpoint supplied the same run's reconstruction. |

## THM-12 · Mixture evaporation and uptake

Routing `droplet_evaporation / estimate_multicomponent_evaporation`.

| Path and fields | Requirement and source |
|---|---|
| Scenario `profile_id`, `t_surface_k`, `pressure_kpa`, `liquid_fractions`, `ambient_partial_pressures_kpa` | Required ID, surface temperature, pressure and two maps keyed by component ID. Liquid mole fractions sum to one. The ambient map gives far-field partial pressures in kPa. |
| Profile `id`, `validity.{t_surface_k,pressure_kpa}`, `components` | Matched profile, ranges and at least two uniquely named components. |
| Component `id`, `activity_coefficient`, `volatile` | ID and compatible activity coefficient required. `volatile` defaults to true. A unit activity coefficient is an explicit ideal-mixture assumption. |
| Volatile component `reference_temperature_k`, `reference_vapor_pressure_kpa`, `vaporization_enthalpy_j_mol` | Required reference properties. Store the reference temperature and property ranges. |
| Component `transfer_conductance_mol_s_kpa` | Setup coefficient for a rate in mol/s. Optional for a snapshot; required for each volatile component in a time evolution. Involatile species require zero ambient partial pressure and omitted or zero conductance. |
| Scenario `liquid_transport.{radius_m,circulation_speed_m_s,mass_diffusivity_m2_s}` | Optional block for the liquid Péclet number. All three required if supplied. Use the stated geometry and representative mixture diffusivity. |
| Scenario `time_evolution.{initial_total_moles,duration_s,min_total_moles,plot_points}` | Optional block. First two required. Defaults are 0.01% minimum inventory and 101 points (2–2001). Requires the conductances above. |

Nonboiling model. A surface snapshot can return direction of transfer with null rates when conductance is missing.

## THM-13 · Low-speed radiative quenching

Routing `extinction / estimate_radiative_quench`.

| Path and fields | Requirement and source |
|---|---|
| Scenario `profile_id`, `material_id`, `setup_id`, `gravity`, `flow_direction` | Required. The profile repeats the last four identifiers and carries its own `id`. |
| Scenario `u_flow_ms`, `x_o2`, `pressure_kpa`, `t_amb_k`, `co2_frac`, `h2o_frac`, `surface_emissivity` | Required scenario values, with ranges under the same keys in profile `validity`. O₂ is inlet mole fraction. CO₂ and H₂O are mole fractions of the radiating gas, with sum ≤1. Emissivity is a dimensionless surface property tied to material and state. |
| Scenario `surroundings_temperature_k` | Optional independent boundary temperature (defaults to ambient). |
| Profile `flame_temperature_k`, `surface_temperature_k`, `planck_mean_per_atm_m_inv.{co2,h2o}` | Required representative local temperatures and Planck mean coefficients in m⁻¹/atm at the radiating-gas state. |
| Profile `optical_path_length_m`, `gas_volume_per_reference_area_m`, `emitting_surface_to_reference_area` | Required path and volume/area in m. Optional area ratio defaults to 1. Geometry comes from the setup. Solver limits optical depth to 0.1. |
| Profile `oxygen_heat_coupling_factor`, `heat_per_mol_oxygen_j` | Required compatible coupling factor (0 < factor ≤1) and J per mole of oxygen. Fit the coupling for this transport closure. |
| Profile `soot_absorption_m_inv`, `other_loss_w_m2`, `oxygen_diffusion.{diffusivity_m2_s,length_m}` | Optional absorption and loss, default zero. Optional diffusion block requires both gas diffusivity and the setup's effective diffusion length. Match calibration to chosen terms. |

## THM-14 · Radiative fraction

Routing `heat_release / estimate_radiative_fraction`.

| Path and fields | Requirement and source |
|---|---|
| Scenario `run_id`; `evidence.runs[].{id,samples,geometry}` | Required and matching. |
| `samples[].{time_s,radiometer_flux_w_m2,total_hrr_w,background_flux_w_m2}` | Required time, measured incident radiant flux and total HRR from the **same run**. Time must increase. THM-04 can supply aligned HRR. Background can override geometry's value for one sample. |
| `geometry.{method,transmission,background_flux_w_m2}` | Method required. Optional transmission (default 1) and background (default 0) are setup assumptions when omitted. |
| `geometry.{detector_area_m2,view_factor_f12}` | Both required for `view_factor` method. Use source-to-detector view factor, not its reciprocal. |
| `geometry.{source_distance_m,incidence_angle_deg}` | Both required for `isotropic_point_source` method. Angle is measured from the sensor normal, below 90°. Use compatible far-field geometry. |
| `geometry.gray_body.{emitting_area_m2,emissivity,temperature_k,surroundings_temperature_k}` | Optional separate gray-body estimate. All four fields when supplying the block. |

## THM-15 · Soot onset

Routing `soot / screen_soot_inception`.

| Path and fields | Requirement and source |
|---|---|
| Scenario `calibration_id`, `fuel_id`, `setup_id`, `gravity`, `pressure_kPa` | Required calibration selection and scenario identity. Calibration repeats fuel, setup, gravity and gives `id` and `pressure_range_kPa`. |
| Scenario `flame_temperature_K`, `temperature_gradient_K_m`, `residence_time_s`, `carbon_to_oxygen_atomic_ratio`, `radial_gas_velocity_m_s` | Required local conditions for the same flame region. Temperature gradient and gas velocity use outward sign convention. THM-01 equilibrium temperature requires a supported conversion to the local value. |
| Calibration `min_carbon_to_oxygen_atomic_ratio`, `threshold_curve[].{residence_time_s,threshold_temperature_K}`, `temperature_margin_band_K` | Required setup-relevant C/O threshold and ordered curve. Optional temperature band defaults to zero. Near-threshold band is a screening choice. |
| Calibration `kinematic_viscosity_m2_s`, `thermophoretic_coefficient` | Required compatible gas property and dimensionless particle transport coefficient. |

Soot onset is a screening output. THM-20 needs a separately supported smoke mass-rate input.


## THM-16 · Solid heating to an ignition criterion

Routing `ignition / estimate_ignition`.

| Path and fields | Requirement and source |
|---|---|
| Scenario `setup_id`, `materials`, `gravity`, `specimen_thickness` | Required setup and one material ID. Optional gravity defaults to setup; optional Q thickness in `m` must equal the material record. |
| `scenario.ambient.{pressure,oxygen,air_speed,temperature}` | Required Q in `kPa`, `%`, `cm/s`, `K`. Use matching scenario measurements or specified conditions. |
| `scenario.exposure.{heat_flux,heating_time}` | Required Q in `kW/m2` and `s`. Flux is a constant **incident** exposure. Model multiplies by absorptivity to get absorbed flux. |
| `evidence.setups[].{id,model,gravity_regime,h_W_m2K,h_back_W_m2K}` | Required setup with `model="THM-16"`, applicable gravity and front convection coefficient in W/(m² K). Optional back coefficient defaults to front. |
| `evidence.materials[].{id,properties,calibrations}` | Required matching material record. |
| `properties.{thickness_m,density_kg_m3,cp_J_kgK,conductivity_W_mK,absorptivity,emissivity}` | Required specimen geometry and matching-grade material/surface properties. Fractions dimensionless, temperature and surface finish matter for optical properties. |
| `properties.{pyrolysis_pre_exponential_s_inv,pyrolysis_activation_energy_j_mol,heat_of_pyrolysis_j_kg}` | Required mutually compatible kinetics and heat of pyrolysis. Use a material-specific fit and its validity, with the same kinetic model. |
| Calibration `id`, `setup_id`, `pressure_kPa`, `oxygen_pct`, `speed_range_m_s`, `ambient_temperature_range_K`, `flux_range_kW_m2`, `max_heating_time_s`, `t_ign_k`, `source_locator` | Required setup fit. Pressure and oxygen match exactly. Flux bounds apply to incident flux. `t_ign_k` is the fitted surface criterion in K. Optional `source_url` and `illustrative` (default false in code); include both for external evidence. |

The current fixture is a synthetic slab. A generic PMMA property record can help a what-if heat-transfer estimate. Actual ignition thresholds and a complete real-material THM-16 profile need matched calibration.

## THM-17 · Limiting oxygen for sustained spread

Routing `flammability / estimate_limiting_oxygen`.

| Path and fields | Requirement and source |
|---|---|
| Scenario `calibration_id`, `material_id`, `setup_id`, `gravity`, `flow_direction`, `pressure_kPa`, `air_speed_m_s` | Required scenario. Calibration repeats the four descriptors and provides `id`, `pressure_range_kPa`, `air_speed_range_m_s`. |
| Scenario `ambient_oxygen_pct` | Optional oxygen percentage used to calculate distance to threshold in percentage points. |
| Calibration `quench`, `blowoff`, `axis_units_per_m_s` | Both branches required and must describe the same setup. Optional speed-to-axis multiplier, default 1. If using stretch, the multiplier can be derived from compatible geometry. |
| Branch `form` and associated data | For `linear`: `intercept_pct`, `slope_pct_per_axis_unit`. For `exponential`: `base_pct`, `amplitude_pct`, `decay_per_axis_unit`. For `table`: `points` as two or more increasing `[axis coordinate, oxygen percent]` pairs covering the selected speed range. |
| Calibration `combination_rule`, `shared_baseline_pct` | Required `maximum` for two independent criteria, or `shared_baseline_excess_sum` with required fitted `shared_baseline_pct`. |
| Calibration `reference_1g.oxygen_pct` | Optional separate comparison. Carry source and setup details with the percentage. |

THM-13 can supply a compatible low-flow table. THM-07 needs a conversion from critical speed versus oxygen to oxygen versus speed for the high-flow table. Use their overlapping support for the same fuel, geometry and atmosphere.

## THM-18 · Suppressant thermal budget

Routing `suppression / estimate_thermal_capacity`.

| Path and fields | Requirement and source |
|---|---|
| Scenario `profile_id`, `mode`, `pressure_kPa`; profile `id`, `mode`, `pressure_range_kPa` | Required matching profile in `evidence.profiles[]`, supports `gas_dilution` and `water_mist`. |
| Gas scenario `initial_temperature_K`, `target_temperature_K`, `agent_mole_fraction`, `base_gas_mole_fractions` | Required initial/target temperatures, added agent fraction of final mixture, and gas-species map before dilution (sum one). |
| Gas profile `agent_species`, `oxygen_species`, `species` | Required species identifiers and property map keyed by name for participating gases. |
| Gas `species[name].{cp_at_reference_J_mol_K,cp_reference_temperature_K,cp_slope_J_mol_K2,temperature_range_K}` | Required reference heat capacity, temperature and applicable interval. Slope optional, default zero. Supply a linearization over the intended interval, not a fit for another range. |
| Gas `conduction.{agent_mole_fraction,area_m2,path_length_m,base_conductivity_W_m_K,mix_conductivity_W_m_K}` | Optional block for the matching fraction. Needs both gas conductivities and setup heat-transfer geometry. |
| Mist scenario `water_mass_kg`, `inlet_water_temperature_K`, `liquid_endpoint_temperature_K`, `evaporated_fraction` | All required. The amount evaporating is a scenario assumption or from a spray/delivery study. |
| Mist profile `liquid_cp_J_kg_K`, `liquid_temperature_range_K`, `vaporization_enthalpy_J_kg`, `phase_change_temperature_range_K` | Required water properties and domains. With nonzero evaporation, the endpoint must fall in the supplied phase-change range. |

Thermal budget covers absorbed heat and dilution. Flame extinction needs additional evidence linking delivered agent to the fire.

## THM-19 · Sealed cabin response

Routing `cabin_fire / estimate_cabin_response`.

| Path and fields | Requirement and source |
|---|---|
| Scenario `fire_id`, `cabin`; `evidence.fires[].{id,time_s,hrr_W}` | Required. Align a fire history to at least two increasing timestamps with nonnegative power. THM-04 can supply the history after a documented baseline treatment if required. |
| `cabin.{volume_m3,initial_pressure_kPa,initial_temperature_K,wall_temperature_K,wall_ua_W_K,effective_molar_cv_J_mol_K,fire_heat_fraction_to_gas}` | All required. Geometry and wall state are setup-specific. Use an effective heat capacity at constant volume for the initial mixture; heat fraction is the fraction of total HRR entering bulk gas. |
| Fire `species.{oxygen_consumption_kg_s,co2_production_kg_s,co_production_kg_s,other_net_gas_mol_s}` | Optional complete block of histories aligned to fire samples. First three nonnegative in the named directions; other signed net gas rate in mol/s, including water if applicable. Use experimentally or physically supported source terms. |
| `cabin.initial_mole_fractions.{oxygen,carbon_dioxide,carbon_monoxide}` | Mandatory with species block. Omit species input to run heat and pressure with fixed total moles. |

## THM-20 · Smoke aerosol transport

Routing `smoke / estimate_aerosol_transport`.

| Path and fields | Requirement and source |
|---|---|
| Scenario `profile_id`, `setup_id`; profile `id`, `setup_id`, `scenario_bounds` | Required selection of `evidence.profiles[]` and matching setup. Set applicable numeric bounds keyed by scenario fields. Code checks supplied bounds. |
| Scenario `duct_length_m`, `duct_area_m2`, `air_speed_m_s`, `axial_temperature_gradient_K_m`, `smoke_mass_rate_kg_s`, `duration_s` | All required. Geometry and airflow are setup inputs. Gradient positive when temperature increases toward outlet. Smoke source strength comes from measurement or a supported emission model. |
| Profile `gas_temperature_K`, `gas_dynamic_viscosity_Pa_s`, `gas_density_kg_m3` | Required compatible gas state and properties. THM-02 can supply gas viscosity and density for the relevant state. |
| Profile `source_particle_diameter_m`, `particle_density_kg_m3`, `thermophoretic_coefficient`, `axial_dispersion_m2_s`, `wall_loss_rate_s_inv` | Required source particle size, material density, thermophoretic coefficient, and effective dispersion; wall loss optional, with default zero. Size and dispersion need source/setup evidence. |
| Profile `collision_kernel_m3_s` or `gas_mean_free_path_m`, `cunningham_slip_factor`, `laminar_shear_rate_s_inv` | Supply a compatible kernel or the first two inputs to the continuum/slip kernel, with shear optional (default zero). The solver rejects that approximation if `2 × mean free path / diameter > 0.1`. |

THM-20 estimates arrival and aerosol state. An alarm prediction requires a separate detector response characterization.

