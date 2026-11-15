# Implementation and validation status

The Omri interface (`7f21748`) is integrated with the shared v2 backend. The
original improvement plan remains the design reference. This is an implementation
with explicit data and validation limits, rather than a claim that all scientific
capabilities in that plan have been established.

| Audit finding | Implemented change | Limit |
| --- | --- | --- |
| F01, F06 | Persistent requirements, pre-execution model/scope checks, per-output fulfilment, terminal inspection, partial/error results, summaries from actual outputs | General language interpretation and scientific fulfilment need a larger held-out evaluation. |
| F02, F03 | Same-experiment query binding and returned-resource projection; regression tests for both defects | More complex scientific entity identity still depends on verified source metadata. |
| F04, F05 | Source-preserving numeric oxygen/pressure overlay, quantity-basis guards, complete investigation vocabulary | Ambiguous headers, ranges and unsupported units remain unknown; broader scientific normalisation needs source checks. |
| F07, F08 | Exclusion/contradiction handling, no unrelated scoped fallback, term rarity, wider candidate pools, eligibility and investigation coverage | Dense/reranker quality is not established by the metadata benchmark. |
| F09, F10 | Versioned request/retrieval/answer contracts, condition diagnostics, task traces and a bounded missing-input retrieval expansion | Broad evidence discovery is limited to retained graph/source coverage. |
| F11 | Packaged passage index, locators/hashes/status, cited composition, citation/numeric consistency checks, explicit extractive fallback | Citation validity does not prove entailment; independent scientific review remains required. |
| F12, F13 | Signature-derived legacy input contracts/defaults, capability matrix, typed parameter-only scenarios and generated-program provenance checks | Missing calibrated evidence for modern models is reported, not fabricated. The bundled example shapes remain illustrative hints alongside implementation contracts. |
| F14 | Bounded multi-step programs, row predicates, source row provenance, explicit omission policy, registered conversions and aggregates | General cross-run joins, interpolation and arbitrary transforms remain unsupported. |
| F15, F16 | Link budgets separated from transfers; structured trusted profile hashes in v2 and checksum enforcement during fetch | Unprofiled resources cannot acquire verified column semantics just from a download. |
| F17 | Warm inference child with queue/loading/generation deadline; matrix vector scoring, compact index support and graph expansion cap | Deployment-specific latency/memory/cost targets and a full dense index are still to be measured. |
| F18 | Backend configuration/docs, v2 schemas, baseline retrieval benchmark, targeted live checks, frontend integration tests | The proposed human-adjudicated scientific benchmark is still outstanding. |

Validated during implementation:

- Root Python suite: **96 tests; 95 passed, one optional plotting-render test skipped**.
- Frontend Python suite: **6 passed**.
- JavaScript story/tour suites: **2 passed**.
- Omri browser suite: ask flow, cards, PDF/share, library, experiments, mock preview and mobile layout.
- NASA browser integration: real offline graph report retrieval through HTTP,
  source links, explicit error display and rendering computed synthetic charts.
- Metadata discovery benchmark: **114/114** top-result/no-match checks, compared
  with **109/114** using the baseline retriever. See
  [the recorded benchmark](backend-retrieval-benchmark.json). These labels concern
  metadata identity, not the quality of scientific explanations.
- Three targeted live API checks: CFI report selection, a THM-03 scenario with
  verified inputs and Z_st approximately 0.05496, and a cited BASS-II explanation.
  See [the recorded checks](backend-live-validation.json).

The current website process on port 8015 uses `THERMO_PLANNER=api` and
`OPENAI_MODEL=gpt-4.1-mini` with the existing configured account. Local Qwen and
retrieval-only modes are also available; see [configuration](backend-v2.md).

No broad claim of scientific validity, all-model evidence coverage, or passing
the plan's human-evaluation release gates is made by these software checks.
