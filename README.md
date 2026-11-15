# IMPER-ai-L · Imperial-Thermo-AI

**Live website: [Open IMPER-ai-L](https://ic-dynamics-bwyvnsywwq-ew.a.run.app/)**

Explore NASA combustion experiments and run the team's thermo models through a
browser interface. The application combines Omri's IMPER-ai-L frontend with
Hayk2's backend for graph retrieval, question planning, model calculations,
charts, source references and downloadable results.

## Use the hosted website

Open the link above. No installation is needed.

1. Choose an environment, such as **ISS cabin** or **Lunar habitat**.
2. Choose who the answer is for, type a question, and press **Enter** or the send button.
3. Open the answer card to see results, charts, assumptions and references. Use
   **Input JSON**, **Output JSON**, **Provenance JSON** or **PDF** to download the
   available results.

For example:

> How much heat could 250 grams of water mist absorb if it warms from 20 °C to
> 100 °C and half of it evaporates?

Some calculations use bundled reference or illustrative inputs. Read the
assumptions and provenance shown with the result. Missing measurements or
calibration can require additional input.

## Run the UI on your laptop

Install **Git** and **[uv](https://docs.astral.sh/uv/getting-started/installation/)**
first. Open a terminal and run:

```bash
git clone --branch main https://github.com/sarthak0604/Imperial-Thermo-AI.git
cd Imperial-Thermo-AI
uv python install 3.14
uv sync --locked
```

The following mode starts the complete UI with source retrieval and supported
deterministic model calculations. It needs no API key and does not download an
LLM. General LLM planning requires one of the optional modes below.

**macOS or Linux:**

```bash
THERMO_PLANNER=retrieval PORT=8015 uv run python "NASA Space Apps/frontend/standin/server.py"
```

**Windows PowerShell:**

```powershell
$env:THERMO_PLANNER = "retrieval"
$env:PORT = "8015"
uv run python "NASA Space Apps/frontend/standin/server.py"
```

Keep that terminal open, wait for the server to start, then open
**[http://localhost:8015](http://localhost:8015)** in your browser. Use the UI as
described above. Press **Ctrl+C** in the terminal to stop the server.

If port 8015 is already in use, set `PORT` to `8016` and open
`http://localhost:8016`. Start the Python server rather than opening `index.html`
directly: the UI needs its HTTP backend.

### Optional: run Qwen locally

This enables local LLM planning. It installs the additional inference dependencies
and downloads `Qwen/Qwen3-4B-Instruct-2507` on the first model request. Model
loading and response time depend on your laptop's memory and hardware.

Stop the existing server first. From the repository root, run:

**macOS or Linux:**

```bash
THERMO_PLANNER=local PORT=8015 uv run --extra search python "NASA Space Apps/frontend/standin/server.py"
```

**Windows PowerShell:**

```powershell
$env:THERMO_PLANNER = "local"
$env:PORT = "8015"
uv run --extra search python "NASA Space Apps/frontend/standin/server.py"
```

Open the same `http://localhost:8015` address. The hosted website runs its model
on Google Cloud, so using the hosted link does not require downloading weights.

### Optional: use API planning

Set `THERMO_PLANNER=api`, `OPENAI_MODEL` to a model available to your account,
and `OPENAI_API_KEY` in the server's environment, then run the same server command
without `--extra search`. Keep the key server-side; do not put it in frontend
JavaScript or commit it to Git. API usage is billed by your provider.

### Update your local copy

Stop the server, run these commands from the repository root, then repeat your
chosen startup command above:

```bash
git switch main
git pull --ff-only
uv sync --locked
```

## Deploy the website to Google Cloud Run

For maintainers with access to the `nasa26` project, install and authenticate the
Google Cloud CLI, then run from the repository root:

```bash
gcloud auth login
gcloud config set project nasa26
uv sync --locked
uv run google-website --project nasa26 --region europe-west1 --service ic-dynamics --public
```

This builds the current checkout on Google Cloud and deploys Qwen with one L4
GPU. Dependencies and model weights are downloaded in Cloud Build, not on your
laptop. It requires billing, the relevant APIs and deployment permissions, and
available GPU quota. Use your own project and service name when hosting a
separate instance. `--public` makes the website publicly accessible.

Wait for the deployment to finish successfully before checking the new site.
The existing revision can continue serving while the build is running. Retrieve
the service URL with:

```bash
gcloud run services describe ic-dynamics --project nasa26 --region europe-west1 --format="value(status.url)"
```

Preview the deployment command without deploying:

```bash
uv run google-website --project nasa26 --region europe-west1 --service ic-dynamics --public --dry-run
```

`uv run google-website` deploys the website. `uv run google` deploys the separate
batch job. See [the Cloud Run website guide](docs/cloud-website.md) for API and
CPU-only deployment options, service requirements and conversation-storage limits.

## Development and documentation

`main` contains the published application from `final` (`f34d680`), based on the
Omri frontend (`4bb5afe`) and Hayk2 backend (`23e17ea`). Live questions use the
Python backend; frontend demo calculations are not used as an error fallback.

```bash
uv run pytest tests "NASA Space Apps/frontend/tests"
uv run python thermo-reference/build_demo.py --check
```

The `src/` directory contains the backend, reviewed NASA graph and THM solvers.
`NASA Space Apps/frontend/` contains the UI and HTTP adapter. `thermo-reference/`
contains reference inputs. The separate `psi_kg/` package builds knowledge graphs.

- [Backend architecture and workflow](docs/backend-v2.md)
- [THM function pipeline](docs/thm-function-pipeline.md)
- [Frontend response contract](docs/frontend-workflow.md)
- [Reviewed graph](docs/reviewed-graph.md)
- [Model documentation](docs/models/)
- [Integration validation](docs/final-validation.md)
- [Graph-builder deployment](psi_kg/CLOUD_RUN.md)

Test fixtures and mocked-provider tests do not establish live LLM accuracy or
scientific validity for every scenario. The application provides research support,
not safety certification. NASA data, calculated results and illustrative inputs
retain separate provenance labels. Code and synthetic fixtures include SI
assistance from OpenAI Codex and Claude.
