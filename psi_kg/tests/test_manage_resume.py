import subprocess
import sys
from pathlib import Path

import pytest
from test_manage import fake_pipeline, graph

from psi_graph import manage
from psi_graph.common import read_json, write_json


def arguments(tmp_path, *extra):
    return [
        "manage",
        "PSI-2",
        "PSI-3",
        "--mode",
        "create",
        "--provider",
        "local",
        "--model",
        "test-qwen",
        "--graph",
        str(tmp_path / "combined.json"),
        "--runs",
        str(tmp_path / "runs"),
        *extra,
    ]


def test_resume_reuses_failed_directory_skips_completed_and_publishes_progress(
    tmp_path, monkeypatch
):
    target = tmp_path / "combined.json"
    monkeypatch.setattr(sys, "argv", arguments(tmp_path))
    calls = []

    def fail_second(command, check):
        calls.append(command)
        if command[3].endswith("PSI-3"):
            receipt = read_json(target.with_suffix(".publication.json"))
            assert receipt["completed_studies"] == ["PSI-2"]
            assert receipt["pending_studies"] == ["PSI-3"]
            output = Path(command[command.index("--output") + 1]) / "PSI-3"
            write_json(output / "preparation_state.json", {"complete": True})
            raise subprocess.CalledProcessError(1, command)
        fake_pipeline(command, check)

    monkeypatch.setattr(manage.subprocess, "run", fail_second)
    with pytest.raises(subprocess.CalledProcessError):
        manage.main()
    failed_directory = calls[-1][calls[-1].index("--output") + 1]
    monkeypatch.setattr(sys, "argv", arguments(tmp_path, "--resume"))
    # Performance controls can be tuned without invalidating completed science.
    monkeypatch.setenv("LLM_INPUT_TOKENS", "16384")
    resumed = []

    def succeed(command, check):
        resumed.append(command)
        assert command[3].endswith("PSI-3")
        assert command[command.index("--output") + 1] == failed_directory
        assert command[-2:] == ["--stage", "generate"]
        fake_pipeline(command, check)

    monkeypatch.setattr(manage.subprocess, "run", succeed)
    assert manage.main() == 0
    assert len(resumed) == 1
    receipt = read_json(target.with_suffix(".publication.json"))
    assert receipt["complete"] is True
    assert receipt["pending_studies"] == []
    assert receipt["completed_studies"] == ["PSI-2", "PSI-3"]
    monkeypatch.setattr(
        manage.subprocess,
        "run",
        lambda *a, **k: pytest.fail("Complete session must not rerun"),
    )
    assert manage.main() == 0


@pytest.mark.parametrize("change", ["target", "artifact", "provider"])
def test_resume_rejects_changed_output_or_scientific_configuration(
    tmp_path, monkeypatch, change
):
    monkeypatch.setattr(sys, "argv", arguments(tmp_path))
    monkeypatch.setattr(manage.subprocess, "run", fake_pipeline)
    assert manage.main() == 0
    args = arguments(tmp_path, "--resume")
    target = tmp_path / "combined.json"
    if change == "target":
        target.write_text(target.read_text() + " ")
    elif change == "artifact":
        state = read_json(target.with_suffix(".run-state.json"))
        report = (
            Path(state["studies"][0]["run_directory"])
            / "PSI-2"
            / "validation_report.json"
        )
        report.write_text(report.read_text() + " ")
    else:
        args[args.index("--provider") + 1] = "gemini"
    monkeypatch.setattr(sys, "argv", args)
    monkeypatch.setattr(
        manage.subprocess, "run", lambda *a, **k: pytest.fail("Refuse before inference")
    )
    with pytest.raises((RuntimeError, SystemExit)):
        manage.main()


def test_resume_from_adopts_old_directory_but_reruns_old_graph(tmp_path, monkeypatch):
    source = tmp_path / "old-runs/PSI-2-old/PSI-2"
    write_json(source / "metadata.json", {"accession": "PSI-2"})
    write_json(source / "preparation_state.json", {"complete": True})
    write_json(source / "knowledge_graph.json", graph("PSI-2"))
    monkeypatch.setattr(sys, "argv", arguments(tmp_path, "--resume-from", str(source)))
    calls = []

    def run(command, check):
        calls.append(command)
        fake_pipeline(command, check)

    monkeypatch.setattr(manage.subprocess, "run", run)
    assert manage.main() == 0
    assert len(calls) == 2
    assert calls[0][calls[0].index("--output") + 1] == str(source.parent)
    assert calls[0][-2:] == ["--stage", "generate"]


def test_invalid_validation_is_never_published(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", arguments(tmp_path))

    def run(command, check):
        fake_pipeline(command, check)
        output = Path(command[command.index("--output") + 1]) / "PSI-2"
        write_json(
            output / "validation_report.json",
            {"structural_validation": {"passed": False}},
        )

    monkeypatch.setattr(manage.subprocess, "run", run)
    with pytest.raises(RuntimeError, match="passing validation"):
        manage.main()
    assert not (tmp_path / "combined.json").exists()


def test_target_lock_blocks_concurrent_managers(tmp_path, monkeypatch):
    lock = tmp_path / "combined.json.run-lock"
    lock.mkdir()
    monkeypatch.setattr(sys, "argv", arguments(tmp_path))
    monkeypatch.setattr(
        manage.subprocess, "run", lambda *a, **k: pytest.fail("No concurrent work")
    )
    with pytest.raises(RuntimeError, match="already running"):
        manage.main()
    assert lock.exists()


def test_resume_recovers_interruption_between_graph_and_receipt_write(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(sys, "argv", arguments(tmp_path))
    monkeypatch.setattr(manage.subprocess, "run", fake_pipeline)
    original = manage.write_json
    target = tmp_path / "combined.json"
    interrupted = False

    def write(path, value):
        nonlocal interrupted
        if Path(path) == target.with_suffix(".publication.json") and not interrupted:
            interrupted = True
            raise KeyboardInterrupt()
        original(path, value)

    monkeypatch.setattr(manage, "write_json", write)
    with pytest.raises(KeyboardInterrupt):
        manage.main()
    assert target.exists()
    assert not target.with_suffix(".publication.json").exists()
    monkeypatch.setattr(manage, "write_json", original)
    monkeypatch.setattr(sys, "argv", arguments(tmp_path, "--resume"))
    calls = []

    def run(command, check):
        calls.append(command[3])
        fake_pipeline(command, check)

    monkeypatch.setattr(manage.subprocess, "run", run)
    assert manage.main() == 0
    assert len(calls) == 1 and calls[0].endswith("PSI-3")
    assert read_json(target.with_suffix(".publication.json"))["complete"]
