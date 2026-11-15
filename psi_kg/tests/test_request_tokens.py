"""The local request budget includes schema, system and chat-template tokens."""

import json
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from psi_graph import local_model
from psi_graph.local_model import DEFAULT_MODEL, LocalModel, LocalModelError
from psi_graph.providers import LLM
from psi_graph.science import SYSTEM


class Result(BaseModel):
    value: str


def test_fit_counts_exact_messages_with_schema_and_generation_template():
    client = LocalModel.__new__(LocalModel)
    client.input_tokens = 10000
    client.context_tokens = 262144
    client.max_new_tokens = 8192
    loaded = []
    client.load = lambda: loaded.append(True)
    observed = {}

    def tokenize(messages, **kwargs):
        observed.update(messages=messages, kwargs=kwargs)
        return [0] * (len(json.dumps(messages)) + 37)

    client.tokenizer = SimpleNamespace(apply_chat_template=tokenize)
    assert client.fits("Scientific source only", "ΔT = 3 K", Result)
    assert loaded == [True]
    assert observed["messages"][0]["role"] == "system"
    assert observed["messages"][0]["content"].startswith("Scientific source only")
    assert json.dumps(Result.model_json_schema()) in observed["messages"][0]["content"]
    assert observed["messages"][1] == {"role": "user", "content": "ΔT = 3 K"}
    assert observed["kwargs"] == {
        "return_dict": False,
        "tokenize": True,
        "add_generation_prompt": True,
        "enable_thinking": False,
    }
    exact_count = len(json.dumps(observed["messages"])) + 37
    client.input_tokens = exact_count
    assert client.fits("Scientific source only", "ΔT = 3 K", Result)
    client.input_tokens -= 1
    assert not client.fits("Scientific source only", "ΔT = 3 K", Result)


@pytest.mark.parametrize(
    "input_limit,context,output,count,expected",
    [
        (8192, 262144, 8192, 8192, True),
        (8192, 262144, 8192, 8193, False),
        (8192, 10000, 8192, 1808, True),
        (8192, 10000, 8192, 1809, False),
    ],
)
def test_fit_obeys_working_budget_and_total_context_reserve(
    input_limit, context, output, count, expected
):
    client = LocalModel.__new__(LocalModel)
    client.input_tokens = input_limit
    client.context_tokens = context
    client.max_new_tokens = output
    client.load = lambda: None
    client.tokenizer = SimpleNamespace(apply_chat_template=lambda *a, **k: [0] * count)

    assert client.fits("System", "Source", Result) is expected


def test_provider_budget_includes_stage_and_serialized_payload(monkeypatch, tmp_path):
    observed = []

    def fits(*args):
        observed.append(args)
        return True

    monkeypatch.setattr(local_model, "LocalModel", lambda _: SimpleNamespace(fits=fits))
    client = LLM(tmp_path, "local", DEFAULT_MODEL)
    payload = {"sections": [{"locator": "page 1", "text": "ΔT = 3 K"}]}
    assert client.fits("extract", payload, Result)

    system, prompt, schema = observed[0]
    assert system == SYSTEM
    assert prompt.startswith("STAGE: extract\n")
    assert json.dumps(payload, ensure_ascii=False) in prompt
    assert schema is Result


def test_provider_refuses_unsplit_request_before_inference(monkeypatch, tmp_path):
    monkeypatch.setattr(
        local_model,
        "LocalModel",
        lambda _: SimpleNamespace(
            fits=lambda *a: False,
            generate=lambda *a: pytest.fail(
                "Oversized request must not reach inference"
            ),
        ),
    )
    client = LLM(tmp_path, "local", DEFAULT_MODEL)

    with pytest.raises(LocalModelError, match="Unsplit extract request"):
        client.call("extract", {"sections": ["Huge source"]}, Result)

    assert client.last_request_at is None
    assert not list(tmp_path.rglob("*.json"))


def test_context_rejection_happens_before_moving_tokens_to_gpu():
    class Inputs(dict):
        def to(self, _):
            pytest.fail("Over-context input must stay off the GPU")

    client = LocalModel.__new__(LocalModel)
    client.context_tokens = 10
    client.max_new_tokens = 4
    client.load = lambda: None
    client.model = SimpleNamespace(device="cuda")
    client.tokenizer = SimpleNamespace(
        apply_chat_template=lambda *a, **k: Inputs(
            input_ids=SimpleNamespace(shape=(1, 8))
        )
    )

    with pytest.raises(LocalModelError, match="No source text was truncated"):
        client.complete([])


@pytest.mark.parametrize(
    "message_count,count,context,allowed,error",
    [
        (2, 100, 5000, True, None),
        (2, 101, 5000, False, "working budget"),
        (4, 1144, 5000, True, None),
        (4, 1145, 5000, False, "working budget"),
        (4, 1144, 1160, False, "LLM_CONTEXT_TOKENS"),
    ],
)
def test_initial_and_repair_working_guards_precede_gpu_transfer(
    message_count, count, context, allowed, error
):
    class ReachedGPU(Exception):
        """Stop the fake success path before inference or allocation."""

    moved = []

    class Inputs(dict):
        def to(self, device):
            moved.append(device)
            raise ReachedGPU

    client = LocalModel.__new__(LocalModel)
    client.input_tokens = 100
    client.max_new_tokens = 20
    client.context_tokens = context
    client.load = lambda: None
    client.model = SimpleNamespace(device="cuda")
    client.tokenizer = SimpleNamespace(
        apply_chat_template=lambda *a, **k: Inputs(
            input_ids=SimpleNamespace(shape=(1, count))
        )
    )
    messages = [{"role": "user", "content": "source"}] * message_count

    if allowed:
        with pytest.raises(ReachedGPU):
            client.complete(messages)
        assert moved == ["cuda"]
    else:
        with pytest.raises(LocalModelError, match=error):
            client.complete(messages)
        assert not moved
