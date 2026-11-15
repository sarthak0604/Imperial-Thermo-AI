# Imperial-Thermo-AI

Graph search → LLM request planning → temporary dataset downloads → THM functions
→ frontend JSON with results, chart data, media links and provenance.

See [the shared backend and Omri interface](docs/backend-v2.md) for the v2 workflow and website launch instructions.

## Website: Omri frontend + Hayk2 backend

`final` uses the new IMPER-ai-L interface from `omri` (`4bb5afe`) and the complete
backend from `hayk2` (`23e17ea`). These sources were copied directly, without a
branch merge. The HTTP and result-rendering adapters connect the two; live
questions use Hayk2's backend rather than the frontend demo pipeline.

From a checkout of **final**, deploy the website with:

```bash
uv sync --locked
uv run google-website --project nasa26 --region europe-west1 --service ic-dynamics --public
```

This builds the current checkout on Google Cloud and deploys the website with
Qwen on one L4 GPU. Model weights are downloaded in Cloud Build, not locally.
`uv run google` is the separate batch-job launcher. For requirements, previewing
the build command and local testing, see [Cloud Run website setup](docs/cloud-website.md).

## Run locally

Use Python 3.14 and [uv](https://docs.astral.sh/uv/). From the repository root:

```bash
uv sync
uv run python examples/run_workflow_demo.py
```

The demo uses synthetic fixture data and mocked downloads, then runs the real
THM-04 calculation. It needs no API key or network after dependencies are installed.

The application searches the reviewed NASA PSI graph by default: 19 investigations,
63,244 nodes and 69,463 edges. Set `OPENAI_API_KEY` and `OPENAI_MODEL`, then run:

```bash
uv run thermo-execute \
  --prompt "Show the PSI-39 CFI final science report PDF" \
  --output frontend-response.json
```

`main` and `imperial-thermo-ai` invoke the same workflow. `thermo-plan` produces
only a validated request. `thermo-search --query "BASS-II video"` searches the
reviewed graph without an API key. Supply `--graph` or `THERMO_GRAPH` to override
the snapshot, or `--search-results` to execute an existing retrieval result;
`python -m imperial_thermo_ai.search_files` runs the vector-search integration.
`thermo-plot` is the optional Matplotlib PNG exporter. `thermo-evaluate` evaluates
parser cases supplied with `--cases examples/parser_cases.json`.

Local Qwen parsing/embedding inference additionally requires `uv sync --extra search`.
PyTorch, Transformers and Accelerate are excluded from the default cloud runtime.

## Layout

```text
src/
  imperial_thermo_ai/   Graph search, parser, evaluation and cloud launcher
  request_planner/      LLM contracts, planning, downloads, workers and frontend output
  Functions/            Canonical THM-01 through THM-20 implementations and input contracts
  reviewed_knowledge_graph/output/  Canonical reviewed NASA PSI graph and source cautions
psi_kg/
  src/psi_graph/        Independent graph-building package and NASA adapter
  tests/               Graph-building checks
  output/, reviewed/   Source snapshots and scientific provenance
examples/              Development fixtures and reproducible demos
tests/                Application checks
docs/                 Workflow, cloud, search, parser and model documentation
```

The Python package `thermo_functions` maps to `src/Functions`. Runtime packages
are installed into the container; no repository-root import paths are required.
The graph builder retains its own dependencies and Docker image in `psi_kg`.

## Cloud

The root Docker image runs `thermo-execute`. Supply runtime arguments and files
through the cloud job configuration. Only `src`, the package manifest/lockfile,
README, Dockerfile, frontend and thermo-reference data enter the root build context.

See [cloud setup and container usage](docs/cloud-run.md). The separate graph
builder has its own [cloud guide](psi_kg/CLOUD_RUN.md).

## Contracts and examples

- [Execution and frontend contract](docs/frontend-workflow.md)
- [Graph-search result contract](docs/search-results-contract.md)
- [Parser and vector-search handoff](docs/parser.md)
- [Reviewed graph integration and validation](docs/reviewed-graph.md)
- [Small PSI test fixture and provenance](examples/PSI_GRAPH.md)
- [Model input/output documentation](docs/models/)
- [Structured THM request](examples/thermo_request.json)
- [Computed synthetic frontend response](examples/thermo_frontend_response.json)
- [Challenge context](docs/challenge-context.md) and [model tracker](docs/thermo-models.xlsx)

## Verify

```bash
uv run --extra plotting python -m unittest discover -s tests -v
```

Graph-builder tests run separately from `psi_kg` with `uv run pytest -q`.
Tests use offline fixtures and mocked providers; they do not establish live LLM
selection quality or scientific validity. Unsupported formats, missing units and
missing calibration evidence remain explicit diagnostics.

Code, synthetic examples and generated artifacts include SI assistance from
OpenAI Codex. NASA source data, derived results and synthetic fixtures retain
separate provenance and evidence labels.
