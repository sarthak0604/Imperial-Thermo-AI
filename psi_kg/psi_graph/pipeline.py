"""CLI: discover -> download -> parse -> extract -> synthesize -> audit -> export."""

import argparse
import json
import os
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

from .common import now, read_json, write_json
from .coverage import audit
from .discovery import (
    discover,
    discover_document_links,
    discover_open_versions,
    download_all,
)
from .graph import SCHEMA, apply_review, build, scientific_review, validate
from .nasa_access import investigation_id
from .parsing import parse_resources
from .providers import LLM
from .science import extract_all, synthesize
from .storage import source_storage


def report(output, graph, resources, validation, rejected, verdicts, failures, usage):
    counts = Counter(r["extraction_status"] for r in resources)
    accesses = Counter(r["access_status"] for r in resources)
    report = dict(
        generated_at=now(),
        source_url=graph["source_url"],
        structural_validation=validation,
        resource_count=len(resources),
        extraction_status_counts=dict(counts),
        access_status_counts=dict(accesses),
        processing_failures=[
            {
                k: r.get(k)
                for k in (
                    "id",
                    "title",
                    "source_url",
                    "error",
                    "extraction_error",
                    "access_status",
                    "extraction_status",
                    "extraction_warnings",
                )
            }
            for r in resources
            if r["extraction_status"] in ("failed", "inaccessible", "unsupported")
        ],
        extraction_issues=failures,
        rejected_during_graph_construction=rejected,
        scientific_review=dict(
            method="LLM independent entailment review plus deterministic verbatim source checks; not expert peer review",
            reviewed=len(verdicts),
            rejected=sum(not v["supported"] for v in verdicts),
        ),
        llm_calls=len(usage),
        limitations=[
            "PDF figures and visual-only equations were not digitized.",
            "MEASURES includes documented computed observables; node summaries distinguish simulations from physical experiments.",
            "Citation-only and inaccessible publications are not represented as full-text parsed.",
            "Retrieval is lexical concept/synonym matching plus graph traversal, not global GraphRAG.",
        ],
    )
    if any(r.get("original_retention") == "discarded" for r in resources):
        report["limitations"].append(
            "Original files were processed temporarily and removed. Evidence validation uses retained extracted text; source URLs and SHA-256 hashes remain available."
        )
    write_json(output / "validation_report.json", report)
    text = [
        "# Validation report",
        "",
        f"Source: {graph['source_url']}",
        f"Generated: {report['generated_at']}",
        "",
        f"Structural validation: {'PASS' if validation['passed'] else 'FAIL'}",
        f"Nodes: {validation['nodes']}; edges: {validation['edges']}",
        f"Node types: {json.dumps(validation['node_counts'])}",
        f"Edge types: {json.dumps(validation['edge_counts'])}",
        f"Resources: {len(resources)}; access: {json.dumps(dict(accesses))}",
        f"Parsing: {json.dumps(dict(counts))}",
        "",
        "## Scientific checks",
        "",
        f"{len(verdicts)} node/relationship claims reviewed; {sum(not v['supported'] for v in verdicts)} rejected.",
        "Rejected scientific nodes/edges are excluded; rejected resource summaries are cleared. Exact evidence is checked against saved page/sheet/row text. This is automated source validation, not scientific peer review.",
        "",
        "## Limitations",
        "",
        *["- " + s for s in report["limitations"]],
        "",
        "## Failures",
        "",
    ]
    for r in report["processing_failures"]:
        text.append(
            f"- {r['title']}: {r.get('error') or r.get('extraction_error') or '; '.join(r.get('extraction_warnings') or []) or r.get('extraction_status')}"
        )
    if not report["processing_failures"]:
        text.append("None.")
    for error in validation["errors"]:
        text.append("- Validation error: " + error)
    (output / "validation_report.md").write_text("\n".join(text) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "url", help="NASA PSI investigation URL; no investigation ID is hardcoded"
    )
    parser.add_argument("--output", type=Path, default=Path("output"))
    parser.add_argument(
        "--env-file", type=Path, default=Path.home() / ".config/imperial-thermo-ai/.env"
    )
    parser.add_argument(
        "--provider",
        choices=["gemini", "openai", "anthropic", "openai-compatible"],
        default=None,
    )
    parser.add_argument(
        "--model", help="Model available to your provider/account (or LLM_MODEL)"
    )
    parser.add_argument(
        "--base-url", help="Compatible endpoint base URL, including /v1"
    )
    parser.add_argument(
        "--api-key-env",
        help="Override the provider credential environment variable name",
    )
    parser.add_argument(
        "--stage", choices=["prepare", "all", "generate", "validate"], default="all"
    )
    parser.add_argument(
        "--reviewed-bundle",
        type=Path,
        help="Explicit pre-reviewed source extraction; no API call, snapshot and claim hashes are checked",
    )
    parser.add_argument(
        "--refresh", action="store_true", help="Refresh NASA metadata/file list"
    )
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--keep-originals",
        action="store_true",
        help="Keep original downloaded files; default uses temporary files and preserves extracted text only",
    )
    args = parser.parse_args()
    load_dotenv(args.env_file, override=False)
    args.provider = args.provider or os.environ.get("LLM_PROVIDER", "gemini")
    model = args.model or os.environ.get("LLM_MODEL") or os.environ.get("GEMINI_MODEL")
    output = args.output.resolve() / investigation_id(args.url)
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "graph_schema.json", SCHEMA)
    client = None
    if args.stage in ("all", "generate") and not args.reviewed_bundle:
        client = LLM(output, args.provider, model, args.base_url, args.api_key_env)
    if args.stage in ("all", "prepare"):
        metadata, resources = discover(args.url, output, args.refresh)
        resources = discover_open_versions(resources, metadata, output)
        with source_storage(
            output, resources, args.url, args.keep_originals
        ) as raw_output:
            download_all(
                resources, metadata, output, args.workers, storage_output=raw_output
            )
            documents = parse_resources(
                resources, metadata, args.url, output, storage_output=raw_output
            )
            while added := discover_document_links(documents, resources, metadata):
                resources.extend(added)
                download_all(
                    resources, metadata, output, args.workers, storage_output=raw_output
                )
                documents = parse_resources(
                    resources, metadata, args.url, output, storage_output=raw_output
                )
        write_json(
            output / "resources_manifest.json",
            dict(source_url=args.url, generated_at=now(), resources=resources),
        )
        write_json(
            output / "coverage_report.json",
            audit(read_json(output / "files.json"), resources),
        )
        if args.stage == "prepare":
            print(
                f"Prepared {len(resources)} resources and {len(documents)} source documents in {output}"
            )
            return 0
    else:
        metadata = read_json(output / "metadata.json")
        resources = read_json(output / "resources_manifest.json")["resources"]
        documents = read_json(output / "documents.json")
    if args.stage == "validate":
        result = validate(
            read_json(output / "knowledge_graph.json"), documents, resources
        )
        print(json.dumps(result, indent=2))
        return 0 if result["passed"] else 1
    if args.reviewed_bundle:
        from .reviewed import export_reviewed

        graph, validation, caveats = export_reviewed(
            args.reviewed_bundle, resources, metadata, args.url, documents, output
        )
        verdicts = read_json(output / "scientific_review.json")
        report(output, graph, resources, validation, [], verdicts, [], [])
        data = read_json(output / "validation_report.json")
        data["extraction_mode"] = "assistant_source_review"
        data["external_llm_api_calls"] = 0
        data["api_extraction_status"] = "pending_credentials"
        data["scientific_review"]["method"] = (
            "Assistant authored and reviewed extraction with verbatim source checks and snapshot-bound claim approvals; not external API or expert peer review"
        )
        data["limitations"].extend(caveats)
        write_json(output / "validation_report.json", data)
        markdown = output / "validation_report.md"
        text = markdown.read_text().replace(
            "This is automated source validation, not scientific peer review.",
            "This run used assistant source review and deterministic validation, not an external LLM API or scientific peer review.",
        )
        text += (
            "\n## Execution mode\n\nAssistant source review; external LLM API calls: **0**. API extraction remains **pending credentials**.\n\n"
            + "\n".join("- " + c for c in caveats)
            + "\n"
        )
        markdown.write_text(text)
        print(json.dumps(validation, indent=2))
        return 0
    extractions, failures = extract_all(client, documents, resources, output)
    synthesis = synthesize(client, extractions, resources, metadata, output)
    graph, provenance, rejected = build(
        synthesis, resources, metadata, args.url, documents
    )
    write_json(output / "candidate_graph.json", graph)
    write_json(output / "node_provenance.json", provenance)
    verdicts = scientific_review(client, graph, provenance, documents, output)
    graph = apply_review(graph, verdicts)
    validation = validate(graph, documents, resources)
    write_json(output / "llm_usage.json", client.usage)
    report(
        output, graph, resources, validation, rejected, verdicts, failures, client.usage
    )
    if not validation["passed"]:
        write_json(output / "failed_graph.json", graph)
        raise RuntimeError(
            "Structural/source validation failed; see validation_report.json. Final graph not published."
        )
    if not validation["node_counts"].get("Experiment"):
        raise RuntimeError(
            "No source-validated experiments survived scientific review; final graph not published."
        )
    write_json(output / "knowledge_graph.json", graph)
    print(json.dumps(validation, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
