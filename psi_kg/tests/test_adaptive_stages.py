import json
from copy import deepcopy

import pytest

from psi_graph.graph import scientific_review
from psi_graph.local_model import LocalModelError, LocalOutputLimitError
from psi_graph.science import Review, Synthesis, synthesize


def record(number, caveats=None):
    return dict(
        document_id=f"doc-{number}",
        extraction=dict(
            studies=[], resources=[], caveats=caveats or [f"fact-{number}"]
        ),
    )


class OutputBudget:
    def __init__(self, max_items=2):
        self.max_items = max_items
        self.attempts = []
        self.successes = []

    def fits(self, *args):
        return True

    def call(self, stage, payload, schema):
        self.attempts.append(deepcopy(payload))
        if schema is Review:
            count = len(payload["items"])
        else:
            count = sum(
                len(r["extraction"][field])
                for r in payload["extractions"]
                for field in ("studies", "resources", "caveats")
            )
        if count > self.max_items:
            raise LocalOutputLimitError("Output was truncated")
        self.successes.append(deepcopy(payload))
        if schema is Review:
            return Review(
                verdicts=[
                    dict(id=item["id"], supported=True, reason="Supported")
                    for item in payload["items"]
                ]
            )
        return Synthesis(
            investigation_summary="Summary",
            investigation_keywords=[],
            investigation_evidence=[],
            studies=[],
            resources=[],
            caveats=[
                c for r in payload["extractions"] for c in r["extraction"]["caveats"]
            ],
        )


def test_synthesis_output_limit_splits_and_preserves_every_record(tmp_path):
    client = OutputBudget(2)
    records = [record(n) for n in range(7)]
    original = deepcopy(records)
    result = synthesize(client, records, [], {}, tmp_path)
    assert all(f"fact-{n}" in result.caveats for n in range(7))
    assert [r["document_id"] for p in client.successes for r in p["extractions"]] == [
        f"doc-{n}" for n in range(7)
    ]
    assert len(client.attempts) < 2 * len(records)
    checkpoints = json.loads((tmp_path / "synthesis_batches.json").read_text())
    assert len(checkpoints) == len(client.successes)
    assert records == original


def test_synthesis_single_record_can_split_into_whole_scientific_items(tmp_path):
    client = OutputBudget(1)
    result = synthesize(client, [record(0, ["one", "two", "three"])], [], {}, tmp_path)
    assert all(c in result.caveats for c in ("one", "two", "three"))
    assert len(client.successes) == 3
    assert all(len(p["extractions"]) == 1 for p in client.successes)


def test_synthesis_indivisible_output_limit_fails_once_without_truncated_checkpoint(
    tmp_path,
):
    client = OutputBudget(0)
    with pytest.raises(LocalOutputLimitError, match="single synthesize record"):
        synthesize(client, [record(0)], [], {}, tmp_path)
    assert len(client.attempts) == 1
    assert client.successes == []
    assert not (tmp_path / "synthesis.json").exists()
    assert not (tmp_path / "synthesis_batches.json").exists()


def review_graph(count):
    return dict(
        nodes=[
            dict(id=f"exp-{n}", type="Experiment", properties=dict(title=f"Study {n}"))
            for n in range(count)
        ],
        edges=[],
    )


def test_review_output_limit_splits_without_skipping_items_and_keeps_scope(tmp_path):
    client = OutputBudget(2)
    result = scientific_review(client, review_graph(7), {}, [], tmp_path)
    assert [v["id"] for v in result] == [f"exp-{n}" for n in range(7)]
    assert all(v["supported"] for v in result)
    assert [i["id"] for p in client.successes for i in p["items"]] == [
        f"exp-{n}" for n in range(7)
    ]
    assert len(client.attempts) < 14
    scope = json.loads((tmp_path / "scientific_review_scope.json").read_text())
    assert scope["complete"] is True
    assert scope["reviewed_items"] == 7


def test_review_indivisible_output_limit_fails_without_false_completion(tmp_path):
    client = OutputBudget(0)
    with pytest.raises(LocalOutputLimitError, match="single scientific_review record"):
        scientific_review(client, review_graph(1), {}, [], tmp_path)
    assert len(client.attempts) == 1
    assert not (tmp_path / "scientific_review.json").exists()
    scope = json.loads((tmp_path / "scientific_review_scope.json").read_text())
    assert scope["complete"] is False
    assert scope["reviewed_items"] == 0


def test_non_output_model_failures_do_not_retry_or_split(tmp_path):
    class Failure(OutputBudget):
        def call(self, stage, payload, schema):
            self.attempts.append(payload)
            raise LocalModelError("GPU unavailable")

    client = Failure()
    with pytest.raises(LocalModelError, match="GPU unavailable"):
        synthesize(client, [record(n) for n in range(7)], [], {}, tmp_path)
    assert len(client.attempts) == 1


def test_synthesis_rebudgets_wrapper_overhead_after_output_limited_atomization(
    tmp_path,
):
    class InputAndOutputBudget(OutputBudget):
        def fits(self, stage, payload, schema):
            # Repeated record metadata dominates a multi-record request. The
            # original one-record/four-fact payload fits, but two atoms do not.
            return len(json.dumps(payload)) < 2100

        def call(self, stage, payload, schema):
            assert self.fits(stage, payload, schema), (
                "Oversized child reached inference"
            )
            return super().call(stage, payload, schema)

    client = InputAndOutputBudget(2)
    item = record(0, ["one", "two", "three", "four"])
    item["document_id"] = "document-" + "x" * 750
    result = synthesize(client, [item], [], {}, tmp_path)
    assert all(value in result.caveats for value in ("one", "two", "three", "four"))
    assert len(client.attempts) == 5  # Original output failure, then four safe atoms.
    assert len(client.successes) == 4
    assert all(len(p["extractions"]) == 1 for p in client.successes)


def test_adaptive_calls_reject_initial_atomic_input_before_generation():
    from psi_graph.synthesis_batches import adaptive_calls

    class TooLarge(OutputBudget):
        def fits(self, *args):
            return False

    client = TooLarge()
    with pytest.raises(LocalModelError, match="single scientific_review record"):
        list(
            adaptive_calls(
                client,
                "scientific_review",
                [[{"id": "one"}]],
                lambda items: {"items": items},
                Review,
            )
        )
    assert client.attempts == []
