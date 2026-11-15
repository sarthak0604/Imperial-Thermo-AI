import json
from types import SimpleNamespace

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from psi_graph import cloud_auto, local_model, science
from psi_graph.local_model import (
    DEFAULT_MODEL,
    LocalModel,
    LocalModelError,
    validate_json,
)
from psi_graph.providers import LLM


class Result(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str


def test_local_provider_needs_no_key_or_api(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(
        local_model,
        "LocalModel",
        lambda model: SimpleNamespace(
            generate=lambda *a: (calls.append(model) or Result(value="local"), {}),
            fits=lambda *a: True,
        ),
    )
    for name in (
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "LLM_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    client = LLM(tmp_path, "local", DEFAULT_MODEL)
    monkeypatch.setattr(client, "post", lambda *a: pytest.fail("Must not use an API"))
    assert client.call("extract", {}, Result).value == "local"
    assert client.call("extract", {}, Result).value == "local"
    assert calls == [DEFAULT_MODEL]
    assert client.key is None


def test_local_repair_is_bounded_and_validated():
    client = LocalModel.__new__(LocalModel)
    client.device = "cpu"
    replies = iter(['{"wrong":"x"}', '{"value":"fixed"}'])
    calls = []

    def complete(messages):
        calls.append(list(messages))
        return next(replies), {"input_tokens": 2, "output_tokens": 1}

    client.complete = complete
    result, usage = client.generate("Source-only", "Source", Result)
    assert result.value == "fixed"
    assert usage["repair_attempts"] == 1
    assert usage["input_tokens"] == 4
    assert len(calls) == 2
    assert "Validation errors" in calls[1][-1]["content"]
    client.complete = lambda _: (
        '{"wrong":"x"}',
        {"input_tokens": 2, "output_tokens": 1},
    )
    with pytest.raises(LocalModelError, match="after one repair"):
        client.generate("Source-only", "Source", Result)


def test_partial_json_is_never_salvaged():
    assert validate_json('```json\n{"value":"ok"}\n```', Result).value == "ok"
    with pytest.raises(ValidationError):
        validate_json('{"value":"ok"', Result)
    with pytest.raises(ValidationError):
        validate_json('{"value":"ok", "invented":true}', Result)


def test_context_overflow_does_not_truncate_or_generate():
    client = LocalModel.__new__(LocalModel)
    client.context_tokens = 10
    client.max_new_tokens = 4
    client.model = SimpleNamespace(device="cpu")

    class Inputs(dict):
        def to(self, _):
            return self

    client.tokenizer = SimpleNamespace(
        apply_chat_template=lambda *a, **k: Inputs(
            input_ids=SimpleNamespace(shape=[1, 8])
        )
    )
    client.load = lambda: None
    with pytest.raises(LocalModelError, match="No source text was truncated"):
        client.complete([])


def test_local_failure_stops_source_processing(tmp_path):
    def call(*a):
        raise LocalModelError("Capacity exceeded")

    doc = {
        "id": "doc",
        "title": "Source",
        "resource_type": "paper",
        "sections": [{"locator": "page 1", "text": "Scientific source"}],
    }
    with pytest.raises(LocalModelError):
        science.extract_all(SimpleNamespace(call=call), [doc], [], tmp_path)
    failures = json.loads((tmp_path / "extraction_failures.json").read_text())
    assert failures[0]["issue"] == "Capacity exceeded"


def test_cloud_local_preview_has_no_api_secrets(monkeypatch, capsys):
    monkeypatch.setattr(
        local_model,
        "LocalModel",
        lambda *a, **k: pytest.fail(
            "Cloud launcher must not load/download model weights on this computer"
        ),
    )
    monkeypatch.setattr(cloud_auto.shutil, "which", lambda _: "gcloud")
    monkeypatch.setattr(cloud_auto, "project_setting", lambda *a: None)
    monkeypatch.setattr(cloud_auto, "load_dotenv", lambda *a, **k: None)
    for name in ("LLM_MODEL", "GEMINI_MODEL", "LLM_PROVIDER"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(
        "builtins.input", lambda _: pytest.fail("No credential prompts")
    )
    assert (
        cloud_auto.main(
            [
                "--file",
                "cloud_pipeline.py",
                "--project",
                "test",
                "--provider",
                "local",
                "--mode",
                "create",
                "--graph",
                "qwen.json",
                "--url",
                "PSI-117",
                "--dry-run",
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert DEFAULT_MODEL in output
    assert "--clear-secrets" in output and "--set-secrets" not in output
    assert "--memory 32Gi" in output and "--cpu 8" in output
    assert "name=scratch,type=ephemeral-disk,size=10Gi" in output
    assert '"HF_HOME": "/data/.huggingface"' in output
    assert '"LLM_DEVICE": "cuda"' in output
    assert "--gpu=1" in output and "--gpu-type=nvidia-l4" in output
    assert "--no-gpu-zonal-redundancy" in output
    assert "--task-timeout=12h" in output
    assert "gcloud beta run jobs deploy" in output
    assert "--gpu=0" not in output


def test_local_provision_skips_secret_manager(monkeypatch):
    calls = []
    monkeypatch.setattr(
        cloud_auto, "run", lambda command, **k: calls.append(command) or ""
    )
    monkeypatch.setattr(cloud_auto, "exists", lambda _: False)
    account, version = cloud_auto.provision(
        "gcloud", "test", "region", "bucket", None, None
    )
    assert account.startswith("psi-kg-runner@") and version is None
    assert not any(
        "secretmanager.googleapis.com" in cmd or "secrets" in cmd for cmd in calls
    )


def test_report_identifies_local_model_without_api_calls(tmp_path):
    from psi_graph.pipeline import report

    report(
        tmp_path,
        {"source_url": "https://example.test"},
        [],
        {
            "passed": True,
            "nodes": 0,
            "edges": 0,
            "node_counts": {},
            "edge_counts": {},
            "errors": [],
        },
        [],
        [],
        [],
        [],
        provider="local",
        model=DEFAULT_MODEL,
    )
    data = json.loads((tmp_path / "validation_report.json").read_text())
    assert data["extraction_mode"] == "local_model"
    assert data["external_llm_api_calls"] == 0
    assert data["model_execution"] == {"provider": "local", "model": DEFAULT_MODEL}


@pytest.mark.parametrize("available", [False, True])
def test_explicit_cuda_never_falls_back_to_cpu(monkeypatch, capsys, available):
    import sys

    torch = SimpleNamespace(
        cuda=SimpleNamespace(
            is_available=lambda: available,
            get_device_properties=lambda _: SimpleNamespace(
                name="NVIDIA L4", total_memory=24 * 1024**3
            ),
        ),
        version=SimpleNamespace(cuda="13.0"),
    )
    for name, module in (
        ("torch", torch),
        ("accelerate", SimpleNamespace()),
        ("transformers", SimpleNamespace()),
    ):
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setenv("LLM_DEVICE", "cuda")
    monkeypatch.delenv("LLM_CONTEXT_TOKENS", raising=False)
    monkeypatch.delenv("LLM_MAX_NEW_TOKENS", raising=False)
    if available:
        assert LocalModel().device == "cuda"
        assert "CUDA ready: NVIDIA L4" in capsys.readouterr().out
    else:
        with pytest.raises(LocalModelError, match="CPU fallback is disabled"):
            LocalModel()


@pytest.mark.parametrize("provider,gpu", [("local", "none"), ("gemini", "auto")])
def test_cpu_and_remote_api_launches_do_not_allocate_gpu(
    monkeypatch, capsys, provider, gpu
):
    monkeypatch.setattr(cloud_auto.shutil, "which", lambda _: "gcloud")
    monkeypatch.setattr(cloud_auto, "load_dotenv", lambda *a, **k: None)
    assert (
        cloud_auto.main(
            [
                "--file",
                "cloud_pipeline.py",
                "--project",
                "test",
                "--region",
                "europe-west1",
                "--provider",
                provider,
                "--model",
                "test",
                "--gpu",
                gpu,
                "--mode",
                "create",
                "--graph",
                "test.json",
                "--url",
                "PSI-117",
                "--dry-run",
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "--gpu=0" in output and "--gpu-type" not in output
    assert "--task-timeout=168h" in output
    assert "gcloud beta" not in output
    assert '"LLM_DEVICE": "cuda"' not in output
    if provider == "local":
        assert '"LLM_DEVICE": "cpu"' in output


@pytest.mark.parametrize(
    "options",
    [
        ["--cpu", "2"],
        ["--memory", "8Gi"],
        ["--memory", "invalid"],
        ["--provider", "gemini", "--gpu", "l4"],
    ],
)
def test_invalid_gpu_configuration_stops_before_provision(monkeypatch, options):
    monkeypatch.setattr(cloud_auto.shutil, "which", lambda _: "gcloud")
    monkeypatch.setattr(cloud_auto, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr(
        cloud_auto,
        "provision",
        lambda *a, **k: pytest.fail("Invalid GPU settings must not provision"),
    )
    with pytest.raises(SystemExit):
        cloud_auto.main(
            [
                "--file",
                "cloud_pipeline.py",
                "--project",
                "test",
                "--region",
                "europe-west1",
                "--provider",
                "local",
                "--model",
                "test",
                "--mode",
                "create",
                "--graph",
                "test.json",
                "--url",
                "PSI-117",
                "--dry-run",
                *options,
            ]
        )


def test_bundled_model_uses_image_snapshot_without_runtime_download(
    tmp_path, monkeypatch
):
    (tmp_path / "config.json").write_text("{}")
    monkeypatch.setenv("LLM_BUNDLED_MODEL_ID", DEFAULT_MODEL)
    monkeypatch.setenv("LLM_BUNDLED_MODEL_PATH", str(tmp_path))
    monkeypatch.setenv("LLM_LOCAL_FILES_ONLY", "0")
    assert local_model.model_source(DEFAULT_MODEL) == (str(tmp_path), True)
    assert local_model.model_source("other/model") == ("other/model", False)
    (tmp_path / "config.json").unlink()
    with pytest.raises(LocalModelError, match="Bundled model is missing"):
        local_model.model_source(DEFAULT_MODEL)


def test_local_machine_preserves_normal_model_resolution(monkeypatch):
    monkeypatch.delenv("LLM_BUNDLED_MODEL_ID", raising=False)
    monkeypatch.setenv("LLM_LOCAL_FILES_ONLY", "1")
    assert local_model.model_source(DEFAULT_MODEL) == (DEFAULT_MODEL, True)


def test_gpu_retry_reuses_built_image_without_source_build(monkeypatch, capsys):
    monkeypatch.setattr(cloud_auto.shutil, "which", lambda _: "gcloud")
    monkeypatch.setattr(cloud_auto, "load_dotenv", lambda *a, **k: None)
    image = "europe-west1-docker.pkg.dev/project/repo/image@sha256:" + "a" * 64
    assert (
        cloud_auto.main(
            [
                "--file",
                "cloud_pipeline.py",
                "--project",
                "test",
                "--region",
                "europe-west1",
                "--provider",
                "local",
                "--model",
                DEFAULT_MODEL,
                "--image",
                image,
                "--mode",
                "create",
                "--graph",
                "test.json",
                "--url",
                "PSI-117",
                "--dry-run",
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "gcloud beta run jobs deploy" in output
    assert "--image " + image in output
    assert "--source" not in output
    assert "--task-timeout=12h" in output
