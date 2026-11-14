# Answer-first story layout — design (14 Nov 2026)

Replaces the answer dashboard's bento grid and the box-by-box walkthrough from `2026-11-14-guided-walkthrough-design.md`. The widget library keeps the bento grid.

## Intent
Omri: "the goal of the dashboard is not to show the graphs, the goal is to answer the question using the NASA data … the graphs should fit to the explanation, not the other way around." The current page has the AI pick 5–8 charts first and write a summary on the side, so the charts drive and the NASA experiments only appear as an evidence list. The reader can't follow why each box is there.

## Goals
- The answer is a short chain of **3–5 points** that build to the conclusion. Each point says one thing, names the NASA PSI experiment(s) it rests on, and attaches **0–2 charts** that show that point. Charts that support no point are not shown.
- The page reads **top to bottom**:
  1. A header row with the question, ask box, a 1–2 sentence short answer and 2–3 key-fact tiles.
  2. One row per point.
  3. A closing row with Caveats | NASA evidence | Ask next.
- **Fills the page and tiles itself (Omri):** every row spans the full width with no gaps. Charts keep their natural shape, and the layout is fully automatic with no per-question tuning.
- **Keeps the widget look (Omri):** every piece is the same bordered widget box (`.widget.sketch` style, labels, gaps), and clicking a box still opens it large in the focus window.
- A point with no fitting chart gets a **NASA experiment card** in the chart's place: acronym/title, platform, dates, a trimmed objective and a link to the PSI page. Every row is about NASA data.
- **Walkthrough** (my call): rows appear in place one at a time, and the page scrolls to each new row. A bar fixed at the bottom shows "Point 2 of 4", Back / Next / Skip to full answer and the "Don't walk me through next time" box. The arrow keys step and Esc skips. There's no pop-up window during the walkthrough. The "skip" preference, the Replay button and the rule of no walkthrough on the library or on answers with under 3 rows carry over.

## Non-goals
- No change to chart widgets, model data, or the tiler used by the widget library.
- No new data sources: experiment cards use `data/investigations.js` fields already on the page.

## Anti-goals
- Charts that don't support the explanation appear "because they're relevant".
- Rows with empty gaps, stretched charts, or text spilling out unreadably.
- The AI stating a number, range or THM id the data doesn't contain (existing rule stays).

## Constraints
- Vanilla JS, works from `file://` (mock) and via `standin/server.py`.
- Groq free plan: 8000 tokens per minute, counting input plus `max_tokens`. Prompt ≤ 15,000 characters (≈4K tokens) and `max_tokens` ≤ 1400.
- Never trust the AI: unknown chart types and PSI ids are dropped. A chart used twice is kept only on its first point. Charts per point are capped at 2 and points at 5. If no valid points are left, fall back as below.

## Answer contract (server → page)
`points: [{ "text": "1–3 sentences, markdown", "psi_ids": ["PSI-xx", …], "charts": ["thm…", …] }]` replaces the top-level `widgets` list and the per-widget `why`/`stage`. `title`, `summary` (now the 1–2 sentence short answer), `key_facts`, `evidence`, `limitations` and `follow_ups` stay. The prompt drops the `stage` and "pick 5–8 widgets" rules, which pays for the new instructions.

Fallbacks:
- AI returned the old `widgets` shape → one point per widget, using its `why`.
- Mock mode, no AI → one point per keyword-picked chart (at most 4). Each point uses the chart's description and gets an experiment card from the model's linked investigations. The page shows the existing "preview without the AI" note.

## Approaches considered
1. **Justified rows (picked by Omri).** Each row is solved on its own. Charts keep their natural aspect within their allowed range. The row height is chosen so text + charts fill the width exactly, and the text box takes the remaining width. This is the same method photo galleries use.
2. Reuse the bento tiler per point. Less new code, but the tiler fills one screen around a centre box, so rows come out uneven. Rejected.
3. Fixed two columns. Charts stretch or leave gaps. Rejected.

## Layout rules (my calls)
- **Width:** row width = page width minus margins. Gaps match the bento gap.
- **Row height `h`:** chosen so that the chart widths (`h × aspect`) plus a text box of at least 30% width fill the row. `h` is clamped to 240 px–62% of the viewport height. If the clamp leaves slack, the chart aspects flex within their own range first, then the text box widens.
- **Text sides:** the text box alternates left/right by row.
- **Text that doesn't fit:** it shrinks a little, then fades with "open to read all" (existing `markClipped`).
- **Header row and closing row:** both solved the same way. The closing row's three boxes share the width by content length.
- **Phones (< 760 px):** each row stacks: text first, then its charts full width.

## Left to the builder
- Exact clamp values and the text-width minimum.
- Experiment-card styling within the existing widget look.
- Scroll and reveal animation, which is disabled under reduced motion.
- How the walkthrough bar sits on phones.
- What to delete from `TW.assemble`/`tour.js` that the new page no longer uses.
