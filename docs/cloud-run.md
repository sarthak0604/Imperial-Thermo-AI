# Cloud runtime

The root image uses Python 3.14 and installs the packages from `src/` with
`uv sync --locked --no-dev --no-editable`. `.python-version` matches the image.
The local `main` and `imperial-thermo-ai` commands delegate to `thermo-execute`.
The image runs the request workflow. PyTorch, Transformers and Accelerate are
optional local-search dependencies (`uv sync --extra search`) and are excluded
from the default image.

## Container usage

From the repository root:

```bash
docker build -t imperial-thermo-ai .
docker run --rm --env OPENAI_API_KEY --env OPENAI_MODEL \
  --mount type=bind,source="$PWD/runtime",target=/data,readonly \
  imperial-thermo-ai --search-results /data/search-results.json \
  --prompt "Calculate heat release and show the test video"
```

Alternatively omit `--search-results` and supply a prompt to search the bundled
reviewed NASA PSI graph before planning. `--graph /data/knowledge_graph.json`
or `THERMO_GRAPH` selects another reviewed-schema snapshot. The wheel includes
the canonical combined graph and source-quality issues; source inventories,
extracted documents and duplicate ZIP exports are excluded from the image.

Place precomputed graph-search results in `runtime/search-results.json`. Configure
credentials through your runtime secret mechanism. Standard output contains the
frontend response JSON. Selected datasets are fetched into temporary storage and
removed after execution. The image requires job arguments; launching it without
inputs prints usage and exits rather than producing a fake successful result.

The independent graph-building image has separate storage and deployment
requirements; see [its cloud guide](../psi_kg/CLOUD_RUN.md).

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
build the image, and deploys the `imperial-thermo-ai` Cloud Run job. Run this
launcher from the repository root. It waits for deployment; workload execution
and input configuration belong to the Cloud Run job. Source builds need
[Cloud Run deployment permissions](https://cloud.google.com/run/docs/deploying-source-code).
Only files listed by `.gcloudignore` are uploaded.

Pass `--project` or `--region` to override the active gcloud project or default
region. The default region is `europe-west1` unless `GOOGLE_CLOUD_REGION` is set.
Configure the job's container arguments, input volume and API-key secret before
executing it. The container entry point is `thermo-execute`; pass its
`--search-results`, `--prompt` and `--model` options as job arguments. Inputs
are runtime files on your mounted storage, and the response is written to stdout.
The image contains installed runtime code and function contracts; examples and
development outputs are excluded from the build context.

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
`--gpu none` or omit `--gpu` to detach a GPU from that job. The request executor
runs deterministic functions on the CPU. GPU workloads need to select a CUDA device and use a CUDA
build compatible with the Cloud Run driver. See
[Cloud Run GPU driver libraries](https://docs.cloud.google.com/run/docs/configuring/jobs/gpu#driver-libraries).

Run `uv run google --help` to see all options.

