# THM-20 · Smoke aerosol transport and coagulation

Estimate smoke transit, changes in particle count, and equivalent particle size in a straight duct. The example uses illustrative inputs for processes investigated by SAME and SAME-R. [NASA smoke experiment](https://ntrs.nasa.gov/citations/20140006579).

## Run

From the repository root in PowerShell, use the existing project Python or any Python 3.10 or later. This model uses the standard library.

```powershell
.\.venv\Scripts\python.exe src/Functions/THM-20/thm_20.py src/Functions/THM-20/THM-20_input.json
```

The CLI prints JSON. The backend can pass the parsed [input file](../../src/Functions/THM-20/THM-20_input.json) directly.

```python
from request_planner.function_registry import run_model

result = run_model("THM-20", payload)
```

The AI fills `request` with the scenario. Retrieval supplies the matching `evidence` records and their source links. The model accepts fresh records in this format.

## Input

Use `request.topic = "smoke"`, `request.analysis = "estimate_aerosol_transport"`, and set `scenario.profile_id` and `setup_id`. Give `duct_length_m`, `duct_area_m2`, `air_speed_m_s`, `axial_temperature_gradient_K_m`, `smoke_mass_rate_kg_s`, and `duration_s`. The gradient is positive if temperature rises toward the outlet. The smoke mass rate is a particle source term. A THM-15 inception flag alone cannot supply it.

The matching profile under `evidence.profiles` supplies `scenario_bounds` as ranges for applicable numeric inputs. It gives representative gas temperature, dynamic viscosity and density, source particle diameter and material density, the thermophoretic coefficient, and axial dispersion in SI units. Use the example for the exact keys. Optional `wall_loss_rate_s_inv` sets a size-independent removal rate. Supply a constant `collision_kernel_m3_s` for the regime, or use the continuum/slip approximation with `gas_mean_free_path_m`, `cunningham_slip_factor`, and optional `laminar_shear_rate_s_inv`.

## Calculation and output

```text
Particle drift        u_p = u_air − K_th × (μ/ρ) × (dT/dx)/T
Travel time           t_adv = duct_length / u_p
Inlet mass density    m0 = particle_mass_rate/(u_p × duct_area)
Number balance        dn/dt = −(K/2)n² − k_wall n
Mass balance          dm/dt = −k_wall m
Equivalent diameter   d_eq = (6m/(π ρ_particle n))^(1/3)
```

The optional default kernel adds equal-size Brownian and laminar shear terms under slip-continuum conditions. The transport arrival fraction is the first-passage probability for a packet with constant drift and dispersion. With zero dispersion the packet arrives at the advective travel time.

Use `time_s` for parcel-aging curves and the kinematic `packet_transport_arrival_fraction`. Use the returned `*_at_mean_arrival_*` fields to summarize conditions at the detector location. The parcel curves describe the same inlet parcel as it ages. Detector signal and alarm time require a separate response or measured alarm curve. The default model resolves a compact-particle equivalent size and number concentration. It assumes uniform flow and coefficients. [Talbot et al. thermophoresis](https://doi.org/10.1017/S0022112080001905), [Aerosol coagulation equation](https://doi.org/10.1080/02786826.2013.770126).

Code, README, and example prepared with SI assistance from OpenAI Codex.
