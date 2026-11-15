"""Run from frontend/:  python3 -m unittest tests/test_server_claude.py   (uses a fake `claude` command; no real call)"""
import json, os, stat, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "standin"))
import server

FAKE = r'''#!/usr/bin/env python3
import sys, json, os
args = sys.argv[1:]; inp = sys.stdin.read()
sp = args[args.index("--system-prompt-file") + 1]
json.dump({"args": args, "cwd": os.getcwd(), "has_key": "ANTHROPIC_API_KEY" in os.environ, "stdin": inp, "sys": open(sp).read()[:50]}, open(os.environ["FAKE_LOG"], "w"))
if os.environ.get("FAKE_FAIL"):
    print(json.dumps({"type": "result", "is_error": True, "result": "Not logged in - Please run /login"})); sys.exit(1)
print(json.dumps({"type": "result", "is_error": False, "result": "```json\n" + json.dumps({"title": "t", "summary": "s", "points": [{"text": "p1", "psi_ids": ["PSI-25"], "charts": ["thm08_richardson"]}]}) + "\n```"}))
'''


class ClaudeProviderTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.bin = Path(self.d) / "claude"; self.bin.write_text(FAKE); self.bin.chmod(self.bin.stat().st_mode | stat.S_IEXEC)
        self.log = Path(self.d) / "log.json"
        os.environ["FAKE_LOG"] = str(self.log); os.environ["ANTHROPIC_API_KEY"] = "should-not-pass"
        os.environ.pop("FAKE_FAIL", None)

    def provider(self):
        p = server.pick_provider({"AI_PROVIDER": "claude", "CLAUDE_BIN": str(self.bin)})
        self.assertEqual((p["name"], p["model"], p["bin"]), ("claude", "haiku", str(self.bin)))
        return p

    def test_answer_goes_through_parse(self):
        raw = server.call_llm(self.provider(), server.build_messages("Moon flame?", "student", "iss", []))
        out = server.parse_and_check(raw)
        self.assertEqual(out["points"][0]["charts"], ["thm08_richardson"])
        log = json.loads(self.log.read_text())
        self.assertFalse(log["has_key"])                       # plan login, never API billing
        self.assertIn("--model", log["args"]); self.assertEqual(log["args"][log["args"].index("--tools") + 1], "")
        self.assertNotEqual(Path(log["cwd"]).resolve(), server.ROOT.resolve())   # not run inside the project
        self.assertIn("Question: Moon flame?", log["stdin"])

    def test_login_error_is_explained(self):
        os.environ["FAKE_FAIL"] = "1"
        with self.assertRaises(RuntimeError) as e:
            server.call_llm(self.provider(), server.build_messages("x", "student", "iss", []))
        self.assertIn("sign in", str(e.exception))

    def test_missing_cli(self):
        self.assertIsNone(server.pick_provider({"AI_PROVIDER": "claude", "CLAUDE_BIN": "/nope", "PATH": ""}) if not server.shutil.which("claude") else None)


if __name__ == "__main__":
    unittest.main()
