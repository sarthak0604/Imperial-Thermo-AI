# IMPER-ai-L — Flame in Freefall frontend

Two ways to run it:
- **Mock answers:** double-click `index.html`. Everything works except the written answer (a preview is built from the question's words).
- **Live AI:** double-click `start_ai_server_claude.command` (Claude through your Claude Code login) or `start_ai_server.command` (Groq / xAI key in `.env.local`), then open http://localhost:8000. Python standard library only — nothing to install.

The stand-in server (`standin/server.py`) does keyword search over `standin/context.json`, sends the top matches to the model, and removes any investigation or chart it can't verify before the site sees it (the answer page says what it removed). Keys stay in `.env.local` (git-ignored) and are never served. The backend team's knowledge-graph service replaces it later — same `/api/ask` contract.
After changing anything in `data/`, rebuild the AI's context: `node standin/build_context.js`.

## The interface (Nov 15, round 5)

The site is called **IMPER-ai-L** (Flame in Freefall challenge). Black and white, with flame colour only as a highlight (the key reading on a chart, focus rings, the flame). Font: Inter, bundled in `fonts/` so it works offline.

- **Layout:** sidebar on the left (New question, Search, All questions, NASA experiments, Data display settings, then Pinned and Recent, each collapsible, and the live-AI status). Share, PDF and the light/dark switch top right.
- **Home:** the centre shows the flame until an environment is chosen, then a line drawing of that environment (ISS, lunar habitat, spacesuit, Earth) with the dust belt still orbiting it (`FLAME.setGlyph`). Under it, just the prompt bar.
- **Prompt bar:** environment dropdown on the left, persona dropdown (General / Student / Professor / Engineer) just left of send. Their menus open above or below the whole bar, never over the text.
  - **Environment starts empty.** Asking without one opens the menu ("Choose an environment to ask") and the question goes as soon as one is picked. "Make … my default" in the same menu pre-selects it on later visits (stored as `fif-env-default`). The environment is sent to the AI as `scenario`.
  - Enter asks; Shift+Enter is a new line; send becomes Stop while thinking. After an answer the bar flattens to one row.
- **Asking:** the question and its thinking steps sit in a **question tab** just above the prompt bar; the centre shows the environment, thinking, with the current step under it. When the answer lands, the tab shrinks to one line (the ▲ button opens it again: the steps and the other questions in this thread) and the AI overview grows out of it to fill the screen. Follow-ups asked from an answer stay in the same thread.
- **Answer page** (`js/answer.js`):
  1. **AI overview** — fills the screen: title, the short answer (streams in), an "In this answer" outline of the findings (click one to jump to it) and the key facts. The whole box is clickable and highlights on hover; it opens the full overview, step by step, with the **Ask next** questions.
  2. **Findings** — the AI's points in reading order, each its own box with the chart(s) that show it.
  3. **More from the data** — what the data can't say, the NASA experiments behind the findings, other charts.
  4. **References** and **Method** — two closed drop-downs. References: every PSI investigation and thermo model (with its literature), numbered; the small numbers in the text open it and jump to the entry. Method: how the answer was made and where the data comes from (this replaced the notes that used to sit under the home screen and the prompt bar).
- **Method from the backend:** if `/api/ask` returns a `method` field it is shown in the Method drop-down instead of the built-in steps. Accepted shapes: a string (markdown paragraphs), a list of steps (strings, or `{ "title", "text" }`), or `{ "summary", "steps": [...], "notes": [...] }`.
- **Full screen** (`js/expand.js`): click any box (or a key fact) and it grows from its place to fill the screen with the full interactive version. Esc, × or the backdrop shrinks it back.
- **Data display settings** (`#display`, `js/manage.js`): on/off switches for the answer sections (key facts, charts in findings, NASA experiment cards, limits, more charts) and for every chart. Anything off is left out of every answer, saved ones included (stored as `fif-display`); the overview says how many displays your settings hid. Charts can still be previewed here.
- **File manager** (`js/fm.js`), used by Data display settings, NASA experiments and All questions: search, grid / list / details view, item size S / M / L, sort menu or click a column header in details, group by, status bar. View choices are remembered per page.
- **NASA experiments** (`#experiments`): the 26 PSI investigations; group by platform, type, NASA center or decade; open one for its full record.
- **All questions** (`#questions`): every question with its saved answer (up to 60; pinned ones are never dropped). Folders on the left (New folder, rename, delete); drag a question onto a folder or use Move to in its ⋯ menu; pin, rename, delete; group by date, thread, persona, environment or folder.
- **Share:** copy link (re-asks the same question), share sheet, copy the answer as text. **PDF** (`js/report.js`): everything the AI wrote, with charts and references.
- **Pages:** `#display` (`#library` still works) · `#experiments` · `#questions` · `#q=…&p=…&s=…` an answer (p = persona, s = environment).

## Where things are
- `index.html` — loads the data, the chart kit, then the interface
- `css/app.css` — the design: tokens for both themes, layout, prompt bar, question tab, boxes, drop-downs, file manager, charts (`css/skeleton.css` is kept for `model-widgets.html` and `skeleton-full.html`)
- `js/dashboard.js` — routing and the ask flow (question tab, thinking, the overview growing in) · `js/ui.js` — icons, theme, menus, persona and environment pickers, display settings, history (folders, pins, threads), sidebar, share menu
- `js/answer.js` — turns the AI's reply into the page, the References and Method drop-downs, and the question tab · `js/expand.js` — full-screen boxes · `js/report.js` — PDF
- `js/fm.js` — the file manager · `js/manage.js` — Data display settings, NASA experiments, All questions
- `js/bg.js`, `js/flame.js` — the background, and the flame / environment drawings
- `js/api.js` — AI client (`/api/ask`; mock answers from `js/mockgen.js` when opened as a file)
- `js/charts.js`, `js/model_widgets*.js` — the thermo-model charts (monochrome SVG drawn at each box's real size); data in `data/model_outputs.js`, regenerated by `standin/precompute_models.py`
- `js/story.js` — cleans the AI's points (unknown charts and investigations dropped); `js/text_widgets.js` — experiment cards and the literature block
- `data/investigations.js` (26 real PSI investigations), `data/models.js` (thermo model catalogue), `data/literature.js` (method + sources per model)
- Not used by the main page any more: `js/tour.js`, `js/tiler.js` layouts (only its hash helper), `js/library.js` grid (only `W.def` / `W.full`), `js/pages.js` + `js/widgets.js` (the old skeleton, `skeleton-full.html`). Backups of earlier versions are in the `_backup_*` folders; the version before round 5 is `_backup_before_round5/`.

## Tests
- `python3 -m unittest tests/test_server_points.py tests/test_server_nocache.py tests/test_server_claude.py`
- `node --test tests/story.test.js tests/tour.test.js`
- Browser checks (needs `pip install playwright` and `python3 -m playwright install chromium`): `python3 -I tests/ui_e2e.py`. It starts the server with a fake `claude` (`tests/fake_claude.py`), so it never uses your Claude plan.

## Using Claude (your Pro plan) instead of Groq

Double-click **`start_ai_server_claude.command`** instead of `start_ai_server.command`. The stand-in server then asks **Claude Haiku** through your own Claude Code login, so there's no API key and no Groq rate limit; it counts against your Claude plan's usage limits.

- One-time setup: install Claude Code (https://code.claude.com), open Terminal, run `claude` and sign in with your Claude account.
- Each question runs `claude -p --model haiku --output-format json` in an empty temp folder with all tools switched off, so it can't read or change files. `ANTHROPIC_API_KEY` is removed from its environment, so it always uses your plan login and never API billing.
- This launcher also gives the AI 6 matching NASA investigations per question instead of 4.
- Options: `AI_MODEL=sonnet` for a stronger model; `CLAUDE_BIN=/path/to/claude` if the command isn't found.
- This is for running the site on your own computer. A site other people use needs a Claude API key from the Claude Console instead.
- Test (no real call, uses a fake `claude`): `python3 -m unittest tests/test_server_claude.py`.

## The theory behind each chart (literature)

`data/literature.js` holds the method, governing equations and three literature sources for each thermo model (THM-01 to THM-20). It is built from the thermo team's `src/Functions/thm_literature_map.py` on the Imperial-Thermo-AI `main` branch:

```bash
cd ~/Documents/Imperial-Thermo-AI && git fetch origin
cd ~/Documents/Imperial-Thermo-AI/"NASA Space Apps/frontend" && python3 standin/build_literature.py --repo ~/Documents/Imperial-Thermo-AI
```

- In the reference list: each thermo model with its three literature sources (DOI / ISBN / NTRS links).
- In a chart opened full screen: "Where this comes from", with the method summary, equations, full citations with DOI/ISBN/NTRS links, why each source matters, and the evidence boundary.
- In the Claude prompt: each chart's method and sources, so the explanation can name them (e.g. "Richardson-number scaling (Sacksteder 1990)"). Groq gets only the chart facts, to stay inside its free-plan limit.
- Short method names are in `METHOD` at the top of `standin/build_literature.py`; edit them there and rebuild.
