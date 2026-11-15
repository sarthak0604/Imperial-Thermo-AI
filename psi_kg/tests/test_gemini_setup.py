from types import SimpleNamespace

import pytest
from dotenv import dotenv_values
from google.genai.errors import APIError

from psi_graph import cloud_auto, setup_gemini


def fake_error(code, message):
    return APIError(
        code, {"error": {"code": code, "message": message, "status": "TEST"}}
    )


def fake_client(monkeypatch, generate, names=()):
    models = SimpleNamespace(
        list=lambda: [
            SimpleNamespace(name="models/" + n, supported_actions=["generateContent"])
            for n in names
        ],
        generate_content=generate,
    )
    client = SimpleNamespace(models=models, close=lambda: None)
    monkeypatch.setattr(setup_gemini.genai, "Client", lambda **kwargs: client)
    return client


def test_model_selection_filters_specialized_endpoints():
    names = [
        "antigravity-preview",
        "deep-research-pro",
        "gemma-4-31b-it",
        "gemini-2.5-flash-image",
        "gemini-3.8-live",
        "gemini-3.8-flash-tts",
        "gemini-2.5-flash",
        "gemini-3.6-flash",
        "gemini-3.8-flash",
    ]
    client = SimpleNamespace(
        models=SimpleNamespace(
            list=lambda: [
                SimpleNamespace(
                    name="models/" + n, supported_actions=["generateContent"]
                )
                for n in names
            ]
        )
    )
    assert setup_gemini.text_models(client) == [
        "gemini-3.8-flash",
        "gemini-3.6-flash",
        "gemini-2.5-flash",
    ]


def test_404_reselection_reuses_key_and_saves_success_only(
    tmp_path, monkeypatch, capsys
):
    key = "private-test-key"
    prompts = []
    monkeypatch.setattr(
        setup_gemini.getpass, "getpass", lambda p: prompts.append(p) or key
    )
    monkeypatch.setattr("builtins.input", lambda _: "gemini-3.6-flash")
    called = []

    def generate(**kwargs):
        called.append(kwargs["model"])
        if kwargs["model"] == "gemini-2.5-flash":
            raise fake_error(
                404,
                f"Not available to new users. key={key} https://example.test/?key={key}",
            )
        return SimpleNamespace(text='{"ok":true}')

    fake_client(monkeypatch, generate, ["gemini-2.5-flash", "gemini-3.6-flash"])
    config = tmp_path / ".env"
    setup_gemini.configure(config, "gemini-2.5-flash", show_next_step=False)
    assert called == ["gemini-2.5-flash", "gemini-3.6-flash"]
    assert len(prompts) == 1
    assert dotenv_values(config)["LLM_MODEL"] == "gemini-3.6-flash"
    output = capsys.readouterr().out
    assert "HTTP 404" in output
    assert key not in output
    assert "psi-graph-manage" not in output


def test_transient_failure_retries_are_bounded(monkeypatch):
    calls, waits = [], []

    def generate(**kwargs):
        calls.append(kwargs["model"])
        raise fake_error(503, "High demand")

    client = fake_client(monkeypatch, generate)
    monkeypatch.setattr(setup_gemini.time, "sleep", waits.append)
    with pytest.raises(APIError):
        setup_gemini.probe(client, "gemini-3.8-flash", "test-key")
    assert calls == ["gemini-3.8-flash"] * 3
    assert waits == [1, 2]


def test_transient_failure_can_recover(monkeypatch):
    count = []

    def generate(**kwargs):
        count.append(1)
        if len(count) == 1:
            raise fake_error(504, "Deadline expired")
        return SimpleNamespace(text='{"ok":true}')

    client = fake_client(monkeypatch, generate)
    monkeypatch.setattr(setup_gemini.time, "sleep", lambda _: None)
    setup_gemini.probe(client, "gemini-3.6-flash", "test-key")
    assert len(count) == 2


def test_quota_diagnostic_is_distinct_and_does_not_leak_secrets():
    key = "private-key"
    text = setup_gemini.safe_error(
        fake_error(429, f"Quota exhausted; api_key={key}"), "test-model", key
    )
    assert "HTTP 429" in text and "quota" in text.lower()
    assert key not in text
    assert "https://" not in text


def test_cloud_launcher_preserves_safe_setup_diagnostic(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        cloud_auto, "__file__", str(tmp_path / "psi_graph/cloud_auto.py")
    )
    (tmp_path / "cloud_pipeline.py").write_text("")
    monkeypatch.setattr(cloud_auto.shutil, "which", lambda _: "gcloud")
    monkeypatch.setattr(cloud_auto, "project_setting", lambda *a: "test")
    monkeypatch.setattr(cloud_auto, "check_billing", lambda *a: None)
    monkeypatch.setattr(cloud_auto, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    for name in ("LLM_MODEL", "GEMINI_MODEL", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    def fail(*a, **k):
        raise setup_gemini.GeminiSetupError("Gemini test: HTTP 404. Model unavailable.")

    monkeypatch.setattr(setup_gemini, "configure", fail)
    monkeypatch.setattr(
        cloud_auto, "provision", lambda *a, **k: pytest.fail("Must not provision")
    )
    with pytest.raises(SystemExit):
        cloud_auto.main(["--file", "cloud_pipeline.py"])
    assert "HTTP 404" in capsys.readouterr().err
