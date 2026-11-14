# Flame in Freefall · THM-16 ignition model

THM-16 estimates when the heated face of a solid slab reaches a specified ignition temperature. It models one-dimensional heat conduction, solid pyrolysis, and convective and radiative losses at both faces. The example uses a synthetic slab and calibration.

## Run the example

From the repository root in PowerShell, install the project and its scientific dependencies with uv.

```powershell
uv sync
```

Run the example with the project interpreter.

```powershell
.\.venv\Scripts\python.exe src/Functions/THM-16/thm_16.py src/Functions/THM-16/THM-16_input.json
```

In VS Code, open the repository folder and select `.venv\Scripts\python.exe` with **Python: Select Interpreter** so the editor can find the installed packages.

The command prints JSON. In the example, the heated face reaches the 600 K criterion at about 43.05 s.

## Inputs for the dashboard

The backend assembles one [input JSON](../../src/Functions/THM-16/THM-16_input.json) with these sections.

- `request` is the scenario the AI and backend assemble from the prompt. It names one material and one setup and gives ambient temperature in K, pressure in kPa, oxygen in percent, air speed in cm/s, incident heat flux in kW/m², and heating time in s. Follow the example's exact unit strings.
- `evidence` is the format for retrieved or reviewed model inputs. Supply the matching setup, heat-transfer coefficients, material properties, and a calibration with a source and applicable conditions. The current example shows the required structure using synthetic values.
- [thm_16.py](../../src/Functions/THM-16/thm_16.py) validates the scenario against the supplied evidence. Pressure and oxygen must match one calibration, and air speed, temperature, heat flux, and duration must fall within its bounds. The calibration supplies the surface-temperature criterion. The setup supplies the heat-transfer coefficients.

The backend can pass the parsed input object to the installed solver through its registered ID.

```python
from request_planner.function_registry import run_model

result = run_model("THM-16", payload)
```

## Equations

```text
Slab energy balance   rho c_p dT/dt = k d²T/dx² - rho H_p r
Pyrolysis rate        r = A exp(-E_a / (R T)) Y
Remaining fraction   dY/dt = -r
Surface heat loss     q_loss = h (T_s - T_air) + epsilon sigma (T_s⁴ - T_air⁴)
Front heat input      q_front = absorptivity × q_incident - q_loss,front
Rear heat loss        q_back = q_loss,back
```

Here T is temperature, x is depth, Y is the fraction of solid available for pyrolysis, and H_p is the heat absorbed per unit mass during pyrolysis. The solver starts the slab at the ambient temperature and integrates until the front reaches the calibrated temperature criterion or the heating time ends. Pressure and oxygen are used to match the calibration. Gravity and air speed are handled through the selected setup and supported conditions.

## Output for plots

- Use `time_s` with `surface_temperature_K` and `back_temperature_K` for heating curves. Add a horizontal line at `ignition_criterion_K`.
- Use `time_s`, `depth_m`, and `temperature_by_depth_K` for a heat map. The matrix is indexed as depth by time.
- Use `time_s` with `thermal_penetration_depth_m`, `fourier_number`, or `pyrolysis_mass_flux_kg_m2_s` for engineering plots.
- Show `criterion_reached`, `time_to_ignition_s`, and the evidence metadata beside the plots. A null time means the simulated surface stayed below the criterion during the exposure. THM-16 returns a deterministic threshold estimate.

See the [project and submission context](../challenge-context.md) and the [thermo model tracker](../thermo-models.xlsx).
