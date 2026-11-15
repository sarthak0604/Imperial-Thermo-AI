# Answer-First Story Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Answer pages become a top-to-bottom story: a header row (question, short answer, key facts), then one full-width row per point (text + the 0–2 charts that show it, or a NASA experiment card), then Caveats | Evidence | Ask next. Every row is justified to fill the width. A row-by-row walkthrough with a bottom bar replaces the pop-up tour.

**Architecture:** A new pure module `js/story.js` turns any answer into clean `points` and row specs and solves each justified row (no DOM, so Node-testable). `dashboard.js` renders answer pages as `.story` rows using the existing `W.sketch` / `TW.tile` boxes with explicit pixel sizes. The library keeps the bento grid. `tour.js` shrinks to a generic stepper plus the preference. The server asks the AI for `points` and validates them; `mockgen.js` produces `points` too.

**Tech Stack:** Vanilla JS, Python 3 stdlib, Node 22 `node:test`, Playwright (container only).

**Spec:** `docs/superpowers/specs/2026-11-14-answer-story-layout-design.md`

## Global Constraints

- Vanilla JS; works from `file://` (mock) and `http://localhost:8000`.
- No change to chart widgets, model data, or `js/tiler.js`; `#library` keeps the bento grid.
- Prompt ≤ 15,000 characters; `max_tokens` ≤ 1400.
- Never trust the AI:
  - drop unknown chart types and PSI ids;
  - a chart used twice is kept only on its first point;
  - at most 2 charts per point and at most 5 points;
  - no valid points → fall back to the old `widgets` shape, then to mock.
- Layout invariants:
  - box widths + gaps = row width (±1 px);
  - text box ≥ 30% of the row width;
  - row height clamped to 240 px … 62% of the viewport height;
  - charts within their own aspect range `[amin, amax]` whenever that is feasible.
- Phones < 760 px: each row stacks (text, then charts at full width); no horizontal scroll.
- Walkthrough: one row per step, page scrolls to it, bottom bar with "Point N of M" / Back / Next / Skip / "Don't walk me through next time"; ←/→ step, Esc skips.
  - Never on `#library` or with < 3 rows.
  - `localStorage["tour-off"]` and the Replay button carry over.
- Back up the Mac files to `_backup_before_story/` before overwriting; never print `.env.local`.

## Review Focus

- AI points that reference unknown charts or PSI ids, reuse a chart, or have empty text → cleaned; empty points dropped; the page never shows `undefined`.
- A point with no chart and no PSI id → its text spans the whole row; no empty box.
- A very long point (600+ chars) → the text box shrinks its type, then fades with "open to read all"; the row never grows past its height or overflows.
- Two wide charts at 1200 px, or a 390 px phone → text ≥ 30% (desktop); stacked with no horizontal scroll (phone).
- Resize, new question, `#library` or Esc mid-walkthrough → revealed rows kept on resize, state reset otherwise, page never left scroll-locked.

---

### Task 1: `js/story.js` — points, rows, justified-row solver

**Files:** Create `js/story.js`, `tests/story.test.js`. Modify `js/tour.js`, `tests/tour.test.js`.

**Interfaces:**
- Produces global `STORY` (and `module.exports`):
  - `STORY.points(a, env) → [{text: string, psi_ids: string[], charts: string[]}]`
    - `env = {isChart(t): bool, isPsi(id): bool, linked(t): string[], desc(t): string}`.
    - Uses `a.points` when valid. Otherwise builds one point per `a.widgets` chart: `text` is `why` (or `env.desc(t)`), `psi_ids` come from `env.linked(t)` (first 1), and charts are capped at 4.
    - Cleans per the Global Constraints. Text is trimmed and points with empty text are dropped. `psi_ids` are capped at 3.
  - `STORY.rows(a, points) → Row[]`, where `Row = {kind: "header"|"point"|"close", items: [{type, params}]}`:
    - **header:** `[{type:"lead", params:{title, summary, note?}}]` followed by up to 3 `key_fact`s.
    - **point n (1-based):** `{type:"point", params:{n, text, psi_ids, side: n%2 ? "left" : "right"}}` plus each chart `{type: chart, params:{}}`.
      - No charts but a PSI id → add `{type:"experiment", params:{psi_id: psi_ids[0]}}`.
      - No charts and no PSI → the point alone.
      - With `side: "right"`, the point item comes last in `items`.
    - **close:** whichever of `limitations`, `evidence`, `follow_ups` exist.
  - `STORY.solve(items, W, o) → {h: number, widths: number[]}`
    - `items` are `{flex: true, need: number}` (text, need = px² estimate) or `{aspect, amin, amax}` (chart).
    - `o = {gap: 10, minText: 0.3, hmin: 240, hmax}`.
  - `TOUR` becomes `{MIN_BOXES: 3, pref, steps(n) → {total, pos, next(), back(), atEnd(), shown(): number}}`. `shown()` is the count revealed (`pos + 1`). Remove `stageOf`, `order` and `caption`.

- [ ] **Step 1: Failing tests** in `tests/story.test.js`:
  - `points cleans AI output`:
    - unknown chart `"zzz"`, unknown PSI `"PSI-999"`, chart reused in point 2, 3 charts in one point and an empty-text point → cleaned as the Global Constraints say;
    - 7 points → 5.
  - `points falls back to widgets`: `{widgets:[{type:"thm02_diluents", why:"w"}]}` → `[{text:"w", psi_ids:["PSI-20"], charts:["thm02_diluents"]}]`, with the fake `linked` returning `["PSI-20","PSI-10"]`.
  - `rows builds header, points, close`:
    - point without charts but with a PSI id → contains an `experiment` item;
    - point without charts or PSI ids → a single item;
    - point 2 has the point item last;
    - no limitations, evidence or follow-ups → no close row.
  - `solve fills the width`: for W ∈ {1200, 1440, 1920} and a text + 1 chart row (aspect 2.0, range 1.5–3.0) and a text + 2 charts row (2.4 and 2.0) →
    - `sum(widths) + gap*(n−1)` is within 1 px of W;
    - `widths[text] ≥ 0.3W`;
    - `hmin ≤ h ≤ hmax`;
    - each chart `w/h` is within `[amin, amax]`.
  - `solve all-flex row`: three flex items → widths proportional to `need` (each ≥ 20% of W) and filling W.
  - `solve keeps text readable`: text need 600×400 px² with 1 chart → `widths[text]*h ≥ 0.8*need` or `h == hmax`.
  - `tests/tour.test.js` is rewritten for `steps(n)`: forward/back bounds, `shown()` and `atEnd()`. The pref test is kept.

- [ ] **Step 2: Run** `node --test tests/story.test.js tests/tour.test.js`. Expected: FAIL (no `story.js`).

- [ ] **Step 3: Implement.** Solver for rows with charts:
  1. Start from the text fraction `t* = 0.40` (one chart) or `0.34` (two charts): `h = (W − gaps)(1 − t*) / Σaspect`.
  2. Raise `h` until the text area meets its `need`.
  3. Clamp `h` to `[hmin, hmax]`.
  4. If the text width falls below `minText·W`: shrink the chart aspects toward `amin`, then lower `h` (floor 160).
  5. If the text width exceeds 0.6W: grow the aspects toward `amax`.
  6. Give the text the exact remainder.

  For all-flex rows, `h = clamp(Σneed / (W − gaps))` and the widths are proportional to `need`, with a 20% floor.

- [ ] **Step 4: Run** the same command. Expected: all pass.

---

### Task 2: Server and mock produce `points`

**Files:** Modify `standin/server.py` (prompt and contract, `parse_and_check`, `max_tokens`), `js/mockgen.js`, `js/api.js` (`normalise` passes `points`). Replace `tests/test_server_stage.py` with `tests/test_server_points.py`.

**Interfaces:**
- `parse_and_check(raw)` returns `points: [{text, psi_ids, charts}]`, cleaned by the same rules as `STORY.points`.
- It also returns `widgets`: the flattened charts of the points, each `{type, params: {}, why: point text}`, kept for compatibility.
- The prompt asks for 3–5 `points` that build the answer. Each has 1–3 sentences and the PSI ids it rests on. `charts` holds 0–2 entries, chosen only if the chart shows that point. The `summary` is the 1–2 sentence short answer.
- The prompt removes the `stage` rule, the "pick 5–8 widgets" rule and the `widgets` item from the JSON example.
- `MOCKGEN.answer(q, persona)` adds `points`: one per picked chart, at most 4. Each uses the chart's `desc`, `psi_ids` = the first linked investigation from `DATA.models`, and `charts: [t]`.

- [ ] **Step 1: Failing tests** in `tests/test_server_points.py`:
  - `test_points_cleaned`: unknown chart, unknown PSI, duplicate chart, 3 charts, empty text, 7 points → as the Global Constraints say.
  - `test_widgets_derived_from_points`.
  - `test_prompt_size`: total < 15000 characters, and the prompt contains `"points"` and not `"stage"`.
  - `test_max_tokens`: 1400 or lower (read from `call_llm`'s body via a monkeypatched `urlopen` that captures the request).
- [ ] **Step 2: Run** `python3 -m unittest tests/test_server_points.py`. Expected: FAIL.
- [ ] **Step 3: Implement** as described in the Interfaces block.
- [ ] **Step 4: Run** the test again plus `node --test tests/story.test.js`. Expected: pass.

---

### Task 3: Story page and row walkthrough

**Files:**
- Modify `js/dashboard.js`: in `generate`, replace `draw` for answers with a new `drawStory`; the resize handler, the tour block and `openFocus` captions change.
- Modify `js/text_widgets.js`:
  - add text types `lead`, `point` and `experiment` to `DEF`, `body`, `SHAPES`, `chars` and `need`;
  - `tile` accepts `opts.style`.
- Modify `css/skeleton.css`: `.story`, `.srow`, the point and experiment styles, `.tour-bar.fixed`, and phone stacking.
- Modify `index.html`: add the `js/story.js` script tag before `dashboard.js`.
- Rewrite `tests/tour_e2e.py` (same file name) for the story page.

**Interfaces:**
- Consumes `STORY.points/rows/solve`, `TOUR.steps/pref/MIN_BOXES`, `W.sketch(type, {i, place})` (the `place` string is used as an inline style), `W.shape`, and `TW.tile`.
- `current = {widgets, rows, centreHTML, seed, story: true}`. `widgets` is the flat list of every box in row order, so `data-i` and `openFocus(i)` keep working.
- DOM hooks:
  - containers: `.story`, `.srow[data-row=k]`, `#tour-bar`;
  - buttons and controls: `[data-tour=next|back|skip|off]`, `[data-replay]`;
  - unrevealed rows get the `hidden` attribute.
- The `lead` box hosts `#form-slot` (ask box and persona) and the short answer.

- [ ] **Step 1: Failing e2e tests** in `tests/tour_e2e.py`, mock mode via `file://`, 1440×900 unless stated:
  - `test_story_rows_fill_width`: for every visible `.srow`, the box widths + gaps are within 2 px of the row width. No box overflows the viewport, and there is no horizontal scroll at 1440, 1200 and 1920.
  - `test_charts_keep_shape`: each chart box's `w/h` is within its `W.shape` range (±5%).
  - `test_walkthrough_rows`:
    1. On load, only the header row is visible and the bar reads "1 of M".
    2. Next reveals the next row and scrolls it into view (its top is inside the viewport).
    3. Back hides it again.
    4. Finish hides the bar, shows all rows, and leaves `body` without `focus-open`.
  - `test_keys`: → / ← / Esc.
  - `test_skip_pref_and_replay` (as before, but checking rows).
  - `test_library_still_bento`: `#library` has `.bento`, no `.story` and no bar.
  - `test_resize_keeps_revealed`: after 2 Nexts, resizing to 1200×800 keeps 3 rows revealed and every row still fills the width.
  - `test_new_question_resets`: a new question mid-walkthrough starts a fresh walkthrough with only the header row shown.
  - `test_ai_points_page`: `API.ask` is stubbed with a live-like answer containing:
    - point 1 with 2 charts;
    - point 2 with no chart and a PSI id;
    - point 3 with no chart and no PSI;
    - point 4 with 650 characters of text.

    Expected:
    - an `experiment` box appears in row 2;
    - row 3 is a single box at full width;
    - the row 4 text box has `.clipped` or fits, and its `scrollHeight ≤ row height`;
    - the text never contains `undefined`.
  - `test_phone_stack`: at 390×800, rows stack, `scrollWidth ≤ 390`, and the bar buttons are inside the viewport.
  - `test_click_opens_focus`: after Skip, clicking a chart opens `#focus`, and Esc closes it and unlocks the page.
- [ ] **Step 2: Run** `python3 -I tests/tour_e2e.py`. Expected: FAIL.
- [ ] **Step 3: Implement** `drawStory`:
  - Solve each row with `STORY.solve`, using `W.shape` for charts and `TW.shape(...).need` for text.
  - Render `.srow` with fixed `height: h px` and box `width: w px; height: 100%`.
  - Run `markClipped()`.
  - Re-solve on resize while keeping the revealed count.
  - Below 760 px, skip the solver: rows become a column, the text sizes to its content and charts are full width with `height = width / aspect`.
- [ ] **Step 4: Implement the walkthrough:** a fixed bottom bar, rows revealed through the `hidden` attribute, and `scrollIntoView({block:"nearest"})` (smooth unless reduced motion). The walkthrough runs on each answered question when rows ≥ `TOUR.MIN_BOXES` and the pref is not off. Reset it in `generate`, `library` and `route`. Esc skips. Delete the old ghost/fly code.
- [ ] **Step 5: Run** the e2e tests, the Node tests, the Python tests and `/home/claude/measure.py` (library layout unchanged, no errors). Expected: all pass.

---

### Task 4: Docs, backup, deliver, verify on the Mac

- [ ] Update the README "Guided walkthrough" section to describe the story page and the points contract.
- [ ] Back up the Mac's `js/dashboard.js`, `js/text_widgets.js`, `js/tour.js`, `js/mockgen.js`, `js/api.js`, `css/skeleton.css`, `index.html`, `standin/server.py` and `README.md` to `_backup_before_story/`.
- [ ] Stage the Mac's `standin/server.py` first and diff it against the working copy; re-apply only if Omri changed it since. Then commit all changed and new files with `device_commit_files`. Verify with `grep` on the device after each commit.
- [ ] On the Mac:
  1. Run the Node tests and Python tests.
  2. Make one live `/api/ask` call on port 8793. Expected: `points` present with valid charts and PSI ids.
  3. Open `http://localhost:8000/index.html?v=<now>#q=…` in the built-in browser and step through. Expected: rows fill the width and there are no console errors.
- [ ] Final whole-change review by a fresh reviewer, then fix Critical and Important findings with tests first.
