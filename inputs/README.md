# Thermo input audit and starter library

This folder gives the backend team a field-by-field reference for every current THM model and a working example of populating model JSON from reviewed property records. In this checkout, the model folders are under `src/Functions/`. The audit also covers the six model interfaces on Liem’s branch.

| File | Use |
|---|---|
| [MODEL_INPUT_AUDIT.md](MODEL_INPUT_AUDIT.md) | Canonical paths and units, required and conditional fields, defaults, field sources, and what still needs setup evidence for THM-01 through THM-20. |
| [properties.json](properties.json) | Versioned reference records with stable IDs, values, units, applicable conditions, derivations and exact sources. Four gas species, water, methanol and an unspecified-grade PMMA sensitivity reference. |
| [demo_cases.json](demo_cases.json) | Eight curated recipes. Five reuse existing NASA-linked model inputs. Three assemble an input using property records. |
| [build_demo.py](build_demo.py) | Prints one runnable input JSON or checks its result against the expected demo values. |

## Run from the repository root

Use Python 3.10 or newer. The builder and the eight demo models use the standard library.

```powershell
.\.venv\Scripts\python.exe -B .\inputs\build_demo.py --list
.\.venv\Scripts\python.exe -B .\inputs\build_demo.py --check
.\.venv\Scripts\python.exe -B .\inputs\build_demo.py methanol_water_snapshot
```

Select a case ID from `--list` to print its assembled JSON. To pipe it into a file on Windows, use `| Set-Content -Encoding utf8 model_input.json`, then pass that file as the argument to the corresponding model CLI. For example, the snapshot uses `src/Functions/THM-12/thm_12.py`. See the case catalog for model IDs and expected results.

## Backend handoff

1. The AI selects the model and extracts the requested scenario. Its result can include candidate property IDs and experiment/calibration IDs. Original user conditions remain part of the request.
2. The backend resolves the candidates by ID, checks material or species, phase, temperature, pressure and any method/grade constraints, then converts units to the target field as needed. A property record is eligible only for its applicable state and intended use. For gas film properties at other conditions, evaluate the appropriate correlation or call THM-02 at a compatible state.
3. Build a fresh single JSON payload using the model's input convention in the audit. Copy the value into the designated field and preserve the record ID, source and conditions. A result derived from an upstream model also carries the input records and upstream model/run ID.
4. If a calibration or setup input is missing, return what the valid calculation can provide and what is needed for the rest. For example, THM-12 gives a transfer direction without a conductance. THM-16 needs a matched ignition calibration even when solid properties are available.

`properties.json` keeps scientific inputs individually traceable. The `unit` for a structured heat-capacity value describes its dependent variable, and the member keys carry their own units. `compatible_reference` means the value can be filled after matching the complete property state. `sensitivity_only` means a specific grade/state link is unavailable and using the record needs an explicit what-if. `demo_only` means the value was reduced for a specific demo input, such as the water enthalpy secant over two temperatures. The gas heat capacities are NIST curves linearized for the 300–400 K THM-18 demonstration. Their pressure window is a demo assumption. The PMMA records come from a reference with an unspecified grade and are not used to calibrate the BASS-II results.

`demo_cases.json` is a set of reviewed recipes for known example scenarios. Paths in `remove`, `set`, `bindings` and `expected` use JSON Pointer syntax. The builder reads `base_payload` relative to the repository, applies removals and overrides, copies library values into bound fields, and attaches per-field provenance under `evidence.provenance.property_bindings`. `expected` addresses outputs and is checked with a numeric tolerance. The builder assembles these fixed recipes. Live matching, user confirmation for what-ifs, and source retrieval belong to the backend's workflow.

## Demo coverage

| Case | Expected headline |
|---|---|
| BASS-II acrylic sheet · THM-05 | About 1.11 mm/s at 0.20 mm thickness. The 0.20 and 0.30 mm measured comparisons are approximate figure reads. |
| Saffire II SIBAL · THM-06 | About 2.36 mm/s for 22.5 cm/s inlet flow. The transient inputs are illustrative and the comparison runs used different sample-card positions. |
| FLEX-002 methanol · THM-10 | About 4.29 s to the measured extinction diameter under constant regression. The published burn time is 5 s. |
| FLEX R377 decane · THM-11 | Final extinction near 25.51 s in a reconstruction using that run as the cool-extinction reference. |
| BASS-II PMMA rod · THM-17 | About 13.49% O₂ at 2 cm/s using the published pooled fit. |
| Methanol/water surface snapshot · THM-12 | Methanol evaporates and water condenses at the selected conditions. Rate fields are null because no conductance is included. |
| 30% CO₂ dilution · THM-18 | A mixture starting at 21% O₂ ends at 14.7% O₂ by mole after the specified dilution. |
| Water mist at the 100 °C saturation point · THM-18 | About 365.9 kJ absorbed for 0.25 kg water heated from 20 to 100 °C with an assumed 50% evaporation. |

Start with the NASA-linked cases for retrieval and plotting. The last three are thermal calculations under explicitly selected conditions. To expand the library, prioritize experiment-specific transport conductances, ignition calibrations and smoke source terms for the target cases. General reference properties can then be reused where their phase, grade and state match.

Prepared with SI assistance from OpenAI Codex.

