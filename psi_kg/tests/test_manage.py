import copy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from dotenv import dotenv_values

from psi_graph import manage, setup_gemini
from psi_graph.common import file_hash, read_json, write_json


def graph(accession="PSI-1", description="Source-specific concept"):
    url = f"https://psi.nasa.gov/physci/repo/data/investigations/{accession}"
    nodes = [
        {
            "id": f"inv:{accession}",
            "type": "Investigation",
            "properties": {
                "title": accession,
                "summary": None,
                "keywords": [],
                "doi": None,
                "source_url": url,
            },
        },
        {
            "id": f"exp:{accession}:study",
            "type": "Experiment",
            "properties": {
                "title": "Test study",
                "summary": None,
                "keywords": [],
                "conditions": {},
                "methods": [],
                "source_url": url,
            },
        },
        {
            "id": "concept:temperature",
            "type": "Concept",
            "properties": {
                "name": "Temperature",
                "synonyms": [],
                "description": description,
            },
        },
        {
            "id": "var:temperature",
            "type": "Variable",
            "properties": {
                "name": "Temperature",
                "symbol": "T",
                "unit": "K",
                "role": "dependent",
            },
        },
        {
            "id": f"res:{accession}:data",
            "type": "Resource",
            "properties": {
                "title": "Test data",
                "filename": "data.csv",
                "resource_type": "dataset",
                "file_format": "csv",
                "summary": None,
                "keywords": [],
                "variables": [],
                "source_url": url,
                "storage_uri": None,
                "access_status": "not_verified",
                "size_bytes": None,
            },
        },
    ]
    relations = [
        (0, 1, "CONTAINS"),
        (1, 2, "STUDIES"),
        (1, 3, "MEASURES"),
        (1, 4, "HAS_RESOURCE"),
    ]
    return {
        "schema_version": "1.0.0",
        "graph_id": f"nasa-{accession.lower()}",
        "source_url": url,
        "generated_at": "2026-11-14T00:00:00Z",
        "nodes": nodes,
        "edges": [
            {
                "id": f"edge:{accession}:{i}",
                "source": nodes[s]["id"],
                "target": nodes[t]["id"],
                "type": kind,
                "properties": {
                    "origin": "test_fixture",
                    "verification_status": "needs_review",
                    "evidence": [],
                },
            }
            for i, (s, t, kind) in enumerate(relations)
        ],
    }


def test_expand_preserves_studies_sources_and_distinct_meanings():
    first, second = graph(), graph("PSI-2", "Different source interpretation")
    before = copy.deepcopy(first)
    result = manage.merge(first, second)
    assert first == before
    assert len(result["nodes"]) == 10
    assert len(result["edges"]) == 8
    assert result["source_url"] == first["source_url"]
    assert all(n in result["nodes"] for n in first["nodes"])
    assert {
        n["properties"]["description"]
        for n in result["nodes"]
        if n["type"] == "Concept"
    } == {"Source-specific concept", "Different source interpretation"}
    manage.check(result)


def test_update_same_study_replaces_stale_nodes_without_duplicates():
    first, second = graph(), graph("PSI-2")
    merged = manage.merge(first, second)
    changed = graph("PSI-2", "Updated description")
    changed["nodes"][-1]["properties"]["filename"] = "revised.csv"
    result = manage.merge(merged, changed)
    repeat = manage.merge(result, changed)
    assert result["nodes"] == repeat["nodes"]
    assert result["edges"] == repeat["edges"]
    assert len(result["nodes"]) == 10
    assert all(n in result["nodes"] for n in first["nodes"])
    assert (
        next(n for n in result["nodes"] if n["id"] == "res:PSI-2:data")["properties"][
            "filename"
        ]
        == "revised.csv"
    )


def test_publication_backup_and_concurrent_change(tmp_path):
    target = tmp_path / "graph.json"
    write_json(target, graph())
    original = target.read_bytes()
    manage.publish(target, manage.merge(graph(), graph("PSI-2")), original)
    assert next((tmp_path / "backups").glob("*.json")).read_bytes() == original
    published = target.read_bytes()
    with pytest.raises(RuntimeError, match="changed"):
        manage.publish(target, graph(), original)
    assert target.read_bytes() == published
    with pytest.raises(RuntimeError, match="changed"):
        manage.publish(target, graph(), None)


def fake_pipeline(command, check):
    assert check is True
    assert "--reviewed-bundle" not in command
    output = Path(command[command.index("--output") + 1])
    accession = command[3].rsplit("/", 1)[-1]
    write_json(output / accession / "knowledge_graph.json", graph(accession))


@pytest.mark.parametrize("choice", ["1", "2"])
def test_interactive_modes_forward_provider_options(tmp_path, monkeypatch, choice):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "chosen.json"
    if choice == "1":
        write_json(target, graph())
    answers = iter([choice, graph("PSI-2")["source_url"], str(target)])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    monkeypatch.setattr(
        sys,
        "argv",
        ["psi-graph-manage", "--provider", "gemini", "--model", "test-model"],
    )
    calls = []

    def run(command, check):
        calls.append(command)
        fake_pipeline(command, check)

    monkeypatch.setattr(manage.subprocess, "run", run)
    assert manage.main() == 0
    result = read_json(target)
    assert sum(n["type"] == "Investigation" for n in result["nodes"]) == (
        2 if choice == "1" else 1
    )
    receipt = read_json(target.with_suffix(".publication.json"))
    assert receipt["graph_sha256"] == file_hash(target)
    assert calls[0][-4:] == ["--provider", "gemini", "--model", "test-model"]


def test_failed_pipeline_leaves_existing_graph_unchanged(tmp_path, monkeypatch):
    target = tmp_path / "graph.json"
    write_json(target, graph())
    before = target.read_bytes()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "manage",
            graph("PSI-2")["source_url"],
            "--mode",
            "update",
            "--graph",
            str(target),
            "--runs",
            str(tmp_path / "runs"),
        ],
    )

    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0])

    monkeypatch.setattr(manage.subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        manage.main()
    assert target.read_bytes() == before
    assert not target.with_suffix(".publication.json").exists()


@pytest.mark.parametrize("mode,exists", [("create", True), ("update", False)])
def test_invalid_target_rejected_before_processing(tmp_path, monkeypatch, mode, exists):
    target = tmp_path / "graph.json"
    if exists:
        write_json(target, graph())
    monkeypatch.setattr(
        sys,
        "argv",
        ["manage", graph()["source_url"], "--mode", mode, "--graph", str(target)],
    )
    monkeypatch.setattr(
        manage.subprocess, "run", lambda *a, **k: pytest.fail("Must not call pipeline")
    )
    with pytest.raises(SystemExit):
        manage.main()


def test_gemini_setup_checks_model_and_preserves_other_settings(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("OPENAI_API_KEY=preserve-me\nLLM_PROVIDER=openai\n")
    monkeypatch.setattr(setup_gemini.getpass, "getpass", lambda _: "fake-unit-test-key")
    monkeypatch.setattr("builtins.input", lambda _: "1")
    calls = []
    models = SimpleNamespace(
        list=lambda: [
            SimpleNamespace(
                name="models/test-model", supported_actions=["generateContent"]
            )
        ],
        generate_content=lambda **kwargs: (
            calls.append(kwargs) or SimpleNamespace(text='{"ok":true}')
        ),
    )
    monkeypatch.setattr(
        setup_gemini.genai,
        "Client",
        lambda **kwargs: SimpleNamespace(models=models, close=lambda: None),
    )
    setup_gemini.configure(path)
    values = dotenv_values(path)
    assert values["OPENAI_API_KEY"] == "preserve-me"
    assert values["LLM_PROVIDER"] == "gemini"
    assert values["LLM_MODEL"] == "test-model"
    assert values["GEMINI_API_KEY"] == "fake-unit-test-key"
    assert path.stat().st_mode & 0o777 == 0o600
    assert calls[0]["config"].response_mime_type == "application/json"


def test_failed_gemini_setup_redacts_error_and_keeps_config(
    tmp_path, monkeypatch, capsys
):
    path = tmp_path / ".env"
    path.write_text("LLM_PROVIDER=openai\n")
    before = path.read_bytes()
    monkeypatch.setattr(sys, "argv", ["setup", "--env-file", str(path)])

    def fail(*args):
        raise RuntimeError("sensitive-key-in-error")

    monkeypatch.setattr(setup_gemini, "configure", fail)
    assert setup_gemini.main() == 1
    assert "sensitive-key" not in capsys.readouterr().out
    assert path.read_bytes() == before


def test_combined_retrieval_finds_both_studies():
    from psi_graph.retrieval import search

    combined = manage.merge(graph(), graph("PSI-2"))
    matches = search(combined, "temperature")
    assert {e["node"]["id"] for e in matches["experiments"]} == {
        "exp:PSI-1:study",
        "exp:PSI-2:study",
    }
    assert all(e["resources"][0]["source_url"] for e in matches["experiments"])


def test_missing_api_configuration_fails_before_download(tmp_path, monkeypatch):
    from psi_graph import pipeline

    monkeypatch.setattr(
        sys, "argv", ["psi-graph", graph()["source_url"], "--output", str(tmp_path)]
    )

    def missing(*args):
        raise RuntimeError("Missing credential")

    monkeypatch.setattr(pipeline, "LLM", missing)
    monkeypatch.setattr(
        pipeline,
        "discover",
        lambda *args: pytest.fail("Must check configuration before NASA downloads"),
    )
    with pytest.raises(RuntimeError, match="Missing credential"):
        pipeline.main()
