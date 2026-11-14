# Run a selected Python file on Google Cloud Run

Run these commands from the repository's `psi_kg` directory. `uv run google` is a launcher added by this project, not a built-in uv cloud service. Python and NASA downloads run in the Cloud Run container after deployment. Gemini remains a remote API.

## Storage and prerequisites

This configuration uses a persistent Google Filestore NFS share mounted at `/data`. Provision a share with capacity for original downloads, expanded archives, parsed documents, and future studies. Filestore is separately billed; its allocated capacity can exceed the dataset size. This implementation does not use a Cloud Storage bucket as a POSIX filesystem. Cloud Run container memory is not suitable for 150 GB downloads.

You need a Google Cloud project with billing, an Artifact Registry Docker repository, Cloud Build and Cloud Run enabled, a Filestore share reachable over your VPC/subnet, and a runtime service account. That service account needs Secret Manager Secret Accessor on the API key secret. Your deploying identity needs Cloud Build, Artifact Registry, Cloud Run deployment/execution permissions and permission to act as the runtime account. Configure VPC/firewall access to the NFS share. See [Google's NFS setup guide](https://docs.cloud.google.com/run/docs/configuring/jobs/nfs-volume-mounts).

Put the Gemini API key in Secret Manager using the Google Cloud console, and supply the **secret name**, not the key, below. Choose a model available to that key. The local setup's HTTP 404 issue has not been diagnosed by this cloud change.

## Build and launch

Set these values for your existing cloud resources (replace every example):

```sh
cd "/Users/sarth/Documents/NASA Space Apps/Imperial-Thermo-AI/psi_kg"
uv sync
gcloud auth login

export PSI_PROJECT="your-project-id"
export PSI_REGION="your-region"
export PSI_IMAGE="$PSI_REGION-docker.pkg.dev/$PSI_PROJECT/your-repository/psi-kg:v1"
export PSI_SERVICE_ACCOUNT="your-runtime-account@$PSI_PROJECT.iam.gserviceaccount.com"
export PSI_NETWORK="your-vpc"
export PSI_SUBNET="your-subnet"
export PSI_NFS_SERVER="your-filestore-private-ip"
export PSI_NFS_SHARE="/your-share-name"
export PSI_SECRET="your-gemini-secret-name"
export PSI_MODEL="your-available-model-id"

gcloud builds submit --project "$PSI_PROJECT" --tag "$PSI_IMAGE" .
```

Build context excludes downloaded data, local credentials, caches, and graphs. The image includes the installed `psi_graph` package and sources under `src/psi_graph/`. If selecting a script in another directory, add that directory to both ignore-file allowlists before building. All dependencies must be declared in this project's pyproject/lock files.

Preview a job for the chosen Python file:

```sh
uv run google \
  --file src/psi_graph/cloud_pipeline.py \
  --project "$PSI_PROJECT" --region "$PSI_REGION" --image "$PSI_IMAGE" \
  --service-account "$PSI_SERVICE_ACCOUNT" \
  --network "$PSI_NETWORK" --subnet "$PSI_SUBNET" \
  --nfs-server "$PSI_NFS_SERVER" --nfs-share "$PSI_NFS_SHARE" \
  --secret "$PSI_SECRET" --model "$PSI_MODEL" \
  -- \
  'https://psi.nasa.gov/physci/repo/data/investigations/PSI-117' \
  --mode create --graph /data/graphs/my-graph.json --runs /data/runs
```

Add `--deploy` **before** the standalone `--` to deploy and execute. Deployment reuses the supplied image; rebuild it after code edits. Everything after the separator goes to your chosen Python file. Change `--file` to another included script; that script is responsible for using `/data` for persistent output and for avoiding interactive input. The supplied `src/psi_graph/cloud_pipeline.py` requires explicit create/update mode and graph path.

To expand the same cloud graph, use `--mode update`, the same `--graph`, and your new study URL. A local graph is not uploaded automatically. Copy it and its source files to the share and rebase local storage paths before using it in the cloud, or create a fresh cloud graph.

## Results and safeguards

- Graph: `/data/graphs/my-graph.json`.
- NASA originals: temporary `.originals-*` directories under the accession directory, removed after parsing by default. Add `--keep-originals` after the launcher separator to retain `downloads/` and archive members.
- Manifest, coverage report, and scientific validation: in the same accession directory.
- Extracted documents, manifests and graphs persist on Filestore after the job ends. Access them from another machine mounting that share. Graph `file://` references describe paths on that shared mount, not public download links; original NASA URLs remain in the graph.
- The job uses one task, no automatic retries, a seven-day timeout, 2 CPUs and 8 GiB memory by default. Override memory with `--memory`.
- An atomic directory lock prevents overlapping jobs using the same share. A forced termination can leave `/data/.psi-job.lock` or a graph `.publish-lock` directory. Confirm the previous execution has stopped before removing its stale lock.
- With `--keep-originals`, completed original files are cached. By default, only extracted content and provenance remain after parsing. NASA transfers retain partial files and resume only if the server supports Range with a validator; otherwise they restart safely. Reuse a failed run with the lower-level pipeline to reuse its caches. Managed runs currently create a new run directory each time.

## Coverage and large raw datasets

The pipeline does not filter the NASA inventory by category, filename, or file size. A `coverage_report.json` distinguishes listing completeness, downloaded bytes, restricted/missing files and parse status. Run a fresh inventory and local hash audit with:

```sh
uv run psi-coverage 'https://psi.nasa.gov/physci/repo/data/investigations/PSI-117'
# For a managed run:
uv run psi-coverage 'YOUR_NASA_URL' --output runs/ACTUAL-RUN-DIRECTORY
```

`--offline` audits the saved listing; default fetches the latest NASA listing. A successful command means all listed public files are currently present and verified, or were verified before intentional removal. The report distinguishes these cases; neither establishes that all scientific content is fully understood. PDF figures/equations remain partial. Videos/images and unsupported scientific formats are not fully analyzed. Numeric CSVs are traversed row by row and summarized deterministically; the full numerical array is not sent to the LLM.

**150 GB end-to-end processing has not been validated.** Text-bearing rows and extracted document sections are still collected in memory; ZIP expansion can require substantially more storage than the compressed download. Large textual tables, archives, HDF5 slices or document collections may exhaust memory even with streaming downloads. This cloud packaging and resumable transfer do not solve every parser-scale limit. Check coverage and processing failures before trusting a graph as exhaustive.

As of the live PSI-117 inventory check on 2026-11-14, NASA listed 16 files totaling 70,820,870 bytes: ten analyzed-data files, four presentations, one report and one metadata file. No Raw Data category was returned. This does not establish that separate raw datasets do not exist elsewhere.

Cloud deployment and 150 GB execution have not been performed in this environment.
