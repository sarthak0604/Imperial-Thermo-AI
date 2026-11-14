# Search results contract

Please return search results as the JSON object below so they can feed directly
into our request planner. Return one record per file, including relevant datasets,
PDFs, images, and videos. Flatten your graph results into `files`; the planner
accepts this file-level contract rather than graph nodes/edges or an answer summary.

This documents the existing Python models in
[`request_planner/models.py`](../src/request_planner/models.py). The matching
machine-readable schema is [`search-results.schema.json`](search-results.schema.json).
The TypeScript interfaces below describe the JSON wire format; the teammate can
implement search in any language.

## Interface

Fields without `?` are required. Optional fields may be omitted; only fields whose
type explicitly includes `null` accept JSON `null`.

```ts
export interface SearchResults {
  query_id: string; // Nonempty correlation ID, passed through to the service request.
  files: FileRecord[]; // [] when there are no matches.
}

export interface FileRecord {
  file_id: string;          // Nonempty; unique within this response.
  investigation_id: string; // Nonempty source investigation ID, e.g. "PSI-69".
  title: string;
  role: "measurement" | "documentation" | "video" | "image" | "other";
  media_type: string; // MIME type, e.g. "text/csv" or "video/mp4".

  retrieval_url?: string | null;   // HTTP(S) file download URL; default null.
  source_page_url?: string | null; // HTTP(S) provenance/landing URL; default null.
  size_bytes?: number | null;      // Nonnegative integer bytes; default null.
  run_ids?: string[];              // Verified run IDs; default [].
  variables?: Variable[] | null;   // Column metadata; default null if unknown.
  encoding?: string | null;       // E.g. "utf-8-sig" or "cp1252"; default null.
  data_notes?: string[];           // Parsing caveats/data limitations; default [].
  conditions?: Record<string, string | number | null>; // Default {}.
  related_file_ids?: string[];     // Related file IDs; default [].
  match_reason?: string | null;   // Brief relevance/graph-path explanation.
}

export interface Variable {
  name: string;             // Nonempty, exact column header; unique within file.
  unit?: string | null;     // E.g. "mmHg", "% by vol", "1"; default null.
  numeric?: boolean | null; // true = verified numeric; null = unknown.
}
```

Do not include additional properties at any level. Fields such as `score`,
`nodes`, `edges`, `total`, `schema_version`, `doi`, or `sha256` are not part of this
payload and will fail validation. Keep graph-specific metadata in your service,
or agree on a model change before sending it. Ranking can be represented by
ordering `files` from most to least relevant; the current planner does not consume
a numeric score.

## Required behavior

- Keep file IDs stable so the downstream service can resolve selected IDs against
  the original search records. Preserve the `query_id` when enriching records
  after inspection. No particular ID prefix is required.
- Supply `retrieval_url` for every file you want the planner to be able to select.
  The schema permits a missing/null URL, but the planner cannot select that file.
  Use a public URL that returns file bytes, directly or through a download
  redirect. A page displaying download links belongs in `source_page_url`.
  Authentication, archive-member extraction, and expiring-link refresh are not
  represented by this contract.
- Use `size_bytes: null` for an unknown size, not `0`. Known selected sizes must
  total at most 100,000,000 bytes under the current planner limit. Unknown sizes
  are allowed and cause a warning requiring a streaming download cap.
- Preserve exact variable names, including punctuation, case, and whitespace.
  Use `unit: null` and `numeric: null` when unknown. Use `unit: "1"` only for a
  known dimensionless quantity. Do not guess units or silently convert values.
- Set `numeric: true` only when the raw column can be used as numeric input.
  The current CSV executor rejects blanks, nonnumeric cells, and nonfinite
  values; it does not clean or drop rows. Use `false` for a known unsuitable
  column and explain mixed/missing values in `data_notes`.
- Supply known encoding and parsing caveats when available. Leave unknown column
  metadata as `variables: null`; the planner can request inspection first.
- Put only supported file-level facts in `conditions`. Include units in the key
  or string value where needed. Do not assign one run's conditions to an entire
  multi-run table. Unknown conditions can be omitted or have null values.
- Use `run_ids: []` when run membership is unknown. A shared investigation or
  `related_file_ids` link does not establish that two files describe the same run.
  Related IDs may refer to files outside this result page, but a related file must
  also appear in `files` before the planner can select it.
- Return an empty result for a successful search with no matches. Report search
  failures through your caller's error path; this payload has no error envelope.

## How the planner uses the fields

| Next action | Metadata needed |
| --- | --- |
| Inspect a dataset | `role: "measurement"` and a retrieval URL; columns/units may be unknown. This requests inspection, not execution of a calculation. |
| Plot a relationship | One measurement file with `media_type: "text/csv"`, a retrieval URL, and both requested exact column names with `numeric: true` and nonblank units. |
| Retrieve supporting media | Role is `documentation`, `image`, or `video`; MIME type is `application/pdf`, `image/*`, or `video/*`; retrieval URL is present. |
| No supported action | Empty results, unsuitable files, or an unsupported requested analysis lead to a `no_match` plan. |

The only calculation currently supported is `plot_relationship`: two numeric
columns from one CSV, without unit conversion, aggregation, or joining runs.
Other measurement formats can be returned for inspection. The `other` role is
accepted in search results but cannot currently be selected for inspection,
calculation, or asset retrieval.

The search service returns metadata, not file contents, a plan, or generated
scientific conclusions. The planner makes selections by ID; its LLM adapter
replaces download URLs with availability flags and removes source-page URLs
before sending metadata to the model. Retain the original records for downstream
URL resolution. The existing local plotter additionally requires the original
`MiniGraph` snapshot for checksum/provenance checks; this response alone is not
its full execution input.

## Example response

This shortened record uses the real FLEX metadata already stored in our example
graph. `variables` lists two inspected columns, not the complete CSV schema.
For full responses, see
[`examples/psi_search_results.json`](../examples/psi_search_results.json).

```json
{
  "query_id": "flex-search-001",
  "files": [
    {
      "file_id": "psi69-experimental-table",
      "investigation_id": "PSI-69",
      "title": "PSI-69_Experimental table_FLEX.csv",
      "role": "measurement",
      "media_type": "text/csv",
      "retrieval_url": "https://psi.nasa.gov/geode-py/ws/studies/PSI-69/download?file=PSI-69_Experimental%20table_FLEX.csv&version=1&redirect=true",
      "source_page_url": "https://psi.nasa.gov/physci/repo/data/investigations/PSI-69",
      "size_bytes": 24776,
      "run_ids": [],
      "variables": [
        {"name": "Ambient pressure; mmHg", "unit": "mmHg", "numeric": true},
        {"name": "O initial ambient composition; mole fraction", "unit": "1", "numeric": true}
      ],
      "encoding": "cp1252",
      "data_notes": ["Table spans multiple tests; conditions vary between rows."],
      "conditions": {},
      "related_file_ids": [],
      "match_reason": "FLEX investigation contains the requested pressure and composition columns."
    }
  ]
}
```

No matches:

```json
{"query_id": "search-002", "files": []}
```

## Validate before handing off

From the repository root, with dependencies installed, validate your saved JSON:

```sh
uv run python -c 'from pathlib import Path; from request_planner.models import SearchResults; SearchResults.model_validate_json(Path("search-results.json").read_text()); print("Valid search results")'
```

The JSON Schema checks the structural contract. The Python model also rejects
duplicate file IDs and duplicate variable names within a file. URL availability,
correct units, run relationships, and scientific relevance require source checks;
structural validation does not establish them.

To regenerate the schema after an agreed Python model change:

```sh
uv run python -c 'import json; from pathlib import Path; from request_planner.models import SearchResults; Path("docs/search-results.schema.json").write_text(json.dumps(SearchResults.model_json_schema(), indent=2) + "\n")'
```

Documentation and schema export prepared with SI assistance from the existing
code contract; example measurements remain NASA source data.
