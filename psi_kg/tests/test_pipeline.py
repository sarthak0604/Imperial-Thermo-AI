import copy
import zipfile

import pytest
from jsonschema import Draft202012Validator

from psi_graph.graph import SCHEMA
from psi_graph.nasa_access import investigation_id
from psi_graph.parsing import chunks, extract_archive, table
from psi_graph.providers import LLM
from psi_graph.science import Extraction, check_evidence


def test_url_input_and_wrong_domain():
    assert (
        investigation_id("https://psi.nasa.gov/physci/repo/data/investigations/PSI-117")
        == "PSI-117"
    )
    with pytest.raises(ValueError):
        investigation_id("https://other.example/PSI-117")


def test_complete_streamed_numeric_profile_and_metadata_values():
    sections, profile = table(
        iter(
            [
                ["t (s)", "T (K)"],
                *[[i, i + 273] for i in range(10000)],
                ["case B", 0.21],
            ]
        ),
        "data",
    )
    assert profile["rows"] == 10002
    assert profile["column_statistics"][0]["numeric_count"] == 10000
    assert profile["column_statistics"][0]["max"] == 9999
    assert any("0.21" in s["text"] for s in sections if "case B" in s["text"])


def test_no_chunk_truncation():
    source = "0123456789" * 27000
    result = list(
        chunks({"sections": [{"locator": "page 1", "text": source}]}, budget=10000)
    )
    assert "".join(s["text"] for block in result for s in block) == source


def test_evidence_rejects_paraphrase_wrong_page_and_invention():
    index = {"doc": {"page 2": "Pressure is 1 atm.\nDroplet diameter is 0.5 mm."}}
    good = {"document_id": "doc", "locator": "page 2", "text": "Pressure is 1 atm."}
    wrong = {**good, "text": "Pressure is 2 atm."}
    other = {**good, "locator": "page 3"}
    assert check_evidence([good, wrong, other], index) == [good]


def test_zip_traversal_is_rejected(tmp_path):
    archive = tmp_path / "source.zip"
    with zipfile.ZipFile(archive, "w") as f:
        f.writestr("../escape.txt", "bad")
    with pytest.raises(ValueError, match="Unsafe archive member"):
        extract_archive(
            {"id": "res:PSI-1:test", "local_path": str(archive)}, tmp_path / "out"
        )
    assert not (tmp_path / "escape.txt").exists()


def test_provider_request_contracts_and_response_validation(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-no-network")
    client = LLM(tmp_path, "openai", "test-model")
    observed = {}

    def fake(route, body, headers):
        observed.update(route=route, body=body)
        return {
            "status": "completed",
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": '{"studies":[],"resources":[],"caveats":[]}',
                        }
                    ]
                }
            ],
        }

    monkeypatch.setattr(client, "post", fake)
    result, _ = client.generate("system", "input", Extraction)
    assert result.studies == []
    assert observed["route"] == "/responses"
    assert observed["body"]["text"]["format"]["strict"] is True
    assert observed["body"]["store"] is False


def test_anthropic_missing_tool_result_fails(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "unit-test-no-network")
    client = LLM(tmp_path, "anthropic", "test-model")
    monkeypatch.setattr(
        client, "post", lambda *args: {"content": [], "stop_reason": "end_turn"}
    )
    with pytest.raises(ValueError, match="Missing/truncated"):
        client.generate("system", "input", Extraction)


def test_local_compatible_provider_allows_no_secret(monkeypatch, tmp_path):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    client = LLM(
        tmp_path, "openai-compatible", "local-model", "http://localhost:8000/v1"
    )
    assert client.key is None
    with pytest.raises(RuntimeError, match="Missing credential"):
        LLM(tmp_path, "openai-compatible", "remote-model", "https://api.example/v1")


def test_graph_schema_disallows_extra_types_and_properties():
    base = {
        "schema_version": "1.0.0",
        "graph_id": "nasa-psi-1",
        "source_url": "https://psi.nasa.gov/PSI-1",
        "generated_at": "2026-11-14T00:00:00Z",
        "nodes": [],
        "edges": [],
    }
    assert not list(Draft202012Validator(SCHEMA).iter_errors(base))
    bad = copy.deepcopy(base)
    bad["nodes"] = [{"id": "new", "type": "Finding", "properties": {}}]
    assert list(Draft202012Validator(SCHEMA).iter_errors(bad))
    bad = {**base, "findings": []}
    assert list(Draft202012Validator(SCHEMA).iter_errors(bad))


def test_archive_member_cache_does_not_redownload_parent(monkeypatch, tmp_path):
    from psi_graph.common import file_hash
    from psi_graph.discovery import download_one

    p = tmp_path / "member.txt"
    p.write_text("real archive member")
    record = {
        "local_path": str(p),
        "parent_resource_id": "res:PSI-1:parent",
        "sha256": file_hash(p),
    }
    assert download_one(record, {}, tmp_path) == []


def test_real_snapshot_rejects_dangling_and_wrong_direction_edges():
    from pathlib import Path

    from psi_graph.common import read_json
    from psi_graph.graph import validate

    out = Path(__file__).resolve().parents[1] / "output/PSI-117"
    if not (out / "knowledge_graph.json").exists():
        pytest.skip("PSI-117 snapshot not downloaded")
    graph = read_json(out / "knowledge_graph.json")
    docs = read_json(out / "documents.json")
    resources = read_json(out / "resources_manifest.json")["resources"]
    # The committed snapshot carries cache URIs from the machine that built it.
    # This test verifies the graph structure using the bundled evidence text.
    for node in graph["nodes"]:
        if node["type"] == "Resource" and (node["properties"].get("storage_uri") or "").startswith("file:"):
            node["properties"]["storage_uri"] = None
    report = validate(graph, docs, resources)
    assert report["passed"], report["errors"]
    bad = copy.deepcopy(graph)
    bad["edges"][0]["target"] = "missing"
    assert any(
        "Missing endpoint" in e for e in validate(bad, docs, resources)["errors"]
    )
    bad = copy.deepcopy(graph)
    edge = bad["edges"][0]
    edge["source"], edge["target"] = edge["target"], edge["source"]
    assert any("Wrong direction" in e for e in validate(bad, docs, resources)["errors"])


def test_openai_compatible_structured_response(monkeypatch, tmp_path):
    client = LLM(
        tmp_path, "openai-compatible", "local-model", "http://localhost:8000/v1"
    )
    seen = {}

    def fake(route, body, headers):
        seen.update(route=route, body=body)
        return {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": '{"studies":[],"resources":[],"caveats":[]}'
                    },
                }
            ]
        }

    monkeypatch.setattr(client, "post", fake)
    result, _ = client.generate("system", "source", Extraction)
    assert not result.studies
    assert seen["route"] == "/chat/completions"
    assert seen["body"]["response_format"]["type"] == "json_schema"


def test_anthropic_structured_tool_response(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "unit-test-no-network")
    client = LLM(tmp_path, "anthropic", "test-model")
    monkeypatch.setattr(
        client,
        "post",
        lambda *args: {
            "stop_reason": "tool_use",
            "content": [
                {
                    "type": "tool_use",
                    "name": "emit_science",
                    "input": {"studies": [], "resources": [], "caveats": []},
                }
            ],
        },
    )
    result, _ = client.generate("system", "source", Extraction)
    assert result.resources == []


def test_changed_nasa_version_does_not_reuse_same_size_file(monkeypatch, tmp_path):
    from pathlib import Path

    from psi_graph.common import digest, file_hash, write_json
    from psi_graph.discovery import discover, download_one

    old = tmp_path / "data.txt"
    old.write_text("old")
    rid = "res:PSI-1:" + digest("file-id")
    metadata = {"accession": "PSI-1", "version": 2, "publications": []}
    entry = {
        "id": "file-id",
        "version": 2,
        "key": "psi-data/PSI-1/data.txt",
        "bytes_size": 3,
    }
    write_json(tmp_path / "metadata.json", metadata)
    write_json(tmp_path / "files.json", [entry])
    write_json(
        tmp_path / "resources_manifest.json",
        {
            "resources": [
                {
                    "id": rid,
                    "nasa_file_version": 1,
                    "investigation_version": 1,
                    "local_path": str(old),
                    "sha256": file_hash(old),
                    "access_status": "accessible",
                }
            ]
        },
    )
    _, records = discover(
        "https://psi.nasa.gov/physci/repo/data/investigations/PSI-1", tmp_path
    )
    assert "sha256" not in records[0]
    calls = []

    def fresh(accession, version, entry, folder):
        calls.append(version)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "data.txt"
        path.write_text("new")
        return path

    monkeypatch.setattr("psi_graph.discovery.download_file", fresh)
    download_one(records[0], metadata, tmp_path)
    assert calls == [2]
    assert Path(records[0]["local_path"]).read_text() == "new"
