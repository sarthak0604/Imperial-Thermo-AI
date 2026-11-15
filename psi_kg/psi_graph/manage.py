"""Create or expand a graph using one or more source-validated investigation runs."""

import argparse
import copy
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from .budget import positive_gb
from .common import digest, file_hash, now, read_json, write_json
from .graph import DIRECTIONS, SCHEMA
from .nasa_access import investigation_id
from .studies import select_studies


def check(graph):
    Draft202012Validator(SCHEMA, format_checker=FormatChecker()).validate(graph)
    nodes = {n["id"]: n for n in graph["nodes"]}
    if len(nodes) != len(graph["nodes"]):
        raise ValueError("Duplicate node IDs")
    if len({e["id"] for e in graph["edges"]}) != len(graph["edges"]):
        raise ValueError("Duplicate edge IDs")
    for e in graph["edges"]:
        if e["source"] not in nodes or e["target"] not in nodes:
            raise ValueError("Dangling edge")
        if (nodes[e["source"]]["type"], nodes[e["target"]]["type"]) != DIRECTIONS[
            e["type"]
        ]:
            raise ValueError("Invalid relationship direction")


def merge(existing, incoming):
    check(existing)
    check(incoming)
    result = copy.deepcopy(existing)
    invs = [n["id"] for n in incoming["nodes"] if n["type"] == "Investigation"]
    if len(invs) != 1:
        raise ValueError("Incoming run must contain exactly one investigation")
    inv = invs[0]
    accession = inv.split(":", 1)[1]
    removed = {inv} | {
        n["id"]
        for n in result["nodes"]
        if n["id"].startswith((f"exp:{accession}:", f"res:{accession}:"))
    }
    old_targets = {e["target"] for e in result["edges"] if e["source"] in removed}
    result["edges"] = [
        e
        for e in result["edges"]
        if e["source"] not in removed and e["target"] not in removed
    ]
    still_used = {e[k] for e in result["edges"] for k in ("source", "target")}
    removed |= old_targets - still_used
    result["nodes"] = [n for n in result["nodes"] if n["id"] not in removed]
    nodes = {n["id"]: n for n in result["nodes"]}
    mapping = {}
    for original in incoming["nodes"]:
        node = copy.deepcopy(original)
        # Preserve different source interpretations instead of overwriting shared labels.
        if node["type"] in ("Concept", "Variable"):
            node["id"] = (
                node["type"].lower() + ":" + accession + ":" + digest(original["id"])
            )
        mapping[original["id"]] = node["id"]
        if node["id"] in nodes and nodes[node["id"]] != node:
            raise ValueError("Conflicting node identity: " + node["id"])
        nodes[node["id"]] = node
    for original in incoming["edges"]:
        edge = copy.deepcopy(original)
        edge["source"], edge["target"] = (
            mapping[edge["source"]],
            mapping[edge["target"]],
        )
        edge["id"] = "edge:" + digest(
            edge["source"] + "|" + edge["type"] + "|" + edge["target"]
        )
        result["edges"].append(edge)
    result["nodes"] = sorted(nodes.values(), key=lambda n: n["id"])
    result["edges"] = sorted(result["edges"], key=lambda e: e["id"])
    result["generated_at"] = now()
    # Preserve the collection identity and seed source; each Investigation has its own URL.
    check(result)
    return result


def publish(path, graph, expected, receipt=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_suffix(path.suffix + ".publish-lock")
    try:
        lock.mkdir()
    except FileExistsError:
        raise RuntimeError(
            "Graph publication is locked; confirm any previous writer has stopped before removing "
            + str(lock)
        ) from None
    try:
        current = path.read_bytes() if path.exists() else None
        if current != expected:
            raise RuntimeError(
                "Target changed during processing; refusing to overwrite it"
            )
        if current is not None:
            backup = (
                path.parent
                / "backups"
                / (path.stem + "-" + digest(current.decode()) + ".json")
            )
            backup.parent.mkdir(parents=True, exist_ok=True)
            if not backup.exists():
                backup.write_bytes(current)
        write_json(path, graph)
        if receipt is not None:
            receipt["graph_sha256"] = file_hash(path)
            write_json(path.with_suffix(".publication.json"), receipt)

    finally:
        lock.rmdir()


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("url", nargs="*", help="Study names, PSI IDs or URLs")
    parser.add_argument(
        "--study",
        action="append",
        default=[],
        help="Study name, PSI ID or URL; repeat for multiple studies",
    )
    parser.add_argument("--mode", choices=["create", "update"])
    parser.add_argument("--graph", type=Path, help="Graph to create or update")
    parser.add_argument("--runs", type=Path, default=Path("runs"))
    parser.add_argument("--env-file", type=Path)
    parser.add_argument(
        "--provider",
        choices=["local", "gemini", "openai", "anthropic", "openai-compatible"],
    )
    parser.add_argument("--model")
    parser.add_argument("--base-url")
    parser.add_argument("--api-key-env")
    parser.add_argument("--workers", type=int)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--keep-originals", action="store_true")
    parser.add_argument(
        "--max-temp-gb",
        type=positive_gb,
        help="Original-file cap in GB (pipeline default: 50)",
    )
    parser.add_argument(
        "--min-free-gb",
        type=positive_gb,
        help="Free-space reserve in GB (pipeline default: 5)",
    )
    args = parser.parse_args()
    extra = []
    for option in (
        "env_file",
        "provider",
        "model",
        "base_url",
        "api_key_env",
        "workers",
        "max_temp_gb",
        "min_free_gb",
    ):
        value = getattr(args, option)
        if value is not None:
            extra.extend(["--" + option.replace("_", "-"), str(value)])
    if args.keep_originals:
        extra.append("--keep-originals")
    if args.refresh:
        extra.append("--refresh")
    if not args.mode:
        answer = input(
            "1: Update current graph\n2: Create new graph\nChoose 1 or 2: "
        ).strip()
        if answer not in ("1", "2"):
            parser.error("Choose 1 or 2")
        args.mode = "update" if answer == "1" else "create"
    try:
        urls = select_studies(args.url + args.study)
    except (ValueError, RuntimeError) as error:
        parser.error(str(error))
    accession = investigation_id(urls[0])
    if not args.graph:
        default = (
            "output/PSI-117/knowledge_graph.json"
            if args.mode == "update"
            else "graphs/" + (accession if len(urls) == 1 else "combined") + ".json"
        )
        args.graph = Path(input(f"Graph path [{default}]: ").strip() or default)
    target = args.graph.resolve()
    if args.mode == "create" and target.exists():
        parser.error(
            "Create refuses to overwrite an existing graph; choose another path or update"
        )
    if args.mode == "update" and not target.is_file():
        parser.error("Update requires an existing graph")
    expected = target.read_bytes() if target.exists() else None
    existing = json.loads(expected) if expected is not None else None
    if existing is not None:
        check(existing)
    args.runs.mkdir(parents=True, exist_ok=True)
    result = existing
    incoming_runs = []
    for index, url in enumerate(urls, 1):
        accession = investigation_id(url)
        print(f"Processing study {index}/{len(urls)}: {accession}", flush=True)
        run = Path(tempfile.mkdtemp(prefix=accession + "-", dir=args.runs.resolve()))
        command = [
            sys.executable,
            "-m",
            "psi_graph.pipeline",
            url,
            "--output",
            str(run),
            *extra,
        ]
        subprocess.run(command, check=True)
        source = run / accession
        incoming = read_json(source / "knowledge_graph.json")
        # Normalize concept/variable identities on create as well as updates.
        seed = result if result is not None else {**incoming, "nodes": [], "edges": []}
        result = merge(seed, incoming)
        incoming_runs.append(
            dict(
                investigation=accession,
                source_url=url,
                run_directory=str(source),
                incoming_validation_report=str(source / "validation_report.json"),
                incoming_resources_manifest=str(source / "resources_manifest.json"),
            )
        )
    check(result)
    receipt = dict(
        mode=args.mode,
        target=str(target),
        incoming_runs=incoming_runs,
        generated_at=now(),
        nodes=len(result["nodes"]),
        edges=len(result["edges"]),
        node_counts=dict(Counter(n["type"] for n in result["nodes"])),
        structural_validation="passed",
        validation_scope="Combined graph structure checked; scientific review covers the incoming runs only. Existing claims retain their original review status.",
        investigations=[
            {"id": n["id"], "source_url": n["properties"]["source_url"]}
            for n in result["nodes"]
            if n["type"] == "Investigation"
        ],
    )
    if len(incoming_runs) == 1:
        receipt.update(incoming_runs[0])  # Preserve single-study receipt fields.
    # Publish only after all studies succeed; failure leaves the target unchanged.
    publish(target, result, expected, receipt)
    for incoming_run in incoming_runs:
        write_json(
            Path(incoming_run["run_directory"]) / "publication_receipt.json", receipt
        )
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
