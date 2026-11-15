# Imperial-Thermo-AI

We've got thrust issues.

## Run locally

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and run this
from the repository root.

```sh
uv run main
```

The current `main` branch has the Python environment but no integrated application.
The local `main` command runs the CPU PyTorch smoke test in
`src/imperial_thermo_ai/main.py`. Replace the body of `main()` there to run
the application in both environments.

## Generate a knowledge graph on Google Cloud

```sh
uv run google
```

At the Python-file prompt, press Enter for `psi_kg/cloud_pipeline.py`, then choose create/update and supply the NASA investigation URL. The launcher reuses your current Google Cloud project, builds from source, automatically configures private result storage and API credentials, runs the job, and copies the graph to `psi_kg/cloud_results/`. Missing Gemini settings are prompted for securely. Google login, billing and resource-creation permissions remain necessary. See [the cloud guide](psi_kg/CLOUD_RUN.md).

Enter `main` at the file prompt to run the previous application, or pass `--file src/imperial_thermo_ai/main.py` explicitly. The options below continue to apply to that application.

## Run on Google Cloud

Install the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install), sign in,
and select a [billing-enabled project](https://cloud.google.com/billing/docs/how-to/modify-project).

```sh
gcloud auth login
gcloud config set project nasa26  # Replace nasa26 if you use a different project
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
uv run google
```

For the `main` file selection, `uv run google` uploads the current checkout's build files, uses Cloud Build to
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
