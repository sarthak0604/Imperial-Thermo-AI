"""The page sends the figures it generated for a question; the server must offer only those (and the fixed charts)."""
import json, sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "standin"))
import server  # noqa: E402

FIGS = [{"id": "fabc_spread", "title": "Flame spread", "model": "THM-05", "shows": "Mars: 1.76 mm/s", "built_on": ["PSI-25", "PSI-999"]},
        {"id": "bad id!", "title": "x"}]


class Figures(unittest.TestCase):
    def test_prompt_lists_generated_figures(self):
        sys_prompt = server.build_messages("How fast on Mars?", "student", "mars", [], FIGS)[0]["content"]
        self.assertIn("fabc_spread", sys_prompt)
        self.assertIn("DEMO data", sys_prompt)
        self.assertNotIn("bad id", sys_prompt)

    def test_mars_scenario_reaches_the_ai(self):
        self.assertIn("Mars surface habitat", server.build_messages("q", None, "mars", [], FIGS)[-1]["content"])

    def test_points_keep_figure_ids(self):
        raw = json.dumps({"title": "t", "summary": "s", "points": [{"text": "a", "psi_ids": ["PSI-25"], "charts": ["fabc_spread", "thm05_spread", "nope"]}]})
        out = server.parse_and_check(raw, FIGS)
        self.assertEqual(out["points"][0]["charts"], ["fabc_spread", "thm05_spread"])
        self.assertIn("chart nope", out["dropped"])


if __name__ == "__main__":
    unittest.main()
