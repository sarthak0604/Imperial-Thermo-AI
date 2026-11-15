# Run on Google Cloud with one command

From the repository root:

```sh
cd "/Users/sarth/Documents/NASA Space Apps/Imperial-Thermo-AI"
uv run google
```

Press Enter to select `psi_kg/cloud_pipeline.py`. The command asks whether to create or update a cloud graph, asks for NASA study names, acronyms, PSI IDs or URLs (separate multiple entries with `;`), and asks for a graph filename (default `current.json`). Enter `main` at the file prompt to run the previous application instead.

The launcher reuses your active `gcloud` project, your configured Cloud Run region (or `europe-west1`), and your private LLM configuration. If Gemini setup is incomplete, it prompts for the key privately, lists available models and tests the selected model before starting cloud resources.

You do not need to manually create an image, Filestore share, VPC, service account, bucket or API secret. The launcher enables the required APIs, creates/reuses a private results bucket and dedicated runtime identity, for API providers syncs the configured key into Secret Manager using standard input and assigns access only to that bucket/secret, then builds and runs the current source code. Google login, billing, API quota, and permission to create these cloud resources are still required; code cannot bypass account permissions. Cloud Run, Cloud Build, temporary disk and Cloud Storage use normal Google Cloud billing.

## Billing prerequisite

The launcher checks project billing before model setup or cloud provisioning. If billing is disabled, it exits cleanly with a project billing link and a local execution command; it never links or upgrades billing automatically. A failed permission check is reported separately from disabled billing. `--dry-run` still works without billing.

For `nasa26`, review [the project's billing settings](https://console.cloud.google.com/billing/linkedaccount?project=nasa26) and link an active billing account if you want Cloud Run execution. Eligible users can use a [Google Cloud Free Trial](https://docs.cloud.google.com/free/docs/free-cloud-features). Cloud free allowances require billing; usage on paid accounts can incur charges. Gemini API access is configured separately.

To execute locally using your saved API configuration, from the repository root:

```sh
cd psi_kg
uv run --extra local psi-graph-manage --env-file ~/.config/imperial-thermo-ai/.env
```

This prompts for create/update, study names/IDs/URLs separated by `;`, and a local graph path. Parsing and temporary NASA downloads happen on your computer; Qwen inference is local; API providers still use their selected API and quotas. This command does not update a graph stored in Cloud Storage.

## Local Qwen running in the cloud job

`local` names the in-process inference backend; it does not mean the launcher runs inference on your laptop. The launcher does not download or load model weights. When your saved `LLM_PROVIDER=local`, `uv run google` runs `Qwen/Qwen3-4B-Instruct-2507` inside the Cloud Run container. It does not ask for a Gemini/API key, enable Secret Manager, upload a key or attach a secret. Redeploying the same job with this provider clears previous secret mounts. The image includes the optional local inference dependencies, with CUDA 13.0-enabled PyTorch on Linux. The build checks that CUDA support is present. macOS continues to use its native PyTorch build.

The image bundles the default Qwen model at `/opt/models/qwen`, pinned to revision `cdbee75f17c01a7cc42f958dc650907174af0554`. It loads that snapshot offline without using the temporary disk for weights. Building the image now downloads roughly 8 GB of weights; startup reuses the image copy. Other model overrides download into `/data/.huggingface` and must fit alongside study data; that cache is excluded from result uploads. NASA resources are also processed in the cloud and discarded after parsing by default. Saved artifacts remain in Cloud Storage. The model has no per-call API fee, but Cloud Run, builds and storage still require billing and can incur charges. For local Qwen, the launcher now provisions one NVIDIA L4 (24 GB VRAM), sets `LLM_DEVICE=cuda`, and logs the detected GPU at startup. It stops if CUDA is unavailable rather than falling back to CPU. Use `--gpu none` only to explicitly request CPU inference. API providers use no GPU. A full investigation has not been benchmarked on the L4.

## Noninteractive execution

From the repository root:

```sh
uv run google --file psi_kg/cloud_pipeline.py \
  --url 'https://psi.nasa.gov/physci/repo/data/investigations/PSI-117' \
  --mode create --graph current.json
```

For another study, replace the URL and use `--mode update --graph current.json`. Create refuses to overwrite an existing cloud graph. Update requires that graph to already exist. A graph saved only on your Mac is not automatically imported; create a cloud graph first.

To preview without uploading credentials, provisioning resources or deploying:

```sh
uv run google --file psi_kg/cloud_pipeline.py \
  --url 'https://psi.nasa.gov/physci/repo/data/investigations/PSI-117' \
  --mode create --graph current.json --dry-run
```

From inside `psi_kg`, use `uv run google` directly, or specify `--file cloud_pipeline.py`. Other Python files directly inside `psi_kg` can be selected; arguments after `--` are passed to those files. Custom scripts must be noninteractive in the cloud and write outputs under `/data`. Their outputs are archived, but automatic graph publication applies to the supplied `cloud_pipeline.py`.

The repository launcher also accepts existing Python application files under `src/`, using the original application's image/environment. The original CPU/GPU options still work for that application.

## What is saved

The results bucket is chosen deterministically from the active project; its exact name is printed before deployment. Override it with `--bucket` for an existing bucket in the same project.

- `gs://BUCKET/graphs/current.json`: the current published graph.
- `gs://BUCKET/executions/UNIQUE-ID/`: each run's extracted documents, manifests, coverage and validation reports.
- `gs://BUCKET/backups/current.json/GENERATION.json`: previous graph versions.
- `psi_kg/cloud_results/current.json` on your Mac: a downloaded copy of the successful cloud graph. Any previous local copy is saved with a `.previous` suffix.

Google Cloud Storage generation checks prevent overlapping executions from silently overwriting each other's graph changes. Failed runs retain diagnostics when normal exception handling can run, and never replace the current published graph. A forcibly terminated job can lose its unfinished diagnostics.

Original scientific files are downloaded temporarily and removed after parsing. They are not included in persisted artifacts by default. Source URLs, hashes, extracted content and provenance remain. Add `--keep-originals` if you explicitly want originals uploaded too; their graph storage references are then converted to `gs://` URLs.

## Capacity and coverage

With the local Qwen provider, the default job has one NVIDIA L4 (24 GB VRAM), 8 CPUs, 32 GiB system RAM and a 10 GiB temporary disk. API providers default to 2 CPUs, 8 GiB RAM and a 10 GiB temporary disk. GPU jobs deploy through `gcloud beta run jobs deploy`, which sets the required BETA launch-stage annotation for the 12-hour GPU timeout; CPU jobs retain the seven-day timeout. Long GPU executions can be interrupted, and the current scratch storage is not a durable checkpoint: a forcibly terminated execution can lose unpublished work. Automatic retries remain disabled. Use `--cpu`, `--memory`, or `--scratch-size` to change these. The default per-instance ephemeral-disk limit is 10 GiB. Larger `--scratch-size` values require an approved per-instance quota increase, as well as sufficient regional quota; the default is not a configuration for arbitrary 150 GB studies. Some parsers still collect extracted sections in memory, and archives can expand beyond their compressed size. No 150 GB end-to-end run has been validated.

The pipeline uses the original NASA file-tree listing function, without category or size filters. Coverage distinguishes all files listed, fetched/verified, intentionally discarded, inaccessible, partially parsed and unsupported. All 16 files in the checked PSI-117 inventory were accounted for; that inventory totaled 70,820,870 bytes and did not list a Raw Data category. Numeric CSV rows are all traversed, but this is not full scientific reanalysis of every format.

## Configuration

Your private `~/.config/imperial-thermo-ai/.env` remains the normal model/provider configuration. Optional overrides include `--project`, `--region`, `--provider`, `--model`, `--env-file`, `--secret` (an existing Secret Manager secret), and `--bucket`. API keys are not placed in command arguments, build context or graph artifacts.

The previous explicit NFS launcher is still available when supplied `--nfs-server` and its other configuration flags; it is not needed for the normal command.

The automatic launcher has been unit-tested and previewed against the existing gcloud configuration. A live deployment has not been executed during implementation.

## Gemini setup errors

Model listing is not proof of generation access. Gemini 2.5 Flash can appear in the list but return HTTP 404 for newer users. Setup now displays the redacted API status/message and lets you select another text model without re-entering the key. Image/audio/agent endpoints are excluded from the suggested list. Temporary HTTP 500/502/503/504 failures retry at most three times; persistent failures allow reselection. Quota (429) and authentication errors remain distinguishable. Configuration is saved only after a successful JSON test, and the cloud launcher preserves the diagnostic rather than replacing it with a generic message.


## Multiple studies in one JSON file

At the study prompt, enter titles, acronyms, PSI IDs or URLs separated by semicolons:

```text
Burning and Suppression of Solids; PSI-117
```

Titles and acronyms are resolved against NASA's current public investigation catalogue. Exact matches take priority; partial matches must be unique. The interactive prompt asks you to choose when multiple studies match. Command-line ambiguity stops with matching titles and PSI IDs, so you can rerun with explicit IDs. Commas are kept as part of study titles.

You can also repeat `--study` or `--url`:

```bash
uv run google --file cloud_pipeline.py \
  --study 'Burning and Suppression of Solids' --study PSI-117 \
  --mode create --graph combined.json
```

Use `--mode update --graph combined.json` to add more studies to that same file. Repeating an existing study refreshes its contribution. Duplicate selections within one batch run only once. Each study keeps its source URLs and provenance; similar concepts from different studies remain distinct rather than being asserted equivalent.

Studies run sequentially, then the combined graph is validated and published once. If any study fails, the existing published graph remains unchanged (or no graph is created). Completed per-study runs remain in the execution artifacts. Publication receipts list every incoming run and its validation report. Cloud output is `gs://BUCKET/graphs/combined.json`, with a local copy in `psi_kg/cloud_results/combined.json` after success.

Local equivalent from `psi_kg`:

```bash
uv run --extra local psi-graph-manage \
  --study 'Burning and Suppression of Solids' --study PSI-117 \
  --mode create --graph graphs/combined.json
```

Batch selection uses one L4 for local Qwen by default and processes studies sequentially. `--memory` controls system RAM, separate from the L4's fixed 24 GB VRAM. L4 requires at least 4 CPUs and 16 GiB system RAM. The default `europe-west1` region supports L4; the project needs available GPU quota. `--gpu none` explicitly requests CPU inference. See [Google GPU configuration](https://docs.cloud.google.com/run/docs/configuring/jobs/gpu) and [task timeout limits](https://docs.cloud.google.com/run/quotas).


If a container build succeeds but deployment fails, use `--image IMAGE_URL` to reuse that image on the next `uv run google` invocation. Prefer the immutable `@sha256:...` image reference from Cloud Build results. This skips building local source; it does not incorporate subsequent changes to container code. Launcher-only changes (such as the Beta launch stage) still apply. Install the Beta command component with `gcloud components install beta` if your gcloud installation does not include it.
