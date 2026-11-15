# Reviewed NASA PSI graph integration

The default runtime source is
`src/reviewed_knowledge_graph/output/knowledge_graph.json`, graph ID
`NASA-PSI-19-reviewed-2026-11-15`. It contains 19 investigations, 2,038 experiment
records, 61,065 resources, 44 concepts and 78 variables. Experiment records include
campaigns, source-table rows and numerical studies; they are not all independent
physical runs. See the [source scope and review notes](../src/reviewed_knowledge_graph/output/README.md).

The frontend's Thermo provider, `thermo-search`, `thermo-execute`, `main` and the
optional vector-search CLI use this graph by default. The graph and source-quality
issues ship in the installed Python package, including the cloud runtime. Set
`THERMO_GRAPH` or pass `--graph` to select another graph in the same 1.0.0 schema.
The original small graphs remain test fixtures; their saved IDs are different.

```bash
uv run thermo-search --query "BASS-II video" --output search-results.json
uv run thermo-search --query "experimental table" --investigation PSI-69 --role measurement
uv run thermo-execute --prompt "Show the PSI-102 SAME final science report PDF"
```

Execution requires `OPENAI_API_KEY` and `OPENAI_MODEL`. The frontend uses its
configured cached local Qwen model. Retrieval itself needs neither a model nor
network access. Graph parsing and indexing take several seconds on first use;
subsequent frontend requests reuse the index. Explicit PSI IDs and recognized
campaign acronyms scope retrieval. Discovery ranks file descriptions and owning
experiment/investigation context, without expanding across shared concepts into
unrelated studies. An exact unknown PSI ID returns no files. Lexical relevance
does not establish requested numerical conditions, units or scientific conclusions.

The file adapter recognizes recorded versioned NASA download resolvers, retains
stable resource IDs and uses investigation landing pages for provenance. Other
landing pages and bibliographic citations do not become downloadable datasets.
Review status, resource summaries and recorded quality issues reach the planner
and appear as warnings when those files are selected. Campaign membership never
supplies verified run IDs or file-wide conditions.

`imperial_thermo_ai/reviewed_file_metadata.json` supplements the immutable reviewed
export with separately verified BASS-II and FLEX CSV profiles. The source URL and
size must match before a profile is applied. All rows were checked for numeric
suitability and the source checksums matched the retained review records. FLEX
requires `cp1252`; its pressure and oxygen-fraction columns have explicit unit
mappings. Other unmapped units remain null, including the suspect burning-rate
header. The source SHA-256 is retained as provenance; transfers still use the
executor's existing size check and byte/runtime caps. Temporary downloads are
removed at the end of every request.

Recreate these profiles with live NASA downloads:

```bash
uv run python examples/profile_reviewed_tables.py
```

Run offline regression checks and explicit live prompt validation:

```bash
uv run --extra plotting python -m unittest discover -s tests -v
uv run python examples/validate_reviewed_workflow.py --live --model gpt-4.1-mini
```

The live script uses the configured OpenAI account and bounded NASA downloads.
It saves plans, output blocks, source checksums and diagnostics to
`/tmp/reviewed-workflow-validation.json`. Cases cover final reports, video,
inspection, plotting, a THM calculation, missing scientific inputs and an unknown
investigation. This exercises the API planner; it does not establish cached Qwen
inference quality or test every NASA file's current availability.

The [recorded validation](reviewed-graph-validation.json) includes eight passing
live cases with `gpt-4.1-mini`. The FLEX chart contains all 274 rows; THM-01 uses
the first row's oxygen fraction of 0.21 and returns 2224.23 K for the requested
CH4 scenario at 101.325 kPa and 298.15 K. This is a model estimate, not a measured
flame temperature. Offline checks also cover all 19 investigations, acronym
isolation, source URL handling, file inspection, temporary cleanup, frontend
handoff and bounded planner correction.
