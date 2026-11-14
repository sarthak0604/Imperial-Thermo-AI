# THM-13 · Low-speed radiative quenching

From the repository root in PowerShell, run:

```powershell
python .\THM-13\thm_13.py .\THM-13\THM-13_input.json
```

Use Python 3.10+ with the standard library.

## What it calculates

The model compares oxygen-fed heat input with radiation and an optional constant additional loss near the low-flow extinction branch. Use properties for a single flame and geometry, expressed on the same reference area.

- The total optically thin absorption coefficient is `κ = Σ(p_i kP_i) + κ_soot`. Partial pressures `p_i = x_i P` use atm here. Supply temperature-appropriate Planck mean coefficients per atm in m⁻¹/atm. The two gases are CO₂ and H₂O. Optional soot absorption is an effective coefficient in m⁻¹. The model checks `κL ≤ 0.1` for the supplied optical path `L`.
- Gas radiation per reference area is `q_g = 4σκ(T_g⁴ − T_sur⁴)(V_g/A_ref)`. Net solid emission is `q_s = εσ(T_s⁴ − T_sur⁴)(A_s/A_ref)` with a view of the surroundings of one. The gas temperature, surface temperature and effective radiation properties stay fixed in the sweep.
- The reduced heating closure is `q_chem = η (P/RT_∞) x_O₂ (u + u_diff) ΔH_O₂`. Use Pa for `P` in this equation, J/mol of oxygen for `ΔH_O₂` and m/s for `u`. Here `η` is an effective oxygen capture and heat-coupling fraction referred to the same area. It needs evidence for the selected system. The optional `oxygen_diffusion` object in a profile supplies `diffusivity_m2_s` and `length_m`, giving `u_diff = D_O₂/L_O₂` for a linear oxygen concentration drop to a depleted reaction zone. Leave it out for an effective flow-only calibration. Fit or select the coupling consistently with the chosen transport terms to avoid counting diffusion twice.
- The heat margin is `q_chem − (q_g + q_s + q_other)`. The critical speed or oxygen is the value that makes this margin zero with the other inputs fixed. Negative margin indicates the low-flow side of the heat-balance boundary.

Use supported low-speed cases with nearly uniform radiating-gas conditions and optically thin paths. Strong absorption, changes in flame structure and high-flow blowoff need separate models. A positive margin indicates that the reduced heat budget closes. Flame stability also depends on transport and chemistry.

## JSON and backend handoff

Use one JSON object with `request` and `evidence`. The topic is `extinction` and the analysis is `estimate_radiative_quench`. Under `request.scenario` include `profile_id`, `material_id`, `setup_id`, `gravity`, `flow_direction`, `u_flow_ms`, `x_o2`, `pressure_kpa`, `t_amb_k`, `co2_frac`, `h2o_frac` and `surface_emissivity`. The CO₂ and H₂O inputs are in the radiating gas and the oxygen fraction is in the inlet. All three are mole fractions. Optionally supply `surroundings_temperature_k`, defaulting to inlet temperature. Under `evidence.profiles[]` provide the same identifiers, numeric validity ranges and the heat-balance properties illustrated by the example. Include `evidence.provenance` and `evidence.sources`.

Call `run_request(payload)` for the heat budget, within-range threshold estimates and graph data. Plot `plot_data.chemical_input_w_m2` and `plot_data.heat_loss_w_m2` against `plot_data.air_speed_m_s`. Thresholds return null when the crossing is outside the supplied bounds or undefined. `quench_branch` returns a table with rows `[speed_m_s, oxygen_percent]` when there is a positive-loss crossing over a nonzero length of the covered speed interval.

For THM-17, copy `quench_branch` to the selected calibration's `quench` field. Use the same material, apparatus, gravity, flow direction and pressure. Set `axis_units_per_m_s` to 1 and use a speed range within both `quench_speed_range_m_s` and the independently supported blowoff branch's range. Keep the source and assumptions of both branches in the combined evidence. THM-17 needs a separate blowoff branch and combination rule.

The included PMMA case uses illustrative coefficients to exercise the math and integration. At 21% inlet oxygen it gives a threshold near 1.17 cm/s. NASA's BASS-II work documents low-speed quenching in microgravity and supplies the physical context.

[NASA BASS-II report](https://ntrs.nasa.gov/api/citations/20210011385/downloads/TM-20210011385.pdf?attachment=true) · [NASA studies of radiative extinction](https://ntrs.nasa.gov/citations/19930011002) · [TNF workshop Planck means](https://tnfworkshop.org/radiation/)
