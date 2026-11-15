# Final integration validation — 15 November 2026

## Integrated source

`final` contains real merge commits for all three branch tips fetched from GitHub:

| Branch | Commit | Contribution |
| --- | --- | --- |
| `codex/thm-model-integration` | `f9ce6d1` | Shared backend, THM solvers, reviewed graph, conversation handling |
| `omri` | `7f21748` | Redesigned frontend |
| `temp` | `86043db` | Property records, model input audit, eight demo input builders |

The uncommitted `cloud_website.py` helper and its tests from the original checkout
were incorporated and completed. Unrelated untracked graph-testing files were
left in that checkout. Integration work used an isolated clone.

Omri's CSS, fonts, background and flame JavaScript match `origin/omri` exactly.
Frontend integration changes handle the shared backend's response blocks,
conversation state, errors, calculated charts and exports. No visual redesign was
performed. The legacy Claude configuration no longer selects the HTTP provider.

## Checks completed

- Combined Python suite: **158 passed, 1 skipped, 23 subtests passed**.
- The skipped image-rendering test was then enabled by installing the optional
  plotting dependency: `tests/test_plotting.py` passed **5 tests and 8 subtests**,
  including PNG generation, row counts and source-checksum verification.
- The deployment command tests passed again after adding automatic scaling.
- All eight `inputs/build_demo.py --check` examples recomputed successfully.
- Real Chrome browser test (`frontend/tests/final_e2e.py`) passed: two different
  oxygen inputs produce different THM-01 outputs; live THM-05 scatter plots and
  THM-01 bar charts render; numeric downloads exist; PDF export contains the
  calculated chart; mobile layout does not overflow; missing inputs produce no
  fabricated calculation; NASA report links come from retrieval; all 26 existing
  library widgets open and their sliders work; an actual server outage shows an
  error without fallback findings. No browser JavaScript errors were observed.
- Source distribution and wheel built; wheel contains backend, solvers, reviewed
  graph and evidence index. The real filtered Cloud Run GPU staging helper was
  exercised without deployment. The upload manifest contains the frontend and
  evidence index and excludes environment files, backups and bytecode.
- Targeted lint and Git whitespace checks passed. All three requested branch tips
  are ancestors of `final`.

## Hardcoded-response audit

The main page no longer loads `mock_answers.js` or `mockgen.js`, and its API adapter
has no mock fallback. Old saved responses are not replayed when a question is
opened. Runtime responses use the shared backend's returned blocks and source
locators. Dynamic numerical outputs were checked through actual HTTP requests,
not by substituting test responses into the browser. Missing calibration inputs
and out-of-domain calibration conditions correctly prevented calculation.

The repository still contains legacy test fixtures and Omri's labeled precomputed
widget-library demonstrations. The `temp` recipes contain known expected values
for testing. Those are not live answer sources. Backend response templates,
scientific constants and calibrated model parameters also exist; this audit does
not claim that every string or number in the repository is generated at runtime.

## Hosting state and limits

The existing `nasa26` service is
<https://imperial-thermo-website-bwyvnsywwq-ew.a.run.app>.
It returned HTTP 503, `Service is disabled`, because it was configured for manual
scaling with zero instances. Billing was enabled. The new launcher sets
`--scaling=auto` when the user deploys. The old service was not changed.

No new Cloud Build, Docker container run, Cloud Run deployment or live Qwen/GPU
inference was performed for `final`. Browser checks used retrieval mode and the
real deterministic solvers. Unit tests that supply planner responses are not proof
of live model correctness. Conversation storage remains ephemeral SQLite; see the
[deployment guide](cloud-website.md) for commands and limitations.
