# Conversation and model-routing implementation status

This work implements a first integrated version of the search/model/memory plan.
The complete 14-section plan is not yet delivered. In particular, model discovery
metadata is not a substitute for scientifically reviewed domain/input contracts.

## Implemented

- Capability discovery for all 20 functions, implicit computation routing, explicit
  ID enforcement, validated structured decisions and one routing schema repair.
- Shared provider configuration for API, warm Transformers local inference, source
  retrieval, and an OpenAI-compatible open-source inference server.
- SQLite conversation storage, session ownership checks, four recent exchanges,
  retained literal user facts, revisions, bounded retry snapshots, expiry, deletion,
  API state retrieval, and CLI `--conversation` / `--conversation-id` support.
- Follow-up resolution validates quotes against historical user content. Corrections
  are proposed by the resolver; assistant prose cannot become literal user evidence.
- Structured pending questions with choices, task continuation through later turns,
  and a frontend conversation ID/revision persisted in session storage.
- Context-aware rerouting, recovery from stale revision/expired conversations,
  isolation from the legacy saved-answer lookup, and explicit new-conversation reset.
- Deduplicated semantic/lexical candidates; reuse of the graph index; bounded
  ownership context for ranking instead of unrestricted concept fanout.
- Local approved evidence-package manifests with path containment, model matching,
  SHA-256 checks, and execution through the bounded scientific worker. Current
  integration requires the explicit phrase `using evidence package ID unchanged`.
  It executes the packaged scenario; automatic modification/adaptation is unfinished.
- Post-execution explanations reference actual calculation outputs and mechanically
  check quoted numerical values, including ordinary rounding tolerance. This is
  not an independent check of scientific entailment.
- Bounded conversation inference (six calls/120 seconds), cached capability and
  function catalogues, and configurable vLLM-compatible endpoint serving.
- Routing comparison harness and a four-case smoke set; these are not a replacement
  for the planned held-out scientific/conversation evaluation.

## Configuration

`THERMO_CONVERSATION_DB` selects the SQLite database (default
`/tmp/thermo-conversations.sqlite3`); use a persistent, protected runtime data path
for durable local deployments. Local SQLite is appropriate for one host, not a
multi-instance service. Session cookies are HttpOnly/SameSite and mutations check
Origin when present. Production authentication/HTTPS configuration remains a
separate deployment requirement.

`THERMO_EVIDENCE_PACKAGES` points to an administrator-controlled JSON manifest:

```json
{"packages":[{"id":"my-reviewed-package","model_id":"THM-05",
"payload_path":"payload.json","sha256":"<64 hex characters>",
"review_status":"approved","provenance":[{"source_url":"...","locator":"..."}],
"illustrative":false}]}
```

Payloads use each function's existing request/evidence contract. Approval is
external: this software checks manifest selection and integrity but does not
scientifically certify the calibration. No bundled example was automatically
approved or promoted to NASA evidence.

See [open-source inference](open-source-inference.md) for deployment and comparison.
GPU access was blocked in this workspace; no inference speed/accuracy improvement
has been measured. Keeping the same checkpoint with a more efficient serving
runtime is the first candidate to benchmark before testing smaller/quantized models.

## Outstanding plan items

- Fully typed quantity/slot extraction with deterministic conflict and basis
  validation before execution; present context facts are validated literal spans,
  not the complete proposed ResolvedInput contract.
- A unified typed task graph with dependent value bindings, task-level partial
  continuation, systematic sweeps and all-case fulfilment.
- Scientifically reviewed applicability/conditional input contracts for all 20
  functions, rather than registry signatures and general model descriptions.
- Automatic verified evidence-package discovery/adaptation, source-run calibration
  review, and broader calibrated model availability.
- Complete constrained passage/index fingerprint unification, dense provider
  wiring, and measured reranking/latency improvements.
- Full saved-result branching, durable result artifacts, exact-once work across
  simultaneous requests, and propagation of browser cancellation to inference.
- Human-reviewed 120-scenario evaluation, live API-versus-open-source accuracy and
  latency comparison, and production release thresholds.

Do not describe this version as implementation of every item in the plan or as
proving scientific accuracy. The end-to-end regression demonstrates a concrete
clarification reply resuming real THM-03 execution; broader behavior needs the
remaining evaluation and scientific input work.
