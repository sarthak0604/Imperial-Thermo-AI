# Final source replacement — 15 November 2026

- Frontend source: `omri`, `4bb5afecc048ab3f57bd881ed78f434088d2733f`.
- Backend source: `hayk2`, `23e17ea49750c65ee00dfb00fb703c83b012ee0b`.
- Direct file replacement, no branch merge. The previous temp staging was discarded.
- All files under `src/` match Hayk2; the only extra file is the existing
  `imperial_thermo_ai/cloud_website.py` deployment helper.
- `thermo-reference`, backend tests, lockfile and backend packaging come from Hayk2.
- Omri's new interface, design CSS, fonts, flame and management UI are retained.
  Adapter changes connect it to `/api/ask`, display real backend blocks, preserve
  conversation state and export calculated results. The demo-answer fallback is disabled.

## Validation

The Hayk2 backend tests, including all twenty dashboard model examples, passed.
Eight reference input examples recomputed successfully. Combined tests initially
found three legacy Omri helper-signature mismatches; the current Omri formatting
helpers were retained alongside the Thermo HTTP adapter and retested.

The real HTTP regression checks two water-mist inputs and verifies that doubling
the mass doubles the Hayk2 result, without frontend demo figures. A browser check
verified the IMPER-ai-L interface, THM-05 results (1.1138 and 0.7426 mm/s), rendered
chart, three JSON downloads, reference assumptions, and PDF export with an embedded
chart. No browser console errors or mobile horizontal overflow were observed.

The Cloud Run upload manifest includes the new frontend, reference package and
reviewed graph and excludes environment files, backups and Python bytecode. The
website deployment command was checked in dry-run mode. No deployment or live
Qwen inference is performed by these local checks; the caller must deploy final
to update the existing Cloud Run service.

After resolving the legacy helper mismatch, all 17 focused HTTP, frontend and
deployment tests passed. Source distribution and wheel builds succeeded.

A fresh installation from the filtered Cloud Run upload files, using
`uv sync --locked --no-dev --no-editable`, also passed a packaged THM-18
calculation (365.865 kJ) from outside the checkout. This validates packaging
and runtime data availability; it is not a Docker or live GPU execution test.
