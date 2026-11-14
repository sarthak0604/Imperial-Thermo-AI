"""Command-line entry point. SI-assisted code; see README.md."""

import argparse
import os
from pathlib import Path
import sys

from openai import OpenAIError
from pydantic import ValidationError

from .models import Plan, SearchResults
from .planner import OpenAIPlanner, PlanningError, build_request


class ReplayPlanner:
    """Replay a saved response to exercise validation without calling an LLM."""

    def __init__(self, path: Path):
        self.plan = Plan.model_validate_json(path.read_text())

    def propose(self, prompt, results, limits):
        return self.plan


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan a data-service request from graph results")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--search-results", type=Path, required=True)
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL"))
    parser.add_argument("--replay", type=Path, help="Validate a saved model response; no API call")
    parser.add_argument("--output", type=Path, help="Write JSON to a file instead of stdout")
    args = parser.parse_args()
    if not args.replay and (not args.model or not os.getenv("OPENAI_API_KEY")):
        parser.error("Live planning requires OPENAI_API_KEY and --model (or OPENAI_MODEL)")
    try:
        results = SearchResults.model_validate_json(args.search_results.read_text())
        planner = ReplayPlanner(args.replay) if args.replay else OpenAIPlanner(args.model)
        request = build_request(args.prompt, results, planner)
        content = request.model_dump_json(indent=2) + "\n"
        if args.output:
            args.output.write_text(content)
        else:
            sys.stdout.write(content)
    except OpenAIError as exc:
        # Provider errors can include request details; keep CLI output minimal.
        print(f"Planning failed: {type(exc).__name__}; check API credentials/model/access.", file=sys.stderr)
        return 1
    except (OSError, ValidationError, PlanningError) as exc:
        print(f"Planning failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

