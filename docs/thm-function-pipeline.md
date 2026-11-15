# THM selection, JSON inputs, dependencies, and dashboard reports

The shared backend enables the function pipeline by default for configured local,
API, and OpenAI-compatible providers (`THERMO_FUNCTION_PIPELINE=true`). Source-only
retrieval remains available. `THERMO_FUNCTION_PIPELINE=false` retains the previous
program/action planner. Existing explicit deterministic calculation shortcuts
continue to use their bounded solvers; they also expose method explanations.

For a computational request the backend resolves the requested functions, searches
the active NASA graph, and proposes a typed `FunctionPlan`. Each task records its
scientific purpose, model ID, source mappings, scenario identity, and prerequisites.
The catalogue covers THM-01 through THM-20; only relevant outputs and their needed
prerequisites are included. Planning uses compact descriptions, expanding input
contracts for shortlisted models and registered prerequisites.

## Inputs and execution

`src/request_planner/thm_pipeline.py` validates and topologically orders the plan.
It prepares independent source inputs before executing solvers. Each task gets a
`TASK.input.json`. A task needing an earlier output has a base input prepared,
then its final JSON is completed after that prerequisite succeeds. It is
impossible to finalize an unknown calculated input before obtaining its value.
`TASK.output.json` contains the corresponding function result.

Input origins are explicit:

- A literal user value must match an exact prompt span. Historical values can
  reach this stage through validated conversation resolution.
- A NASA CSV mapping uses a known resource ID, exact inspected column name,
  units, and row/series selection. Source hash, row mapping, and investigation
  are retained. Multiple files require compatible verified run identities.
- Downloaded JSON evidence uses the existing source-fetch/hash checks. Approved
  local calibration packages can also be selected from `THERMO_EVIDENCE_PACKAGES`.
  The model cannot generate its own `evidence` object.
- Explicit scenario scalar changes to a sourced payload use `user_inputs` with
  JSON pointer, exact source quote, and matching units for quantity objects.
  Protected source identities and calibration contents cannot be overridden.
- A prior function output uses a registered source-output/destination-input link,
  exact units and a shared scenario. The downstream task owns its `results` list;
  each entry names the upstream producer using `source_task_id`. Dependency cycles, missing task IDs, unknown
  links, and conflicting linked conditions are rejected.

Each Python function runs through the existing allowlisted worker subprocess.
Downloads are temporary and capped, source profiles are verified, and execution
has a shared runtime budget. Independent valid tasks can finish while another
requires clarification. Failed prerequisites block their dependants. Aggregate
output artifacts are limited to 10 MB per function pipeline response.

The first registered numerical dependency is THM-01's equilibrium adiabatic
flame temperature into THM-07's flame-temperature input. Its theoretical
substitution and heat-loss limitation are disclosed. Other scientific dependencies
need an explicit reviewed adapter before automatic numerical substitution is
allowed; a list of declared dependencies alone does not authorize a transfer.

## Dashboard output

The interface reuses the website's chart renderer (`CH.host` / `CH.frame`) and
report cards. It shows:

1. A summary derived from executed outputs, optionally composed by the LLM with
   result-reference and numerical consistency checks.
2. Actual scalar results, charts from numeric model arrays or declared model
   chart-series metadata, readable axes/units and chart-data tables.
3. Downloadable input, output, and available provenance JSON artifacts.
4. Task order and explicit completed/blocked/missing-input statuses.
5. Detailed model method summaries, governing equations, implementation contract,
   assumptions/evidence boundaries, and literature references from the repository's
   scientific method registry.

Reference descriptions explain the method. They do not establish that a
particular NASA experiment supplied a compatible calibration. User scenarios
remain distinguished from measured inputs, and illustrative packages are labelled.

Temporary files are removed after execution. Their JSON contents are carried in
response artifacts and can be downloaded in the browser; no public persistent
artifact directory or filesystem paths are exposed.

## Scientific coverage

The current graph has no downloadable JSON evidence templates. Verified CSV
profiles and separately approved evidence packages therefore determine actual
computational availability. An appropriate function can be selected while still
requiring additional measurements or calibration. The system must ask for those
inputs rather than fabricate a runnable payload from examples or a merely related
report. The existing narrowly scoped BASS-II calibration calculation is retained.

Output plots are generated only when numeric series, categorical composition,
or declared model chart metadata supports a meaningful chart. Scalar-only results
remain readable tables rather than invented curves. Charts of built-in parameter
sweeps describe model predictions, not additional NASA observations.

## Validation

`tests/test_thm_pipeline.py` checks actual source-to-JSON-to-solver execution,
source provenance, a real THM-01 → THM-07 dependency, JSON preparation before the
first solver, cycle/unknown-link rejection, missing calibration, and shared
backend/dashboard serialization. Browser integration also checks downloadable
JSON, rendered charts, and the detailed method section.

These mechanical tests do not establish scientific accuracy for every model,
calibration, or possible natural-language prompt.
