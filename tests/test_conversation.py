import tempfile
import unittest
from pathlib import Path

from request_planner.context_resolution import resolve
from request_planner.conversation import ConversationError, ConversationStore
from request_planner.task_router import capabilities, route


class Conversations(unittest.TestCase):
    def test_isolation_revision_and_retry(self):
        with tempfile.TemporaryDirectory() as d:
            store = ConversationStore(Path(d) / "state.sqlite")
            cid, rev, state = store.load("alice")
            with self.assertRaises(ConversationError):
                store.load("bob", cid)
            store.commit("alice", cid, rev, state, "r1", {"answer": "ok"})
            self.assertEqual(store.cached("alice", cid, "r1"), {"answer": "ok"})
            with self.assertRaises(ConversationError):
                store.commit("alice", cid, rev, state, "r2", {})
            store.delete("alice", cid)
            with self.assertRaises(ConversationError):
                store.load("alice", cid)

    def test_historical_values_are_literal(self):
        state = {"turns": [{"q": "Compute at 300 K for methane"}]}
        r = resolve(
            "Same at 400 K",
            state,
            lambda _: (
                '{"continuation":true,"references":[{"turn":0,"quote":"for methane"}]}'
            ),
        )
        self.assertIn("for methane", r["question"])
        self.assertNotIn("300 K", r["question"])
        with self.assertRaises(ValueError):
            resolve(
                "Same at 400 K",
                state,
                lambda _: (
                    '{"continuation":true,"references":[{"turn":0,"quote":"for hydrogen"}]}'
                ),
            )

    def test_router_infers_without_id_and_validates(self):
        r = route("What is the Lewis number at 300 K?")
        self.assertEqual(r.model_ids, ["THM-02"])
        self.assertEqual(r.intent, "calculation")
        self.assertEqual(len(capabilities()), 20)
        with self.assertRaises(ValueError):
            route(
                "Calculate something",
                lambda _: '{"intent":"calculation","model_ids":["THM-99"]}',
            )

    def test_unknown_clarification_slot_rejected(self):
        with self.assertRaises(ValueError):
            resolve("30", {"turns": []}, answers=[{"slot_id": "invented", "value": 30}])

    def test_evidence_package_hash_and_actual_execution(self):
        import hashlib
        import json
        import os
        from unittest.mock import patch

        from request_planner.backend import answer
        from request_planner.evidence_packages import EvidencePackageRegistry

        source = (
            Path(__file__).resolve().parents[1]
            / "src/Functions/THM-05/THM-05_input.json"
        )
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            raw = source.read_bytes()
            (root / "payload.json").write_bytes(raw)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "packages": [
                            {
                                "id": "fixture",
                                "model_id": "THM-05",
                                "payload_path": "payload.json",
                                "sha256": hashlib.sha256(raw).hexdigest(),
                                "review_status": "approved",
                                "provenance": [
                                    {"note": "Test fixture, not NASA observations"}
                                ],
                                "illustrative": True,
                            }
                        ]
                    }
                )
            )
            with patch.dict(os.environ, {"THERMO_EVIDENCE_PACKAGES": str(manifest)}):
                result = answer(
                    "Calculate THM-05 using evidence package fixture unchanged"
                )
            self.assertEqual(result.status, "completed")
            self.assertTrue(result.result.blocks[0]["illustrative"])
            (root / "payload.json").write_text("{}")
            with self.assertRaises(ValueError):
                EvidencePackageRegistry(manifest).load("fixture", "THM-05")

    def test_result_explanation_rejects_unknown_numbers(self):
        from request_planner.composition import compose_results

        blocks = [
            {
                "type": "calculation",
                "model_id": "THM-01",
                "data": {"temperature": 2224.23},
            }
        ]
        good = compose_results(
            "Explain",
            blocks,
            lambda _: (
                '{"claims":[{"text":"Temperature is 2224 K","result_ids":["result-0"]}]}'
            ),
        )
        self.assertEqual(good[0]["source_type"], "computed_result")
        with self.assertRaises(ValueError):
            compose_results(
                "Explain",
                blocks,
                lambda _: (
                    '{"claims":[{"text":"Temperature is 5000 K","result_ids":["result-0"]}]}'
                ),
            )

    def test_clarification_reply_resumes_real_calculation(self):
        import json
        from unittest.mock import Mock, patch

        from request_planner.conversation import ask_conversation

        first = "Calculate THM-03 for CH4 with fuel mass fraction 1"
        generated = Mock(
            side_effect=[
                json.dumps(
                    {
                        "intent": "calculation",
                        "model_ids": ["THM-03"],
                        "missing": [
                            {
                                "id": "oxygen",
                                "question": "What oxidizer oxygen mass fraction should I use?",
                            }
                        ],
                    }
                ),
                json.dumps(
                    {"continuation": True, "references": [{"turn": 0, "quote": first}]}
                ),
                json.dumps({"intent": "calculation", "model_ids": ["THM-03"]}),
                json.dumps(
                    {
                        "steps": [
                            {
                                "id": "calculate",
                                "kind": "scenario",
                                "scenario": {
                                    "model_id": "THM-03",
                                    "params": {
                                        "fuel_formula": "CH4",
                                        "y_fuel_stream": 1,
                                        "y_ox_stream": 0.232,
                                    },
                                    "input_origins": {
                                        "fuel_formula": "user",
                                        "y_fuel_stream": "user",
                                        "y_ox_stream": "user",
                                    },
                                },
                                "input_source_spans": {
                                    "fuel_formula": "CH4",
                                    "y_fuel_stream": "fuel mass fraction 1",
                                    "y_ox_stream": "oxygen mass fraction 0.232",
                                },
                            }
                        ]
                    }
                ),
            ]
        )
        with (
            tempfile.TemporaryDirectory() as d,
            patch(
                "request_planner.providers.configure",
                return_value={"planner": None, "program_generator": generated},
            ),
        ):
            env = {"THERMO_CONVERSATION_DB": str(Path(d) / "session.sqlite")}
            one = ask_conversation(first, env, "owner", {"client_request_id": "one"})
            self.assertEqual(one["meta"]["conversation_state"], "awaiting_user")
            two = ask_conversation(
                "Use oxygen mass fraction 0.232",
                env,
                "owner",
                {
                    "client_request_id": "two",
                    "conversation_id": one["conversation_id"],
                    "expected_state_revision": one["state_revision"],
                },
            )
            self.assertEqual(two["meta"]["status"], "completed")
            self.assertEqual(two["blocks"][0]["model_id"], "THM-03")
            self.assertEqual(two["state_revision"], 2)
