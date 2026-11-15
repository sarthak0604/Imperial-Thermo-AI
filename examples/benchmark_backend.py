"""Reproducible metadata-discovery benchmark; not a scientific answer evaluation."""

import json
import subprocess
import time
import types
from pathlib import Path

from imperial_thermo_ai.reviewed_graph import load_graph
from request_planner.backend import retrieve
from request_planner.intent import interpret


def main():
    current = load_graph()
    baseline = types.ModuleType("imperial_thermo_ai._baseline_reviewed")
    baseline.__file__ = str(Path("src/imperial_thermo_ai/reviewed_graph.py").resolve())
    source = subprocess.check_output(
        ["git", "show", "1ae7c06:src/imperial_thermo_ai/reviewed_graph.py"], text=True
    )
    exec(compile(source, baseline.__file__, "exec"), baseline.__dict__)  # noqa: S102 -- fixed trusted repository revision
    old = baseline.load_graph()
    cases = []
    for study, node in current.investigations.items():
        tables = [
            n
            for n in current.graph.nodes.values()
            if n["type"] == "Resource"
            and n["properties"].get("access_status") == "structured_table_reviewed"
            and current.owners.get(n["id"], ("",))[0] == node
        ]
        if not tables:
            continue
        table = tables[0]
        alias = next((a for a, s in current.aliases.items() if s == study), study)
        for question in [
            f"Find {study} experimental table",
            f"Show {study} measurement CSV",
            f"Find {alias} experimental table",
            f"{study} {table['properties']['filename']}",
            f"Find experimental CSV table for {alias}",
            f"Locate {study} table measurements",
        ]:
            cases.append(
                {
                    "prompt": question,
                    "expected_file_id": table["id"],
                    "category": "metadata_table_discovery",
                }
            )
    # Separate adversarial no-relevance/exclusion cases, with known expected empty sets.
    for question in [
        "PSI-25 quantum banana zebra",
        "PSI-69 quantum banana zebra",
        "PSI-39 quantum banana zebra",
        "Find BASS-II videos excluding PSI-25",
        "Find FLEX video excluding PSI-69",
        "Find PSI-99999 data",
    ]:
        cases.append(
            {
                "prompt": question,
                "expected_file_id": None,
                "category": "negative_discovery",
            }
        )
    rows = []
    for case in cases:
        question = case["prompt"]
        begin = time.monotonic()
        before = old.search(question).files
        old_time = time.monotonic() - begin
        begin = time.monotonic()
        spec = interpret(question, aliases=current.aliases)
        after = retrieve(spec, current).files
        new_time = time.monotonic() - begin
        gold = case["expected_file_id"]
        check = lambda files, gold=gold: (
            bool(files) and files[0].file_id == gold if gold else not files
        )
        rows.append(
            {
                **case,
                "baseline_top1_correct": check(before),
                "current_top1_correct": check(after),
                "baseline_seconds": round(old_time, 4),
                "current_seconds": round(new_time, 4),
                "baseline_ids": [f.file_id for f in before],
                "current_ids": [f.file_id for f in after],
            }
        )
    report = {
        "graph_id": current.graph.graph["graph_id"],
        "baseline_commit": "1ae7c06",
        "scope": "Automatically labelled metadata discovery, not human-adjudicated scientific answer or LLM evaluation.",
        "case_count": len(rows),
        "baseline_top1_correct": sum(r["baseline_top1_correct"] for r in rows),
        "current_top1_correct": sum(r["current_top1_correct"] for r in rows),
        "cases": rows,
    }
    Path("docs/backend-retrieval-benchmark.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print({k: v for k, v in report.items() if k != "cases"})


if __name__ == "__main__":
    main()
