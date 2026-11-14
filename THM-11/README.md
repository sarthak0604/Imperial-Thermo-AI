# Flame in Freefall · THM-11 two-stage cool-flame model

THM-11 estimates how an isolated alkane droplet shrinks during hot-flame and cool-flame burning in microgravity. It uses evidence for the hot-flame endpoint and cool-stage burning rate, then applies a published scaling law to estimate when the cool flame goes out. The bundled example reconstructs NASA FLEX run R377.

## Run the example

Open PowerShell in the repository's top-level folder. With Python 3.10 or later, run the following command. THM-11 uses Python's standard library.

```powershell
py -3 THM-11/thm_11.py THM-11/THM-11_request.json THM-11/THM-11_evidence.json
```

The script prints JSON. R377's visible flame ends at about **14.6 s**, with **10.9 s** of cool burning and final extinction at about **25.5 s**. The result is marked `calibration_reconstruction` because R377 supplies its own cool-extinction reference.

## Inputs for the dashboard

The backend calls THM-11 with two JSON objects. The AI turns the user's question into a request. The retrieval layer supplies matching experimental evidence with sources.

| File | What it contains |
| --- | --- |
| [THM-11_request.json](THM-11_request.json) | The requested scenario. Use `topic: "droplet_combustion"`, `analysis: "estimate_cool_flame"`, one material ID in `scenario.materials`, and a `scenario.setup_id`. Give initial diameter in `mm`, pressure in `kPa`, and oxygen in `%` as `{"value": number, "unit": "…"}` objects. Give `ambient.additional_diluent` as the setup's string, such as `"none"` for the bundled oxygen/nitrogen setup. Optional `scenario.gravity` must match the setup. |
| [THM-11_evidence.json](THM-11_evidence.json) | A matching setup under `setups` and a fuel under `materials`. Its `calibrations` contain the supported pressure, oxygen, and initial diameter range, the measured starting size, hot extinction time and squared diameter, the cool-stage burning rate, and source information. Its `cool_extinction_references` provide the reference atmosphere, squared extinction diameter, burning rate, and source. Set `provenance.illustrative` to indicate whether the parameters are for an illustrative example. |

The AI may generate new request values and the retrieval layer may supply new evidence in the same format. A run requires exactly one matching calibration and one cool-extinction reference for that setup and fuel. The bundled evidence covers **n-decane at 50.6625 kPa** in oxygen and nitrogen, with **21% O₂ at 4.03 mm** or **17% O₂ at 3.86 mm**. Requests outside that evidence return an error. For a wider case, supply a comparable data-backed calibration and reference, including evidence that two-stage burning applies and that the ambient temperatures are comparable.

The backend can call `run_request(request, evidence)` directly with the two parsed JSON objects. From the repo root, load the module by string because the folder name contains a hyphen.

```python
from importlib import import_module

run_request = import_module("THM-11.thm_11").run_request
result = run_request(request, evidence)
```

## Equations

```text
Each stage                     D²(t) = D_start² − K × (t − t_start)
Effective hot-stage slope      K_hot = (D_0,ref² − D_hot,end²) / t_hot,ref
Oxygen partial pressure ratio  r = (P × x_O2) / (P_ref × x_O2,ref)
Cool extinction timescale       τ = (D_cool,ref² / K_cool,ref) × r^(−3/2)
Cool extinction diameter        D_cool,end² = K_cool × τ
Elapsed cool-stage time         Δt_cool = (D_hot,end² − D_cool,end²) / K_cool
```

Diameter is in mm, time in seconds, and K in mm²/s. At comparable ambient temperatures the oxygen partial pressure ratio approximates the oxygen molar concentration ratio used in the paper. The effective hot-stage slope is calculated from the supplied endpoints. The cool-extinction timescale enters the diameter calculation, and the elapsed duration comes from the drop in squared diameter across the cool stage. The model follows established burning through cool-flame extinction. It requires evidence of the hot-to-cool transition and uses an empirical correlation for the cool endpoint.

## Output and evidence check

- Plot `time_s` against `diameter_mm` or `diameter_squared_mm2`. The 121 aligned samples carry `phase` labels for coloring the two portions of the curve.
- Use `hot_extinction_time_s` and `cool_extinction_time_s` for event markers. Both are measured from the start of modeled burning. `cool_stage_duration_s` gives time spent in the cool stage.
- Keep `status`, `sources`, `limitations`, and any `held_out_check` with the plot. R379 is a conditional estimate. Its calculated final extinction at **24.3 s** is about **11 s later** than the approximately **13 s** read from Figure 1c. Only the final endpoint was held out. The run still supplies its hot-stage endpoint and cool burning rate. Use the result as a research demonstration within the stated setup.

Sources [NASA FLEX report, Figure 1](https://ntrs.nasa.gov/api/citations/20140006750/downloads/20140006750.pdf#page=3) and [Section 3.4 extinction correlation](https://ntrs.nasa.gov/api/citations/20140006750/downloads/20140006750.pdf#page=7).

README prepared with SI assistance from OpenAI Codex.
