"""Small local PSI graph and lexical search. SI-assisted code; see README.md."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Annotated, Literal

from pydantic import Field, HttpUrl, ValidationError, model_validator

from .models import Contract, FileRecord, SearchResults


class InvestigationNode(Contract):
    kind: Literal["investigation"]
    id: str
    title: str
    acronym: str
    version: int
    doi: str
    license: str
    source_page_url: HttpUrl
    metadata_url: HttpUrl
    metadata_sha256: str
    keywords: list[str]


class TopicNode(Contract):
    kind: Literal["topic"]
    id: str
    title: str
    keywords: list[str]


class FileVerification(Contract):
    checked_at: str
    http_status: Literal[200]
    bytes: int
    sha256: str
    reported_media_type: str


class FileNode(Contract):
    kind: Literal["file"]
    id: str
    record: FileRecord
    file_version: int
    keywords: list[str]
    verification: FileVerification


Node = Annotated[InvestigationNode | TopicNode | FileNode, Field(discriminator="kind")]


class Edge(Contract):
    source: str
    relation: Literal["has_file", "studies_topic"]
    target: str


class MiniGraph(Contract):
    schema_version: Literal["1.0"]
    generated_by: str
    provenance_notes: list[str]
    nodes: list[Node]
    edges: list[Edge]

    @model_validator(mode="after")
    def validate_edges(self):
        nodes = {node.id: node for node in self.nodes}
        if len(nodes) != len(self.nodes):
            raise ValueError("Graph node IDs must be unique")
        triples = {(edge.source, edge.relation, edge.target) for edge in self.edges}
        if len(triples) != len(self.edges):
            raise ValueError("Graph edges must be unique")
        owners: dict[str, list[str]] = {}
        for edge in self.edges:
            source, target = nodes.get(edge.source), nodes.get(edge.target)
            if not isinstance(source, InvestigationNode):
                raise ValueError("Every edge must start at an existing investigation")
            if edge.relation == "has_file":
                if not isinstance(target, FileNode):
                    raise ValueError("has_file must target an existing file")
                owners.setdefault(target.id, []).append(source.id)
            elif not isinstance(target, TopicNode):
                raise ValueError("studies_topic must target an existing topic")
        for node in self.nodes:
            if isinstance(node, FileNode):
                if node.id != node.record.file_id:
                    raise ValueError("File node ID must match its record's file_id")
                if owners.get(node.id) != [node.record.investigation_id]:
                    raise ValueError("Each file must have exactly one matching investigation owner")
                if node.record.size_bytes != node.verification.bytes:
                    raise ValueError("File size must match verified byte count")
        return self


STOP_WORDS = {"a", "an", "and", "are", "can", "find", "for", "from", "give", "i", "in",
              "is", "me", "of", "on", "please", "show", "some", "the", "to", "with"}


def tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower())) - STOP_WORDS


def search_graph(
    graph: MiniGraph,
    query: str,
    *,
    investigation_id: str | None = None,
    role: str | None = None,
    limit: int = 6,
) -> SearchResults:
    """Rank file nodes by lexical matches along investigation/topic relationships."""
    if not query.strip():
        raise ValueError("Search query must not be empty")
    if limit < 1:
        raise ValueError("Search limit must be positive")
    nodes = {node.id: node for node in graph.nodes}
    if investigation_id and not isinstance(nodes.get(investigation_id), InvestigationNode):
        raise ValueError(f"Unknown investigation: {investigation_id}")
    terms = tokens(query)
    hits = []
    for edge in graph.edges:
        if edge.relation != "has_file":
            continue
        investigation = nodes[edge.source]
        file = nodes[edge.target]
        if investigation_id and investigation.id != investigation_id:
            continue
        if role and file.record.role != role:
            continue
        topics = [nodes[item.target] for item in graph.edges
                  if item.source == investigation.id and item.relation == "studies_topic"]
        direct = tokens(" ".join([file.record.title, file.record.role, *file.keywords]))
        inherited = tokens(" ".join([
            investigation.id, investigation.title, investigation.acronym,
            *investigation.keywords,
            *(word for topic in topics for word in [topic.title, *topic.keywords]),
        ]))
        matched = terms & (direct | inherited)
        if not matched:
            continue
        score = 3 * len(terms & direct) + len(terms & inherited)
        related_ids = [item.target for item in graph.edges
                       if item.source == investigation.id and item.relation == "has_file"
                       and item.target != file.id]
        record = file.record.model_copy(update={
            "source_page_url": file.record.source_page_url or investigation.source_page_url,
            "related_file_ids": related_ids,
            "match_reason": (
                f"Matched terms: {', '.join(sorted(matched))}. "
                f"Graph path: {investigation.id} --has_file--> {file.id}. "
                "Other related files share the investigation, not necessarily a run."
            ),
        })
        hits.append((score, file.id, record))
    hits.sort(key=lambda item: (-item[0], item[1]))
    fingerprint = json.dumps([query, investigation_id, role, limit], ensure_ascii=True)
    return SearchResults(
        query_id="psi-mini-" + hashlib.sha256(fingerprint.encode()).hexdigest()[:12],
        files=[item[2] for item in hits[:limit]],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Search a tiny local PSI knowledge graph")
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--investigation", help="Exact investigation ID, such as PSI-25")
    parser.add_argument("--role", choices=["measurement", "documentation", "video", "image", "other"])
    parser.add_argument("--limit", type=int, default=6)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        graph = MiniGraph.model_validate_json(args.graph.read_text())
        results = search_graph(graph, args.query, investigation_id=args.investigation,
                               role=args.role, limit=args.limit)
        output = results.model_dump_json(indent=2) + "\n"
        if args.output:
            args.output.write_text(output)
        else:
            sys.stdout.write(output)
    except (OSError, ValidationError, ValueError) as exc:
        print(f"Search failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

