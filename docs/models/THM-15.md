# THM-15 · Soot inception screening

Estimate whether local conditions in a diffusion flame support the onset of soot formation, and estimate how thermophoresis changes radial particle motion.

## Run

From the repository root in PowerShell, use the existing project Python or any Python 3.10 or later. This model uses the standard library.

```powershell
.\.venv\Scripts\python.exe src/Functions/THM-15/thm_15.py src/Functions/THM-15/THM-15_input.json
```

The CLI prints JSON. The backend can pass the parsed [input file](../../src/Functions/THM-15/THM-15_input.json) directly.

```python
from request_planner.function_registry import run_model

result = run_model("THM-15", payload)
```

The AI fills `request` with the scenario. Retrieval supplies the matching `evidence` records and their source links. The model accepts fresh records in this format.

## Input

- Use `request.topic = "soot"` and `request.analysis = "screen_soot_inception"`. In `scenario`, set `calibration_id`, `fuel_id`, `setup_id`, `gravity`, and `pressure_kPa`. The identifiers and pressure must match the calibration under `evidence.calibrations`.
- Supply `flame_temperature_K` at the fuel-side composition used for the threshold, `residence_time_s`, and the local `carbon_to_oxygen_atomic_ratio`. Use `temperature_gradient_K_m` and `radial_gas_velocity_m_s` with the outward sign convention.
- Supply the calibration's `threshold_curve` ordered by increasing residence time, the minimum atomic C/O, the transport properties, and any `temperature_margin_band_K`. Use `evidence.sources` and `evidence.provenance` to explain where the threshold and transport parameters came from. Temperature, composition, and residence time should describe the same flame region. THM-01 adiabatic temperature needs a supported mapping before use as a local temperature.

## Calculation and output

The model interpolates threshold temperature linearly in log residence time within the supplied curve. It computes the temperature and composition margins. At or above the minimum C/O, cases within the supplied temperature band return `near_threshold`, and cases above the band return `inception_possible`. Cases below the required C/O or below the band return `below_inception_criteria`.

```text
Temperature margin  = T_local − T_threshold(t_res)
Thermophoretic speed = −K_th × ν × (dT/dr) / T_local
Radial particle speed = radial gas speed + thermophoretic speed
```

Plot `threshold_curve` against residence time and mark the scenario temperature. Display `inception_screen` and the two velocities from the output. The example uses a published **1190 K** long-residence reference at atomic C/O **0.6**. The example's transport inputs and **50 K** screening band are illustrative. The result screens for soot inception. Visible color, soot yield, and detector response need separate information. [NASA soot limits, Fig. 4 and conclusions](https://ntrs.nasa.gov/api/citations/20070017900/downloads/20070017900.pdf), [Thermophoresis reference](https://doi.org/10.1017/S0022112080001905).

Code, README, and example prepared with SI assistance from OpenAI Codex.
