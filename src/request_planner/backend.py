"""Shared prompt → scoped retrieval → evidence/execution → verified output service."""

import os
import time
import uuid
from functools import lru_cache
from pathlib import Path

from .backend_models import AnswerResult, RetrievalBundle
from .intent import fulfilment, interpret, summarize_result
from .model_worker import InferenceError
from .models import FrontendResponse, SearchResults


@lru_cache(maxsize=2)
def evidence_index(path, mtime=0):
    from imperial_thermo_ai.evidence import EvidenceIndex

    return EvidenceIndex.read(path)


def retrieve(
    spec, graph, *, semantic_plan=None, limit=20, expansion=None, dense_search=None
):
    from imperial_thermo_ai.graph_search import evaluate
    from imperial_thermo_ai.semantic_plan import resource_expression

    prompt = spec.original_prompt
    kinds = {r.kind for r in spec.requirements}
    data_only = kinds.issubset({"calculation", "chart", "inspection"})
    pool = graph.search(
        prompt + (" " + expansion if expansion else ""),
        limit=100,
        role="measurement" if data_only else None,
        investigation_id=spec.investigations[0]
        if len(spec.investigations) == 1
        and spec.investigations[0] in graph.investigations
        else None,
    )
    candidates = pool.files
    if dense_search is not None:
        from imperial_thermo_ai.hybrid import reciprocal_rank_fusion

        candidates = reciprocal_rank_fusion(
            [candidates, dense_search(prompt, semantic_plan)]
        )
    known = set(graph.investigations)
    coverage = {
        inv: {"known": inv in known, "file_count": 0} for inv in spec.investigations
    }
    files, diagnostics = [], []
    for file in candidates:
        if file.file_id not in graph.graph.nodes:
            continue
        if (
            spec.investigations
            and file.investigation_id not in spec.investigations
            or file.investigation_id in spec.excluded_investigations
        ):
            continue
        eligible = file.retrieval_url is not None and (
            file.role in {"video", "image"}
            or file.media_type == "application/pdf"
            or file.role == "measurement"
            and file.media_type in {"text/csv", "application/json"}
            and (file.size_bytes is None or file.size_bytes <= 100_000_000)
        )
        checks = []
        if semantic_plan:
            checks = [
                evaluate(
                    graph.graph,
                    file.file_id,
                    resource_expression(q["return_type"], q["where"]),
                )
                for q in semantic_plan["queries"]
            ]
            if not checks or not any(
                e.state is True
                or e.state is None
                and not any(d["status"] == "conflicting" for d in e.details)
                for e in checks
            ):
                eligible = False
        diagnostics.append(
            {
                "file_id": file.file_id,
                "eligible": eligible,
                "conditions": [d for e in checks for d in e.details],
            }
        )
        if eligible and len(files) < limit:
            files.append(file)
            if file.investigation_id in coverage:
                coverage[file.investigation_id]["file_count"] += 1
    return RetrievalBundle(
        query_id=pool.query_id,
        graph_id=graph.graph.graph.get("graph_id", "unknown"),
        files=files,
        coverage=coverage,
        diagnostics=diagnostics,
        trusted_source_hashes={
            f.file_id: graph.graph.nodes[f.file_id]["properties"]["profile_sha256"]
            for f in files
            if graph.graph.nodes[f.file_id]["properties"].get("profile_sha256")
        },
    )


def _answer(
    prompt,
    *,
    planner=None,
    graph_path=None,
    context=None,
    semantic_generator=None,
    evidence_path=None,
    deadline_seconds=120,
    answer_generator=None,
    program_generator=None,
    dense_search=None,
    **execution_options,
):
    import re

    from imperial_thermo_ai.reviewed_graph import load_graph

    from .service import run_workflow

    started = time.monotonic()
    import inspect

    def budgeted(generate):
        if generate is None:
            return None

        def call(messages):
            remaining = deadline_seconds - (time.monotonic() - started)
            if remaining <= 0:
                raise ValueError("Request deadline exceeded during model inference.")
            if "max_time" in inspect.signature(generate).parameters:
                return generate(messages, max_time=remaining)
            return generate(messages)

        return call

    semantic_generator = budgeted(semantic_generator)
    answer_generator = budgeted(answer_generator)
    program_generator = budgeted(program_generator)
    graph = load_graph(graph_path)
    spec = interpret(prompt, aliases=graph.aliases, context=context)
    context_sources = []
    if re.search(r"\b(that|previous)\b", prompt, re.IGNORECASE) and (context or {}).get(
        "history"
    ):
        last = context["history"][-1]
        if isinstance(last, dict):
            context_sources = [
                fid for fid in last.get("source_file_ids", []) if fid in graph.owners
            ]
            if not spec.investigations:
                spec.investigations = sorted(
                    {
                        graph.owners[fid][0].removeprefix("inv:")
                        for fid in context_sources
                    }
                )
            if not context_sources:
                spec.clarifications.append(
                    "The previous answer has no identified source file; specify which report or dataset to use."
                )
    kinds = {r.kind for r in spec.requirements}
    scenario_only = (
        "calculation" in kinds
        and not spec.investigations
        and not re.search(
            r"\b(csv|dataset|table|measurements)\b", prompt, re.IGNORECASE
        )
    )
    simple_content = (
        kinds.issubset({"document", "video", "image", "explanation"})
        and not spec.explicit_conditions
        and not re.search(r"\b(compare|contrast|difference)\b", prompt, re.IGNORECASE)
    )
    if semantic_generator is not None and not scenario_only and not simple_content:
        from .interpretation import enrich

        try:
            spec = enrich(spec, semantic_generator, graph.graph.graph)
        except (ValueError, OSError, RuntimeError) as exc:
            if isinstance(exc, InferenceError):
                raise
            spec.clarifications.append(
                "Could not validate the request interpretation: " + str(exc)
            )
    bundle = retrieve(
        spec, graph, semantic_plan=spec.semantic_plan, dense_search=dense_search
    )
    retrieved = time.monotonic()
    unknown = [inv for inv, c in bundle.coverage.items() if not c["known"]]
    spec.clarifications.extend(
        "Investigation is absent from this graph: " + inv for inv in unknown
    )
    response = FrontendResponse(
        query_id=bundle.query_id, status="needs_input", message=""
    )
    claims = []
    out_of_scope = bool(
        spec.semantic_plan and spec.semantic_plan["intent"] == "out_of_scope"
    )
    needs_explanation = not out_of_scope and any(
        r.kind == "explanation" for r in spec.requirements
    )
    if needs_explanation:
        default = (
            Path(__file__).resolve().parents[1]
            / "reviewed_knowledge_graph/output/evidence-index.json"
        )
        path = Path(evidence_path or os.getenv("THERMO_EVIDENCE_INDEX") or default)
        index = evidence_index(
            str(path), path.stat().st_mtime_ns if path.exists() else 0
        )
        # A request to summarise a named report is constrained to those retrieved documents.
        named = (
            {f.file_id for f in bundle.files if f.media_type == "application/pdf"}
            if re.search(r"\bsummari[sz]e\b.*\b(report|pdf)\b", prompt, re.IGNORECASE)
            else None
        )
        if context_sources:
            named = set(context_sources)
        bundle.evidence = index.search(
            prompt, spec.investigations, spec.excluded_investigations, file_ids=named
        )
        if len(spec.investigations) > 1:
            groups = [
                index.search(
                    prompt, [inv], spec.excluded_investigations, limit=4, file_ids=named
                )
                for inv in spec.investigations
            ]
            bundle.evidence = [
                items[i] for i in range(4) for items in groups if i < len(items)
            ][:8]
        # Extractive answers retain source wording and context; no unsupported generated findings.
        claims = [
            {
                "text": e.text,
                "evidence_ids": [e.id],
                "psi_ids": [e.investigation_id],
                "kind": "source_excerpt",
            }
            for e in bundle.evidence[:4]
        ]
        if answer_generator and claims:
            from .composition import compose

            try:
                claims = compose(prompt, bundle.evidence, answer_generator)
            except ValueError as exc:
                if isinstance(exc, InferenceError):
                    raise
                response.warnings.append(str(exc))
                claims = []
        if not claims:
            response.warnings.append(
                "No indexed source passage supports this explanation. Source links alone do not establish an answer."
            )
    computational = any(
        r.kind in {"calculation", "chart", "inspection", "document", "video", "image"}
        for r in spec.requirements
    )
    program_ran = False
    if (
        program_generator
        and any(r.kind in {"calculation", "chart"} for r in spec.requirements)
        and not spec.clarifications
    ):
        from .program import execute, propose

        try:
            program = propose(prompt, bundle.files, program_generator)
            if not program.steps and program.missing_inputs:
                extra = retrieve(
                    spec,
                    graph,
                    semantic_plan=spec.semantic_plan,
                    expansion=" ".join(program.missing_inputs)[:1000],
                )
                original_ids = {f.file_id for f in bundle.files}
                new_files = [f for f in extra.files if f.file_id not in original_ids]
                bundle.diagnostics.append(
                    {
                        "retrieval_expansion": program.missing_inputs,
                        "new_file_count": len(new_files),
                    }
                )
                if new_files:
                    bundle.files.extend(new_files[:20])
                    program = propose(prompt, bundle.files, program_generator)
            if program.steps:
                from .models import ExecutionLimits

                left = deadline_seconds - (time.monotonic() - started)
                if left <= 0:
                    raise ValueError("Request deadline exceeded before execution.")
                response.blocks, response.sources, trace = execute(
                    program,
                    prompt,
                    bundle.files,
                    limits=ExecutionLimits(
                        max_runtime_seconds=max(1, min(60, int(left)))
                    ),
                    client=execution_options.get("client"),
                    url_validator=execution_options.get("url_validator"),
                )
                bundle.diagnostics.append({"program_trace": trace})
                response.warnings.extend(
                    "Model defaults: " + str(t["model_defaults"])
                    for t in trace
                    if t.get("model_defaults")
                )
                response.status = "completed"
                program_ran = True
            response.warnings.extend(program.missing_inputs)
        except ValueError as exc:
            if isinstance(exc, InferenceError):
                raise
            response.warnings.append(str(exc))
    if (
        computational
        and not program_ran
        and not spec.clarifications
        and not (set(spec.investigations) & set(spec.excluded_investigations))
    ):
        if planner is None and all(
            r.kind in {"document", "video", "image", "inspection"}
            for r in spec.requirements
        ):
            from .models import Plan

            class DirectPlanner:
                def propose(self, prompt, results, limits):
                    selected, assets = [], []
                    for requirement in spec.requirements:
                        for inv in spec.investigations or [None]:
                            choices = [
                                f
                                for f in results.files
                                if inv is None or f.investigation_id == inv
                            ]
                            if requirement.kind == "inspection":
                                selected.extend(
                                    f.file_id
                                    for f in choices
                                    if f.role == "measurement"
                                )
                            else:
                                selected_files = [
                                    f
                                    for f in choices
                                    if f.role == requirement.kind
                                    or requirement.kind == "document"
                                    and f.media_type == "application/pdf"
                                ]
                                assets.extend(f.file_id for f in selected_files[:1])
                    return Plan(
                        action="inspect_files"
                        if selected
                        else "retrieve_assets"
                        if assets
                        else "no_match",
                        selected_file_ids=list(dict.fromkeys(selected[:2])),
                        requested_asset_ids=list(dict.fromkeys(assets)),
                        operation=None,
                        explanation="Retrieve the requested sources.",
                        warnings=[],
                    )

            planner = DirectPlanner()
        if planner is None:
            response.warnings.append(
                "A planning provider is required for this operation. Configure local or API planning."
            )
        else:
            remaining = deadline_seconds - (time.monotonic() - started)
            if remaining <= 0:
                response.status = "error"
                response.message = "Request deadline exceeded during retrieval."
            else:
                from .models import ExecutionLimits

                options = dict(execution_options)
                options["trusted_source_hashes"] = bundle.trusted_source_hashes
                options["limits"] = ExecutionLimits(
                    max_runtime_seconds=max(1, min(60, int(remaining))),
                    max_download_bytes=min(
                        100_000_000,
                        options.get("limits", ExecutionLimits()).max_download_bytes,
                    ),
                )
                previous_warnings = list(response.warnings)
                response = run_workflow(
                    prompt,
                    SearchResults(query_id=bundle.query_id, files=bundle.files),
                    planner,
                    request_spec=spec,
                    planning_seconds=min(60, max(0, remaining - 60)),
                    **options,
                )
                response.warnings.extend(previous_warnings)
    elif not computational and not needs_explanation and bundle.files:
        response.message = "Found " + str(len(bundle.files)) + " relevant source files."
        response.sources = [
            {
                "file_id": f.file_id,
                "title": f.title,
                "investigation_id": f.investigation_id,
                "source_page_url": str(f.source_page_url or f.retrieval_url or ""),
                "downloaded": False,
            }
            for f in bundle.files
        ]
    rows = fulfilment(spec, response, claims=claims, files=bundle.files)
    if spec.investigations:
        cited_ids = {eid for claim in claims for eid in claim["evidence_ids"]}
        selected = {s.get("investigation_id") for s in response.sources} | {
            e.investigation_id for e in bundle.evidence if e.id in cited_ids
        }
        if all(r.kind == "discovery" for r in spec.requirements):
            selected |= {f.investigation_id for f in bundle.files}
        for inv in spec.investigations:
            rows.append(
                {
                    "id": "group-" + inv,
                    "kind": "investigation",
                    "satisfied": inv in selected,
                    "missing": None
                    if inv in selected
                    else "No output for requested investigation " + inv,
                }
            )
    # A file matching topic words cannot establish requested numerical conditions.
    source_outputs = bool(response.sources or claims)
    if spec.explicit_conditions and source_outputs:
        verified = bool(spec.semantic_plan) and all(
            all(d.get("status") == "satisfied" for d in diag.get("conditions", []))
            for diag in bundle.diagnostics
            if diag.get("eligible")
        )
        if not verified:
            rows.append(
                {
                    "id": "conditions",
                    "kind": "conditions",
                    "satisfied": False,
                    "missing": "Requested source conditions are not fully verified: "
                    + ", ".join(spec.explicit_conditions),
                }
            )
    if out_of_scope:
        status = "unsupported"
    elif response.status == "error":
        status = "error"
    elif spec.clarifications:
        status = "partial" if any(r["satisfied"] for r in rows) else "needs_input"
    elif all(r["satisfied"] for r in rows):
        status = "completed"
    elif any(r["satisfied"] for r in rows):
        status = "partial"
    else:
        status = "needs_input" if computational else "no_evidence"
    message = summarize_result(response)
    if claims:
        message = "\n\n".join(
            (
                "Source excerpt ("
                if c.get("kind") == "source_excerpt"
                else "Source-supported summary ("
            )
            + next(e.locator for e in bundle.evidence if e.id == c["evidence_ids"][0])
            + "): "
            + c["text"]
            for c in claims
        )
        if response.blocks:
            message += "\n\n" + summarize_result(response)
    missing = [r["missing"] for r in rows if not r["satisfied"]]
    if missing:
        message += ("\n\n" if message else "") + " ".join(missing)
    if spec.clarifications:
        message += "\n\n" + " ".join(spec.clarifications)
    return AnswerResult(
        trace_id=uuid.uuid4().hex,
        status=status,
        message=message,
        request=spec,
        retrieval=bundle,
        result=response,
        fulfilment=rows,
        claims=claims,
        timings={
            "retrieval": round(retrieved - started, 3),
            "total": round(time.monotonic() - started, 3),
        },
    )


def answer(prompt, **options):
    """Return structured provider failures; never replace them with mock science."""
    from openai import OpenAIError

    try:
        return _answer(prompt, **options)
    except (OpenAIError, InferenceError):
        spec = interpret(prompt, context=options.get("context"))
        bundle = RetrievalBundle(
            query_id=uuid.uuid4().hex, graph_id="unavailable", files=[]
        )
        response = FrontendResponse(
            query_id=bundle.query_id,
            status="error",
            message="Planning provider failed; check model access, credentials and connectivity.",
            errors=[
                {
                    "code": "planning_provider_error",
                    "message": "Planning provider failed.",
                }
            ],
        )
        return AnswerResult(
            trace_id=uuid.uuid4().hex,
            status="error",
            message=response.message,
            request=spec,
            retrieval=bundle,
            result=response,
            fulfilment=fulfilment(spec, response),
        )
