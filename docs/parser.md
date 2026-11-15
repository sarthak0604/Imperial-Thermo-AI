# Graph search and planner handoff

Run `uv sync --extra search` from the repository root to install the local Qwen
inference dependencies. The default request-executor image consumes graph-search
results without installing PyTorch or Transformers.

SI-assisted implementation: OpenAI Codex. Fixtures and test vectors are synthetic, not NASA measurements.

The local Qwen instruction model extracts a semantic plan from the original question. Python constructs graph paths and checks conditions. Qwen3-Embedding-0.6B embeds query text and node descriptions in the same space; vectors drive retrieval, not the LLM's text input.

`VectorGraphSearch.local_search(query_vector, query_id=...)` ranks seed nodes and explores their bounded graph neighborhoods. `global_search` searches all Resource vectors with a small investigation relevance contribution. Global here means repository-wide file retrieval, not community-summary GraphRAG. Both return exactly `{query_id, files}` using the supplied planner contract. Internal scores are represented only by result order.

From the WSL repository:

```bash
.venv/bin/python -m imperial_thermo_ai.search_files "Find data on flame spread in microgravity" --query-id demo-001 --mode local --output local-results.json
.venv/bin/python -m imperial_thermo_ai.search_files "Find data on flame spread in microgravity" --query-id demo-002 --mode global --output global-results.json
```

The default is `src/reviewed_knowledge_graph/output/knowledge_graph.json`; use
`--graph` or `THERMO_GRAPH` to override it. A model cache is required; no models
are downloaded automatically. The reviewed graph has over 63,000 nodes, so its
first embedding build is a substantial optional workload. The frontend and
`thermo-search` use indexed lexical retrieval and do not need embeddings.
Embedding descriptions deduplicate shared context and are bounded to 24,000
characters and 8,192 tokens. Long tables therefore contribute a sample of their
linked context for ranking; graph constraint checks still use the complete graph.
Node vectors are cached in graph-embeddings.json and regenerated when the graph changes. The cache includes model identity and graph fingerprint. `--min-score` is an uncalibrated cosine threshold, default 0.3, not a confidence value; tune it using labeled retrieval examples. Local defaults to 5 seeds and 2 hops. The Python API exposes both settings.

Existing query embeddings: save `{"model_id":"Qwen/Qwen3-Embedding-0.6B","vector":[...]}` then use `--query-vector query-vector.json`. Include `--plan saved-parser-output.json` to enforce conditions, or explicitly use `--semantic-only` for vector-only relevance. Embedding dimensions, finite values, model identity and graph coverage are checked. Matching dimension/model labels cannot prove the supplied vector was encoded correctly; use the same encoder and query instruction.

```bash
.venv/bin/python -m imperial_thermo_ai.search_files --query-vector query-vector.json --graph graph.json --query-id external-001 --mode global --semantic-only --output search-results.json
```

No-match searches return an empty files list. Failures raise in Python; CLI failures exit 2 and report on stderr rather than emitting an invalid error envelope. Do not consume a previous output file after a failed command. `--strict` excludes unknown conditions; otherwise unknowns are explicitly labeled candidate-only in match_reason. Known conflicts are excluded. Comparisons retrieve a union of their groups; the supplied wire contract has no comparison-group field. No science answers or calculations are generated.

## Metadata mapping

Stable Resource IDs become file_id. HAS_RESOURCE then CONTAINS identifies the investigation. Missing or ambiguous investigation provenance raises an error. Each Resource must represent one file, not an archive member or abstract collection.

The shared file adapter recognizes recorded, versioned NASA PSI download resolver
URLs in Resource.source_url when their study matches the Resource ID. Other
`source_url` values remain provenance pages and are never guessed to be downloads.
Explicit `retrieval_url`/`download_url` values remain supported. Citation-only and
failed downloads are not promoted. URL availability is not checked by retrieval.
Both CLI paths attach the separately profiled BASS-II/FLEX encoding and column
metadata and retain source-quality cautions; see [the integration guide](reviewed-graph.md).

Resource.variables strings are concept tags, NOT verified CSV headers. To publish inspected columns supply `columns_verified: true` and `column_metadata: [{name,unit,numeric}]`. Preserve exact headers. Numeric suitability must be established by upstream inspection; this service does not inspect file bytes. Supply verified `encoding`, `size_bytes`, `data_notes` when known. Null size is not zero. The planner enforces its selected-file budget; retrieval does not select or download files.

Only `file_conditions` is exported as conditions. Experiment/run conditions are never copied into file-wide facts. `run_ids` requires `run_ids_verified: true`. `related_file_ids` contains only explicit source metadata, not assumed shared-run links. Missing metadata stays unknown. Images/videos are included by declared MIME or format. Illustrative/review-needed provenance is retained in data_notes.

The retrieval layer's `file_contract.py` validates its output. Both packages are
installed by the root project; validate the planner handoff with:

```bash
uv run python -c 'from pathlib import Path; from request_planner.models import SearchResults; SearchResults.model_validate_json(Path("search-results.json").read_text()); print("Valid")'
```

Run code tests with `.venv/bin/python -m unittest discover -s tests -v`. These validate mechanics and contract handling, not universal retrieval accuracy. Qwen embedding usage follows https://huggingface.co/Qwen/Qwen3-Embedding-0.6B .
