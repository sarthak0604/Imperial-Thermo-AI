from pathlib import Path
from types import SimpleNamespace

import pytest
from dotenv import dotenv_values
from google.genai.errors import APIError

from psi_graph import science, setup_gemini
from psi_graph.common import read_json
from psi_graph.providers import LLM, QuotaExceededError


def test_quota_error_stops_without_retries_or_model_switch(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    client = LLM(tmp_path, "openai-compatible", "free-model", "https://example.test/v1")
    calls = []

    def generate(*args):
        calls.append(1)
        raise APIError(429, {"error": {"code": 429, "message": "Quota exhausted"}})

    monkeypatch.setattr(client, "generate", generate)
    monkeypatch.setattr(
        "psi_graph.providers.time.sleep",
        lambda _: pytest.fail("Quota should stop immediately"),
    )
    with pytest.raises(QuotaExceededError, match="HTTP 429"):
        client.call("extract", {"text": "test"}, science.Extraction)
    assert len(calls) == 1
    assert client.model == "free-model"


def test_extraction_does_not_continue_after_quota_exhaustion(tmp_path):
    calls = []

    def call(*args):
        calls.append(1)
        raise QuotaExceededError("HTTP 429; resume later")

    doc = {
        "id": "doc",
        "title": "Source",
        "source_url": "https://example.test",
        "resource_type": "paper",
        "sections": [{"locator": "page 1", "text": "Scientific text"}],
    }
    with pytest.raises(QuotaExceededError):
        science.extract_all(
            SimpleNamespace(call=call), [doc, {**doc, "id": "second"}], [], tmp_path
        )
    assert len(calls) == 1
    assert read_json(tmp_path / "extraction_failures.json")[0]["document_id"] == "doc"


def test_pacing_does_not_delay_cache_hits(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MIN_REQUEST_INTERVAL_SECONDS", "15")
    monkeypatch.setattr("psi_graph.providers.time.monotonic", lambda: 0)
    waits = []
    monkeypatch.setattr("psi_graph.providers.time.sleep", waits.append)
    client = LLM(tmp_path, "openai-compatible", "free-model", "https://example.test/v1")
    monkeypatch.setattr(
        client,
        "generate",
        lambda *a: (science.Extraction(studies=[], resources=[], caveats=[]), {}),
    )
    client.call("extract", {"text": "first"}, science.Extraction)
    client.call("extract", {"text": "first"}, science.Extraction)
    assert waits == []
    client.call("extract", {"text": "second"}, science.Extraction)
    assert waits == [15]


def test_flash_lite_is_preferred_and_example_has_no_credentials():
    names = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite"]
    client = SimpleNamespace(
        models=SimpleNamespace(
            list=lambda: [
                SimpleNamespace(
                    name="models/" + name, supported_actions=["generateContent"]
                )
                for name in names
            ]
        )
    )
    assert setup_gemini.text_models(client)[0] == "gemini-3.5-flash-lite"
    values = dotenv_values(Path(__file__).resolve().parents[1] / ".env.example")
    assert not any(value for name, value in values.items() if name.endswith("_API_KEY"))
