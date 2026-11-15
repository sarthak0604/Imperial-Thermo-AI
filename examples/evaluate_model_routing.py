"""Compare provider routing on labelled JSONL prompts; no scientific execution."""

import argparse
import json
import os
import time
from pathlib import Path

from openai import OpenAIError

from request_planner.providers import configure
from request_planner.task_router import route


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--cases", required=True, type=Path)
    cli.add_argument("--output", required=True, type=Path)
    cli.add_argument(
        "--provider",
        choices=["retrieval", "local", "api", "open_source"],
        default="retrieval",
    )
    args = cli.parse_args()
    generate = configure({**os.environ, "THERMO_PLANNER": args.provider}).get(
        "program_generator"
    )
    rows = []
    for line in args.cases.read_text().splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        started = time.monotonic()
        try:
            result = route(case["question"], generate)
            ok = (
                set(result.model_ids) == set(case["model_ids"])
                and result.intent == case["intent"]
            )
            rows.append(
                {
                    "id": case["id"],
                    "correct": ok,
                    "route": result.model_dump(),
                    "seconds": time.monotonic() - started,
                }
            )
        except (ValueError, OSError, RuntimeError, OpenAIError) as exc:
            rows.append(
                {
                    "id": case["id"],
                    "correct": False,
                    "error_type": type(exc).__name__,
                    "seconds": time.monotonic() - started,
                }
            )
    args.output.write_text(
        json.dumps(
            {
                "provider": args.provider,
                "model": os.getenv("PSI_PARSER_MODEL", os.getenv("OPENAI_MODEL")),
                "cases": len(rows),
                "correct": sum(r["correct"] for r in rows),
                "results": rows,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
