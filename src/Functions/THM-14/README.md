# THM-14 · Radiative heat release and fraction

From the repository root in PowerShell, run:

```powershell
python .\THM-14\thm_14.py .\THM-14\THM-14_input.json
```

Use Python 3.10+ with the standard library.

## What it calculates

A radiometer measures incident flux at one location in W/m². The geometry converts the background-corrected reading `q_net = q_read − q_bg` to total radiant power `Q̇_rad` in W.

- With `view_factor`, `Q̇_rad = q_net A_detector/(F₁₂ τ)`. Supply detector active area `A_detector` in m², transmission `τ` and the fraction `F₁₂` of the emitting source's radiant power that reaches the detector geometrically. Using a standard geometric view factor assumes a diffuse source represented by the given geometry and an area-averaged flux reading. Use source-to-detector direction for `F₁₂`.
- With `isotropic_point_source`, `Q̇_rad = 4πr² q_net/(τ cos θ)`. This requires an approximately isotropic source, distance `r` in m in the far field, and detector incidence angle `θ` from the detector normal in degrees. This is an inverse-square approximation for a compact flame.
- Optionally supply `geometry.gray_body` with `emitting_area_m2`, `emissivity`, `temperature_k` and `surroundings_temperature_k` for a separate net exchange estimate `εσA(T⁴ − T_sur⁴)` into large isothermal surroundings with unit view factor. This comparison has no effect on the radiometer-derived fraction.
- Radiative fraction is `χ_rad = Q̇_rad/Q̇_total`. The time-integrated fraction is `∫Q̇_rad dt / ∫Q̇_total dt` using trapezoids over the samples. It weights points by energy.
- Negative net flux, zero total HRR and radiative fraction above one produce sample flags. Signed estimates remain visible and the fraction is null where the denominator is zero. A single sample gives instantaneous outputs and null integrated quantities.

Use an incident radiant flux reading or a sensor signal already calibrated to that quantity. If the instrument responds to convection too, apply instrument corrections first. Flame shape, obscuration, directional radiation and changes in viewing geometry can affect the inversion. The supplied geometry is fixed over the analyzed period. Background is in the same units as the reading. If transmission is omitted, it defaults to one. If background is omitted, it defaults to zero.

## JSON and backend handoff

Use one JSON object with `request` and `evidence`. Set topic to `heat_release`, analysis to `estimate_radiative_fraction`, and set `request.scenario.run_id` to the matching record in `evidence.runs[]`. The record contains `geometry` and one or more `samples`. Each sample has `time_s`, `radiometer_flux_w_m2`, and `total_hrr_w`, with an optional per-sample `background_flux_w_m2` overriding the geometry default. Include `evidence.provenance` and `evidence.sources`.

If THM-04 is the HRR source, take its `time_s` and `hrr_W` arrays and align independent radiometer measurements to the same experiment clock. Copy each corresponding `hrr_W` value to the THM-14 sample's `total_hrr_w`. The backend or preprocessing code aligns the samples and records any interpolation, time lag correction and calibration. Do not pair different experiments. Call `run_request(payload)` with the assembled request.

Plot `plot_data.time_s` against `radiant_power_w`, `total_hrr_w` or `radiative_fraction`. Use `sample_flags` by matching index. A 0.25 fraction is 25%. The example uses synthetic readings and geometry and returns 25% at every timestamp and 25% integrated. The NASA Saffire VI paper shows examples of paired radiometer and HRR histories. The NIST note provides an example of using a far-field radiometer to estimate a radiant fraction.

[NASA Saffire VI paper](https://ntrs.nasa.gov/citations/20240002981) · [NIST Technical Note 2083](https://nvlpubs.nist.gov/nistpubs/TechnicalNotes/NIST.TN.2083.pdf)
