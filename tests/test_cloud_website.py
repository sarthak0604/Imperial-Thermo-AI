"""Verify Cloud Run website command construction without calling Google Cloud."""

from pathlib import Path
from unittest.mock import patch

import pytest

from imperial_thermo_ai.cloud_website import main

ROOT = Path(__file__).resolve().parents[1]


def test_api_requires_secret(monkeypatch):
    monkeypatch.chdir(ROOT)
    with pytest.raises(SystemExit) as error:
        main(["--planner", "api", "--dry-run"])
    assert error.value.code == 2


def test_public_service_command(monkeypatch):
    monkeypatch.chdir(ROOT)
    with (
        patch(
            "imperial_thermo_ai.cloud_website.shutil.which", return_value="/bin/gcloud"
        ),
        patch("imperial_thermo_ai.cloud_website.subprocess.run") as run,
    ):
        run.return_value.returncode = 0
        assert (
            main(
                [
                    "--planner",
                    "api",
                    "--project",
                    "demo",
                    "--api-key-secret",
                    "key:1",
                    "--public",
                ]
            )
            == 0
        )
    command = run.call_args.args[0]
    assert command[1:4] == ["run", "deploy", "imperial-thermo-website"]
    assert "--set-secrets=OPENAI_API_KEY=key:1" in command
    assert "--args=/app/frontend/standin/server.py" in command
    assert "--allow-unauthenticated" in command
    assert "--max=1" in command
    assert "--scaling=auto" in command
    assert any("HOST=0.0.0.0" in arg for arg in command)


def test_retrieval_dry_run_is_private(monkeypatch, capsys):
    monkeypatch.chdir(ROOT)
    with patch("imperial_thermo_ai.cloud_website.subprocess.run") as run:
        assert main(["--planner", "retrieval", "--dry-run"]) == 0
        run.assert_not_called()
    output = capsys.readouterr().out
    assert "--no-allow-unauthenticated" in output
    assert "THERMO_PLANNER=retrieval" in output
    assert "--set-secrets" not in output


def test_default_is_self_hosted_qwen(monkeypatch, capsys):
    monkeypatch.chdir(ROOT)
    with patch("imperial_thermo_ai.cloud_website.subprocess.run") as run:
        assert main(["--dry-run", "--public"]) == 0
        run.assert_not_called()
    output = capsys.readouterr().out
    assert "THERMO_PLANNER=local" in output
    assert "PSI_PARSER_MODEL=Qwen/Qwen3-4B-Instruct-2507" in output
    assert "--gpu-type=nvidia-l4" in output
    assert "--memory=16Gi" in output
    assert "--no-cpu-throttling" in output
    assert "--concurrency=8" in output
    assert "--set-secrets" not in output


def test_gpu_source_uses_filtered_files(tmp_path):
    from imperial_thermo_ai.cloud_website import prepare_gpu_source

    root = tmp_path / "repo"
    stage = tmp_path / "stage"
    root.mkdir()
    stage.mkdir()
    (root / "Dockerfile").write_text("FROM python:3.14-slim\n")
    for name in (".dockerignore", ".gcloudignore"):
        (root / name).write_text("*\n!Dockerfile\n")
    (root / ".env").write_text("DO_NOT_UPLOAD=true")
    with patch("imperial_thermo_ai.cloud_website.subprocess.run") as run:
        run.return_value.stdout = "Dockerfile\n"
        prepare_gpu_source(root, stage, "gcloud", "Qwen/Qwen3-4B-Instruct-2507")
    content = (stage / "Dockerfile").read_text()
    assert "--extra search" in content
    assert "snapshot_download" in content
    assert "HF_HUB_OFFLINE=1" in content
    assert not (stage / ".env").exists()
    assert (root / "Dockerfile").read_text() == "FROM python:3.14-slim\n"
