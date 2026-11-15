"""Verify that busy GPU inference does not block ordinary HTTP requests."""

import importlib.util
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_old_claude_configuration_cannot_select_the_standin(monkeypatch):
    directory = ROOT / "NASA Space Apps/frontend/standin"
    monkeypatch.syspath_prepend(str(directory))
    spec = importlib.util.spec_from_file_location("website_provider_test", directory / "server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv("AI_PROVIDER", "claude")
    assert module.load_env()["AI_PROVIDER"] == "thermo"


def test_busy_question_is_json_and_health_still_works(monkeypatch):
    directory = ROOT / "NASA Space Apps/frontend/standin"
    monkeypatch.syspath_prepend(str(directory))
    spec = importlib.util.spec_from_file_location(
        "website_server_busy_test", directory / "server.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv("AI_PROVIDER", "thermo")
    monkeypatch.setenv("THERMO_PLANNER", "local")
    monkeypatch.setattr(module.thermo, "health", lambda env: {"ok": True})
    server = module.ThreadingHTTPServer(("127.0.0.1", 0), module.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    module.INFERENCE_SLOT.acquire()
    try:
        request = urllib.request.Request(
            base + "/api/ask",
            data=b'{"question":"test"}',
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(request, timeout=5)
            raise AssertionError("Expected busy response")
        except urllib.error.HTTPError as error:
            assert error.code == 503
            assert json.load(error)["code"] == "model_busy"
        with urllib.request.urlopen(base + "/api/health", timeout=5) as response:
            assert json.load(response)["ok"]
    finally:
        module.INFERENCE_SLOT.release()
        server.shutdown()
        server.server_close()
        thread.join()
    # A malformed request must also release the gate for the next request.
    handler = object.__new__(module.Handler)
    handler.path = "/api/ask"
    monkeypatch.setattr(handler, "_handle_post", lambda: "handled")
    assert handler.do_POST() == "handled"
    assert module.INFERENCE_SLOT.acquire(blocking=False)
    module.INFERENCE_SLOT.release()
