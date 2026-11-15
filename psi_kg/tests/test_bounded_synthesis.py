import json
from copy import deepcopy

import pytest

from psi_graph.graph import scientific_review
from psi_graph.local_model import LocalModelError
from psi_graph.science import Review, Synthesis, synthesize


def evidence(text="Evidence"):
    return {"document_id": "res:1", "locator": "page 1", "text": text}


def study(number):
    return dict(
        key="same-study",
        title="Study",
        summary=f"Summary {number}. " * 25,
        keywords=[f"keyword-{number}"],
        conditions=[dict(name="pressure", value=str(number))],
        methods=[f"method-{number}"],
        findings=[f"finding-{number}"],
        concepts=[
            dict(
                name="Concept",
                synonyms=[str(number)],
                description=f"Description {number}",
                evidence=[evidence(str(number))],
            )
        ],
        variables=[
            dict(
                name="Temperature",
                symbol="T",
                unit="K",
                role="dependent",
                evidence=[evidence(str(number))],
            )
        ],
        resources=[dict(resource_id="res:1", evidence=[evidence(str(number))])],
        evidence=[evidence(str(number))],
    )


class BudgetClient:
    def __init__(self, limit):
        self.limit = limit
        self.calls = []

    def fits(self, stage, payload, schema):
        return len(json.dumps(payload)) <= self.limit

    def call(self, stage, payload, schema):
        assert self.fits(stage, payload, schema), "Oversized request reached inference"
        self.calls.append(deepcopy(payload))
        if schema is Review:
            return Review(
                verdicts=[
                    dict(id=item["id"], supported=True, reason="Supported")
                    for item in payload["items"]
                ]
            )
        return Synthesis(
            investigation_summary="Summary",
            investigation_keywords=[],
            investigation_evidence=[],
            studies=[
                s for r in payload["extractions"] for s in r["extraction"]["studies"]
            ],
            resources=[
                s for r in payload["extractions"] for s in r["extraction"]["resources"]
            ],
            caveats=[],
        )


def test_synthesis_batches_preserve_all_science_and_scope_inventory(tmp_path):
    records = [
        dict(
            document_id="res:1",
            chunk=i,
            extraction=dict(
                studies=[study(i)],
                resources=[
                    dict(
                        resource_id="res:1",
                        summary=f"Resource summary {i}",
                        keywords=[str(i)],
                        variables=[str(i)],
                        evidence=[evidence(str(i))],
                    )
                ],
                caveats=[],
            ),
        )
        for i in range(6)
    ]
    resources = [
        dict(
            id=f"res:{i}",
            title=f"Resource {i}",
            resource_type="data",
            source_url="https://example.org",
            access_status="accessible",
        )
        for i in range(1000)
    ]
    client = BudgetClient(3300)
    result = synthesize(
        client,
        records,
        resources,
        dict(accession="PSI-1", title="Investigation", objective="Objective", doi=None),
        tmp_path,
    )
    assert len(client.calls) > 1
    assert all(
        [r["id"] for r in p["resource_inventory"]] == ["res:1"] for p in client.calls
    )
    assert len(result.studies) == 1
    merged = result.studies[0]
    assert merged.methods == [f"method-{i}" for i in range(6)]
    assert merged.findings == [f"finding-{i}" for i in range(6)]
    assert len(merged.evidence) == 6
    assert len(merged.concepts) == len(merged.variables) == len(merged.resources) == 1
    assert len(merged.concepts[0].evidence) == 6
    assert len(merged.variables[0].evidence) == 6
    assert all(str(i) in merged.conditions[0].value for i in range(6))
    assert len(result.resources) == 1
    assert result.resources[0].keywords == [str(i) for i in range(6)]
    assert all(f"Resource summary {i}" in result.resources[0].summary for i in range(6))
    assert any("differently named" in c for c in result.caveats)
    assert (tmp_path / "synthesis_batches.json").exists()


def test_synthesis_atomic_record_over_budget_fails_before_generation(tmp_path):
    item = study(0)
    item["summary"] = "Huge summary" * 10000
    client = BudgetClient(3300)
    record = dict(
        document_id="res:1", extraction=dict(studies=[item], resources=[], caveats=[])
    )
    with pytest.raises(LocalModelError, match="single synthesize record"):
        synthesize(client, [record], [], {}, tmp_path)
    assert client.calls == []
    assert not (tmp_path / "synthesis.json").exists()


def review_inputs(quote="The temperature was measured."):
    graph = dict(
        nodes=[
            dict(
                id="res:1",
                type="Resource",
                properties=dict(
                    summary="Measured temperature",
                    keywords=["temperature"],
                    variables=["temperature"],
                ),
            )
        ],
        edges=[],
    )
    refs = dict(source_url="https://example.org/paper", locator="page 1", text=quote)
    provenance = {"res:1": [refs]}
    documents = [
        dict(
            source_url=refs["source_url"],
            sections=[
                dict(
                    locator="page 1",
                    text="Other text. " * 10000 + quote + " More text." * 10000,
                )
            ],
        )
    ]
    return graph, provenance, documents


def test_review_large_context_uses_marked_quote_centered_excerpt(tmp_path):
    graph, provenance, documents = review_inputs()
    original = deepcopy(documents)
    client = BudgetClient(4000)
    verdicts = scientific_review(client, graph, provenance, documents, tmp_path)
    assert verdicts[0]["supported"] is True
    assert "full source context was not reviewed" in verdicts[0]["reason"]
    item = client.calls[0]["items"][0]
    assert provenance["res:1"][0]["text"] in item["source_context"][0]
    assert documents == original
    scope = json.loads((tmp_path / "scientific_review_scope.json").read_text())
    assert scope["excerpt_context_ids"] == ["res:1"]
    assert scope["complete"] is True
    assert scope["full_source_context_reviewed"] is False


def test_review_indivisible_large_evidence_fails_closed(tmp_path):
    graph, provenance, documents = review_inputs("Long evidence " * 10000)
    client = BudgetClient(4000)
    with pytest.raises(LocalModelError, match="audit item res:1"):
        scientific_review(client, graph, provenance, documents, tmp_path)
    assert client.calls == []
    scope = json.loads((tmp_path / "scientific_review_scope.json").read_text())
    assert scope["complete"] is False
    assert scope["blocked_item_id"] == "res:1"
    assert scope["full_source_context_reviewed"] is False
