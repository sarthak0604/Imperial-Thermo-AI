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
    from imperial_thermo_ai.graph_search import evaluate, search_graph
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
    candidates = list(pool.files)
    semantic_candidate_count = 0
    if semantic_plan and semantic_plan.get("queries"):
        # A semantic query must be able to recover a resource that lexical
        # ranking did not place in its first page. Execute its validated routes
        # against Resource nodes, then retain lexical results as recall fallback.
        resource_plan = dict(semantic_plan)
        resource_plan["queries"] = [
            {
                **query,
                "return_type": "Resource",
                "where": resource_expression(query["return_type"], query["where"]),
            }
            for query in semantic_plan["queries"]
        ]
        graph_results = search_graph(
            graph.graph, resource_plan, limit=min(100, max(20, limit * 5))
        )
        semantic_records = []
        seen_semantic_ids = set()
        for bucket in ("matches", "candidates"):
            query_rows = [q[bucket] for q in graph_results["queries"]]
            for rank in range(max((len(rows) for rows in query_rows), default=0)):
                for rows in query_rows:
                    if rank >= len(rows):
                        continue
                    hit = rows[rank]
                    file_id = hit["id"]
                    if file_id in seen_semantic_ids or file_id not in graph.owners:
                        continue
                    seen_semantic_ids.add(file_id)
                    semantic_records.append(
                        graph._record(
                            file_id,
                            "Validated graph-query "
                            + bucket.rstrip("s")
                            + "; metadata match is not a scientific conclusion.",
                        )
                    )
        semantic_candidate_count = len(semantic_records)
        candidates = semantic_records + candidates
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
    seen_files = set()
    for file in candidates:
        if file.file_id in seen_files:
            continue
        seen_files.add(file.file_id)
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
        diagnostics=[
            {"semantic_graph_candidate_count": semantic_candidate_count},
            *diagnostics,
        ],
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
    routing_decision=None,
    routing_generator=None,
    function_generator=None,
    **execution_options,
):
    import re

    from imperial_thermo_ai.reviewed_graph import load_graph

    from .service import run_workflow

    started = time.monotonic()
    import inspect

    def budgeted(generate, *, stage_limit=None):
        if generate is None:
            return None

        def call(messages):
            remaining = deadline_seconds - (time.monotonic() - started)
            if remaining <= 0:
                raise ValueError("Request deadline exceeded during model inference.")
            if stage_limit is not None:
                remaining = min(remaining, stage_limit)
            if "max_time" in inspect.signature(generate).parameters:
                return generate(messages, max_time=remaining)
            return generate(messages)

        return call

    semantic_generator = budgeted(semantic_generator)
    answer_generator = budgeted(answer_generator, stage_limit=12)
    program_generator = budgeted(program_generator)
    graph = load_graph(graph_path)
    spec = interpret(prompt, aliases=graph.aliases, context=context)
    from .calibrated_spread import answer_pmma_comparison

    calibrated = answer_pmma_comparison(spec, graph.graph.graph.get("graph_id", "unknown"))
    if calibrated is not None:
        return calibrated
    from .nist_calorimetry import nist_window, run_nist_window

    window = nist_window(prompt)
    if window is not None:
        from .backend_models import Requirement

        bundle = RetrievalBundle(query_id=uuid.uuid4().hex,
                                 graph_id=graph.graph.graph.get("graph_id", "unknown"), files=[])
        spec.requirements = [Requirement(id="nist-model", kind="calculation", model_id="THM-04",
                                         source_text=prompt),
                             Requirement(id="nist-chart", kind="chart", source_text=prompt)]
        response = FrontendResponse(query_id=bundle.query_id, status="needs_input", message="")
        outcome = run_nist_window(window)
        if outcome is None:
            response.message = "The bundled NIST run covers 995–1005 s. Choose a window within that range."
        else:
            result, response.blocks, source, response.warnings = outcome
            response.sources = [source]
            response.status = "completed"
            response.message = (
                f"THM-04 estimates {result['total_heat_release_kJ']:,.1f} kJ released between "
                f"{window[0]:g} and {window[1]:g} s. The peak within that window was "
                f"{result['peak_hrr_W'] / 1000:,.1f} kW at {result['peak_hrr_time_s']:g} s."
            )
        return AnswerResult(
            trace_id=bundle.query_id, status=response.status, message=response.message,
            request=spec, retrieval=bundle, result=response, fulfilment=fulfilment(spec, response),
            timings={"total": round(time.monotonic() - started, 3)},
        )
    if routing_decision is None and routing_generator is not None:
        from .task_router import route
        routing_decision = route(prompt, budgeted(routing_generator, stage_limit=12), context,
                                 function_planner=function_generator is not None)
    if routing_decision is not None:
        from .backend_models import Requirement
        if routing_decision.intent in {'calculation', 'chart'}:
            spec.requirements = [r for r in spec.requirements if r.kind != 'discovery']
            for mid in routing_decision.model_ids:
                if not any(r.model_id == mid for r in spec.requirements):
                    spec.requirements.append(Requirement(id='route-'+mid,kind='calculation',source_text=prompt,model_id=mid))
            if routing_decision.intent == 'chart' and not any(r.kind == 'chart' for r in spec.requirements):
                spec.requirements.append(Requirement(id='route-chart',kind='chart',source_text=prompt))
        elif routing_decision.intent == 'explanation':
            spec.requirements = [r for r in spec.requirements if r.kind != 'discovery']
            if not any(r.kind == 'explanation' for r in spec.requirements):
                spec.requirements.append(Requirement(id='route-explanation',kind='explanation',source_text=prompt))
        spec.clarifications.extend(
            slot.question for slot in routing_decision.missing
            if function_generator is None or slot.reason_code == "required_model_state"
        )
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
            if not context_sources and not (context or {}).get('previous_results'):
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
    from .flame_temperature import calculate_flame_temperature, flame_temperature_inputs

    temperature_inputs = flame_temperature_inputs(prompt)
    if (temperature_inputs is None and function_generator is not None
            and not spec.clarifications
            and any(r.kind == "calculation" for r in spec.requirements)):
        from .thm_pipeline import answer_functions
        from .models import ExecutionLimits
        from .evidence_packages import EvidencePackageRegistry
        manifest = os.getenv('THERMO_EVIDENCE_PACKAGES')
        result = answer_functions(spec, graph, bundle, budgeted(function_generator, stage_limit=30),
            deadline=started+deadline_seconds,
            answer_generator=answer_generator,
            selected_models={r.model_id for r in spec.requirements if r.model_id},
            limits=ExecutionLimits(max_runtime_seconds=max(1,min(60,int(deadline_seconds-(time.monotonic()-started))))),
            client=execution_options.get('client'),url_validator=execution_options.get('url_validator'),
            package_registry=EvidencePackageRegistry(manifest) if manifest else None)
        result.timings={'retrieval':round(retrieved-started,3),'total':round(time.monotonic()-started,3)}
        return result
    response = FrontendResponse(
        query_id=bundle.query_id, status="needs_input", message=""
    )
    if (context or {}).get('explain_previous'):
        response.blocks = (context or {}).get('previous_results', [])
    package_ran = False
    if temperature_inputs is not None and not spec.clarifications:
        from .execution import ExecutionError, present_result

        try:
            computed = calculate_flame_temperature(temperature_inputs)
        except ExecutionError as exc:
            spec.clarifications.append(str(exc))
        else:
            response.blocks = [block for result in computed
                               for block in present_result("THM-01", result, include_input=True)
                               if len(computed) == 1 or block["type"] == "calculation"]
            if "hypothetical lunar habitat" in prompt.casefold():
                response.warnings.append(
                    "The supplied gas conditions describe a hypothetical lunar habitat. "
                    "THM-01 computes chemical equilibrium and does not model gravity."
                )
            if isinstance(temperature_inputs["fuel_species"], list):
                response.warnings.append(
                    "Assumed standard air: 21% oxygen in nitrogen, 298.15 K and 101.325 kPa. "
                    "The model assumes a stoichiometric mixture (equivalence ratio 1)."
                )
            if len(computed) > 1:
                response.blocks.append({
                    "type": "chart", "chart_type": "bar", "title": "THM-01 flame temperature by fuel",
                    "categories": [r["inputs"]["fuel_species"] for r in computed],
                    "x": {"label": "Fuel", "unit": None, "values": list(range(len(computed)))},
                    "series": [{"label": "Adiabatic flame temperature", "unit": "K",
                                "values": [r["outputs"]["adiabatic_flame_temp_k"] for r in computed]}],
                    "evidence_type": "model_estimate",
                })
            for block in response.blocks:
                block["source_file_ids"] = []
            response.status = "completed"
            package_ran = True
    package_match = re.search(r'using evidence package ([A-Za-z0-9_.-]+) unchanged', prompt, re.I)
    if package_match and os.getenv('THERMO_EVIDENCE_PACKAGES'):
        from .evidence_packages import EvidencePackageRegistry
        from .execution import ExecutionSession, present_result
        from .models import ExecutionLimits
        import tempfile
        mids = {r.model_id for r in spec.requirements if r.model_id}
        if len(mids) != 1:
            spec.clarifications.append('Choose exactly one THM function for this evidence package.')
        elif not spec.clarifications:
            mid = next(iter(mids))
            try:
                package, payload = EvidencePackageRegistry(os.environ['THERMO_EVIDENCE_PACKAGES']).load(package_match.group(1), mid)
                with tempfile.TemporaryDirectory(prefix='thermo-evidence-') as directory:
                    worker = ExecutionSession(directory, ExecutionLimits())
                    computed = worker.calculate(mid, payload)
                response.blocks = present_result(mid, computed, include_input=True)
                for block in response.blocks:
                    block['illustrative'] = package.illustrative
                response.warnings.append('Evidence package '+package.id+'; original packaged scenario used unchanged.')
                response.status = 'completed'
                package_ran = True
            except ValueError as exc:
                spec.clarifications.append(str(exc))
    # Modern THM functions require a sourced calibration envelope. The reviewed
    # graph currently has no function-compatible JSON for some studies; avoid
    # spending an inference round trying to turn an unrelated CSV into one.
    requested_models = {r.model_id for r in spec.requirements if r.kind == "calculation" and r.model_id}
    from .function_registry import model_spec

    if requested_models and not package_ran and not any(f.media_type == "application/json" for f in bundle.files):
        for model_id in sorted(requested_models):
            if model_spec(model_id)["requires_evidence"]:
                missing = (
                    "For THM-05, provide a sourced PMMA calibration and the "
                    "opposed-flow speed, oxygen level, pressure, and sheet width."
                    if model_id == "THM-05"
                    else "Provide its sourced calibration and matching test conditions."
                )
                spec.clarifications.append(
                    f"{model_id} needs a sourced JSON calibration before its "
                    f"calculation or plot can run. {missing}"
                )
    unknown = [inv for inv, c in bundle.coverage.items() if not c["known"]]
    spec.clarifications.extend(
        "Investigation is absent from this graph: " + inv for inv in unknown
    )
    claims = []
    out_of_scope = bool(
        spec.semantic_plan and spec.semantic_plan["intent"] == "out_of_scope"
    )
    needs_explanation = not out_of_scope and any(
        r.kind == "explanation" for r in spec.requirements
    )
    if needs_explanation:
        from imperial_thermo_ai.graph_search import tokens

        query_terms = tokens(prompt)

        def excerpt(text):
            sentences = re.split(r"(?<=[.!?])\s+", " ".join(text.split()))
            best = max(sentences, key=lambda sentence: len(query_terms & tokens(sentence)))
            if len(best) > 320:
                return best[:317].rsplit(" ", 1)[0] + "…"
            return best

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
        if not evidence_path and not os.getenv("THERMO_EVIDENCE_INDEX"):
            graph_files = set(graph.owners)
            named = graph_files if named is None else named & graph_files
        preferred = {f.file_id for f in bundle.files}
        bundle.evidence = index.search(
            prompt, spec.investigations, spec.excluded_investigations, file_ids=named,
            preferred_files=preferred
        )
        if len(spec.investigations) > 1:
            groups = [
                index.search(
                    prompt, [inv], spec.excluded_investigations, limit=4, file_ids=named,
                    preferred_files=preferred
                )
                for inv in spec.investigations
            ]
            bundle.evidence = [
                items[i] for i in range(4) for items in groups if i < len(items)
            ][:8]
        # Extractive answers retain source wording and context; no unsupported generated findings.
        claims = [
            {
                "text": excerpt(e.text),
                "evidence_ids": [e.id],
                "psi_ids": [e.investigation_id],
                "kind": "source_excerpt",
            }
            for e in bundle.evidence[:max(2, len(spec.investigations))]
        ]
        if answer_generator and claims and not any(r.kind == 'calculation' for r in spec.requirements):
            from .composition import compose

            try:
                composed = compose(prompt, bundle.evidence, answer_generator)
                if composed:
                    claims = composed
            except ValueError as exc:
                response.warnings.append(
                    "The summary could not be verified. Relevant source passages are shown below."
                )
        if not claims:
            response.warnings.append(
                "No indexed source passage supports this explanation. Source links alone do not establish an answer."
            )
    computational = any(
        r.kind in {"calculation", "chart", "inspection", "document", "video", "image"}
        for r in spec.requirements
    )
    program_ran = package_ran
    if (
        not package_ran
        and program_generator
        and any(r.kind in {"calculation", "chart"} for r in spec.requirements)
        and not spec.clarifications
        and not any(model_spec(mid)["requires_evidence"] for mid in requested_models)
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
                requested_models = {
                    r.model_id for r in spec.requirements if r.model_id is not None
                }
                if requested_models:
                    selected_models = {
                        step.scenario.model_id
                        for step in program.steps
                        if step.kind == "scenario" and step.scenario is not None
                    }
                    if selected_models != requested_models:
                        raise ValueError(
                            "The proposed program does not run exactly the explicitly requested THM model(s). "
                            f"Requested: {sorted(requested_models)}; selected: {sorted(selected_models)}."
                        )
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
    if answer_generator and needs_explanation and temperature_inputs is None and re.search(
        r"\b(?:explain|why|interpret)\b", prompt, re.I
    ) and any(b['type'] == 'calculation' for b in response.blocks):
        from .composition import compose_results
        try:
            claims = compose_results(prompt, response.blocks, answer_generator)
        except ValueError as exc:
            response.warnings.append(str(exc))
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
    elif claims or any(r["satisfied"] for r in rows):
        status = "partial"
    else:
        status = "needs_input" if computational else "no_evidence"
    message = summarize_result(response)
    if claims:
        message = "\n\n".join(
            ("Source excerpt: " if c.get("kind") == "source_excerpt" else "")
            + c["text"] for c in claims
        )
        if response.blocks and not any(c.get("source_type") == "computed_result" for c in claims):
            message += "\n\n" + summarize_result(response)
    missing = [r["missing"] for r in rows if not r["satisfied"]]
    if claims and "No supported explanation was produced." in missing:
        missing[missing.index("No supported explanation was produced.")] = (
            "Relevant sources were found. The answer above contains source excerpts."
        )
    if (not response.blocks and claims
            and all(c["kind"] == "source_excerpt" for c in claims)
            and any(row["id"] == "conditions" and not row["satisfied"] for row in rows)):
        message = (
            "I found related sources, but they do not verify the requested conditions: "
            + ", ".join(spec.explicit_conditions) + ". See References."
        )
        missing = []
    if missing:
        message += ("\n\n" if message else "") + " ".join(missing)
    if spec.clarifications:
        message += "\n\n" + " ".join(spec.clarifications)
    anchors = spec.investigations or list(dict.fromkeys(
        psi for claim in claims for psi in claim.get("psi_ids", [])
    ))
    links = graph.crosslinks(anchors, spec.excluded_investigations)
    return AnswerResult(
        trace_id=uuid.uuid4().hex,
        crosslinks=links,
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


def with_related_sources(result):
    """Keep useful graph links separate from evidence that supplied model inputs."""
    if result.status not in {"needs_input", "partial", "no_evidence", "error"} or result.result.sources:
        return result
    if not any(r.kind in {"calculation", "chart"} for r in result.request.requirements):
        return result
    from imperial_thermo_ai.graph_search import tokens

    words = tokens(result.request.original_prompt)
    candidates = [
        file for file in result.retrieval.files
        if (file.retrieval_url or file.source_page_url)
        and (file.investigation_id in result.request.investigations
             or len(words & tokens(file.title)) >= 2)
    ]
    for file in candidates[:3]:
        result.result.sources.append({
            "file_id": file.file_id, "investigation_id": file.investigation_id,
            "title": "Related source · " + file.title,
            "source_page_url": str(file.retrieval_url or file.source_page_url),
        })
    if candidates:
        result.message += "\n\nRelated NASA sources are listed under References. They did not supply verified inputs for this calculation."
    return result


def answer(prompt, **options):
    """Return structured provider failures; never replace them with mock science."""
    from openai import OpenAIError

    try:
        from .methods import decorate_result
        return decorate_result(with_related_sources(_answer(prompt, **options)))
    except InferenceError:
        # Keep the graph and direct Python handlers available when inference is unavailable.
        fallback = dict(options)
        for key in ("planner", "routing_generator", "semantic_generator",
                    "function_generator", "program_generator", "answer_generator"):
            fallback.pop(key, None)
        result = with_related_sources(_answer(prompt, **fallback))
        result.result.warnings.append(
            "AI planning did not finish. The dashboard used direct model matching and graph evidence."
        )
        if not result.message.strip():
            result.message = "AI planning did not finish. Try specifying the model inputs or naming the NASA investigation."
        return decorate_result(result)
    except OpenAIError:
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
