#!/usr/bin/env python3
"""Query an exported graph without Gemini or network access."""

import argparse
import json
from pathlib import Path

from psi_graph.common import read_json, write_json
from psi_graph.retrieval import run_cases, search


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?", help="Scientific question or concept")
    parser.add_argument(
        "--graph", type=Path, default=Path("output/PSI-117/knowledge_graph.json")
    )
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument(
        "--cases", type=Path, help="Run retrieval cases and a negative control"
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    graph = read_json(args.graph)
    if args.cases:
        result = run_cases(graph, read_json(args.cases))
    elif args.query:
        result = search(graph, args.query, args.limit)
    else:
        parser.error("Supply a query or --cases")
    if args.output:
        write_json(args.output, result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if args.cases and not all(r["passed"] for r in result) else 0


if __name__ == "__main__":
    raise SystemExit(main())
