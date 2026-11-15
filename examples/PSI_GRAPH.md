# Tiny PSI knowledge graph

This real-source testing fixture has **12 nodes, 11 edges, 7 files, 2 investigations**.
The graph is [psi_graph.json](psi_graph.json); it is distinct from the generated
[psi_search_results.json](psi_search_results.json).

```text
PSI-25 (BASS-II) --has_file--> experimental CSV, calibration XLSX,
                              T23 still-sequence MP4, requirements PDF, flame JPEG
       --studies_topic--> solid fuels, spacecraft fire safety

PSI-69 (FLEX) --has_file--> experimental CSV, reviewed R377 report (NASA NTRS)
       --studies_topic--> droplet combustion, spacecraft fire safety
```

Nodes and edges live in one JSON file; no graph database or new dependency is
required. Search matches words in file metadata and traverses investigation/topic
relationships. It is simple lexical retrieval without embeddings or an LLM.
A shared investigation does not establish a shared run or scientific comparability.

## Run locally

```bash
uv sync
uv run thermo-search \
  --graph examples/psi_graph.json \
  --query "BASS-II airflow calibration video" \
  --investigation PSI-25 \
  --limit 5 \
  --output examples/psi_search_results.json

uv run thermo-plan \
  --prompt "Find BASS-II airflow measurements, calibration and a test video" \
  --search-results examples/psi_search_results.json \
  --replay examples/psi_inspection_plan.json
```

Search generates `match_reason` for each hit. Replay validates a saved request
selecting the table, calibration workbook, and video. It chooses `inspect_files`:
display columns are not established calibrated airflow speeds, and the workbook's
schema is unknown. These commands neither call an LLM nor download files.

For live planning, set `OPENAI_API_KEY` and replace
`--replay examples/psi_inspection_plan.json` with `--model YOUR_MODEL_ID`.

Other searches:

```bash
uv run thermo-search --graph examples/psi_graph.json --query "FLEX methanol droplets"
uv run thermo-search --graph examples/psi_graph.json --query "BASS-II" --role documentation
uv run thermo-search --graph examples/psi_graph.json --query "BASS-II" --role video
```

## Sources and verification

Source investigations are NASA PSI's
[BASS-II / PSI-25](https://psi.nasa.gov/physci/repo/data/investigations/PSI-25)
and [FLEX / PSI-69](https://psi.nasa.gov/physci/repo/data/investigations/PSI-69).
Metadata came from public interfaces observed in PSI's frontend:

- [PSI-25 metadata](https://psi.nasa.gov/geode-py/ws/repo/investigations/PSI-25), investigation version 4, DOI `10.60555/4qc4-de67`.
- [PSI-69 metadata](https://psi.nasa.gov/geode-py/ws/repo/investigations/PSI-69), investigation version 5, DOI `10.60555/mbq8-0451`.

Six PSI file URLs were fetched on **14 November 2026**. The R377 report was verified separately. Each file node
records a timestamp, HTTP 200 status, byte count, SHA-256, server content type, and
source file version. About **1.54 MB** was downloaded to a temporary directory for
verification. Only metadata is included in this repository.

| Local file ID | Verified bytes | Type |
| --- | ---: | --- |
| `psi25-experimental-table` | 16,590 | CSV |
| `psi25-fan-calibration` | 23,973 | XLSX |
| `psi25-t23-video` | 323,810 | MP4 |
| `psi25-science-requirements` | 1,108,340 | PDF |
| `psi25-flame-image` | 37,525 | JPEG |
| `psi69-experimental-table` | 24,776 | CSV |
| `nasa-cool-flame-report` | 324,885 | [PDF](https://ntrs.nasa.gov/citations/20140006750) |

For PSI file records, `retrieval_url` uses the download resolver with `redirect=true` and the **file
version**, which differs from the investigation version. It redirects to storage;
expiring signed destination URLs are not saved. This is an observed website
interface, not a documented supported API. Recheck if PSI changes. The graph is an
offline snapshot rather than a continuously refreshed index.

## Metadata boundaries

- Exact CSV headers were inspected, including BASS-II's header whitespace. BASS-II
  has 129 data rows and FLEX has 274; these counts describe only the selected tables.
- `numeric: true` requires every raw cell to parse as a finite number with no
  blanks. False can mean mixed/missing cells or categorical data. Cleaning may make
  some columns usable. Units come from headers when stated; otherwise they are null.
- FLEX's `Burning rate; mm` is preserved without interpreting or correcting its unit.
  FLEX is served as `application/vnd.ms-excel` but its bytes are CSV, so the file
  record uses `text/csv`. `cp1252` successfully decoded its non-UTF-8 bytes; this is
  an inspection choice rather than a NASA-declared encoding.
- The XLSX was checked as an Office ZIP container; its worksheets and units have
  not been inspected. PDF/JPEG/MP4 signatures were checked without interpreting
  their scientific content.
- T23 appears in the video filename and table, but no same-run edges are asserted.
  `related_file_ids` means same investigation. `run_ids` and `conditions` stay empty;
  no per-run material, oxygen, pressure, or gravity values are invented.

Both investigation records identify `CC0-1.0` as their license. Credit NASA PSI and
the investigation DOI when using source data. Filenames, sizes, versions, URLs, and
headers originate in PSI. Local IDs, topic assignments, keywords, profiling, notes,
code, and the saved example plan are SI-assisted indexing/test artifacts, not NASA
scientific interpretations. No source measurement rows or media are bundled.

## Plotting example

[The FLEX chart](plots/flex/plot.png) is a derived visualization of the two fully
numeric columns `Ambient pressure; mmHg` and
`O initial ambient composition; mole fraction`. All 274 rows are plotted without
aggregation, filtering, or unit conversion. Repeated points can overlap.
It shows sampled experimental conditions, not a controlled causal relationship.

[psi_plot_plan.json](psi_plot_plan.json) is a saved plan;
[psi_plot_request.json](psi_plot_request.json) is its validated service request.
[The artifact manifest](plots/flex/manifest.json) records source and operation
details. Use the saved request with `thermo-execute`, or the `thermo-plot` CLI with a
previously downloaded CSV and this graph snapshot. The [workflow guide](../docs/frontend-workflow.md)
describes execution and output contracts. Original source files remain outside the repository.
