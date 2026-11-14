"""Run from frontend/:  python3 -m unittest tests/test_server_stage.py"""
import json, sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "standin"))
import server


def raw(stage):
    w = {"type": "thm02_diluents", "params": {}, "why": "w"}
    if stage != "MISSING":
        w["stage"] = stage
    return json.dumps({"title": "t", "summary": "s", "widgets": [w]})


class StageTests(unittest.TestCase):
    def test_valid_stage_kept(self):
        for s in ("context", "mechanism", "limits"):
            self.assertEqual(server.parse_and_check(raw(s))["widgets"][0]["stage"], s)

    def test_invalid_stage_dropped(self):
        for s in ("banana", 3, None, ["limits"], "MISSING"):
            out = server.parse_and_check(raw(s))["widgets"]
            self.assertEqual(len(out), 1)
            self.assertNotIn("stage", out[0])

    def test_prompt_stays_small(self):
        msgs = server.build_messages("Is the Moon safer?", "student", "iss", [])
        self.assertLess(sum(len(m["content"]) for m in msgs), 14200)

    def test_prompt_mentions_stage(self):
        system = server.build_messages("x", "student", "iss", [])[0]["content"]
        for word in ("stage", "context", "mechanism", "limits"):
            self.assertIn(word, system)


if __name__ == "__main__":
    unittest.main()
