# THM-17 · Limiting oxygen for sustained spread

Estimate the oxygen concentration needed for an established flame to propagate at a given forced-flow speed in a calibrated microgravity setup.

## Run

From the repository root in PowerShell, use the existing project Python or any Python 3.10 or later. This model uses the standard library.

```powershell
.\.venv\Scripts\python.exe THM-17/thm_17.py THM-17/THM-17_input.json
```

The CLI prints JSON. The backend can pass the parsed [input file](THM-17_input.json) directly.

```python
from importlib import import_module

result = import_module("THM-17.thm_17").run_request(payload)
```

The AI fills `request` with the scenario. Retrieval supplies the matching `evidence` records and their source links. The model accepts fresh records in this format.

## Input

Use `request.topic = "flammability"` and `request.analysis = "estimate_limiting_oxygen"`. Set `scenario.calibration_id`, `material_id`, `setup_id`, `gravity`, `flow_direction`, `pressure_kPa` and `air_speed_m_s`. Optional `ambient_oxygen_pct` produces an oxygen margin in percentage points.

The matching calibration in `evidence.calibrations` identifies the setup and supplies the speed and pressure bounds, `quench` and `blowoff` branches, the axis conversion, and a combination rule. Both branches take the same coordinate and return oxygen in volume percent. The default axis conversion is one for boundaries already in m/s. For a rod tip with forced stretch `a = 1.5 U/R`, supply `axis_units_per_m_s = 1.5/R` using radius in metres. Pressure selects the calibration envelope. Changing pressure beyond it requires new evidence.

- `linear` uses `intercept_pct` and `slope_pct_per_axis_unit`.
- `exponential` uses `base_pct`, `amplitude_pct`, and `decay_per_axis_unit`.
- `table` uses increasing `points` pairs of boundary coordinate and oxygen percent. Tables support the outputs of THM-07 and THM-13 after the backend translates both to oxygen thresholds for the same fuel, pressure, geometry, and speed axis.

## Calculation and output

```text
Boundary coordinate       x = U × axis_units_per_m_s
Two independent criteria  O2_limit = max(O2_quench(x), O2_blowoff(x))
Shared-baseline fit       O2_limit = O2_quench(x) + O2_blowoff(x) − baseline
```

Choose `combination_rule = "maximum"` for two independent criteria. Use `"shared_baseline_excess_sum"` and supply `shared_baseline_pct` when reproducing a fit of the combined form. Plot the speed-indexed `sweep` with the two branches and the combined limit. If supplied, the `reference_1g` record reports a comparison and should retain the test configuration and source.

The example reproduces the published BASS-II pooled PMMA rod fit. It gives about **13.49% O₂** at **2 cm/s** using the 3.18 mm radius conversion. The example assumes nominal pressure and uses a pooled curve across rod sizes. The separately reported Earth reference comes from a different test configuration. The boundary is an estimate for sustained spread, with substantial near-limit variability. [NASA BASS-II boundary, Fig. 4](https://ntrs.nasa.gov/api/citations/20150008961/downloads/20150008961.pdf#page=6), [1g comparison](https://ntrs.nasa.gov/api/citations/20160000593/downloads/20160000593.pdf).

Code, README, and example prepared with SI assistance from OpenAI Codex.
