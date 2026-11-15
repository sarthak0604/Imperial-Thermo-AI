"""Regression cases for extraction prompts whose inventory dwarfs the source."""

import copy
import json

import pytest

from psi_graph.local_model import LocalModelError
from psi_graph.science import SYSTEM, Extraction, extract_all


class BoundedClient:
    """Fake tokenizer counts bytes, including system/schema/prompt overhead."""

    def __init__(self, data_budget=2500):
        self.overhead = (
            len(SYSTEM.encode())
            + len(json.dumps(Extraction.model_json_schema()).encode())
            + 100
        )
        self.limit = self.overhead + data_budget
        self.requests = []

    def fits(self, stage, payload, schema):
        assert stage == "extract"
        assert schema is Extraction
        return (
            self.overhead + len(json.dumps(payload, ensure_ascii=False).encode())
            <= self.limit
        )

    def call(self, stage, payload, schema):
        assert self.fits(stage, payload, schema), "Oversized request reached inference"
        self.requests.append(copy.deepcopy(payload))
        return Extraction(studies=[], resources=[], caveats=[])


def document(text, **overrides):
    return {
        "id": "document-1",
        "title": "Combustion experiment",
        "resource_type": "paper",
        "sections": [{"locator": "page 1", "text": text}],
        **overrides,
    }


def test_large_inventory_and_source_are_both_bounded_without_losing_coverage(tmp_path):
    text = "".join(f"Observation {n}: temperature ΔT={n} K.\n" for n in range(180))
    resources = [
        {
            "id": f"resource-{i}",
            "title": f"Experiment data {i}",
            "resource_type": "dataset",
            "doi": None,
            "nasa_path": f"PSI-25/Measurements/run-{i}/temperature.csv",
            "access_status": "downloaded",
        }
        for i in range(40)
    ]
    client = BoundedClient()
    original_resources = copy.deepcopy(resources)
    doc = document(text)
    original_doc = copy.deepcopy(doc)

    results, failures = extract_all(client, [doc], resources, tmp_path)

    assert len(client.requests) > 1
    assert not failures
    assert len(results) == len(client.requests)
    assert len({(row["document_id"], row["chunk"]) for row in results}) == len(results)
    assert doc == original_doc
    assert resources == original_resources
    # Every inventory entry must see the complete source, even if its source
    # pieces have different boundaries from those for another inventory batch.
    for resource in resources:
        relevant = [
            request
            for request in client.requests
            if resource["id"] in {r["id"] for r in request["resource_inventory"]}
        ]
        assert relevant, f"Dropped inventory entry {resource['id']}"
        assert (
            "".join(
                section["text"]
                for request in relevant
                for section in request["sections"]
            )
            == text
        )
    assert {
        section["locator"]
        for request in client.requests
        for section in request["sections"]
    } == {"page 1"}
    saved = json.loads((tmp_path / "extractions.json").read_text())
    assert saved == results


def test_long_section_without_inventory_preserves_every_character(tmp_path):
    text = "".join(f"行 {i}: pressure = {i} Pa.\n" for i in range(200))
    client = BoundedClient()

    results, failures = extract_all(client, [document(text)], [], tmp_path)

    assert len(results) > 1
    assert not failures
    assert (
        "".join(
            section["text"]
            for request in client.requests
            for section in request["sections"]
        )
        == text
    )
    assert all(request["document_id"] == "document-1" for request in client.requests)


@pytest.mark.parametrize("oversize", ["title", "resource"])
def test_indivisible_metadata_stops_before_generation(tmp_path, oversize):
    client = BoundedClient()
    doc = document("Short source evidence")
    resources = []
    if oversize == "title":
        doc["title"] = "Very long title " * 1000
    else:
        resources = [{"id": "resource-1", "title": "Very long inventory title " * 1000}]

    with pytest.raises(LocalModelError):
        extract_all(client, [doc], resources, tmp_path)

    assert not client.requests
    assert not (tmp_path / "extractions.json").exists()


def test_clients_without_budget_interface_keep_existing_contract(tmp_path):
    class Client:
        def __init__(self):
            self.requests = []

        def call(self, stage, payload, schema):
            self.requests.append(payload)
            return Extraction(studies=[], resources=[], caveats=[])

    client = Client()
    results, failures = extract_all(client, [document("Short source")], [], tmp_path)

    assert len(results) == len(client.requests) == 1
    assert not failures
