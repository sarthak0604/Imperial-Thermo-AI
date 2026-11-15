# NASA PSI knowledge graph — 19 investigations

The completed graph is `knowledge_graph.json`. It uses the existing **1.0.0 schema**, reproduced in `graph_schema.json`.

Requested investigations: PSI-25, PSI-26, PSI-117, PSI-10, PSI-159, PSI-101, PSI-98, PSI-39, PSI-102, PSI-106, PSI-99, PSI-107, PSI-100, PSI-21, PSI-20, PSI-68, PSI-22, PSI-23 and PSI-69.

## Contents

- `knowledge_graph.json`: combined graph, with 63,244 nodes and 69,463 edges.
- `studies/PSI-*.json`: the 19 individual graphs in the same schema.
- `graph_schema.json`: the exact JSON Schema used for validation.
- `node_provenance.json`: source references and evidence keyed by node ID. Edges also carry their own evidence.
- `document_review_log.json`: the 31 document/data-series reviews, with reviewed locators and scientific interpretations.
- `resource_coverage.json`: status, download URL, available checksum and review coverage for every listed file.
- `source_quality_issues.json`: ambiguous units, apparent source errors, duplicate rows and other unresolved source issues.
- `validation_report.json`: counts and validation results.
- `visual_review_log.json`: the five rendered source pages visually checked.

Node types remain `Investigation`, `Experiment`, `Concept`, `Variable` and `Resource`. Edge types remain `CONTAINS`, `STUDIES`, `MEASURES` and `HAS_RESOURCE`. Scientific findings are in the summaries of the relevant Experiment nodes, with supporting evidence and conditions.

## How the contents were established

NASA's live investigation metadata and complete public file inventories were retrieved for all 19 investigations. The graph represents all **60,781 listed files**, plus bibliographic citation records. File availability does not mean the contents were reviewed.

Of 554 selected documents and tables attempted, 548 were downloaded. Text or structured data were extracted from 465; 72 had no extracted text, 10 used unsupported legacy formats, and one file could not be parsed. Six downloads failed. The graph distinguishes those cases through each Resource's `access_status`.

The scientific layer was authored from reviewed report sections, presentations, readmes, data-series descriptions and the 20 experiment tables. Table records retain source values, units, blanks and row numbers. Report findings distinguish observations, numerical results and experimental plans. Extracted but unreviewed documents are explicitly labelled `text_extracted_unreviewed`.

The 2,038 Experiment nodes include investigation campaigns, test records, test days, sample records, parameter sets and documented scientific studies. They are **not 2,038 independent physical experiments**. Check `conditions.record_kind` before comparing or counting them. Parameter ranges were not expanded into invented runs; exact duplicate source rows are flagged.

Raw video, image and other recording contents were not comprehensively analyzed. Their inventory represents 13.47 TB across the requested investigations. Their file nodes use `listed_public_unread` unless a more specific recorded review status applies. Links from a campaign to a resource establish dataset membership, not a verified association with an individual test.

## Evidence and reuse

Use the evidence's `source_url` and `locator` to check an assertion. Locators distinguish PDF pages, slides and table rows. Stable NASA download endpoints are used instead of expiring signed storage links. NASA may change access or file versions later.

Source values that appear erroneous were preserved and flagged. In particular, suspect chemical formulas, oxygen percentages, Saffire geometry values and a FLEX burning-rate unit must not be treated as corrected measurements. The final reports' restrictions and incomplete measurements are retained. `needs_review` edges identify unresolved evidence or reported measurement scope that was not independently established.

PSI-117 includes separate numerical/observational series and differing time axes. A shared row position does not establish a common physical time. Publication citations marked `citation_only` were not represented as full papers read.

The working folder's `sources/` directory retains extracted text, metadata, file inventories and download records. Paths in `resource_coverage.json` are relative to that working folder, one level above this output directory; extracted source files are not bundled in the graph ZIP. Original downloads were temporary, and Resource `storage_uri` values are null.

The combined graph and all 19 individual graphs were checked against the schema, for duplicate IDs, valid edge endpoints, edge direction/type compatibility and evidence presence. Source quotes used in the authored document reviews were checked against the extracted source text.
