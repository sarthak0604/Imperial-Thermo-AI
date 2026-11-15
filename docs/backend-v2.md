# Shared backend and Omri integration

The current interface is imported from `origin/omri` commit `7f21748`, with a thin
`standin/thermo.py` adapter to `request_planner.backend.answer`. The CLI and HTTP
adapter use the same provider factory, execution checks and result contracts.

## Run

From the repository root, use the existing project environment:

```bash
AI_PROVIDER=thermo THERMO_PLANNER=local PORT=8015 \
  OMP_NUM_THREADS=4 TOKENIZERS_PARALLELISM=false \
  .venv/bin/python 'NASA Space Apps/frontend/standin/server.py'
```

Open http://localhost:8015. Local inference uses a warm child process with a hard
request deadline covering model loading, queueing and generation. Model files
must already be cached; `uv sync --extra search` installs inference dependencies.
CPU inference of the 4B model can still be slow. The inference worker is reused
between calls and terminated on timeout.

For API inference, set `OPENAI_API_KEY` and an explicit `OPENAI_MODEL`, then use:

```bash
AI_PROVIDER=thermo THERMO_PLANNER=api OPENAI_MODEL=gpt-4.1-mini PORT=8015 \
  .venv/bin/python 'NASA Space Apps/frontend/standin/server.py'
```

For source discovery without generation, set `THERMO_PLANNER=retrieval`. This
mode can return report/media links and source excerpts. It does not claim to
provide a generated scientific explanation; inspection requires source downloads.

CLI equivalents:

```bash
uv run thermo-execute --provider retrieval --prompt 'Show the PSI-39 CFI final science report PDF'
uv run thermo-execute --provider local --prompt 'Your question'
uv run thermo-execute --provider api --model gpt-4.1-mini --prompt 'Your question'
```

The CLI defaults to the v2 response. Use `--backend v1` for the old envelope;
saved requests and `--search-results` retain the v1 execution path. Python callers
can use `answer(prompt, **configure(environment))`, inspect `AnswerResult`, or
call `.frontend()` for Omri's answer contract.

## Behaviour

The backend preserves the full prompt, required output types, explicit model IDs,
entity exclusions, comparison coverage and client context. It rejects questions
longer than 12,000 characters instead of truncating them. Known incompatible
model/scope choices are rejected before execution; output fulfilment is checked
after execution. Inspection can finish successfully without a calculation.

Retrieval scores rare lexical terms, checks entity scope, interleaves requested
investigations, and selects usable files from a larger candidate pool. Simple
asset and unconstrained explanation requests use this deterministic interpretation;
API planning enables semantic interpretation for more complex source requests.
Set `THERMO_SEMANTIC=true` for local semantic interpretation too. Full semantic
interpretation is bounded and can return a clarification rather than silently
losing a condition.

An optional `dense_search` callable on `answer` supplies dense candidates for
reciprocal-rank fusion. `imperial_thermo_ai.hybrid.DenseRetriever` accepts an
existing compatible index and embedder. Index building is explicit; requests do
not rebuild stale indexes. Vector search uses matrix multiplication, supports
`.npz` storage, and limits neighborhood expansion. Dense retrieval remains opt-in
pending an embedding-quality benchmark.

The normalised graph overlay retains raw source values and adds typed oxygen and
pressure facts only where headers and values establish their meaning and units.
It does not invent gravity, correct suspect source values, infer shared run IDs,
or map arbitrary raw headers into scientific facts. Unsupported fields remain
unknown.

Source passages come from a packaged index built from retained extracted
sections. Rebuild explicitly after source changes:

```bash
uv run python -m imperial_thermo_ai.evidence \
  --sources src/reviewed_knowledge_graph/sources \
  --output src/reviewed_knowledge_graph/output/evidence-index.json
```

The index retains source hashes, locators, review status and stable passage IDs.
Numerical table rows are handled as data, rather than prose passages. Indexing
caps each document at 200,000 characters; it is not complete document coverage.
Extraction does not imply scientific review. Returned PDF/video links do not
imply their contents were analysed.

When enabled, the answer composer uses selected passages, checks referenced IDs
and checks that its numbers occur in cited evidence. These checks cannot prove
scientific entailment: the human scientific evaluation in the improvement plan
is still required. Without generation, original source excerpts remain available
but do not satisfy an explanation requirement by themselves.

V2 calculation programs support bounded steps with dependency ordering, legacy
parameter-only scenarios, and selected table operations. Scenario values must
match exact user source spans. Model defaults are reported separately. Modern
THM models still require sourced calibration/evidence; their availability is
reported through `function_registry.capability_matrix`. Program proposals have a
bounded schema-repair attempt. Missing evidence can trigger one additional,
scoped retrieval attempt. General cross-run joins are unsupported.

The explicit typed Python APIs `operations.scenario` and `operations.table`
support source-attributed inputs, row predicates, declared missing-value policy,
registered unit conversions and simple aggregates. Selection returns original
row indices/source lines. No implicit cleaning, conversion of mole to mass
fraction, or undocumented substitution is allowed.

The v1 function executor remains allowlisted, enforces byte/runtime budgets,
removes temporary data, and verifies trusted profiled source hashes. Link-only
media are not charged against the server download budget. Live model or network
failures produce error results; the connected frontend does not silently replace
them with synthetic answers. File-based preview and the widget library retain
Omri's explicit preview/examples behaviour.

## Validation and remaining scientific work

Run root tests, metadata retrieval comparison and frontend tests:

```bash
uv run python -m unittest discover -s tests -v
uv run python examples/benchmark_backend.py
node --test 'NASA Space Apps/frontend/tests/story.test.js' 'NASA Space Apps/frontend/tests/tour.test.js'
cd 'NASA Space Apps/frontend'
uv run --with playwright python -I tests/ui_e2e.py
uv run --with playwright python -I tests/backend_e2e.py
```

The browser checks cover Omri's interface, actual NASA report retrieval, explicit
backend errors, and rendering a computed synthetic THM-04 chart fixture. They do
not establish scientific validity of the model library.

`backend-retrieval-benchmark.json` contains automatically labelled metadata
lookups and negative discovery cases against the frozen snapshot, compared with
commit `1ae7c06`. It is not the proposed human-adjudicated scientific benchmark.

Still requiring additional evidence or evaluation:

- Independent scientific checks of extracted claims, input mappings and retained
  calibrations; trustworthy evidence packages for the modern models currently
  lacking them. Installing all functions does not supply this evidence.
- A human-adjudicated, held-out set of scientific questions, answer entailment,
  abstention and complete prompt fulfilment. The metadata benchmark is narrower.
- Full-graph dense indexing and lexical/dense/reranker ablations before selecting
  a dense default; broad performance measurements on deployment hardware.
- Extended normalisation for source fields whose quantity meanings, units or
  physical run associations cannot be established from existing metadata.

These remain explicit limitations. They must not be satisfied by inventing source
facts, changing unknowns to matches or marking partial answers complete.
