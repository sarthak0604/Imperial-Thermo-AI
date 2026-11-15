# Integrated NASA backend

This frontend is based on Omri's `7f21748` interface and is connected to the shared
Thermo backend. From the repository root:

```bash
AI_PROVIDER=thermo THERMO_PLANNER=local PORT=8015 OMP_NUM_THREADS=4 \
  TOKENIZERS_PARALLELISM=false .venv/bin/python 'NASA Space Apps/frontend/standin/server.py'
```

Open http://localhost:8015. Use `THERMO_PLANNER=api` with `OPENAI_API_KEY` and
`OPENAI_MODEL` for API inference, or `THERMO_PLANNER=retrieval` for discovery
without generation. See [backend configuration and validation](../../docs/backend-v2.md).

The page renders actual backend results and preserves completed/partial/error
statuses and source locators. Backend failures never silently become mock answers.
The widget library retains Omri’s precomputed demonstrations. Live answers use only backend result blocks; the library data is not substituted for a response.

# Flame in Freefall — frontend

For the graph-backed workflow, double-click `start_ai_server.command` and open
http://localhost:8015. It starts the shared backend, which reports its graph ID
at `/api/health`. By default it uses the cached local model with semantic graph
interpretation enabled. To use API inference, set `THERMO_PLANNER=api`,
`OPENAI_API_KEY`, and `OPENAI_MODEL` before launching. Opening `index.html`
directly shows a backend-unavailable message. Serve it through the backend to ask questions.

The HTTP server always selects the shared Thermo backend, including when an old `.env.local` still names Claude. Legacy stand-in helpers remain only for their existing tests; they are not reachable through the website.

## The interface (Nov 15 design)

Black and white, with flame colour only as a highlight (the key reading on a chart, focus rings, the flame). Font: Inter, bundled in `fonts/` so it works offline.

- **Layout** (design 8): sidebar on the left (new question, search, widget library, NASA experiments, Recent questions, live-AI status), persona picker top left (General / Student / Professor / Engineer), Share, PDF and light/dark switch top right.
- **Ask box** (design 4): frosted, with a thin spectrum rim that turns slowly, faster while the AI thinks. `+` sets the environment (ISS cabin, lunar habitat, spacesuit, Earth), which is sent to the AI as `scenario`. Enter asks; Shift+Enter is a new line; the send button becomes Stop while thinking.
- **The flame** (design 2): a microgravity flame drawn as a ring of light with a belt of dust orbiting it in 3D (`js/flame.js`). Large on the home screen; small as the "Thinking" indicator.
- **Background** (design 3): sparse stars, and a faint dot grid that lights up under the cursor and fades behind it (`js/bg.js`).
- **Answer page** (`js/answer.js`): the question, then "Thinking" steps, then
  1. **AI overview** — title, the short answer (streams in), and a strip of key facts;
  2. **Findings** — the AI's points in reading order, each a box with the chart(s) that show it; two per row, or full width when a finding has two charts;
  3. **More from the data** — what the data can't say, and the NASA experiments behind the findings;
  4. **Ask next** — follow-up questions (asked with the previous answer as context);
  5. **References** — every NASA PSI investigation and thermo model (with its literature) the answer used, numbered; the small numbers in the text jump to them. Ends with how the answer was made (model, time, what the server removed).
  Nothing is hidden behind a Next button: boxes arrive one after another as the answer lands, and the rest as you scroll to them.
- **Full screen** (`js/expand.js`): click any box (or a key fact) and it grows from its place to fill the screen with the full interactive version: sliders, dropdowns, readouts, both charts as tabs, the method, equations and sources. Esc, × or the backdrop shrinks it back.
- **Share:** copy link (re-asks the same question), share sheet, copy the answer as text.
- **PDF** (`js/report.js`): everything the AI wrote — overview, key facts, findings with their charts, limits, experiments, next questions, references with links. jsPDF and the PDF font load only when asked (`vendor/`).
- **Recent:** each question is saved in the browser with its answer, so reopening it (or pressing Back) is instant; "Ask again" gets a fresh answer.
- **Pages:** `#library` (all thermo-model widgets, filter by kind) · `#experiments` (the 26 PSI investigations, filterable) · `#q=…&p=…&s=…` an answer (p = persona, s = environment).

## Where things are
- `index.html` — loads the data, the chart kit, then the interface
- `css/app.css` — the design: tokens for both themes, layout, boxes, charts (`css/skeleton.css` is kept for `model-widgets.html` and `skeleton-full.html`)
- `js/dashboard.js` — routing and the ask flow · `js/ui.js` — icons, theme, menus, persona, environment, Recent, share menu
- `js/answer.js` — turns the AI's reply into the page (and the references) · `js/expand.js` — full-screen boxes · `js/report.js` — PDF
- `js/bg.js`, `js/flame.js` — the background and the flame
- `js/api.js` — backend client (`/api/ask`; explicit errors when the server is unavailable)
- `js/charts.js`, `js/model_widgets*.js` — the thermo-model charts (monochrome SVG drawn at each box's real size); data in `data/model_outputs.js`, regenerated by `standin/precompute_models.py`
- `js/story.js` — cleans the AI's points (unknown charts and investigations dropped); `js/text_widgets.js` — experiment cards and the literature block
- `data/investigations.js` (26 real PSI investigations), `data/models.js` (thermo model catalogue), `data/literature.js` (method + sources per model)
- Not used by the main page any more: `js/tour.js` (old walkthrough), `js/tiler.js` layouts (only its hash/random helpers), `js/pages.js` + `js/widgets.js` (the old multi-page skeleton, `skeleton-full.html`). Backups of earlier versions are in the `_backup_*` folders; the version before this redesign is `_backup_before_redesign/`.

## Tests

From the repository root:

```bash
uv sync --locked
uv run pytest tests 'NASA Space Apps/frontend/tests'
uv pip install playwright
uv run python -m playwright install chromium
uv run python 'NASA Space Apps/frontend/tests/final_e2e.py'
```

The final browser check uses the real HTTP backend, deterministic THM solvers, and
reviewed graph in `retrieval` mode. It does not test LLM inference. It checks varying
inputs, missing inputs, backend outages, backend charts, mobile layout, and the
existing widget library. Older `ui_e2e.py` checks document the superseded Claude
stand-in and mock-preview behavior; use `final_e2e.py` for this integrated site.

## Google Cloud hosting

See [the website deployment guide](../../docs/cloud-website.md).
Run `uv run google-website --project nasa26 --region europe-west1 --public` from
the repository root. The default uses Qwen on an L4 GPU and downloads its weights
in Cloud Build. `uv run google` remains the separate batch-job launcher.

## The theory behind each chart (literature)

`data/literature.js` holds the method, governing equations and three literature sources for each thermo model (THM-01 to THM-20). It is built from the thermo team's `src/Functions/thm_literature_map.py` on the Imperial-Thermo-AI `main` branch:

```bash
cd ~/Documents/Imperial-Thermo-AI && git fetch origin
cd ~/Documents/Imperial-Thermo-AI/"NASA Space Apps/frontend" && python3 standin/build_literature.py --repo ~/Documents/Imperial-Thermo-AI
```

- In the reference list: each thermo model with its three literature sources (DOI / ISBN / NTRS links).
- In a chart opened full screen: "Where this comes from", with the method summary, equations, full citations with DOI/ISBN/NTRS links, why each source matters, and the evidence boundary.
- Short method names are in `METHOD` at the top of `standin/build_literature.py`; edit them there and rebuild.
