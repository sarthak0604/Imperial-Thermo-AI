# Context for reviewing this NASA PSI knowledge graph

This folder contains a completed, source-linked knowledge graph for 19 NASA Physical Sciences Informatics (PSI) investigations. **Start with `output/knowledge_graph.json`**. It is the main combined graph. `output/studies/PSI-<number>.json` contains the same schema restricted to one investigation. `NASA_PSI_19_Knowledge_Graph.zip` packages the deliverables; the adjacent `NASA_PSI_19_Knowledge_Graph/` directory is an unpacked copy. Do not count these copies as separate graphs.

The requested studies are PSI-25, PSI-26, PSI-117, PSI-10, PSI-159, PSI-101, PSI-98, PSI-39, PSI-102, PSI-106, PSI-99, PSI-107, PSI-100, PSI-21, PSI-20, PSI-68, PSI-22, PSI-23 and PSI-69.

## Where to look

| Path relative to this folder | Purpose |
| --- | --- |
| `output/knowledge_graph.json` | Canonical combined graph; 63,244 nodes and 69,463 edges at creation. |
| `output/studies/PSI-*.json` | Nineteen smaller, study-specific graphs. Start here if only one PSI study matters. |
| `output/graph_schema.json` | JSON Schema version 1.0.0 for the graph. |
| `output/node_provenance.json` | Evidence references keyed by node ID. Each edge also has its own `properties.evidence`. |
| `output/document_review_log.json` | Thirty-one authored reviews of selected document sections and data series. |
| `output/resource_coverage.json` | One record for each of the 60,781 listed public files, including access status, source URL, and any extracted-source path. |
| `output/source_quality_issues.json` | Unresolved source mistakes, ambiguous units, duplicate rows and similar cautions. |
| `output/validation_report.json` | Schema and integrity checks, coverage, and counts. |
| `output/visual_review_log.json` | Five source pages checked as rendered images. |
| `output/README.md` | More detail about scope, methods and limitations. |
| `sources/PSI-<number>/metadata.json` | NASA investigation metadata captured for that study. |
| `sources/PSI-<number>/files.json` | NASA's public file inventory captured for that study. |
| `sources/PSI-<number>/extracted/*.json` | Extracted document sections or table rows, with locators such as `page 23` or `table, row 4`. |
| `sources/PSI-<number>/download_records/*.json` | Historical retrieval results, including SHA-256 checksums for downloaded files. |
| `review_images/` | Rendered pages used for visual spot checks. |
| `collect_inventory.py`, `collect_sources.py`, `extract_sources.py`, `curation.py`, `author_reviews.py`, `assemble_graph.py` | Historical collection, extraction, scientific curation and graph assembly scripts. |

## Reading the graph

The top-level JSON has `schema_version`, `graph_id`, `source_url`, `generated_at`, `nodes` and `edges`. A node has `id`, `type` and `properties`. Node types are `Investigation`, `Experiment`, `Concept`, `Variable` and `Resource`. Edge types are `CONTAINS` (Investigation → Experiment), `STUDIES` (Experiment → Concept), `MEASURES` (Experiment → Variable) and `HAS_RESOURCE` (Experiment → Resource). Edge evidence includes `source_url`, `locator` and supporting `text`.

For a specific study, open its smaller file directly, for example `output/studies/PSI-25.json`. An Investigation node has ID `inv:PSI-25`. Its `CONTAINS` edges point to campaign, test, table-row or documented-study Experiment nodes. `Experiment.properties.conditions.record_kind` says what sort of record it is; these nodes are **not all independent physical runs**. The matching Resource node gives the NASA file link and `access_status`.

For a scientific claim, follow this path: Experiment summary → its incoming `CONTAINS` edge and outgoing `HAS_RESOURCE`/`MEASURES`/`STUDIES` edges → edge evidence and `output/node_provenance.json` → the matching `sources/PSI-*/extracted/*.json` section or table row → the original NASA source URL. Check `output/source_quality_issues.json` before interpreting a questionable value. A report's plan or hypothesis is not automatically an observed result.

The current graph covers all listed public files as Resource nodes, but most raw recordings were inventoried rather than analyzed. A Resource marked `listed_public_unread` is **not evidence that its contents were inspected**. Other statuses distinguish selected reviewed sections, extracted but unreviewed text, unsupported formats, and failed retrievals. `output/validation_report.json` has the exact coverage numbers. The complete public inventory represents about 13.47 TB; it is not stored here.

The original temporary downloads were removed. `Resource.properties.storage_uri` is null. `local_path` fields in historical download records point to the former temporary location and should not be used as live file paths. Use the local extracted JSON when present, or resolve the NASA `source_url` for the original. Download URLs may be subject to later NASA changes.

## Access and maintenance notes

This directory currently lives at `src/reviewed_knowledge_graph/` inside the Imperial-Thermo-AI local project. The Python scripts were created when the folder was beside `psi_kg/`; their `ROOT.parent / 'psi_kg'` imports do not resolve from the current `src/` location. Treat the delivered JSON as the current artifact, and adjust those imports and temporary dependency paths before attempting a rebuild. A rebuild can require substantial network transfer and may encounter changed NASA files.

`output/` and the unpacked ZIP directory are duplicates of the delivered data. Prefer `output/` for local inspection. If this context file or another artifact is later changed, the existing ZIP and checksum files will not update automatically.
