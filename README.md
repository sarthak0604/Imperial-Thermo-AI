# Imperial-Thermo-AI

We've got thrust issues.

## Run locally

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and run this
from the repository root.

```sh
uv run main
```

The local `main` command and the Cloud Run job run the same CPU PyTorch smoke test in
`src/imperial_thermo_ai/main.py`. Replace the body of `main()` there to run
the application in both environments.

## Run on Google Cloud

Install the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install), sign in,
and select a [billing-enabled project](https://cloud.google.com/billing/docs/how-to/modify-project).

```sh
gcloud auth login
gcloud config set project nasa26  # Replace nasa26 if you use a different project
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
uv run google
```

`uv run google` uploads the current checkout's build files, uses Cloud Build to
build the image, deploys the `imperial-thermo-ai` Cloud Run job, and waits for it
to finish. Source builds need
[Cloud Run deployment permissions](https://cloud.google.com/run/docs/deploying-source-code).
Only files listed by `.gcloudignore` are uploaded.

Pass `--project` or `--region` to override the active gcloud project or default
region. The default region is `europe-west1` unless `GOOGLE_CLOUD_REGION` is set.
The command prints the execution name and a logs link.

```sh
uv run google --project nasa26 --region europe-west1
gcloud run jobs logs read imperial-thermo-ai --project nasa26 --region europe-west1
```


### Choose CPU, RAM, and GPU

Pass `--cpu` for vCPUs per task and `--memory` for RAM per task. Use a size such
as `512Mi` or `8Gi`. Pass `--gpu` to select one GPU per task. If you omit CPU or
RAM, the launcher uses the corresponding default below.

| `--gpu` | Default vCPUs | Default RAM | Example region |
| --- | ---: | ---: | --- |
| `none` (default) | 1 | `2Gi` | `europe-west1` |
| `nvidia-l4` | 4 | `16Gi` | `europe-west1` |
| `nvidia-rtx-pro-6000` | 20 | `80Gi` | `europe-west4` |

```sh
# CPU only
uv run google --cpu 2 --memory 8Gi

# NVIDIA L4
uv run google --gpu nvidia-l4 --cpu 8 --memory 24Gi --region europe-west1

# NVIDIA RTX PRO 6000 Blackwell, using its CPU and RAM defaults
uv run google --gpu nvidia-rtx-pro-6000 --region europe-west4
```

For CPU-only jobs, the supported RAM ranges are 512 MiB to 4 GiB at 1 vCPU,
512 MiB to 8 GiB at 2 vCPUs, 2 to 16 GiB at 4 vCPUs, 4 to 24 GiB at 6 vCPUs,
and 4 to 32 GiB at 8 vCPUs. For GPU jobs, the CPU and RAM defaults in the table
are also the minimums for each model. Google validates the resource combination,
region, and quota. See the Cloud Run docs for
[CPU and RAM limits](https://docs.cloud.google.com/run/docs/configuring/jobs/memory-limits)
and [GPU availability](https://docs.cloud.google.com/run/docs/configuring/jobs/gpu).

Each invocation sets the resources on the job in the selected region. Use
`--gpu none` or omit `--gpu` to detach a GPU from that job. The smoke test in
`main.py` uses the CPU. GPU workloads need to select a CUDA device and use a CUDA
build compatible with the Cloud Run driver. See
[Cloud Run GPU driver libraries](https://docs.cloud.google.com/run/docs/configuring/jobs/gpu#driver-libraries).

Run `uv run google --help` to see all options.

## Request planner

A small Python MVP for this boundary:

```text
User prompt + graph-search JSON + supported operation definitions
                          ↓
                  LLM proposes a plan
                          ↓
           Python validates IDs, inputs, and limits
                          ↓
                Structured service-request JSON
```

It uses OpenAI Structured Outputs and Pydantic. The planner exposes a Python function
and a CLI. A tiny local graph-search command is also available for real-source
testing. No web server or database is needed. A separate optional plotter executes
one supported operation on an already downloaded CSV. There is no downloader or frontend.

## Real PSI example graph

[examples/psi_graph.json](examples/psi_graph.json) contains **11 nodes and 10 edges**:
two real NASA PSI investigations (BASS-II and FLEX), three topics, and six real
file records with verified download URLs. It is the knowledge graph itself;
[examples/psi_search_results.json](examples/psi_search_results.json) is example output
from searching it. No source datasets or media are bundled.

```bash
uv sync
uv run thermo-search \
  --graph examples/psi_graph.json \
  --query "BASS-II airflow calibration video" \
  --investigation PSI-25 \
  --limit 5 \
  --output examples/psi_search_results.json

uv run thermo-plan \
  --prompt "Find BASS-II airflow measurements, calibration and a test video" \
  --search-results examples/psi_search_results.json \
  --replay examples/psi_inspection_plan.json
```

See [the graph notes](examples/PSI_GRAPH.md) for sources, verification details, and
data limitations. Search and replay run offline; for live LLM planning, replace
`--replay examples/psi_inspection_plan.json` with `--model YOUR_MODEL_ID` and set
`OPENAI_API_KEY`.

## Synthetic planner-only example

```bash
uv sync
uv run thermo-plan \
  --prompt "Plot flame spread against airflow for the demo fabric and show the experiment video" \
  --search-results examples/graph_search.json \
  --replay examples/plan.json
```

Replay validates a saved example response. It does **not** call an LLM or interpret
your prompt. No API key is needed, and no files are downloaded. The records in
`examples/graph_search.json` are synthetic, SI-generated metadata with placeholder
URLs, not NASA observations. The separate `psi_*` examples use real source metadata.

For a real model call, set `OPENAI_API_KEY` in your shell and provide a model that
your account can access and that supports Structured Outputs:

```bash
uv run thermo-plan \
  --model YOUR_MODEL_ID \
  --prompt "Plot flame spread against airflow for the demo fabric and show the experiment video" \
  --search-results examples/graph_search.json \
  --output service-request.json
```

You can use `OPENAI_MODEL` instead of `--model`. Environment variables must already
be set; this MVP does not load `.env` files. Live requests use API credits.

## Plot a real dataset

The optional `thermo-plot` command executes `plot_relationship` from a validated
service request. [This generated chart](examples/plots/flex/plot.png) shows all 274
rows of FLEX's recorded ambient pressure and initial ambient-composition columns.
Each marker uses actual table values, without a fitted line, unit conversion, or
row removal. Different fuels and other conditions are mixed, so the chart shows
sampled test conditions rather than an isolated causal effect or a safety limit.

Download the original 24,776-byte CSV, then run the saved example request:

```bash
curl --fail --location --output /tmp/psi-flex.csv \
  'https://psi.nasa.gov/geode-py/ws/studies/PSI-69/download?file=PSI-69_Experimental%20table_FLEX.csv&version=1&redirect=true'

uv run --extra plotting thermo-plot \
  --graph examples/psi_graph.json \
  --request examples/psi_plot_request.json \
  --csv /tmp/psi-flex.csv \
  --output-dir examples/plots/flex
```

Outputs are `plot.png` and `manifest.json`, which includes exact column names,
source IDs, DOI, SHA-256, row count, operation, and warnings. Image metadata and a
visible footer acknowledge SI assistance. Measurement values are NASA source data.
The executor verifies the local file against the graph's checksum and rejects
missing/non-numeric requested values. It does not silently clean or discard rows.
It does not download data, retrieve additional assets, or implement a worker sandbox.
The manifest's artifact path is relative to the output directory; a future web
service can expose it through an artifact URL.

The plot uses [a saved SI-generated plan](examples/psi_plot_plan.json), not a live
LLM call. To exercise planning, search for `FLEX`, then pass those results and the
plotting prompt through `thermo-plan`, using the saved plan for replay or your model
for live generation. Pass the resulting service request to `thermo-plot`.

## Contract with the graph-search teammate

Start with [examples/graph_search.json](examples/graph_search.json). Required file
fields are `file_id`, `investigation_id`, `title`, `role`, and `media_type`. Include
`retrieval_url` for selectable files. Also supply `size_bytes`, `run_ids`,
`variables`, `conditions`, `source_page_url`, and `related_file_ids` when known.
Optional `encoding` and `data_notes` carry inspected parsing details and caveats.

Each variable has an exact `name`, a `unit`, and a `numeric` flag. Use null for
unknown information; use `"1"` as the unit for a known dimensionless quantity.
A landing-page URL is not a substitute for a retrieval URL. The MVP assumes public,
direct file URLs; authentication, archive members, and expiring-link resolution
need a later extension to the retrieval contract.

The schema deliberately rejects extra fields so contract mismatches are visible.
Adapt your teammate's graph response into `SearchResults` if its field names differ.
Actual download URLs are omitted from LLM context and resolved later by file ID.

## What the LLM can request

| Action | Meaning |
| --- | --- |
| `inspect_files` | Retrieve measurement files and discover missing schema/types/units before planning a calculation |
| `calculate` | Request the proposed `plot_relationship` function for two known numeric columns in one CSV |
| `retrieve_assets` | Request PDFs, images, or videos without a calculation |
| `no_match` | No supported next action; return an explanation without executable selections |

A calculation or inspection request can also include requested assets. Only
`plot_relationship` is defined as a calculation contract and implemented by the
optional local plotter for previously downloaded, verified CSVs. It does not aggregate runs, convert
units, or implement general scientific analysis. Unsupported or partially fulfilled
requests should be explained in the plan's explanation/warnings.

The output includes the original `query_id`, a `plan`, fixed download/runtime
limits, a schema version, and SI-generation metadata. For example, its `plan` is:

```json
{
  "action": "calculate",
  "selected_file_ids": ["demo-measurements"],
  "requested_asset_ids": ["demo-video"],
  "operation": {
    "name": "plot_relationship",
    "file_id": "demo-measurements",
    "parameters": {"x": "airflow_speed", "y": "flame_spread_rate"}
  },
  "explanation": "Both columns have declared numeric types and units.",
  "warnings": ["Synthetic example; not NASA observations."]
}
```

Python rejects unknown/duplicate file IDs, invalid action combinations, unsupported
operations, nonexistent columns, missing numeric types/units, unsuitable media
types, missing retrieval URLs, and known selections over the 100 MB total limit.
An invalid plan fails without producing a service request; there is no automatic
repair loop. Unknown sizes produce a warning. Structural validation cannot prove
that a selected experiment answers the scientific question.

## Connect it to your service

```python
from request_planner.models import SearchResults
from request_planner.planner import OpenAIPlanner, build_request

results = SearchResults.model_validate(graph_search_json)
request = build_request(user_prompt, results, OpenAIPlanner(model="YOUR_MODEL_ID"))
service_request_json = request.model_dump(mode="json")
```

The executor should resolve IDs against the original search records, enforce byte
limits while streaming, validate actual file contents, and enforce runtime limits.
The planner does not enforce limits on downloads or computation because it executes
neither. The executor must also validate destination URLs/redirects before fetching.

When the action is `inspect_files`, your service returns discovered columns,
numeric types, and units. Enrich those same file records and call `build_request`
again with the original prompt. This MVP performs one planning step per call;
your orchestrator owns the loop. Preserve unknown units if inspection cannot find them.

To add a calculation, extend the typed operation schema in
[models.py](request_planner/models.py), its definition and preconditions in
[planner.py](request_planner/planner.py), and the downstream function registry.

## Verify

```bash
uv run --extra plotting python -m unittest discover -s tests -v
```

Tests run offline. They cover calculation/inspection/media/no-match requests,
invalid references and inputs, download budgets, and a real OpenAI SDK call using a
mock HTTP transport, including refusal and incomplete-response handling. Mocked
responses verify the integration shape, not live model selection quality. Evaluate
live planning on representative real graph results before integrating downloads.
The plotting checks exercise parsing, invalid values, source-checksum validation,
PNG generation, and the artifact manifest. Without the plotting extra, the image
rendering test is skipped.

## References and SI disclosure

Implementation follows the official OpenAI
[Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs)
and [API quickstart](https://developers.openai.com/api/docs/quickstart).
Core dependencies are the OpenAI Python SDK and Pydantic; the plotting extra uses
[Matplotlib](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.scatter.html).
See `uv.lock` for resolved
packages and versions. The offline SDK test also uses httpx, a dependency of the SDK.
For deeper API implementation help, the OpenAI Developers plugin is an optional resource.

The workflow concept was supplied by the team. Code, tests, documentation, and
synthetic example metadata in this MVP were generated with OpenAI Codex assistance.
Code modules and output metadata acknowledge SI generation. Automated checks do not
constitute scientific validation. The real-source graph contains NASA metadata and
inspected column schemas; no original source files are bundled. The example chart
is a derived visualization of the real FLEX table, with provenance in its manifest.
Competition context is in
[NASA_SPACE_APPS_2026_LLM_CONTEXT.md](NASA_SPACE_APPS_2026_LLM_CONTEXT.md).
