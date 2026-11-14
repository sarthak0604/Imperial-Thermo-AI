# NASA PSI single-investigation knowledge graph

This isolated Python/uv project reuses the canonical NASA downloader in `src/psi_graph/nasa_access.py`. It extends those working metadata, file-tree and streaming download functions with resource discovery, parsing, configurable LLM extraction, evidence validation, and graph retrieval. The parent repository's existing application and dependency files are not changed.

## Delivered PSI-117 result and execution status

The delivered graph is `output/PSI-117/knowledge_graph.json`. It follows the requested **1.0.0** interface with exactly five node types and four directed edge types. `resources_manifest.json`, `validation_report.json`, `validation_report.md`, `retrieval_results.json`, `documents.json`, and `node_provenance.json` are beside it.

**No external LLM API was called in this run.** No API credential was available, and the user requested configurable providers after Gemini setup was unsuccessful. The delivered graph uses an explicit assistant-authored source review in `reviewed/PSI-117/`, with checked source excerpts and approvals bound to the source snapshot and claim hashes. The API extraction path is implemented and tested with mocked provider responses, but live provider execution remains pending credentials. Do not describe this artifact as an API-generated graph or an exhaustive automated scientific extraction.

The graph contains **12 documented study units**, including numerical studies, experimental comparisons, and supporting studies in the uploaded dissertation. NASA's metadata has an empty `experiments` array; these are **not 12 newly discovered NASA experiment records or invented flight runs**. Physical run names are used only where the source states them. Summaries distinguish simulations from measurements. `MEASURES` includes documented computed observables because the agreed schema has no separate simulation-output relation.

## Original-file retention

New runs process original scientific files temporarily and remove those temporary copies after parsing, including extracted archive members. The graph, extracted text, numerical profiles, source URLs, source hashes and evidence remain saved. This still transfers file contents over the network and requires temporary disk capacity; it is not a metadata-only mode. The current parser batches downloads before parsing, so peak temporary storage can still approach the full study plus expanded archives.

Use the normal `uv run psi-graph-manage` command locally or the same Cloud Run command. Add `--keep-originals` to `psi-graph` or `psi-graph-manage` (after the cloud launcher's `--` separator) to retain original downloads explicitly. The option applies to future downloads; existing retained files are not deleted automatically.

For discarded originals, Resource `storage_uri` is null and `source_url` remains the retrieval reference. Manifest records carry `original_retention: discarded` and verification status before removal. `--stage generate` can reuse retained extracted documents without original files. Re-running preparation can fetch originals again. A coverage report distinguishes files present now from files fetched and verified before intentional removal.

Cleanup runs on normal completion and Python exceptions. A force-killed process or machine shutdown can leave a `.originals-*` scratch directory; remove it only after confirming its run has stopped. On Cloud Run, scratch storage stays on the mounted `/data` volume, not container memory.

## Setup and run with uv

Run commands from this directory:

```sh
cd "/Users/sarth/Documents/NASA Space Apps/Imperial-Thermo-AI/psi_kg"
uv sync
```

### Gemini setup and interactive graph selection

Create a key at [Google AI Studio](https://aistudio.google.com/apikey), then run:

```sh
uv run psi-setup-gemini
uv run psi-graph-manage
```

The setup command asks for your key with hidden input, lists models returned for your account, and lets you select a text model. It tests one small structured JSON API request before saving `LLM_PROVIDER`, `LLM_MODEL`, and `GEMINI_API_KEY` to `$HOME/.config/imperial-thermo-ai/.env` with owner-only file permissions. Other provider settings in that file are preserved. The test uses your API quota. If it fails, the saved configuration stays unchanged. You can specify `--model MODEL_ID` or `--env-file /your/private/.env`; use the same custom env-file with the graph command. Shell environment variables take precedence over the saved file.

The graph command prompts for:

1. **Update current graph** or **Create new graph**.
2. The NASA PSI investigation URL to process.
3. The graph JSON path. Update defaults to the delivered `output/PSI-117/knowledge_graph.json`; create defaults to `graphs/<accession>.json`.

Update adds the supplied study, or replaces that study's previous nodes and relationships if already present. Other studies remain intact. Create refuses to overwrite an existing file. The full configured API pipeline runs before publication, and an update saves the previous JSON in `backups/` beside the graph. Failed processing leaves the selected graph unchanged. Concept and variable identities are scoped to the incoming investigation so similar labels cannot silently overwrite different source meanings. The five node types, four relationship types, and JSON property structures remain unchanged; no cross-investigation scientific relationships are inferred.

For noninteractive use, replace the quoted URL with your new study's URL:

```sh
uv run psi-graph-manage 'https://psi.nasa.gov/physci/repo/data/investigations/PSI-117' \
  --mode create --graph graphs/my-study.json

uv run psi-graph-manage 'https://psi.nasa.gov/physci/repo/data/investigations/PSI-117' \
  --mode update --graph graphs/my-study.json

uv run psi-search 'your scientific question' --graph graphs/my-study.json
```

Each managed run keeps its extracted documents, manifest, extraction caches, and scientific validation report in a separate `runs/<accession>-<unique>/<accession>/` directory. Keep these directories for provenance. Original files are retained only with `--keep-originals`. A `<graph-name>.publication.json` sidecar records combined node counts, all investigation URLs, the graph hash, and the latest run location. Old per-investigation reports still describe their original runs; they are not combined-graph validation reports. A combined graph keeps its original top-level `graph_id` and seed `source_url`; use each Investigation node's `source_url` to enumerate studies. Existing evidence retains its original review status, while the incoming study receives the configured API review. Repeated managed runs currently use isolated caches; `psi-graph --stage generate` remains available for reusing a specific prepared run.

Download and parse an investigation **without an API key**:

```sh
uv run psi-graph \
  'https://psi.nasa.gov/physci/repo/data/investigations/PSI-117' \
  --stage prepare
```

The URL is an input. Replace it to process a different single investigation. Outputs are namespaced under `--output/PSI-NNN`; the program never traverses the `related_glds` cross-investigation links.

A complete API run is:

```sh
uv run psi-graph \
  'https://psi.nasa.gov/physci/repo/data/investigations/PSI-117' \
  --env-file "$HOME/.config/imperial-thermo-ai/.env"
```

To reuse already downloaded/parsed files and perform only extraction, synthesis, review and export, add `--stage generate`. `--stage validate` checks an existing graph offline. `--refresh` refreshes NASA metadata and the file list. Downloaded files are verified by byte count and SHA-256; parsing and LLM calls are cached. API cache keys include provider, endpoint, model, prompt version, payload and schema. Changing scientific source content invalidates relevant caches. `--workers` controls bounded concurrent downloads; no page, row, file-count or total-byte truncation is imposed.

## Execute for a different investigation

Configure `LLM_PROVIDER`, `LLM_MODEL`, and the matching API key in your private `.env` file (see Provider configuration below). The program loads that file directly; shell exports are not required.

From this directory, paste the new NASA investigation URL when prompted:

```sh
printf 'NASA PSI investigation URL: '
read -r PSI_URL
uv run psi-graph "$PSI_URL" \
  --env-file "$HOME/.config/imperial-thermo-ai/.env" \
  --output output
```

This invokes download, parsing, configured LLM extraction, synthesis, evidence review and validation. The API path has not yet been run with live credentials. Without credentials, add `--stage prepare` to download and parse only; this does not generate a new scientific graph. The saved `reviewed/PSI-117/` artifact is specific to PSI-117 and must not be reused for a different investigation.

Results are saved in `output/<accession>/`, where accession is the PSI number in the supplied URL. Validate and query the new result:

```sh
uv run psi-graph "$PSI_URL" --stage validate --output output
printf 'Accession from that URL (PSI- followed by its number): '
read -r PSI_ACCESSION
uv run psi-search 'your scientific question' \
  --graph "output/$PSI_ACCESSION/knowledge_graph.json"
```

The supplied retrieval test cases concern PSI-117. For a new investigation, create cases from its actual sources. To regenerate from already prepared sources, use `--stage generate`; to refresh NASA metadata and the file list, use `--refresh`.

## Provider configuration

Set variables in your shell, or a local `.env` file. The default file location is `$HOME/.config/imperial-thermo-ai/.env`; a custom path can be passed with `--env-file`. Keys are loaded into environment variables and never stored in graph output, logs or command arguments. Do not commit your `.env` file.

| `LLM_PROVIDER` / `--provider` | Required credential | Protocol |
| --- | --- | --- |
| `gemini` | `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) | Google GenAI structured JSON |
| `openai` | `OPENAI_API_KEY` | Responses API with strict JSON Schema |
| `anthropic` | `ANTHROPIC_API_KEY` | Messages API with forced structured tool output |
| `openai-compatible` | `LLM_API_KEY` | Chat Completions with JSON Schema |

All providers require **`LLM_MODEL` or `--model`** set to a model available to your account. There is intentionally no fixed model/version dependency. Choose a model supporting structured output and enough context for the scientific synthesis. Gemini Flash-class models are a reasonable cost/latency starting point; larger reasoning models may improve scientific synthesis. Actual accuracy still depends on evidence checks and review. No cost or quality benchmark was performed in this credential-free run.

Example configuration (fill in your own model and key locally):

```dotenv
LLM_PROVIDER=openai
LLM_MODEL=your_available_model
OPENAI_API_KEY=your_key
```

For compatible services or local servers:

```dotenv
LLM_PROVIDER=openai-compatible
LLM_MODEL=your_model
LLM_BASE_URL=http://localhost:8000/v1
```

Localhost endpoints may omit credentials. Remote endpoints require `LLM_API_KEY` and HTTPS. You can override the environment-variable name with `--api-key-env` and the endpoint with `--base-url`. The compatible server must support `response_format: json_schema`; unsupported modes fail explicitly. Provider errors redact secret-bearing request details. Authentication/configuration errors stop extraction rather than publishing a pretend complete graph.

Official protocol references: [Gemini structured output](https://ai.google.dev/gemini-api/docs/structured-output), [OpenAI structured output](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses), [Anthropic Messages](https://platform.claude.com/docs/en/api/messages/create).

## Retrieval demo

No provider or network is needed:

```sh
uv run psi-search \
  'Why do ozone-assisted n-heptane cool flames oscillate?'

uv run psi-search \
  --cases output/PSI-117/retrieval_cases.json \
  --output output/PSI-117/retrieval_results.json
```

The search scores Concept names, descriptions and synonyms, traverses incoming `STUDIES` edges to experiments, then `HAS_RESOURCE` and `MEASURES` edges to source files and variables. Results explain matched concepts and return original evidence, `source_url`, `storage_uri` and access status. It is a transparent lexical baseline, not semantic embedding search or global GraphRAG. Nine science queries and one unrelated negative control are included; positive cases assert expected concepts, experiments in the top three, and specific associated resources.

```python
import json
from pathlib import Path
from psi_graph.retrieval import search

graph = json.loads(Path('output/PSI-117/knowledge_graph.json').read_text())
result = search(graph, 'three-stage burning with helium')
for experiment in result['experiments']:
    for resource in experiment['resources']:
        print(resource['source_url'], resource['storage_uri'])
```

## Output and provenance contract

`graph_schema.json` is a machine-readable JSON Schema with no additional top-level/node/edge/property keys except the intentionally open Experiment `conditions` object. Node and edge IDs are derived deterministically from source IDs, normalized study keys, concepts, variable units/roles, and endpoint/relation triples. All relations point in the mandated directions. The API's structured intermediates are validated with Pydantic; exports with JSON Schema and additional referential/provenance checks.

Evidence includes exact excerpts, source URLs and PDF page / spreadsheet sheet-row / CSV row / metadata-field locators. Whitespace normalization is allowed; invented and paraphrased quotations are rejected. API exports require a separate LLM entailment review; quote matching alone is not sufficient for `verified`. Delivered edges use `origin: assistant_source_review` so the different execution mode is visible inside the exact agreed edge structure. Detailed node evidence and findings/caveats are sidecars, rather than incompatible new graph fields or node types.

`Resource.source_url` points to a stable NASA file resolver, a real DOI, a discovered publisher link, or the NASA citation metadata where no paper URL exists. Temporary signed download URLs are not persisted. `storage_uri` is null when temporary originals were removed. With `--keep-originals`, it is an absolute local `file://` URI; `local_path` in the manifest points to the same cached file. An archive-member URL carries `#member=...` and its manifest record includes `parent_resource_id`; retrieve the parent ZIP and member or use `storage_uri`. DOI/article/PDF resources can represent different retrievable formats of the same publication; identical source URLs are deduplicated.

If moving the cache to another computer, regenerate/rebase its local paths; the original source URLs remain usable. The original binaries are outside the graph, and each manifest file has its SHA-256 and byte size. Inaccessible papers and citation-only records remain visible with truthful status and no fabricated full-text content. Some discovered resources are unconnected because the reviewed material does not establish a specific experiment association.

## Parsing and coverage

- CSV/TSV: streaming pass through **every row**, numerical counts/ranges/means per column, all text-bearing rows and original headers retained. Raw series stay in the source CSV; numerical aggregates are not scientific findings.
- XLSX/XLSM: all sheets and rows read in streaming mode, including full data-index rows linking datasets, paper DOIs and figure numbers.
- PDF: every page processed, per-page text and missing-text diagnostics retained. PDF status remains `partially_parsed`: figures, visual-only equations and embedded media are not comprehensively digitized. Representative slides were also rendered and visually checked.
- HTML: verified HTTP and HTML redirects followed; scientific text, PDF links and explicit open-manuscript links discovered. HTML parsing is conservatively marked partial, even where a full article is visible.
- ZIP: every member extracted with traversal/symlink protection, members separately inventoried and parsed recursively.
- TXT/JSON/XML/Markdown: entire text chunked with line locators.
- HDF5 / HDF5-backed NetCDF: array metadata and streamed numerical profiles. Classic NetCDF, legacy `.xls` and other unhandled encodings are recorded as failures/unsupported rather than silently accepted. MATLAB `.mat` currently receives an array inventory only and is explicitly partial. These scientific formats were not present in PSI-117's NASA file list.

Publisher access errors, empty/image-only pages, metadata-only citations and parser failures are distinguishable in the manifest. NASA NTRS was also searched for exact listed publication DOIs; search responses and outcomes are retained. Background references are not recursively expanded into unrelated investigations.

## Reproduce the delivered source-reviewed graph

This mode imports a deliberately reviewed artifact; it is not a substitute advertised as a live API call:

```sh
uv run psi-graph \
  'https://psi.nasa.gov/physci/repo/data/investigations/PSI-117' \
  --stage generate \
  --reviewed-bundle reviewed/PSI-117/reviewed_bundle.json
```

The bundle checks the source-content fingerprint and per-claim review hashes. It refuses to apply stale approvals after source changes. `reviewed/PSI-117/assemble_review.py` records the authored extraction decisions and how source quotes were selected. Changes to it or to source documents require scientific review, not blind reapproval. The numeric thresholds and ambiguous conditions are traced in the validation report; notably spreadsheet gas-composition conventions, FLEX-1268 rounding differences, and inconsistencies within dissertation passages.

## Tests and modules

```sh
uv run pytest -q
uv run ruff check src/psi_graph tests
```

`nasa_access.py`: original website adapter; `discovery.py`: download/crawl/cache; `parsing.py`: format readers and profiles; `providers.py`: provider-neutral API layer; `science.py`: typed extraction/synthesis; `graph.py`: exact contract and evidence checks; `reviewed.py`: explicit reviewed-artifact import; `retrieval.py`: graph traversal; `pipeline.py`: CLI.

No global GraphRAG, cross-investigation graph, dashboard, commits, deployment, or unrelated repository changes are included.

## Cloud execution and file coverage

See [CLOUD_RUN.md](CLOUD_RUN.md) for `uv run google --file src/psi_graph/cloud_pipeline.py`, persistent cloud storage, choosing another Python file, and explicit raw-data coverage limits. Use `uv run psi-coverage INVESTIGATION_URL` to reconcile the latest NASA inventory with downloaded files.
