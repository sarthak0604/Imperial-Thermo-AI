"""Run from frontend/:  python3 -m unittest tests/test_server_points.py"""
import json, sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "standin"))
import server


class PointsTests(unittest.TestCase):
    def test_points_cleaned(self):
        raw = json.dumps({"summary": "s", "points": [
            {"text": " a ", "psi_ids": ["psi-20", "PSI-999"], "charts": ["thm02_diluents", "zzz", "thm08_richardson", "thm01_flame_temp"]},
            {"text": "b", "charts": ["thm02_diluents", "thm07_blowoff"]}, {"text": ""}, "junk",
            {"text": "c"}, {"text": "d"}, {"text": "e"}, {"text": "f"}]})
        o = server.parse_and_check(raw)
        self.assertEqual(len(o["points"]), 5)
        self.assertEqual(o["points"][0], {"text": "a", "psi_ids": ["PSI-20"], "charts": ["thm02_diluents", "thm08_richardson"]})
        self.assertEqual(o["points"][1]["charts"], ["thm07_blowoff"])
        self.assertEqual([w["type"] for w in o["widgets"]], ["thm02_diluents", "thm08_richardson", "thm07_blowoff"])

    def test_prompt(self):
        msgs = server.build_messages("Is the Moon safer?", "student", "iss", [])
        self.assertLess(sum(len(m["content"]) for m in msgs), 22000)
        self.assertIn('"points"', msgs[0]["content"])
        self.assertNotIn("stage", msgs[0]["content"])


if __name__ == "__main__":
    unittest.main()
