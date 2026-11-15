# Build THM inputs from retrieved NASA data

Prepared with SI assistance from OpenAI Codex.

This route connects Kobi's existing file search to all 20 registered thermo
models. Use the normal `run_workflow(prompt, search_results, planner)` entry point
with the existing `{query_id, files}` results. The planner can choose a
model-ready JSON, a reviewed FLEX mapping, or a field map over raw data. A
calculation operation runs one THM model. Applications can issue additional
operations with the same search results if the question calls for more models.

## What the planner provides

For selected sources in CSV, JSON, PDF, plain text or Markdown, use a
`run_thermo_model` operation. Select the files referenced by the assignments,
with one as the operation's `file_id`. Set `template_file_id: null` and
`bindings: []`. Serialize the object below as the existing `request_json` string.

```json
{
  "input_mapping": {
    "assignments": [
      {
        "target": "/params/pressure_kpa",
        "source": {
          "kind": "quote",
          "file_id": "report",
          "page": 4,
          "quote": "at 0.5 atm pressure",
          "token": "0.5",
          "unit": "atm"
        }
      }
    ]
  }
}
```

This is one field of a THM-02 request. That model also needs
`/params/mole_fracs/*` and `/params/temp_k`. Example model JSONs supply the
input structure. Route names, units, quantity wrappers and field availability
come from the [field contracts](../src/request_planner/input_contracts.py).
For a printable machine-readable catalog, run:

```powershell
uv run python -c "import json; from request_planner.input_contracts import catalog; print(json.dumps(catalog(), indent=2))"
```

| Source kind | Fields and behavior |
|---|---|
| `csv` | `file_id`, exact `column`, optional zero-based `row` and/or exact `where: {column, equals}`. A scalar selection must resolve one row. Target a `#` path with a column, optionally `rows: [start, stop]` (half-open) or `where`. Source units come from verified column metadata or an explicitly selected unit that matches the printed header when metadata is absent. |
| `json` | `file_id` and `pointer` to a scalar, quantity wrapper or array in the retrieved file. For an array of objects, map a pointer such as `/records/#/signal` to a `#` target. Numeric values need `{value, unit}` or verified variable metadata. Each bulk column must share one source unit. A source already holding a structured THM input can instead use the existing direct JSON route. |
| `quote` | `file_id`, exact `quote` and `token`. Numeric tokens also need the exact printed `unit`; an optional `unit_quote` can point to a repeated table header in the same page or text file. `page` is a one-based PDF page index. Omit it for plain text/Markdown. |
| `prompt` | Same `quote`, `token` and numeric unit as above, checked against the user's prompt. This records scenario values separately from file evidence. Supply the original prompt when replaying a saved request that uses prompt bindings. |
| `config` | A `value` for a method, mode, ID, Boolean setting, plot resolution or named gravity. Record real material and setup identity when selecting IDs. |
| `copy` | `target` containing another assembled, sourced field. For example, copy an exact oxygen measurement to both endpoints of the matching validity array. Units are checked again at the destination. |

Use concrete indices for lists where different sources supply different
elements. `#` in a target broadcasts a CSV column or JSON array. Use actual
keys for `*` map positions (e.g. `/params/mole_fracs/O2`). Match the sample
grid and verified run IDs for multi-channel measurements. The assembler keeps
field-level provenance, checks numeric units, sets the solver routing keys,
and reports missing model inputs before execution where the contract can
identify them. Model validators then enforce their physical limits.

## Try the public NASA report example

This saved request reads the reported n-decane droplet size, atmosphere and
hot-stage regression from NASA's R377 report, and combines them with a user
request for a 10-second reconstruction. The same question runs from the dashboard
in [Thermo mode](../NASA%20Space%20Apps/frontend/README.md). The model input and frontend response
are separate JSON outputs. In a frontend calculation block, show model-provided
`data.assumptions` when present and any scenario choices in the response's
`warnings`. The `assembled_input_provenance.field_sources` map also shows the
value for each `config` binding.

```powershell
uv run thermo-execute --search-results examples/r377_report_search.json --request examples/r377_report_request.json --prompt "How much does a burning fuel droplet shrink in 10 seconds in space?" --model-input r377-thm10.json --output r377-response.json
```

The model uses the reported **0.41 mm²/s** regression rate and gives a
diameter of about **3.48 mm at 10 s**. For backend code, pass
`on_model_input(model_id, payload)` to `run_workflow` or `execute_request`
to capture the validated inputs. The frontend calculation block also carries
`assembled_input_provenance`.

## Coverage and interpretation

- The generic field mapping is shared by THM-01 through THM-20. Each model
  gets its own canonical fields, units and mode conditions. Source selection
  still has to provide the measurements, physical properties and calibration
  that model needs. Selecting a relevant document can lead to `needs_input`.
- PDF handling extracts searchable text. For scanned reports or values available
  only as plotted points, provide a reviewed transcription or digitized table
  with its original citation. For workbook data, export the relevant sheet as
  CSV with exact headers and verified units. PDF page extraction is bounded
  for planner inspection. An exact page hint in the search record's
  `conditions.page` or the user's prompt can surface a specific later page.
- Quote verification establishes that the value and stated units occur in the
  cited passage. Matching the specimen, test conditions and scientific meaning
  still depends on the document context and the model's applicability checks.
  An example input is useful for validating the format. Its values apply to
  the example it describes.
