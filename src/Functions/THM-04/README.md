# Flame in Freefall · THM-04 oxygen-consumption calorimetry

THM-04 calculates the time history and total energy of an experimental fire from the oxygen it consumes. It accepts synchronized measurements from a well-mixed exhaust duct or paired inlet and outlet oxygen mass-flow channels.

## Run the example

Open PowerShell at the repo root. With the project Python environment from the [THM-16 setup instructions](../THM-16/README.md#run-the-example), run:

```powershell
.\.venv\Scripts\python.exe THM-04/thm_04.py THM-04/THM-04_input.json
```

Python 3.10 or later is sufficient for this model. You can also use `py -3` in place of the project interpreter. The command prints JSON.

The included 10 s excerpt is from a NIST ground-based natural-gas burner test. It produces about **309 kW peak** and **3,055 kJ** over that excerpt. Integrating the independently metered burner channel for the same timestamps gives **2,997 kJ**, a difference of about **1.9%**. [NIST burner data and test parameters](https://www.nist.gov/el/fcd/design-fires-residential-and-office-items/ngqc3m2kgs)

## Inputs for the dashboard

The AI and backend assemble **one** [input JSON](THM-04_input.json). Its `request` section describes the scenario. Its `evidence` section carries retrieved measurements, model parameters and sources. Feed the entire parsed JSON object to the Python entry point from the repo root.

```python
from importlib import import_module

run_request = import_module("THM-04.thm_04").run_request
result = run_request(payload)
```

Set `request.topic` to `"heat_release"` and `request.analysis` to `"estimate_hrr"`. Set `request.scenario.run_id` to the ID of one item under `evidence.runs`. Optional `time_window_s` gives two timestamps inside the recorded interval. The solver linearly interpolates calculated rates at window boundaries and integrates the selected portion. Omit it to analyze the whole record.

Each evidence run has `id`, `measurement_method`, `samples`, `source_url` and `source_locator`. Every sample has `time_s`. Supply at least two samples in strictly increasing order, with the analyzer lag and channel synchronization already addressed. Set `evidence.provenance.illustrative` for synthetic examples and record estimated parameters in `evidence.provenance.notes`.

| Measurement method | Channels and parameters |
| --- | --- |
| `exhaust_mass_flow` | Set `gas_basis` to `"dry"`. Give wet exhaust flow as `mass_flow_kg_s` and dry `o2_vol_frac`, `co2_vol_frac`, `co_vol_frac` at each timestamp. Mole or volume fractions use values from 0 to 1. Give the same three inlet fractions in `inlet`, with `water_vapor_vol_frac` on a wet basis, `expansion_factor`, and `gas_molar_mass_kg_mol` for the inlet mixture. |
| `paired_oxygen_mass_flow` | Give `inlet_o2_kg_s` and `outlet_o2_kg_s` at each timestamp. Include net `net_co_kg_s` or `net_co2_kg_s` channels if measured. This mode fits a setup that measures oxygen mass rates on both sides. |
| Both methods | Optional `heat_per_kg_o2_J` defaults to 13.1 MJ/kg O₂. Supply `soot_carbon_kg_s` if measured as carbon mass flow. To compare against an independent rate, supply `reference_hrr_W` for each sample and `benchmark.source_url` and `benchmark.source_locator` on the run. Supply each optional channel for the entire analyzed record or omit it. |

The backend can use a different experiment by mapping its measured channels to one of the two methods. The NIST example uses the fuel-specific 12.54 MJ/kg O₂ and pre-burn O₂/CO₂ baselines from the CSV. Its inlet humidity is unavailable and handled with a documented dry-inlet assumption. NASA Saffire VI is the spaceflight precedent for this method. To rerun that experiment, use synchronized oxygen measurements with verified flow units. [Saffire VI report, Figure 5 and Table 2](https://ntrs.nasa.gov/api/citations/20240002981/downloads/Saffire-ICES-2024-ICES-365-accepted%20final.pdf)

For an input or evidence mismatch, the Python call raises an error and the CLI returns a usage error. The backend can use that message to request the missing or compatible data.

## Equations

In exhaust-flow mode, let `I = 1 − xO2 − xCO2 − xCO` be the residual dry inert fraction. Superscript `in` denotes the inlet and `out` denotes the exhaust.

```text
Dry exhaust / inlet molar flow       r = I_in / I_out
Oxygen depletion factor             φ = (xO2_in − r × xO2_out) / xO2_in
Estimated dry inlet molar flow      n_in = m_exhaust × (1 − xH2O_in) / ((1 + φ(α − 1)) × M_air)
Oxygen actually consumed            mO2 = M_O2 × n_in × (xO2_in − r × xO2_out)
Net species rate (CO or CO2)         m_i = M_i × n_in × (r × x_i,out − x_i,in)
```

Paired-flow mode takes the measured difference between inlet and outlet oxygen mass rates. In either mode, `E` is the heat per kg of O₂ consumed. The optional CO and elemental-carbon soot corrections account for the oxygen and heat of completing their oxidation.

```text
O2 needed to oxidize net CO          mO2,CO = 0.5 × (M_O2 / M_CO) × mCO
O2 needed to oxidize soot carbon     mO2,C = (M_O2 / M_C) × mC
Corrected power (W)                  Q = E × mO2 + (E − E_CO) × mO2,CO + (E − E_C) × mO2,C
Heat over the sampled window (kJ)    integral of Q by trapezoids / 1000
```

The exhaust-flow method uses the NIST dry-inert balance and wet exhaust-flow approximation, including the assumption of similar mean inlet and exhaust molar masses. Soot correction treats measured soot carbon as elemental carbon. Signed samples are retained to make baseline problems visible. [NIST TN 2077, Eqs. 4–12](https://doi.org/10.6028/NIST.TN.2077), [Chow and Han, incomplete combustion corrections](https://doi.org/10.1016/j.applthermaleng.2010.09.010)

## Output for plots and other models

- Use `time_s` with `hrr_kW` for the power curve and `cumulative_heat_kJ` for cumulative energy. Show `peak_hrr_W`, `peak_hrr_time_s`, and `total_heat_release_kJ` with the selected window.
- Pass `time_s` and `hrr_W` to THM-19 as the fire input. Use `hrr_W` matched to the radiometer timestamps or averaging window for THM-14. The backend aligns the data by run and time. Use the derived `co2_production_kg_s` and `oxygen_consumption_kg_s` where THM-19 also needs species source terms and the setup supports that handoff.
- If present, plot `benchmark_check.reference_hrr_W` on the same time axis. A missing optional species or correction is returned as `null`. Show the `warnings`, `sources` and `provenance` with the result.

Code, README and example JSON prepared with SI assistance from OpenAI Codex.
