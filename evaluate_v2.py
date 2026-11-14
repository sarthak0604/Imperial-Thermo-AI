"""Evaluate the version 2 parser against reviewed semantic expectations.

SI assistance: OpenAI Codex. Test prompts/labels are synthetic software fixtures,
not NASA measurements. This evaluates a finite development set, not all inputs.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from typing import Any


def expressions(expression: dict, negated: bool = False):
    """Walk a plan without losing which filters occur inside a negation."""
    if not isinstance(expression, dict):
        return
    yield expression, negated
    kind = expression.get("kind")
    if kind in ("all", "any"):
        for item in expression.get("items", []):
            yield from expressions(item, negated)
    elif kind == "not":
        yield from expressions(expression.get("item", {}), not negated)
    elif kind == "relation":
        yield from expressions(expression.get("where", {}), negated)


def equal(actual: Any, expected: Any) -> bool:
    if isinstance(actual, str) and isinstance(expected, str):
        return actual.casefold().strip() == expected.casefold().strip()
    if isinstance(actual, bool) != isinstance(expected, bool):
        return False
    return actual == expected


def matches(actual: dict, expected: dict) -> bool:
    """Compare only the listed fields, allowing explicitly reviewed aliases."""
    for key, value in expected.items():
        if key == "positive_only":
            continue
        if key == "value_any_of":
            if not any(equal(actual.get("value"), allowed) for allowed in value):
                return False
        elif key not in actual or not equal(actual[key], value):
            return False
    return True


def check_plan(plan: dict, expected: dict) -> list[str]:
    """Return semantic failures; an empty list means the assertions passed."""
    failures: list[str] = []
    queries = plan.get("queries", [])
    walked = [item for query in queries for item in expressions(query.get("where", {}))]
    filters = [(node, negated) for node, negated in walked if node.get("kind") == "filter"]
    if "intent" in expected and plan.get("intent") != expected["intent"]:
        failures.append(f"intent: expected {expected['intent']!r}, got {plan.get('intent')!r}")
    if "return_types" in expected:
        actual = sorted({query.get("return_type") for query in queries})
        wanted = sorted(set(expected["return_types"]))
        if actual != wanted:
            failures.append(f"return_types: expected {wanted!r}, got {actual!r}")
    for condition in expected.get("filters", []):
        if not any(matches(node, condition) for node, _ in filters):
            failures.append(f"missing filter: {condition!r}")
    for condition in expected.get("forbidden_filters", []):
        if any(matches(node, condition) for node, negated in filters
               if not condition.get("positive_only", True) or not negated):
            failures.append(f"invented or forbidden positive filter: {condition!r}")
    for edge in expected.get("edges", []):
        if not any(node.get("kind") == "relation" and node.get("edge") == edge for node, _ in walked):
            failures.append(f"missing relation: {edge}")
    for kind in expected.get("expression_kinds", []):
        if not any(node.get("kind") == kind for node, _ in walked):
            failures.append(f"missing expression kind: {kind}")
    if "alternative_values" in expected:
        alternative = expected["alternative_values"]
        field, wanted = alternative["field"], alternative["values"]
        found = False
        for node, negated in walked:
            if negated:
                continue
            if node.get("kind") == "filter" and node.get("field") == field and node.get("operator") == "in":
                found |= all(any(equal(value, item) for item in node.get("value", [])) for value in wanted)
            elif node.get("kind") == "any":
                alternatives = [leaf for leaf, neg in expressions(node) if not neg and leaf.get("kind") == "filter"
                                and leaf.get("field") == field and leaf.get("operator") == "eq"]
                found |= all(any(equal(value, leaf.get("value")) for leaf in alternatives) for value in wanted)
        if not found:
            failures.append(f"missing OR alternatives: {alternative!r}")
    for requested in expected.get("requested_fields", []):
        if not any(matches(item, requested) for item in plan.get("requested_fields", [])):
            failures.append(f"missing requested output: {requested!r}")
    if "min_queries" in expected and len(queries) < expected["min_queries"]:
        failures.append(f"expected at least {expected['min_queries']} query groups, got {len(queries)}")
    if "max_queries" in expected and len(queries) > expected["max_queries"]:
        failures.append(f"expected at most {expected['max_queries']} queries, got {len(queries)}")
    if expected.get("clarification_required") and not plan.get("clarifications"):
        failures.append("expected a clarification question")
    searchable = json.dumps({key: value for key, value in plan.items()
                             if key not in ("original_question", "language")}, ensure_ascii=False).casefold()
    for term in expected.get("required_terms", []):
        if term.casefold() not in searchable:
            failures.append(f"lost requested detail: {term}")
    return failures


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--cases", type=Path, default=Path(__file__).parent / "examples/parser_cases.json")
    cli.add_argument("--output", type=Path, default=Path("parser_v2_evaluation.json"))
    cli.add_argument("--graph", type=Path)
    cli.add_argument("--limit", type=int)
    cli.add_argument("--ids", nargs="+", help="Case IDs, separated by spaces or commas.")
    cli.add_argument("--category", nargs="+", help="Category names, separated by spaces or commas.")
    args = cli.parse_args()
    from imperial_thermo_ai.parser import QuestionParser

    data = json.loads(args.cases.read_text(encoding="utf-8"))
    cases = data["cases"]
    for attribute, key in (("ids", "id"), ("category", "category")):
        selected = getattr(args, attribute)
        if selected:
            allowed = {part for item in selected for part in item.split(",")}
            cases = [case for case in cases if case[key] in allowed]
    if args.limit is not None:
        if args.limit < 1:
            cli.error("--limit must be positive")
        cases = cases[:args.limit]
    if not cases:
        cli.error("No test cases matched the selection")
    graph = json.loads(args.graph.read_text(encoding="utf-8")) if args.graph else None
    parser = QuestionParser()
    report: dict[str, Any] = {
        "schema_version": "2.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "provenance": "SI-generated software evaluation against synthetic prompts and labels.",
            "scope": "Finite development-set assertions; not a guarantee of complete semantic correctness.",
            "cases_file": str(args.cases),
            "graph_file": str(args.graph) if args.graph else None,
        },
        "passed": 0, "total": len(cases), "by_category": {}, "results": [],
    }
    categories = defaultdict(lambda: {"passed": 0, "total": 0})
    for case in cases:
        started = time.monotonic()
        actual = None
        try:
            actual = parser.parse(case["question"], graph=graph)
            failures = check_plan(actual, case["expected"])
        except Exception as error:  # Preserve individual failures and continue the suite.
            failures = [f"{type(error).__name__}: {error}"]
        passed = not failures
        report["passed"] += int(passed)
        categories[case["category"]]["total"] += 1
        categories[case["category"]]["passed"] += int(passed)
        report["results"].append({
            "id": case["id"], "category": case["category"], "question": case["question"],
            "expected": case["expected"], "passed": passed, "failures": failures,
            "actual": actual, "seconds": round(time.monotonic() - started, 3),
        })
        report["by_category"] = dict(categories)
        # Write after every case, so long local-model runs leave a reviewable report.
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{'PASS' if passed else 'FAIL'} {case['id']}: " + ("; ".join(failures) if failures else case["question"]), flush=True)
    print(f"{report['passed']}/{report['total']} passed. Report: {args.output}")
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
