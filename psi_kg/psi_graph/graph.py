"""Exact v1.0.0 export contract, evidence validation, and semantic review."""

from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlparse

from jsonschema import Draft202012Validator, FormatChecker

from .common import digest, file_hash, normalized, now, slug, write_json
from .science import Review, check_evidence, evidence_index


def object_schema(properties):
    return dict(
        type="object",
        properties=properties,
        required=list(properties),
        additionalProperties=False,
    )


STRING = {"type": "string"}
NULL_STRING = {"type": ["string", "null"]}
STRINGS = {"type": "array", "items": STRING}
PROPERTIES = {
    "Investigation": object_schema(
        dict(
            title=STRING,
            summary=NULL_STRING,
            keywords=STRINGS,
            doi=NULL_STRING,
            source_url=STRING,
        )
    ),
    "Experiment": object_schema(
        dict(
            title=STRING,
            summary=NULL_STRING,
            keywords=STRINGS,
            conditions={"type": "object"},
            methods=STRINGS,
            source_url=NULL_STRING,
        )
    ),
    "Concept": object_schema(
        dict(name=STRING, synonyms=STRINGS, description=NULL_STRING)
    ),
    "Variable": object_schema(
        dict(name=STRING, symbol=NULL_STRING, unit=NULL_STRING, role=NULL_STRING)
    ),
    "Resource": object_schema(
        dict(
            title=STRING,
            filename=NULL_STRING,
            resource_type=STRING,
            file_format=NULL_STRING,
            summary=NULL_STRING,
            keywords=STRINGS,
            variables=STRINGS,
            source_url=NULL_STRING,
            storage_uri=NULL_STRING,
            access_status=STRING,
            size_bytes={"type": ["integer", "null"], "minimum": 0},
        )
    ),
}
EVIDENCE_SCHEMA = object_schema(dict(source_url=STRING, locator=STRING, text=STRING))
EDGE_SCHEMA = object_schema(
    dict(
        id=STRING,
        source=STRING,
        target=STRING,
        type={"enum": ["CONTAINS", "STUDIES", "MEASURES", "HAS_RESOURCE"]},
        properties=object_schema(
            dict(
                origin=STRING,
                verification_status={"enum": ["verified", "needs_review"]},
                evidence={"type": "array", "items": EVIDENCE_SCHEMA},
            )
        ),
    )
)
SCHEMA = object_schema(
    dict(
        schema_version={"const": "1.0.0"},
        graph_id=STRING,
        source_url=STRING,
        generated_at={"type": "string", "format": "date-time"},
        nodes={
            "type": "array",
            "items": {
                "oneOf": [
                    object_schema(
                        dict(id=STRING, type={"const": kind}, properties=props)
                    )
                    for kind, props in PROPERTIES.items()
                ]
            },
        },
        edges={"type": "array", "items": EDGE_SCHEMA},
    )
)
SCHEMA["$schema"] = "https://json-schema.org/draft/2020-12/schema"
DIRECTIONS = {
    "CONTAINS": ("Investigation", "Experiment"),
    "STUDIES": ("Experiment", "Concept"),
    "MEASURES": ("Experiment", "Variable"),
    "HAS_RESOURCE": ("Experiment", "Resource"),
}


def build(synthesis, resources, metadata, url, documents):
    doc_map = {d["id"]: d for d in documents}
    index = evidence_index(documents)
    nodes, edges, provenance, rejected = {}, {}, {}, []
    inv_id = "inv:" + metadata["accession"]

    def evidence(items):
        return [
            dict(
                source_url=doc_map[e["document_id"]]["source_url"],
                locator=e["locator"],
                text=e["text"],
            )
            for e in check_evidence(items, index)
        ]

    def node(node_id, kind, props, refs):
        if node_id not in nodes:
            nodes[node_id] = dict(id=node_id, type=kind, properties=props)
        provenance.setdefault(node_id, [])
        for ref in refs:
            if ref not in provenance[node_id]:
                provenance[node_id].append(ref)

    def edge(source, target, kind, refs, origin="extracted"):
        if not refs:
            rejected.append(
                dict(
                    source=source,
                    target=target,
                    type=kind,
                    reason="No valid source evidence",
                )
            )
            return
        edge_id = "edge:" + digest(source + "\0" + kind + "\0" + target)
        if edge_id not in edges:
            edges[edge_id] = dict(
                id=edge_id,
                source=source,
                target=target,
                type=kind,
                properties=dict(
                    origin=origin, verification_status="needs_review", evidence=[]
                ),
            )
        for ref in refs:
            if ref not in edges[edge_id]["properties"]["evidence"]:
                edges[edge_id]["properties"]["evidence"].append(ref)

    node(
        inv_id,
        "Investigation",
        dict(
            title=metadata["title"],
            summary=synthesis.investigation_summary,
            keywords=synthesis.investigation_keywords,
            doi=metadata.get("doi") or None,
            source_url=url,
        ),
        evidence(synthesis.investigation_evidence),
    )
    science = {r.resource_id: r for r in synthesis.resources}
    resource_ids = {r["id"] for r in resources}
    for r in resources:
        extracted = science.get(r["id"])
        props = {
            k: r.get(k)
            for k in (
                "title",
                "filename",
                "resource_type",
                "file_format",
                "source_url",
                "storage_uri",
                "access_status",
                "size_bytes",
            )
        }
        props.update(
            summary=extracted.summary if extracted else None,
            keywords=extracted.keywords if extracted else [],
            variables=extracted.variables if extracted else [],
        )
        node(
            r["id"],
            "Resource",
            props,
            evidence(extracted.evidence) if extracted else [],
        )
    for study in synthesis.studies:
        refs = evidence(study.evidence)
        if not refs:
            rejected.append(dict(study=study.title, reason="No valid study evidence"))
            continue
        exp_id = "exp:" + metadata["accession"] + ":" + digest(slug(study.key))
        node(
            exp_id,
            "Experiment",
            dict(
                title=study.title,
                summary=study.summary,
                keywords=study.keywords,
                conditions={c.name: c.value for c in study.conditions},
                methods=study.methods,
                source_url=refs[0]["source_url"],
            ),
            refs,
        )
        # Membership is supported by the study evidence plus NASA's resource/citation inventory.
        membership = refs[:]
        membership.append(
            dict(source_url=url, locator="metadata.title", text=metadata["title"])
        )
        edge(
            inv_id,
            exp_id,
            "CONTAINS",
            membership,
            "extracted_from_investigation_resources",
        )
        for concept in study.concepts:
            c_refs = evidence(concept.evidence)
            if not c_refs:
                continue
            cid = "concept:" + slug(concept.name)
            node(
                cid,
                "Concept",
                dict(
                    name=concept.name,
                    synonyms=concept.synonyms,
                    description=concept.description,
                ),
                c_refs,
            )
            edge(exp_id, cid, "STUDIES", c_refs)
        for variable in study.variables:
            v_refs = evidence(variable.evidence)
            if not v_refs:
                continue
            # Do not collapse normalized d^2/d0^2 with dimensional d^2 or conflicting roles/units.
            vid = (
                "var:"
                + slug(variable.name)
                + ":"
                + digest(str(variable.unit) + "|" + variable.role)
            )
            node(
                vid,
                "Variable",
                dict(
                    name=variable.name,
                    symbol=variable.symbol,
                    unit=variable.unit,
                    role=variable.role,
                ),
                v_refs,
            )
            edge(exp_id, vid, "MEASURES", v_refs)
        for resource in study.resources:
            if resource.resource_id in resource_ids:
                edge(
                    exp_id,
                    resource.resource_id,
                    "HAS_RESOURCE",
                    evidence(resource.evidence),
                )
            else:
                rejected.append(
                    dict(resource_id=resource.resource_id, reason="Unknown resource ID")
                )
    graph = dict(
        schema_version="1.0.0",
        graph_id="nasa-" + metadata["accession"].lower(),
        source_url=url,
        generated_at=now(),
        nodes=sorted(nodes.values(), key=lambda n: n["id"]),
        edges=sorted(edges.values(), key=lambda e: e["id"]),
    )
    return graph, provenance, rejected


def scientific_review(client, graph, provenance, documents, output):
    nodes = {n["id"]: n for n in graph["nodes"]}
    contexts = {
        (d["source_url"], s["locator"]): s["text"]
        for d in documents
        for s in d["sections"]
    }
    items = []
    for node in graph["nodes"]:
        if node["type"] == "Resource":
            # Download metadata is deterministic; review generated scientific content only.
            claims = {
                k: node["properties"][k] for k in ("summary", "keywords", "variables")
            }
            if not any(claims.values()):
                continue
        else:
            claims = node["properties"]
        refs = provenance.get(node["id"], [])
        items.append(
            dict(
                id=node["id"],
                kind=node["type"],
                claim=claims,
                evidence=refs,
                source_context=[
                    contexts.get((e["source_url"], e["locator"]), "") for e in refs
                ],
            )
        )
    for edge in graph["edges"]:
        refs = edge["properties"]["evidence"]
        items.append(
            dict(
                id=edge["id"],
                kind="relationship",
                relation=edge["type"],
                source=nodes[edge["source"]],
                target=nodes[edge["target"]],
                evidence=refs,
                source_context=[
                    contexts.get((e["source_url"], e["locator"]), "") for e in refs
                ],
            )
        )
    from .synthesis_batches import adaptive_calls, bounded_batches, fit_review_items

    def payload(batch):
        return dict(
            instruction="Independently assess every item against the provided verbatim evidence and source context. Return one verdict per exact ID. Check units, actual vs modeled measurements, conditions, unsupported findings, synonyms, methods and resource association. Exact text match alone does NOT prove entailment. For relationships assess the relationship, not unrelated properties of the endpoint nodes. HAS_RESOURCE requires the document/data to support that specific study, not just general topic overlap. CONTAINS means documented analysis within the investigation resources, not necessarily a new physical flight experiment. Citation titles can support bibliographic association, never numerical claims. A controlled/input parameter must not be called measured unless the source reports it as an observable. Mark unsupported claims false; give precise reasons. Do not require source to literally use our paraphrased labels or slug.",
            items=batch,
        )

    scope = dict(complete=False, total_items=len(items), excerpt_context_ids=[])
    verdicts = []
    scoped = fit_review_items(client, items, payload, Review, scope)
    batches = bounded_batches(
        client, "scientific_review", scoped, payload, Review, max_items=16
    )
    try:
        for batch, review in adaptive_calls(
            client, "scientific_review", batches, payload, Review
        ):
            print(
                f"LLM scientific audit: {len(verdicts) + 1}-"
                f"{len(verdicts) + len(batch)} of {len(items)}",
                flush=True,
            )
            expected = {item["id"] for item in batch}
            seen = set()
            for verdict in review.verdicts:
                if verdict.id in expected and verdict.id not in seen:
                    data = verdict.model_dump()
                    if verdict.id in scope["excerpt_context_ids"]:
                        data["reason"] += (
                            " [Audit used quote-centered excerpts; full source context "
                            "was not reviewed.]"
                        )
                    verdicts.append(data)
                    seen.add(verdict.id)
            for missing in expected - seen:
                verdicts.append(
                    dict(
                        id=missing, supported=False, reason="No audit verdict returned"
                    )
                )
            write_json(output / "scientific_review.json", verdicts)
        scope["complete"] = True
    finally:
        scope["reviewed_items"] = len(verdicts)
        scope["full_source_context_reviewed"] = (
            scope["complete"] and not scope["excerpt_context_ids"]
        )
        write_json(output / "scientific_review_scope.json", scope)
    write_json(output / "scientific_review.json", verdicts)
    return verdicts


def apply_review(graph, verdicts):
    rejected = {v["id"] for v in verdicts if not v["supported"]}
    approved = {v["id"] for v in verdicts if v["supported"]}
    kept = []
    for node in graph["nodes"]:
        if node["id"] in rejected:
            if node["type"] in ("Resource", "Investigation"):
                node["properties"]["summary"] = None
                node["properties"]["keywords"] = []
                if node["type"] == "Resource":
                    node["properties"]["variables"] = []
            else:
                continue
        kept.append(node)
    ids = {n["id"] for n in kept}
    graph["edges"] = [
        e
        for e in graph["edges"]
        if e["id"] in approved and e["source"] in ids and e["target"] in ids
    ]
    for edge in graph["edges"]:
        edge["properties"]["verification_status"] = "verified"
    # Remove orphan science nodes and experiments with no surviving membership edge.
    contained = {e["target"] for e in graph["edges"] if e["type"] == "CONTAINS"}
    graph["edges"] = [
        e for e in graph["edges"] if e["type"] == "CONTAINS" or e["source"] in contained
    ]
    linked = {e["target"] for e in graph["edges"]}
    graph["nodes"] = [
        n
        for n in kept
        if n["type"] in ("Investigation", "Resource") or n["id"] in linked
    ]
    return graph


def validate(graph, documents, resources):
    errors = [
        error.message
        for error in Draft202012Validator(
            SCHEMA, format_checker=FormatChecker()
        ).iter_errors(graph)
    ]
    ids = [n["id"] for n in graph["nodes"]]
    edge_ids = [e["id"] for e in graph["edges"]]
    if len(set(ids)) != len(ids):
        errors.append("Duplicate node IDs")
    if len(set(edge_ids)) != len(edge_ids):
        errors.append("Duplicate edge IDs")
    nodes = {n["id"]: n for n in graph["nodes"]}
    contexts = {
        (d["source_url"], s["locator"]): s["text"]
        for d in documents
        for s in d["sections"]
    }
    manifest = {r["id"]: r for r in resources}
    for edge in graph["edges"]:
        if edge["source"] not in nodes or edge["target"] not in nodes:
            errors.append("Missing endpoint: " + edge["id"])
            continue
        actual = (nodes[edge["source"]]["type"], nodes[edge["target"]]["type"])
        if actual != DIRECTIONS.get(edge["type"]):
            errors.append("Wrong direction/types: " + edge["id"])
        if not edge["properties"]["evidence"]:
            errors.append("Missing evidence: " + edge["id"])
        for ref in edge["properties"]["evidence"]:
            text = contexts.get((ref["source_url"], ref["locator"]), "")
            if not ref["text"].strip() or normalized(ref["text"]) not in normalized(
                text
            ):
                errors.append("Unverifiable evidence: " + edge["id"])
    for n in graph["nodes"]:
        if n["type"] == "Resource":
            r = manifest.get(n["id"])
            if not r or n["properties"]["source_url"] != r["source_url"]:
                errors.append("Unknown resource source: " + n["id"])
            if r and urlparse(r["source_url"]).scheme != "https":
                errors.append("Non-HTTPS original source: " + n["id"])
            uri = n["properties"]["storage_uri"]
            if (
                uri
                and urlparse(uri).scheme == "file"
                and not Path(unquote(urlparse(uri).path)).is_file()
            ):
                errors.append("Missing cached resource: " + n["id"])
            elif uri and r and r.get("sha256") and urlparse(uri).scheme == "file":
                path = Path(unquote(urlparse(uri).path))
                if file_hash(path) != r["sha256"]:
                    errors.append("Cached resource checksum mismatch: " + n["id"])
        if n["type"] == "Experiment":
            if not any(
                e["type"] == "HAS_RESOURCE" and e["source"] == n["id"]
                for e in graph["edges"]
            ):
                errors.append("Experiment has no supported resource: " + n["id"])
    return dict(
        passed=not errors,
        errors=errors,
        nodes=len(ids),
        edges=len(edge_ids),
        node_counts=dict(Counter(n["type"] for n in graph["nodes"])),
        edge_counts=dict(Counter(e["type"] for e in graph["edges"])),
    )
