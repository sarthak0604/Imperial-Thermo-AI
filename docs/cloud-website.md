# Deploy IC Dynamics

The `final` branch merges `codex/thm-model-integration`, `omri` and `temp`.
The Omri interface calls the shared Thermo backend at `/api/ask`. Claude is not
used. The root `google` command still deploys a batch job; use `google-website`
for the website service. Its default Cloud Run service ID is `ic-dynamics`,
separate from the older `imperial-thermo-website` service.

## Qwen on Google Cloud (default)

From the repository root, with uv and the Google Cloud CLI installed:

```bash
git switch final
uv sync --locked
gcloud auth login
gcloud config set project nasa26
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
uv run google-website --service ic-dynamics --project nasa26 --region europe-west1 --public
```

This builds the current checkout and deploys `ic-dynamics`. The launcher
stages only upload-allowed files, installs the locked GPU search dependencies,
and downloads `Qwen/Qwen3-4B-Instruct-2507` in **Cloud Build**, not on your Mac.
It requires a billing-enabled project, deployment/build permissions and available
L4 quota. The defaults are one L4 GPU, 4 CPUs, 16 GiB memory, a 300-second HTTP
timeout, and at most one instance. `--public` allows unauthenticated visitors.
Omit that flag for an IAM-protected service.

Review the exact deployment command without building or changing Cloud Run:

```bash
uv run google-website --service ic-dynamics --project nasa26 --region europe-west1 --public --dry-run
```

The Docker image includes the frontend, the shared backend, the reviewed graph
and its evidence index. The server binds to `0.0.0.0:$PORT`. It loads the graph
once before accepting traffic and returns HTTP 503 with `model_busy` when another
question is already being processed; static files and health checks remain available.
The model weights are baked into the GPU image, and inference runs with offline
model access enabled.

## URL and verification

```bash
gcloud run services describe ic-dynamics \
  --project nasa26 --region europe-west1 --format='value(status.url)'
gcloud run services logs read ic-dynamics \
  --project nasa26 --region europe-west1 --limit 50
```

Use the URL printed by the describe command above after deployment. A URL for
`ic-dynamics` has not been verified yet. The older service's URL is
<https://imperial-thermo-website-bwyvnsywwq-ew.a.run.app>; deploying `ic-dynamics`
does not replace or stop that separate service. To disable the old website:

```bash
gcloud run services update imperial-thermo-website \
  --project nasa26 --region europe-west1 --scaling=0
```

To stop IC Dynamics after using it:

```bash
gcloud run services update ic-dynamics \
  --project nasa26 --region europe-west1 --scaling=0
```

To resume IC Dynamics without rebuilding:

```bash
gcloud run services update ic-dynamics \
  --project nasa26 --region europe-west1 --scaling=auto --min=0 --max=1 --max-instances=1
```

After deploying, open the returned URL and check `/api/health`. It should report
`provider: thermo`, `planner: local`, the Qwen model ID, and the reviewed graph ID.
Health verifies graph availability and configuration, **not successful LLM inference**.
Submit a question requiring planning and check the response and service logs to
verify model inference. Do not treat the retrieval-only checks as proof that the
GPU model has run.

Conversations currently use SQLite on the instance's temporary filesystem. They
can be lost on restarts, scale-to-zero or deployments. The frontend handles an
expired conversation by clearing its saved ID and displaying the error; retrying
starts a new conversation. Session affinity and a single instance do not provide
durable storage. This is a demo deployment configuration.

## Other execution modes

CPU-only source retrieval and explicitly supported calculations, without an LLM:

```bash
uv run google-website --service ic-dynamics --project nasa26 --region europe-west1 --planner retrieval --public
```

API planning (key stays server-side in Secret Manager):

```bash
uv run google-website --service ic-dynamics --project nasa26 --region europe-west1 \
  --planner api --model YOUR_MODEL --api-key-secret YOUR_SECRET:latest \
  --service-account YOUR_RUNTIME_SERVICE_ACCOUNT --public
```

Create the secret and grant the runtime account secret access before using that
command. Neither mode uses Claude or frontend mock responses.

## Local validation

```bash
uv sync --locked
uv run pytest tests 'NASA Space Apps/frontend/tests'
uv run python inputs/build_demo.py --check
uv pip install playwright
uv run python -m playwright install chromium
uv run python 'NASA Space Apps/frontend/tests/final_e2e.py'
```

To run the UI locally without downloading an LLM:

```bash
THERMO_PLANNER=retrieval PORT=8015 uv run python 'NASA Space Apps/frontend/standin/server.py'
```

Open <http://localhost:8015>. Use `THERMO_PLANNER=local` only if you have separately
installed the `search` extra and want local model inference.

The main page does not load mock-answer scripts or replay saved legacy responses.
Runtime calculation and chart values come from the backend. The existing **Widget
library** still contains precomputed, labeled demonstrations, including illustrative
and synthetic cases; these are not generated answers or experimental measurements.
`inputs/demo_cases.json` likewise remains a test/example catalog, not an answer source.

References: [Cloud Run GPU services](https://docs.cloud.google.com/run/docs/configuring/services/gpu),
[source deployment](https://docs.cloud.google.com/run/docs/deploying-source-code).
