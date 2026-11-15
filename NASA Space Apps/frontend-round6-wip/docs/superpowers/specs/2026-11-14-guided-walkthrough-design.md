# Guided walkthrough for answers — design (approved by Omri, 14 Nov 2026)

## Intent
When a question is answered, the dashboard is hard to follow: it is unclear which box answers the question, how, or why it is relevant. Replace "everything appears at once" with a guided walkthrough: each box opens large in a focus window, says what it shows and why it matters for the question, and on Next slots into its place on the dashboard. The order tells a logical story.

## Goals
- One box at a time, in a story order, each with "what it shows" and "why it matters for your question".
- The dashboard fills up visibly: the final layout is computed once; unrevealed boxes are faint empty outlines.
- Back / Next / "Skip to full dashboard"; arrow keys; Esc skips.
- Order and the "why" sentences come from the AI when live; mock mode and invalid AI output use fixed story rules.

## Non-goals
- No change to the tiler, chart widgets or model data.
- No slideshow that replaces the dashboard; no all-at-once fade.

## Constraints
- Vanilla JS, works from file:// (mock) and via standin/server.py. Groq free plan: ~8K tokens/minute, so the prompt must not grow much.
- AI must never be trusted blindly: unknown types ignored, missing order falls back to rules.

## Approaches considered
1. Slideshow replacing the dashboard — loses the "dashboard fills in" picture. Rejected.
2. Fade everything in at once — does not solve "hard to follow". Rejected.
3. (Picked) Tour over the real layout: reuse the focus window, reveal slots one by one.

## Decisions (Omri's / my calls)
- Omri: tour runs on every question; Skip always available; arrow keys. (Remembering a "show everything" choice = my call.)
- Story order = answer first, then charts: context → mechanism → limits/edge cases, then caveats/evidence/"ask next" last. (my proposal, accepted)
- AI supplies `story_order` (list of widget types) and per-widget `why`; fall back to rules in JS. (my call)

## Left to the builder
Exact rules for classifying charts into context/mechanism/limits, animation details, step-caption copy, mobile layout.
