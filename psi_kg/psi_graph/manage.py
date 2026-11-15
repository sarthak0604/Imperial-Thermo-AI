"""Create or expand a graph using one or more source-validated investigation runs."""

import argparse
import copy
import hashlib
import json
import os
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


def configuration_signature(args, urls):
    """Bind resumable science to its model/source choices, never persist credentials."""
    from dotenv import dotenv_values

    env_path = (
        args.env_file or Path.home() / ".config/imperial-thermo-ai/.env"
    ).expanduser()
    settings = {**dotenv_values(env_path), **os.environ}
    provider = args.provider or settings.get("LLM_PROVIDER", "local")
    model = (
        args.model
        or settings.get("LLM_MODEL")
        or (settings.get("GEMINI_MODEL") if provider == "gemini" else None)
    )
    if provider == "local" and not model:
        from .local_model import DEFAULT_MODEL

        model = DEFAULT_MODEL
    configuration = dict(
        mode=args.mode,
        urls=urls,
        provider=provider,
        model=model,
        base_url=args.base_url or settings.get("LLM_BASE_URL"),
        keep_originals=args.keep_originals,
    )
    # Chunk sizes, output limits, disk limits and worker counts may change to
    # recover an unfinished run. Completed, validated studies need no regeneration.
    return digest(json.dumps(configuration, sort_keys=True))


def validated_run(source, url, expected_hashes=None):
    names = (
        "knowledge_graph.json",
        "validation_report.json",
        "resources_manifest.json",
        "documents.json",
    )
    hashes = {name: file_hash(source / name) for name in names}
    if expected_hashes is not None and hashes != expected_hashes:
        raise RuntimeError(
            "Completed study artifacts changed; refusing to reuse " + str(source)
        )
    incoming = read_json(source / "knowledge_graph.json")
    check(incoming)
    report = read_json(source / "validation_report.json")
    if report.get("structural_validation", {}).get("passed") is not True:
        raise RuntimeError(
            "Incoming study lacks a passing validation report: " + str(source)
        )
    accession = investigation_id(url)
    investigations = [n for n in incoming["nodes"] if n["type"] == "Investigation"]
    if len(investigations) != 1 or investigations[0]["id"] != "inv:" + accession:
        raise RuntimeError(
            "Incoming graph belongs to a different study: " + str(source)
        )
    if incoming["source_url"] != url or report.get("source_url") != url:
        raise RuntimeError(
            "Incoming graph/report source differs from the requested study"
        )
    return incoming, hashes


def run_receipt(args, target, state, result):
    completed = [entry for entry in state["studies"] if entry["status"] == "complete"]
    incoming_runs = [
        dict(
            investigation=entry["investigation"],
            source_url=entry["source_url"],
            run_directory=str(Path(entry["run_directory"]) / entry["investigation"]),
            incoming_validation_report=str(
                Path(entry["run_directory"])
                / entry["investigation"]
                / "validation_report.json"
            ),
            incoming_resources_manifest=str(
                Path(entry["run_directory"])
                / entry["investigation"]
                / "resources_manifest.json"
            ),
        )
        for entry in completed
    ]
    pending = [
        entry["investigation"]
        for entry in state["studies"]
        if entry["status"] != "complete"
    ]
    receipt = dict(
        mode=args.mode,
        target=str(target),
        session_id=state["session_id"],
        configuration_signature=state["configuration_signature"],
        incoming_runs=incoming_runs,
        generated_at=now(),
        complete=not pending,
        status="complete" if not pending else "partial",
        completed_studies=[entry["investigation"] for entry in completed],
        pending_studies=pending,
        nodes=len(result["nodes"]),
        edges=len(result["edges"]),
        node_counts=dict(Counter(n["type"] for n in result["nodes"])),
        structural_validation="passed",
        validation_scope="Combined graph structure checked; scientific review covers the incoming runs only. Existing claims retain their original review status. Pending studies are not represented as completed.",
        investigations=[
            {"id": n["id"], "source_url": n["properties"]["source_url"]}
            for n in result["nodes"]
            if n["type"] == "Investigation"
        ],
    )
    if len(incoming_runs) == 1:
        receipt.update(incoming_runs[0])
    return receipt


def run_managed(args, urls, extra, parser):
    target = args.graph.resolve()
    state_path = target.with_suffix(".run-state.json")
    signature = configuration_signature(args, urls)
    current_hash = file_hash(target) if target.exists() else None
    if args.resume:
        if args.refresh:
            parser.error(
                "--resume reuses saved work; start a new update run for --refresh"
            )
        if args.resume_from:
            parser.error(
                "Use --resume for an existing session, or --resume-from to start one from an older run"
            )
        if not state_path.is_file():
            parser.error(
                "No saved manager session; use --resume-from PATH for an older study run"
            )
        state = read_json(state_path)
        if state.get("configuration_signature") != signature or state.get(
            "target"
        ) != str(target):
            parser.error(
                "Resume requires the same target, study list/order, mode, provider and model"
            )
        if state.get("target_sha256") != current_hash:
            # Publication may finish just before interruption prevents its state
            # checkpoint. Only accept a receipt bound to this exact session/hash.
            receipt_path = target.with_suffix(".publication.json")
            receipt = read_json(receipt_path) if receipt_path.is_file() else {}
            pending = state.get("pending_publication", {})
            if pending.get("graph_sha256") == current_hash and current_hash is not None:
                receipt = pending["receipt"]
                receipt["graph_sha256"] = current_hash
                write_json(receipt_path, receipt)
            if (
                receipt.get("session_id") != state["session_id"]
                or receipt.get("graph_sha256") != current_hash
                or receipt.get("completed_studies")
                != [
                    s["investigation"]
                    for s in state["studies"]
                    if s["status"] == "complete"
                ]
            ):
                raise RuntimeError(
                    "Target changed since the saved session; refusing to overwrite it"
                )
            state["target_sha256"] = current_hash
            state.pop("pending_publication", None)
    else:
        if args.mode == "create" and target.exists():
            parser.error(
                "Create refuses to overwrite an existing graph; use --resume for this session or update"
            )
        if args.mode == "update" and not target.is_file():
            parser.error("Update requires an existing graph")
        from uuid import uuid4

        state = dict(
            version=1,
            session_id=uuid4().hex,
            target=str(target),
            configuration_signature=signature,
            target_sha256=current_hash,
            studies=[
                dict(
                    investigation=investigation_id(url),
                    source_url=url,
                    status="pending",
                    run_directory=None,
                )
                for url in urls
            ],
        )
        if args.resume_from:
            first = state["studies"][0]
            accession = first["investigation"]
            imported = args.resume_from.expanduser().resolve()
            source = imported if imported.name == accession else imported / accession
            if not (source / "metadata.json").is_file():
                parser.error(
                    "--resume-from must name an existing run directory with metadata for "
                    + accession
                )
            metadata = read_json(source / "metadata.json")
            if metadata.get("accession") != accession:
                parser.error(
                    "--resume-from metadata does not match the first requested study"
                )
            first["run_directory"] = str(source.parent)
            first["imported_run"] = True
    expected = target.read_bytes() if target.exists() else None
    if (
        hashlib.sha256(expected).hexdigest() if expected is not None else None
    ) != current_hash:
        raise RuntimeError("Target changed while opening the saved session")
    result = json.loads(expected) if expected is not None else None
    if result is not None:
        check(result)
    args.runs.mkdir(parents=True, exist_ok=True)
    write_json(state_path, state)
    receipt = None
    for index, entry in enumerate(state["studies"], 1):
        accession, url = entry["investigation"], entry["source_url"]
        print(f"Processing study {index}/{len(urls)}: {accession}", flush=True)
        if entry["run_directory"] is None:
            entry["run_directory"] = tempfile.mkdtemp(
                prefix=accession + "-", dir=args.runs.resolve()
            )
            write_json(state_path, state)
        run = Path(entry["run_directory"])
        source = run / accession
        if entry["status"] == "complete":
            incoming, _ = validated_run(source, url, entry["artifact_hashes"])
            # Completed runs have already been published, except for the narrow
            # interruption window between recording completion and publication.
            published = (
                read_json(target.with_suffix(".publication.json"))
                if target.with_suffix(".publication.json").is_file()
                else {}
            )
            if published.get("session_id") == state[
                "session_id"
            ] and accession in published.get("completed_studies", []):
                print(f"Reusing validated completed study: {accession}", flush=True)
                continue
        else:
            command = [
                sys.executable,
                "-m",
                "psi_graph.pipeline",
                url,
                "--output",
                str(run),
                *extra,
            ]
            preparation = source / "preparation_state.json"
            if (
                not args.refresh
                and preparation.is_file()
                and read_json(preparation).get("complete")
            ):
                command.extend(["--stage", "generate"])
            entry["status"] = "running"
            write_json(state_path, state)
            try:
                subprocess.run(command, check=True)
                incoming, hashes = validated_run(source, url)
            except BaseException as exc:
                entry["status"] = "failed"
                entry["failure_type"] = type(exc).__name__
                write_json(state_path, state)
                raise
            entry["status"] = "complete"
            entry["artifact_hashes"] = hashes
            entry.pop("failure_type", None)
            write_json(state_path, state)
        seed = result if result is not None else {**incoming, "nodes": [], "edges": []}
        result = merge(seed, incoming)
        receipt = run_receipt(args, target, state, result)
        encoded = (
            json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        ).encode()
        state["pending_publication"] = dict(
            graph_sha256=hashlib.sha256(encoded).hexdigest(), receipt=receipt
        )
        write_json(state_path, state)
        publish(target, result, expected, receipt)
        expected = target.read_bytes()
        state["target_sha256"] = file_hash(target)
        state.pop("pending_publication", None)
        write_json(state_path, state)
        for incoming_run in receipt["incoming_runs"]:
            write_json(
                Path(incoming_run["run_directory"]) / "publication_receipt.json",
                receipt,
            )
        print(
            f"Published {target}: {len(receipt['completed_studies'])}/{len(urls)} studies complete",
            flush=True,
        )
    if receipt is None:
        receipt = read_json(target.with_suffix(".publication.json"))
    print(json.dumps(receipt, indent=2))
    return 0


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
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume this graph's saved session and skip validated completed studies",
    )
    parser.add_argument(
        "--resume-from",
        type=Path,
        help="Reuse an older run directory for the first requested study",
    )
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
    target.parent.mkdir(parents=True, exist_ok=True)
    lock = target.with_suffix(target.suffix + ".run-lock")
    try:
        lock.mkdir()
    except FileExistsError:
        raise RuntimeError(
            "A manager session is already running or was interrupted without cleanup. "
            "Confirm it has stopped before removing " + str(lock)
        ) from None
    try:
        return run_managed(args, urls, extra, parser)
    finally:
        lock.rmdir()


if __name__ == "__main__":
    raise SystemExit(main())
