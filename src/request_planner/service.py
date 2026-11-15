"""Public prompt → plan → temporary execution → frontend JSON boundary."""

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time

import httpx
from openai import OpenAIError
from pydantic import ValidationError

from .execution import ExecutionError, ExecutionSession
from .models import ExecutionLimits, FrontendResponse, SearchResults, ServiceRequest
from .planner import OpenAIPlanner, PlanningError, build_request


def run_workflow(
    prompt, results, planner, *, client=None, url_validator=None, temp_dir=None, limits=None,
    planning_seconds=0, on_model_input=None,
):
    """Accept the search team's wire contract; return a JSON-serializable frontend model.

    `with_context(inspection)` is optional on a planner. Without it, inspection
    returns needs_input so a caller can review/enrich records before replanning.
    Downloads are shared across at most three planning rounds and always removed.
    A caller may give local inference a separate allowance within the workflow.
    An optional on_model_input(model_id, payload) receives a copy of the assembled
    input before the worker starts. Hooks belong to the application, never the plan.
    """
    if not isinstance(results, SearchResults):
        results = SearchResults.model_validate(results)
    response = FrontendResponse(query_id=results.query_id, status="needs_input", message="")
    limits = limits or ExecutionLimits()
    limits = ExecutionLimits(max_download_bytes=min(limits.max_download_bytes, 100_000_000),
                             max_runtime_seconds=min(limits.max_runtime_seconds, 60))
    planning_allowance = max(0, min(planning_seconds, 60))
    options = {"url_validator": url_validator} if url_validator is not None else {}
    with tempfile.TemporaryDirectory(prefix="thermo-request-", dir=temp_dir) as directory:
        session = ExecutionSession(directory, limits, client=client, on_model_input=on_model_input,
                                   raw_prompt=prompt, **options)
        try:
            for _ in range(3):
                session.remaining()
                if hasattr(planner, "with_timeout"):
                    planner = planner.with_timeout(session.remaining() + planning_allowance)
                planning_started = time.monotonic()
                request = build_request(prompt, results, planner, limits=limits)
                elapsed = min(planning_allowance, time.monotonic() - planning_started)
                session.deadline += elapsed
                planning_allowance -= elapsed
                session.remaining()
                response.requests.append(request)
                response.warnings.extend(request.plan.warnings)
                response.message = request.plan.explanation
                if request.plan.action == "no_match":
                    response.status = "no_match"
                    break
                blocks, results = session.execute(request, results)
                response.blocks.extend(blocks)
                for block in blocks:
                    if block["type"] == "calculation":
                        data = block["data"]
                        for key in ("warnings", "limitations"):
                            response.warnings.extend(w for w in data.get(key, []) if isinstance(w, str))
                if request.plan.action != "inspect_files":
                    response.status = "completed"
                    break
                if not hasattr(planner, "with_context"):
                    response.message = "Files inspected. Review missing units/evidence before calculating."
                    break
                planner = planner.with_context(session.inspection)
            else:
                response.message = "Inspection limit reached. Supply the missing units, evidence, or a supported dataset."
            # Include source caveats even if the model omits them.
            selected = {i for request in response.requests for i in
                        request.plan.selected_file_ids + request.plan.requested_asset_ids}
            for file in results.files:
                if file.file_id in selected:
                    response.warnings.extend(file.data_notes)
        except (ExecutionError, PlanningError, ValueError, KeyError, TypeError, OSError, httpx.HTTPError) as exc:
            response.status = "needs_input" if isinstance(exc, PlanningError) or str(exc).startswith("Function needs") else "error"
            # Network exceptions may contain signed URLs; expose only a fixed diagnostic.
            message = "Source transfer failed; check file availability." if isinstance(exc, httpx.HTTPError) else str(exc)
            response.message = message
            response.errors.append({"code": type(exc).__name__, "message": message})
        except OpenAIError:
            response.status = "error"
            response.message = "Planning provider failed; check model access and credentials."
            response.errors.append({"code": "planning_provider_error", "message": response.message})
        response.sources = list(session.sources.values())
    response.warnings = list(dict.fromkeys(response.warnings))
    return FrontendResponse.model_validate(response.model_dump())


def execute_request(request, results, *, prompt=None, **kwargs):
    """Execute a saved validated request without another LLM call."""
    if not isinstance(request, ServiceRequest):
        request = ServiceRequest.model_validate(request)
    if not isinstance(results, SearchResults):
        results = SearchResults.model_validate(results)
    if request.query_id != results.query_id:
        raise PlanningError("Request query_id differs from search results")

    class SavedPlanner:
        def propose(self, prompt, results, limits):
            return request.plan

    # Fixed server caps apply even if a saved request advertises larger limits.
    return run_workflow(prompt or "Execute saved request", results, SavedPlanner(), limits=request.limits, **kwargs)


def main():
    parser = argparse.ArgumentParser(description="Execute graph results and return frontend response JSON")
    parser.add_argument("--search-results", required=True, type=Path)
    parser.add_argument("--prompt")
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL"))
    parser.add_argument("--request", type=Path, help="Execute a saved service request without an LLM")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--model-input", type=Path, help="Save the exact model input to a new JSON file")
    args = parser.parse_args()
    if not args.request and (not args.prompt or not args.model or not os.getenv("OPENAI_API_KEY")):
        parser.error("Supply --request, or --prompt, --model and OPENAI_API_KEY")
    if args.model_input and args.output and args.model_input.resolve() == args.output.resolve():
        parser.error("--model-input and --output must name different files")

    def save_model_input(_model_id, payload):
        content = json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        with args.model_input.open("x", encoding="utf-8") as handle:
            handle.write(content)

    options = {"on_model_input": save_model_input} if args.model_input else {}
    try:
        results = SearchResults.model_validate_json(args.search_results.read_text(encoding="utf-8-sig"))
        if args.request:
            response = execute_request(ServiceRequest.model_validate_json(args.request.read_text(encoding="utf-8-sig")),
                                       results, prompt=args.prompt, **options)
        else:
            response = run_workflow(args.prompt, results, OpenAIPlanner(args.model), **options)
        content = response.model_dump_json(indent=2) + "\n"
        if args.output:
            args.output.write_text(content, encoding="utf-8")
        else:
            sys.stdout.write(content)
        return 1 if response.status == "error" else 0
    except (OSError, ValueError, ValidationError) as exc:
        print(f"Execution failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
