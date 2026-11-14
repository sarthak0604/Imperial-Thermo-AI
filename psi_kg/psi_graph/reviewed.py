"""Export a deliberately supplied, source-reviewed extraction without pretending to call an API."""

import json
from pathlib import Path

from .common import digest, read_json, write_json
from .graph import build, validate
from .science import Synthesis


def document_digest(documents):
    return digest(
        json.dumps(
            [
                {k: d.get(k) for k in ("id", "source_url", "sections", "sha256")}
                for d in sorted(documents, key=lambda d: d["id"])
            ],
            sort_keys=True,
            ensure_ascii=False,
        )
    )


def claim_digest(claim):
    return digest(json.dumps(claim, sort_keys=True, ensure_ascii=False))


def export_reviewed(bundle_path, resources, metadata, url, documents, output):
    bundle = read_json(bundle_path)
    if bundle["source_url"] != url or bundle["document_digest"] != document_digest(
        documents
    ):
        raise ValueError(
            "Reviewed extraction does not match the current source snapshot; re-review changed sources."
        )
    synthesis = Synthesis.model_validate(bundle["science"])
    graph, provenance, rejected = build(synthesis, resources, metadata, url, documents)
    approvals = {r["id"]: r for r in bundle["reviewed_claims"]}
    for claim in graph["nodes"] + graph["edges"]:
        approved = approvals.get(claim["id"])
        # Resource download metadata can move; review only scientific properties.
        content = (
            {
                k: claim["properties"].get(k)
                for k in ("summary", "keywords", "variables")
            }
            if claim.get("type") == "Resource"
            else claim
        )
        if (
            not approved
            or approved["claim_digest"] != claim_digest(content)
            or not approved["supported"]
        ):
            raise ValueError("No matching source-review approval: " + claim["id"])
    for edge in graph["edges"]:
        edge["properties"].update(
            origin="assistant_source_review", verification_status="verified"
        )
    validation = validate(graph, documents, resources)
    if rejected or not validation["passed"]:
        raise ValueError(
            "Reviewed graph failed evidence/structural validation: "
            + str(rejected + validation["errors"])
        )
    write_json(output / "node_provenance.json", provenance)
    write_json(output / "scientific_review.json", bundle["reviewed_claims"])
    write_json(output / "knowledge_graph.json", graph)
    write_json(
        output / "run_provenance.json",
        dict(
            extraction_mode="assistant_source_review",
            external_llm_api_calls=0,
            api_extraction_status="pending_credentials",
            review_bundle=str(Path(bundle_path).resolve()),
            document_digest=bundle["document_digest"],
            caveats=synthesis.caveats,
        ),
    )
    return graph, validation, synthesis.caveats
