# Search results → structured request → Python → frontend

SI-assisted implementation and synthetic examples prepared with OpenAI Codex.

The application boundary is `request_planner.service.run_workflow(prompt,
search_results, planner)`. Supply the existing `{query_id, files}` search contract.
It returns a `FrontendResponse`; use `.model_dump(mode="json")` in your HTTP handler.
No frontend framework or HTTP server is imposed by this library.

```python
from request_planner.planner import OpenAIPlanner
from request_planner.service import run_workflow

response = run_workflow(
    user_prompt,
    graph_search_results,
    OpenAIPlanner(model="YOUR_MODEL_ID"),
)
return response.model_dump(mode="json")  # Your web framework serializes this.
```

Set `OPENAI_API_KEY` for live planning. The model must support Structured Outputs.
The graph search still owns retrieval/ranking; this function consumes its results.

## Execution

1. The LLM chooses file IDs and an action using metadata and registered function
   input contracts. Download URLs are resolved by Python from the original results.
2. If necessary it requests inspection. Python downloads only the selected datasets
   to a temporary directory. CSV inspection checks every row, exact headers and
   numeric suitability. It preserves supplied units; unknown units remain null.
   JSON inspection returns a bounded content preview to the LLM.
3. The LLM receives inspected contents and proposes another structured request.
   There are at most three planning rounds. Previews may be truncated; execution
   always uses the full downloaded file. A downloaded file is reused within the
   workflow, and byte/runtime budgets are shared across rounds.
4. Python validates IDs, file roles, operations, units and run compatibility, builds
   the function input, and calls its registered entry point in a worker process.
5. The response contains the validated requests, full function results, chart
   arrays, selected media links, input hashes and source caveats. Temporary
   downloads and worker files are removed on success or failure.

`calculate` supports a CSV `plot_relationship` and `run_thermo_model` for THM-01
through THM-20. The registry loads only fixed paths in `src/Functions`, packaged
as `thermo_functions`; the LLM cannot select a module path or submit Python code.
THM-16 requires NumPy/SciPy, declared in project dependencies. Cantera remains an
optional implementation used by existing functions when available.

## Structured THM requests

See [thermo_plan.json](../examples/thermo_plan.json) and the full
[thermo_request.json](../examples/thermo_request.json). The existing service-request
envelope and actions remain compatible with earlier examples. A THM operation is:

```json
{
  "name": "run_thermo_model",
  "file_id": "synthetic-measurements",
  "parameters": {
    "model_id": "THM-04",
    "request_json": null,
    "template_file_id": "synthetic-template",
    "bindings": [{
      "target": "/evidence/runs/0/samples",
      "mode": "records",
      "row": null,
      "columns": [
        {"column": "time_s", "field": "time_s", "unit": "s"},
        {"column": "inlet_o2_kg_s", "field": "inlet_o2_kg_s", "unit": "kg/s"},
        {"column": "outlet_o2_kg_s", "field": "outlet_o2_kg_s", "unit": "kg/s"}
      ]
    }]
  }
}
```

For JSON datasets, the downloaded object contains a function-compatible payload.
THM-04–06 and THM-10–20 use `{request, evidence}`. The older adapters use their
`params`/`inputs` conventions; repository example wrappers with `example_request`
are unwrapped. `request_json: null` retains the downloaded request. To change a
scenario, supply a JSON string containing the complete replacement request
(`topic`, `analysis`, `scenario`), or only the params object for an older adapter.
It never replaces downloaded evidence. The string field accommodates the varying
THM request shapes inside the provider's strict structured-output schema.

For CSV datasets, mappings copy actual numeric values into existing input slots:

| Mode | Destination | Selection |
| --- | --- | --- |
| `scalar` | Existing numeric value | One column and explicit zero-based `row` |
| `series` | Existing numeric array | One complete CSV column; `row: null` |
| `records` | Existing sample table | One or more complete columns; `row: null` |

`target` is a JSON pointer. All sample fields must be mapped; sample values from a
template are never carried into a partially mapped table. Source units must match
the declared destination units in `request_planner.execution.INPUT_UNITS`, or an existing quantity
object's `unit`. Unknown destination units are rejected; add an explicit unit
contract when extending mappings. Values are not cleaned, dropped, converted or
joined. Blanks, NaN/Infinity, ragged rows and unsuitable columns fail validation.

A CSV for a model requiring calibration must select a separate JSON evidence
template. Both records must have the same investigation and identical nonempty
verified run IDs. The template supplies sourced properties, calibrations, request
shape, and unit conventions; mappings only replace numeric slots. For older
models without evidence blocks, `request_json` can supply the params shape instead
of a separate template. For example, map a measured mass fraction into
`/params/y_ox_stream` for THM-03.

The LLM cannot generate an `evidence` block or fill missing calibrations from
bundled function examples. Function validators still enforce their own conditions.
Missing evidence results in inspection, `no_match`, or `needs_input`; a search hit
alone is insufficient to run every model. A numeric mapping and matching run IDs
cannot establish scientific suitability by themselves.

## Frontend response

The [complete example response](../examples/thermo_frontend_response.json) is computed
from the bundled **synthetic** mass-flow samples. The schema is
[frontend-response.schema.json](frontend-response.schema.json).

```ts
type WorkflowStatus = "completed" | "needs_input" | "no_match" | "error";

interface FrontendResponse {
  schema_version: "1.0";
  query_id: string;
  status: WorkflowStatus;
  message: string;
  requests: ServiceRequest[]; // Same structured requests used for execution.
  blocks: DisplayBlock[];
  sources: Record<string, unknown>[]; // IDs, investigations, hashes, bytes, provenance.
  warnings: string[];
  errors: {code: string; message: string}[];
  generated_by: string;
}
```

Render blocks in order using `type`:

| `type` | Rendering data |
| --- | --- |
| `calculation` | `model_id`, `data` (complete original function JSON), `evidence_type`, `illustrative`, `source_file_ids` |
| `chart` | `chart_type` (`line`/`scatter`), `title`, `x: {label, unit, values}`, `series: [{label, unit, values}]`, evidence labels |
| `video` | `url`, `media_type`, `title`, `file_id`; use a video player or source link |
| `document` | PDF `url`, `media_type`, `title`, `file_id`; use a PDF viewer or link |
| `image` | `url`, `media_type`, `title`, `file_id`; use an image component |
| `inspection` | `file_id`, `kind`; CSV `columns`, `row_count`, `preview`, or JSON `preview`, or an unsupported-format `message` |

THM results with aligned numeric arrays expose line charts automatically. Other
result shapes remain in `calculation.data` for model-specific tables/heatmaps.
Each auto-generated line chart has one series to avoid combining incompatible
scales on one axis. Original names retain unit suffixes; a null chart unit is not
an assertion that the quantity is dimensionless. Plot relationships preserve exact
column names and source units and emit scatter arrays without needing Matplotlib.

Display `message`, `warnings`, model limitations and provenance with the results.
Keep `illustrative`, `data_reduction` and `model_estimate` labels visible. Render
file/model text as text rather than HTML. Media URLs reference the original source;
browser playback/embedding depends on that host's access and CORS rules. PDFs and
videos are not semantically analyzed or summarized by this executor.

`needs_input` means inspection/missing metadata or an incompatible function input
needs attention. `no_match` means the planner found no supported calculation or
selection. `error` means planning, transfer or execution failed. Never display an
error response as a successful calculation.

## CLI and offline verification

```bash
uv sync
uv run python examples/run_workflow_demo.py

# Live LLM planning, inspection, execution and frontend response:
uv run thermo-execute --prompt "Your question" --model YOUR_MODEL_ID \
  --search-results actual-search-results.json --output frontend-response.json

# Saved request: no LLM call; selected datasets are still downloaded:
uv run thermo-execute --request service-request.json \
  --search-results actual-search-results.json --output frontend-response.json

uv run --extra plotting python -m unittest discover -s tests -v
```

The offline demo uses a mock HTTP transport for the explicitly synthetic URLs;
it still writes temporary downloads and runs the real THM-04 worker. It does not
call an LLM. Integration tests also exercise the actual OpenAI SDK against mocked
inspection/structured-plan responses. No live model-quality or NASA execution
claim is implied by those tests.

Server caps are 100 MB of downloaded input and 60 seconds per workflow. Smaller
limits on saved requests are honored. Selected source byte counts are checked when
known. The executor computes SHA-256 for reproducibility; the current search
contract supplies no trusted expected hash. Public HTTP(S) destinations and every
redirect are DNS-checked; deploy with network egress controls against DNS rebinding.
The worker timeout terminates computations; it is not a general code sandbox or
memory quota. Source originals, parsing buffers and model output must fit worker
memory. ZIP/XLSX/HDF5 datasets require an explicit parser extension rather than
being silently interpreted as CSV. Hard process termination can bypass temporary
directory cleanup.
