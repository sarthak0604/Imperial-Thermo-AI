# Imperial-Thermo-AI

Graph search → LLM request planning → temporary dataset downloads → THM functions
→ frontend JSON with results, chart data, media links and provenance.

## Run locally

Use Python 3.14 and [uv](https://docs.astral.sh/uv/). From the repository root:

```bash
uv sync
uv run python examples/run_workflow_demo.py
```

The demo uses synthetic fixture data and mocked downloads, then runs the real
THM-04 calculation. It needs no API key or network after dependencies are installed.

For real graph-search results, set `OPENAI_API_KEY` and `OPENAI_MODEL`, then run:

```bash
uv run thermo-execute --search-results search-results.json \
  --prompt "Calculate heat release and show the test video" \
  --output frontend-response.json
```

`main` and `imperial-thermo-ai` invoke the same workflow. `thermo-plan` produces
only a validated request. `thermo-search` searches the small example graph;
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
README and Dockerfile enter the root build context.

See [cloud setup and container usage](docs/cloud-run.md). The separate graph
builder has its own [cloud guide](psi_kg/CLOUD_RUN.md).

## Contracts and examples

- [Execution and frontend contract](docs/frontend-workflow.md)
- [Graph-search result contract](docs/search-results-contract.md)
- [Parser and vector-search handoff](docs/parser.md)
- [Real PSI example graph and provenance](examples/PSI_GRAPH.md)
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
