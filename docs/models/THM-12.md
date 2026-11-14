# THM-12 · Multicomponent droplet evaporation

From the repository root in PowerShell, run:

```powershell
python .\src\Functions\THM-12\thm_12.py .\src\Functions\THM-12\THM-12_input.json
```

Use Python 3.10+ with the standard library.

## What it calculates

The model estimates vapor-liquid equilibrium and preferential evaporation or uptake for a nonboiling liquid mixture at a supplied surface temperature.

- Integrated Clausius–Clapeyron gives `p*_i(T) = p*_i(T_ref) exp[(ΔH_vap,i/R)(1/T_ref − 1/T)]`. Each pure-component reference pressure is in kPa, temperature in K and enthalpy in J/mol.
- Modified Raoult's law gives `p_i,s = γ_i x_i p*_i(T)`. The AI can supply nonideal activity coefficients. The example explicitly sets `γ_i = 1`.
- The total surface vapor pressure is `Σp_i,s`. The surface gas mole fraction is `p_i,s/P` and the mole fraction among the modeled vapors is `p_i,s / Σp_i,s`.
- A supplied effective transfer conductance `G_i` gives `ṅ_i,out = G_i(p_i,s − p_i,∞)` in mol/s if `G_i` is in mol/(s·kPa). Positive transfer removes liquid. Negative transfer adds liquid.
- Optional time evolution integrates `dn_i/dt = −ṅ_i,out` with `x_i = n_i/Σn_i` and fixed temperature, activity coefficients, transfer conductances and far-field partial pressures. The solver uses midpoint updates with positivity-preserving exponential steps and stops at the requested duration or minimum total inventory.
- Optional liquid transport inputs produce the liquid mass Péclet number `Pe_L = u_L R_L / D_L`. It is a comparison of circulation and molecular diffusion and is reported separately from the well-mixed solve.

Supply coefficients over the temperature and composition range you use. Time evolution treats the liquid as spatially uniform and keeps the effective conductances fixed. Cases with appreciable internal gradients, changing droplet heat balance, strong composition dependence of activity coefficients, or boiling need a different closure. The remaining gas carrier is implicit through the difference between total chamber pressure and the sum of the supplied species partial pressures.

## JSON and backend handoff

Use one JSON object with `request` and `evidence`. Set the topic to `droplet_evaporation` and analysis to `estimate_multicomponent_evaporation`. Under `request.scenario`, send `profile_id`, `liquid_fractions` as a map of component IDs to mole fractions summing to one, `ambient_partial_pressures_kpa` with the same IDs, `t_surface_k` and `pressure_kpa`. Match `profile_id` to `evidence.profiles[].id`. Each record contains `validity` ranges for surface temperature and pressure and a list of `components` supplying the property data. Use `"volatile": false` for an involatile species and supply zero ambient partial pressure for it. See the example for the exact property fields. Also include `evidence.provenance` and `evidence.sources`.

Omit `time_evolution` for a surface snapshot. To get a history, supply transfer conductances and `time_evolution.initial_total_moles` and `duration_s`. Optional `min_total_moles` defaults to 0.01% of the initial inventory and `plot_points` defaults to 101. Optional `liquid_transport` accepts `radius_m`, `circulation_speed_m_s` and `mass_diffusivity_m2_s`.

Call `run_request(payload)` from Python. Plot `plot_data.surface_partial_pressure_kpa` and `ambient_partial_pressure_kpa` against `component_id`. For the evolution, plot `plot_data.evolution.by_component[id].liquid_mole_fraction` or `net_outward_transfer_mol_s` against `plot_data.evolution.time_s`. A missing conductance gives a null transfer rate even when the direction is known. Feed compatible composition and surface-state inputs into a successive model only with separate evidence for its properties and transfer assumptions.

The sample starts with equal mole fractions of methanol and water at 298.15 K. The initial surface partial pressures are about 8.47 kPa for methanol and 1.58 kPa for water. At 2 kPa ambient water partial pressure, water initially enters the droplet while methanol evaporates. The scenario and conductances are illustrative.

[NIST methanol properties](https://webbook.nist.gov/cgi/cbook.cgi?Name=methanol&cTP=on) · [NIST water properties](https://webbook.nist.gov/cgi/cbook.cgi?ID=C7732185&Mask=4) · [Marchese and Dryer on methanol/water droplets](https://doi.org/10.1016/0010-2180(95)00179-4)
