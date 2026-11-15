"""Scoped extraction and resumable adaptive splitting, without model downloads."""

import copy
import json

import pytest
from test_prompt_budget import BoundedClient, document

from psi_graph.common import digest, read_json
from psi_graph.local_model import LocalModelError, LocalOutputLimitError
from psi_graph.science import Extraction, extract_all


class Client(BoundedClient):
    provider = "local"
    model = "test-qwen"
    base_url = ""


def inventory(count=1000):
    return [
        dict(
            id=f"res:PSI-25:unrelated-{i}",
            filename=f"unrelated-run-{i}.csv",
            title=f"Unrelated experimental measurement {i}",
            resource_type="dataset",
        )
        for i in range(count)
    ]


def test_unrelated_inventory_no_longer_multiplies_model_calls(tmp_path):
    text = (
        "Measurements are stored in bass-temperatures.csv. "
        + "Source observations. " * 250
    )
    own = dict(
        id="res:PSI-25:source",
        title="BASS experimental investigation",
        resource_type="paper",
    )
    named = dict(
        id="res:PSI-25:temperatures",
        filename="bass-temperatures.csv",
        title="BASS temperature measurements",
        resource_type="dataset",
    )
    resources = [own, named, *inventory()]
    original = copy.deepcopy(resources)
    doc = document(text, resource_id=own["id"])
    client = Client(data_budget=2500)
    results, failures = extract_all(client, [doc], resources, tmp_path)
    assert 1 < len(client.requests) < 20
    assert not failures
    assert len(results) == len(client.requests)
    assert len({r["chunk"] for r in results}) == len(results)
    assert resources == original
    assert "".join(s["text"] for r in client.requests for s in r["sections"]) == text
    assert all(
        {r["id"] for r in request["resource_inventory"]} == {own["id"], named["id"]}
        for request in client.requests
    )
    assert read_json(tmp_path / "extractions.json") == results


def test_completed_checkpoint_survives_transfer_status_and_batch_size_change(
    tmp_path, monkeypatch
):
    doc = document("Source evidence", resource_id="own")
    resources = [
        dict(
            id="own",
            title="Source article",
            access_status="downloaded",
            local_path="/tmp/a",
        )
    ]
    client = Client()
    expected = extract_all(client, [doc], resources, tmp_path)
    calls = len(client.requests)
    resources[0].update(access_status="discarded", local_path=None, storage_uri=None)
    resources.extend(inventory())
    client.limit += 10000
    monkeypatch.setenv("LLM_INPUT_TOKENS", "16384")
    actual = extract_all(client, [doc], resources, tmp_path)
    assert actual == expected
    assert len(client.requests) == calls


@pytest.mark.parametrize("changed", ["text", "model", "referenced_resource"])
def test_completed_checkpoint_invalidates_scientific_changes(tmp_path, changed):
    doc = document(
        "Scientific evidence refers to new-bass-data.csv.", resource_id="own"
    )
    resources = [dict(id="own", title="Source article")]
    client = Client()
    extract_all(client, [doc], resources, tmp_path)
    calls = len(client.requests)
    if changed == "text":
        doc["sections"][0]["text"] += " New finding."
    elif changed == "model":
        client.model = "different-qwen"
    else:
        resources.append(
            dict(
                id="new-resource",
                filename="new-bass-data.csv",
                title="New BASS dataset",
            )
        )
    extract_all(client, [doc], resources, tmp_path)
    assert len(client.requests) > calls
    if changed == "referenced_resource":
        assert "new-resource" in {
            r["id"] for r in client.requests[-1]["resource_inventory"]
        }


class LimitedOutputClient(Client):
    def __init__(self, limit=64, interrupt_second=False):
        super().__init__(data_budget=100000)
        self.output_limit = limit
        self.interrupt_second = interrupt_second
        self.attempted = []
        self.generated = []
        self.cache = {}
        self.cache_hits = 0

    def call(self, stage, payload, schema):
        text = "".join(s["text"] for s in payload["sections"])
        key = json.dumps(payload, sort_keys=True)
        if key in self.cache:
            self.cache_hits += 1
            return self.cache[key]
        self.attempted.append(text)
        if len(text) > self.output_limit:
            raise LocalOutputLimitError("Truncated response refused")
        if self.interrupt_second and self.generated:
            self.interrupt_second = False
            raise LocalModelError("Interrupted before next successful response")
        result = Extraction(studies=[], resources=[], caveats=[text])
        self.cache[key] = result
        self.generated.append(text)
        return result


def test_output_limit_splits_without_accepting_partial_output_and_checkpoints(tmp_path):
    text = "".join(chr(0x400 + i) for i in range(256))
    doc = document(text)
    client = LimitedOutputClient()
    results, failures = extract_all(client, [doc], [], tmp_path)
    assert not failures
    assert "".join(client.generated) == text
    assert "".join(r["extraction"]["caveats"][0] for r in results) == text
    assert all(len(s) <= client.output_limit for s in client.generated)
    assert len(client.attempted) > len(client.generated)
    attempted = list(client.attempted)
    assert extract_all(client, [doc], [], tmp_path)[0] == results
    assert client.attempted == attempted


def test_interrupted_split_reuses_split_decision_and_successful_child_cache(tmp_path):
    text = "L" * 64 + "R" * 64
    doc = document(text)
    client = LimitedOutputClient(interrupt_second=True)
    with pytest.raises(LocalModelError, match="Interrupted"):
        extract_all(client, [doc], [], tmp_path)
    assert client.attempted == [text, "L" * 64, "R" * 64]
    partial = read_json(tmp_path / "extractions.json")
    assert len(partial) == 1
    checkpoint = tmp_path / "extraction_checkpoints" / (digest(doc["id"]) + ".json")
    assert not checkpoint.exists()
    results, failures = extract_all(client, [doc], [], tmp_path)
    assert not failures
    assert client.attempted == [text, "L" * 64, "R" * 64, "R" * 64]
    assert client.cache_hits == 1
    assert [r["chunk"] for r in results] == [1, 2]
    assert "".join(r["extraction"]["caveats"][0] for r in results) == text
    assert read_json(checkpoint)["complete"] is True
