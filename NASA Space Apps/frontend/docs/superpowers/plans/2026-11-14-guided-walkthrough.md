# Guided Walkthrough Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After a question is answered, walk the reader through the dashboard one box at a time (focus window with "what it shows" and "why it matters for your question"), each box slotting into a faint empty outline on the real dashboard, in a story order.

**Architecture:** A new pure module `js/tour.js` owns the story order, captions, step state and the "skip" preference (no DOM, testable in Node). `js/dashboard.js` draws the final layout once, marks unrevealed boxes `.ghost`, and reuses `openFocus` with a tour bar (Back / Next / Skip). The AI supplies an optional per-widget `stage` (`context|mechanism|limits`) next to the `why` it already returns; `standin/server.py` validates it; JS rules fill in whenever it is missing or invalid.

**Tech Stack:** Vanilla JS (no libraries; must work from `file://` and via `standin/server.py`), Python 3 standard library, Node 22 `node:test` for unit tests, Playwright (container only) for the browser test.

**Spec:** `docs/superpowers/specs/2026-11-14-guided-walkthrough-design.md`

**Spec refinement (flag to Omri):** the spec says the AI supplies `story_order`. This plan has the AI tag each widget with a `stage` instead: it adds ~40 tokens to the prompt rather than a second list, cannot go out of sync with `widgets`, and the order is still produced by JS. The widget order the AI already returns ("most important first") is the tie-break inside a stage.

## Global Constraints

- Vanilla JS only; every script loads by plain `<script>` tag; works opened from `file://` (mock mode) and from `http://localhost:8000`.
- No change to `js/tiler.js`, any chart widget, `data/model_outputs.js`.
- Groq free plan is 8000 tokens/minute: the prompt may grow by at most 600 characters (it is ~13.6K chars now; test asserts `< 14200`).
- Never trust AI output: unknown or non-string `stage` is ignored; missing `why` gets a fallback caption.
- The walkthrough runs on every answered question; never on the widget library (`#library`); "Skip" is always visible; `Esc` skips; arrow keys step.
- Preference key in `localStorage`: `tour-off` = `"1"`; every storage access is wrapped in try/catch.
- Back up the Mac's current files to `~/NASA Space Apps/frontend/_backup_before_tour/` before overwriting; never print the contents of `.env.local`.

## Review Focus

- AI returns a `stage` that is missing, `"banana"`, or a non-string → rules decide the stage; order is still a full permutation.
- Answer has fewer than 3 boxes (e.g. the AI-failed fallback with only the "did not answer" note) → no tour, dashboard shown fully.
- A chart with empty `why` and a text box with no params → caption still non-empty, no `undefined` on screen.
- User asks a new question, goes to `#library`, resizes, or presses Back in the browser mid-tour → focus closes, no ghost outlines left behind, tour state discarded.
- `localStorage` throws (private mode) or "don't walk me through" was ticked → dashboard shows in full, no error; narrow phone width (390 px) → Back/Next/Skip reachable without scrolling the panel.

---

### Task 1: `js/tour.js` — story order, captions, step state, preference

**Files:**
- Create: `js/tour.js`, `tests/tour.test.js`

**Interfaces:**
- Consumes: widgets as `{type: string, stage?: any, why?: string, params?: object}`.
- Produces (global `TOUR`, and `module.exports` when `module` exists):
  - `TOUR.stageOf(w): "context"|"mechanism"|"limits"` — a valid `w.stage` wins; else `STAGE_RULE[w.type]`; else `"mechanism"`.
  - `TOUR.order(widgets): number[]` — permutation of indices.
  - `TOUR.caption(w): {kicker: string, why: string}` — never empty strings.
  - `TOUR.create(widgets): {order: number[], total: number, pos: number, index(): number, revealed(): number[], next(): boolean, back(): boolean, atEnd(): boolean}`; `next()` returns `false` (and does not move) at the last step, `back()` returns `false` at step 0; `revealed()` is `order.slice(0, pos)`.
  - `TOUR.MIN_BOXES = 3`, `TOUR.pref.off(): boolean`, `TOUR.pref.set(v: boolean): void`.

- [ ] **Step 1: Write the failing tests** in `tests/tour.test.js` (`node --test tests/`), loading `../js/tour.js` with `require`:
  - `order puts answer first, key facts next, then charts by stage, then explain, limitations, evidence, follow_ups`: input types `[follow_ups, thm11_held_out, answer, thm02_diluents, key_fact, thm01_flame_temp, evidence, explain, limitations]` → output types `[answer, key_fact, thm01_flame_temp, thm02_diluents, thm11_held_out, explain, limitations, evidence, follow_ups]`.
  - `stage from the AI wins when valid`: `{type:"thm02_diluents", stage:"limits"}` → `"limits"`.
  - `invalid stage falls back to rules`: stages `"banana"`, `7`, `null`, `{}` on `thm11_held_out` → `"limits"`; unknown type → `"mechanism"`.
  - `ties keep the AI's own order`: three `mechanism` charts keep input order.
  - `order is always a permutation` for 0, 1, 12 widgets, including duplicates of one type.
  - `caption never empty`: for `{type:"answer"}`, `{type:"thm16_heating", why:""}`, `{type:"thm16_heating", why:"  x "}` (trimmed), `{type:"zzz"}`; `kicker` for a chart is `"Context"`, `"Mechanism"` or `"Limits"`.
  - `create walks`: `next()` ×(total−1) true then false; `back()` returns to 0 then false; `revealed()` grows by one per `next()`; `atEnd()` true only on the last step.
  - `pref survives a throwing localStorage`: define `global.localStorage` with throwing getItem/setItem → `off()` is `false`, `set(true)` does not throw; with a Map-backed fake, `set(true)` then `off()` is `true`, `set(false)` then `off()` is `false`.

- [ ] **Step 2: Run** `node --test tests/` — expected: FAIL, `Cannot find module '../js/tour.js'`.

- [ ] **Step 3: Implement `js/tour.js`** as an IIFE assigning `const TOUR = ...` and `if (typeof module !== "undefined") module.exports = TOUR`. Decisions it must encode:
  - Text ranks: `answer 0, key_fact 1`, any chart `2`, `explain 3, limitations 4, evidence 5, follow_ups 6`. Sort key: rank, then (charts only) stage index in `context, mechanism, limits`, then original index.
  - `STAGE_RULE` — context: `thm02_lewis_gauge, thm02_atmospheres, thm01_flame_temp, thm03_zst, thm04_hrr, thm11_facts, thm16_fact`; limits: `thm11_held_out, thm08_richardson, thm16_heating, thm16_heatmap, thm16_ignition_vs_flux, thm20_smoke`; everything else `mechanism`.
  - Caption copy: chart `kicker` = stage label; chart `why` = trimmed `w.why`, else stage sentence (context: "Sets the scene for your question.", mechanism: "Shows how this works.", limits: "Shows where this stops holding or how far to trust it."). Text kickers/`why`: answer "Start here" / "This is the direct answer; the boxes that follow are the evidence for it."; key_fact "Key fact" / "A number from the data that backs the answer."; explain "Recap" / "Ties each chart back to your question."; limitations "Caveats" / "What this answer cannot tell you."; evidence "Evidence" / "The NASA experiments this answer relies on."; follow_ups "Ask next" / "Where to go from here."; unknown types use the mechanism wording.

- [ ] **Step 4: Run** `node --test tests/` — expected: all pass.

- [ ] **Step 5: Commit** (container working copy; Mac commit happens in Task 4): `git`-less project, so record by listing the two files in the Task 4 commit set.

---

### Task 2: Server asks for and validates `stage`

**Files:**
- Modify: `standin/server.py` — prompt text in `build_messages` (widget item schema + one rule line), `parse_and_check` (widgets loop)
- Create: `tests/test_server_stage.py`

**Interfaces:**
- Consumes: Task 1's stage names (`context`, `mechanism`, `limits`).
- Produces: each widget dict returned by `parse_and_check` may carry `"stage"` ∈ {`context`,`mechanism`,`limits`}; the key is absent when the AI sent anything else.

- [ ] **Step 1: Write failing tests** in `tests/test_server_stage.py` (run from `frontend/`; `sys.path.insert(0, "standin")`, `import server`):
  - `test_valid_stage_kept`: raw JSON with a `thm02_diluents` widget `"stage":"context"` → returned widget has `stage == "context"`.
  - `test_invalid_stage_dropped`: stages `"banana"`, `3`, `null`, `["limits"]` → no `"stage"` key, widget itself still kept.
  - `test_prompt_stays_small`: `sum(len(m["content"]) for m in server.build_messages("Is the Moon safer?", "student", "iss", []))` is `< 14200`.
  - `test_prompt_mentions_stage`: the system message contains `"stage"` and all three stage names.

- [ ] **Step 2: Run** `python3 -m unittest tests/test_server_stage.py` from `frontend/` — expected: FAIL (no `stage` handling, prompt lacks it).

- [ ] **Step 3: Implement.** In the JSON example line add `"stage": "context|mechanism|limits"` to the widget item; add one rule under `widgets:` — "stage: context = sets the scene, mechanism = shows how it works, limits = shows where it stops holding or how far to trust it; use each at least once when you can." In `parse_and_check` set `stage` only when `isinstance(w.get("stage"), str)` and it is one of the three.

- [ ] **Step 4: Run** the same command — expected: 4 passed.

- [ ] **Step 5: Live check:** start the server on port 8793 (`PORT=8793 python3 standin/server.py &`), `curl` `/api/ask` with "What happens to a flame on the Moon?"; expected: HTTP 200, `meta.source == "live"` and at least one widget with a valid `stage`; kill via `lsof -ti tcp:8793 -sTCP:LISTEN` then `kill` (never `pkill -f`). If Groq 429s, wait the retry time and rerun once.

---

### Task 3: Walkthrough in the dashboard

**Files:**
- Modify: `js/dashboard.js` (`draw`, `openFocus`, `closeFocus`, `generate`, `route`, key handlers, resize handler), `css/skeleton.css` (`.ghost`, `.tour-bar`, reveal animation, narrow-screen rules), `index.html` (add `<script src="js/tour.js"></script>` before `js/dashboard.js`)
- Create: `tests/tour_e2e.py` (Playwright, container only)

**Interfaces:**
- Consumes: `TOUR.create/order/caption/pref/MIN_BOXES` (Task 1); `current.widgets`, `W.def`, `W.isText`.
- Produces: `current.tour` (the object from `TOUR.create`, or `null`); `startTour()`, `endTour()` inside `dashboard.js`; DOM hooks used by the test: `.widget.sketch.ghost`, `#focus .tour-bar`, `[data-tour="next"]`, `[data-tour="back"]`, `[data-tour="skip"]`, `[data-tour="off"]` (checkbox), `[data-replay]` (button in the centre box).

- [ ] **Step 1: Write the failing browser test** `tests/tour_e2e.py` (Playwright via `python3 -I`, `/usr/bin/google-chrome`, `--allow-file-access-from-files`, opens `file://…/index.html#q=…` in mock mode, viewport 1440×900 unless stated). One function per case, each asserting on DOM only:
  - `test_tour_starts_all_ghost`: after the answer renders, `#focus` is visible, shows "Step 1 of N", step 1 is the answer box, and every `.widget.sketch` carries `.ghost` (nothing is revealed while step 1 is open).
  - `test_next_reveals_in_order`: clicking Next N−1 times un-ghosts one box per click in the order `TOUR.order` gives; the last step's button reads "Finish"; after Finish `#focus` is hidden and `.ghost` count is 0.
  - `test_back_reghosts`: Next, Next, Back → ghost count rises by one.
  - `test_keys`: `ArrowRight` advances, `ArrowLeft` goes back, `Escape` ends the tour with zero ghosts.
  - `test_skip_button_and_pref`: tick `[data-tour="off"]`, press Skip, reload with another question → no `#focus`, zero ghosts, `[data-replay]` present; click it → tour starts at step 1 with all boxes ghost.
  - `test_few_boxes_no_tour`: replace `API.ask` (via `page.evaluate`) with a function returning `{title:"x", widgets:[], meta:{source:"fallback-mock", error:"x"}}` so the answer has only the note box + ask-next (2 boxes) → no `#focus`, zero ghosts.
  - `test_library_never_tours`: `#library` → no `#focus`, zero ghosts.
  - `test_new_question_mid_tour`: during step 2 set `location.hash` to another question → old focus gone, then a fresh tour at step 1 for the new question.
  - `test_resize_keeps_ghosts`: at step 3 resize viewport to 1200×800 → ghost count equals N−2.
  - `test_storage_throws`: init script makes `localStorage` getters throw → tour still starts and Skip works.
  - `test_phone_width`: viewport 390×800 → the three tour buttons are inside the viewport (`bounding_box` within 0..390 × 0..800) with no scrolling of `.focus-panel`.
  - `test_no_undefined_text`: the panel text never contains `undefined` or `null` at any step.

- [ ] **Step 2: Run** `python3 -I tests/tour_e2e.py` — expected: FAIL (no `#focus` appears after the answer).

- [ ] **Step 3: Implement the tour state in `dashboard.js`.** `startTour()` builds `current.tour = TOUR.create(current.widgets)`, applies ghosts, opens step 1; it is called at the end of `generate()` only when `current.widgets.length >= TOUR.MIN_BOXES` and `!TOUR.pref.off()`. `applyReveal()` sets `.ghost` on every `.widget.sketch` whose `data-i` is not in `current.tour.revealed()` (all unghosted when `current.tour` is null); `draw()` re-applies it so resize keeps the state. `endTour()` sets `current.tour = null`, un-ghosts everything, closes focus. `generate()`, `library()` and the no-question branch of `route()` call `endTour()` first (no stale ghosts). Add a `[data-replay]` button to the answered-dashboard `centreHTML`; its click handler calls `startTour()` (re-creating state).

- [ ] **Step 4: Implement the focus tour bar.** Change `openFocus(i)` to `openFocus(i, tour)`; when `tour` is truthy it prepends "Step N of M · {kicker}" to `.focus-cat`, shows the "Why it matters for your question" block from `TOUR.caption(w).why` in place of the existing "Why it's here" block, and appends a `.tour-bar` below the text: Back (disabled at step 1), Next (label "Finish" on the last step), "Skip to full dashboard", and a checkbox "Don't walk me through next time" (`data-tour="off"`, writes `TOUR.pref.set`). Next/Finish reveal the current box (`next()` then `applyReveal()` with the `reveal` animation on the newly shown box) and open the following step, or `endTour()` after the last. Key handling: while `current.tour` is set, `ArrowRight` = Next, `ArrowLeft` = Back, `Escape` = skip (replaces plain close); the backdrop and × also skip. Outside a tour, behaviour is unchanged.

- [ ] **Step 5: CSS.** `.widget.sketch.ghost` = dashed 1px `var(--bone-2)` outline, no content (`> * { visibility: hidden }`), no hover/click (`pointer-events: none`); newly revealed box animates once (opacity+4px rise, 280 ms), disabled under `prefers-reduced-motion`. `.tour-bar` sticks to the bottom of `.focus-panel`, wraps on narrow widths, and at ≤ 700 px keeps Back/Next/Skip inside the panel without internal scrolling (reduce `.focus-visual` height to 34%).

- [ ] **Step 6: Run** `python3 -I tests/tour_e2e.py` — expected: all cases pass. Also run the existing layout regression: `python3 -I measure.py` from `/home/claude`; expected: same ≈95% of charts in shape range as before this change, no console errors in `shoot3.py` for mock, live-like and library views.

---

### Task 4: Docs, backup and delivery to the Mac

**Files:**
- Modify: `README.md` (new "Guided walkthrough" section: what it does, how order is decided, `tour-off` preference, how to reset it, "Replay" button)
- Copy to Mac: everything created or modified in Tasks 1–3 plus `docs/superpowers/specs/2026-11-14-guided-walkthrough-design.md` and this plan

**Interfaces:** none new.

- [ ] **Step 1: Back up** the Mac's current `js/dashboard.js`, `css/skeleton.css`, `index.html`, `standin/server.py`, `README.md` into `~/NASA Space Apps/frontend/_backup_before_tour/` with `device_bash`.
- [ ] **Step 2: Commit files** to the Mac with `device_commit_files` (`stagedPath` under `/mnt/user-data/outputs/frontend/...`, `devicePath` `~/NASA Space Apps/frontend/...`) for each file listed above plus `js/tour.js` and `tests/*`.
- [ ] **Step 3: Verify on the Mac:** via `device_bash`, run `node --test tests/` and `python3 -m unittest tests/test_server_stage.py` from `~/mnt/frontend` (or the mounted folder name); expected: all pass. Then open `http://localhost:8000` in the built-in browser with `start_ai_server.command` already running, ask one question, and step through with Next to the end; expected: boxes fill in story order, no console errors.
- [ ] **Step 4: Tell Omri** what changed in two lines, the caveats (the AI's `why` can still contain a claim the models do not support; `stage` is a hint only), and how to turn the tour off/on.
