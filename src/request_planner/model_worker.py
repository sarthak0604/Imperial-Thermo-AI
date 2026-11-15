"""Warm local inference process with a hard deadline covering loading and generation."""

import atexit
import json
import selectors
import subprocess
import sys
import time
from threading import Lock


class InferenceError(ValueError):
    """Inference failure rather than absent scientific evidence."""


class ModelWorker:
    def __init__(self, model_id=None):
        self.model_id = model_id
        self.process = None
        self.lock = Lock()
        atexit.register(self.close)

    def close(self):
        if self.process is not None:
            self.process.kill()
            self.process.wait()
            self.process.stdin.close()
            self.process.stdout.close()
            self.process = None

    def generate(self, messages, *, max_time=90):
        budget = 90 if max_time is None else max_time
        deadline = time.monotonic() + budget
        if not self.lock.acquire(timeout=max(0, budget)):
            raise InferenceError("Local inference queue deadline exceeded.")
        try:
            if self.process is None or self.process.poll() is not None:
                self.close()
                self.process = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "request_planner.model_worker",
                        self.model_id or "",
                    ],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    bufsize=1,
                )
            self.process.stdin.write(
                json.dumps(
                    {
                        "messages": messages,
                        "max_time": max(0.1, deadline - time.monotonic()),
                    }
                )
                + "\n"
            )
            self.process.stdin.flush()
            with selectors.DefaultSelector() as selector:
                selector.register(self.process.stdout, selectors.EVENT_READ)
                if not selector.select(max(0, deadline - time.monotonic())):
                    self.close()
                    raise InferenceError(
                        "Local inference deadline exceeded, including model loading."
                    )
                line = self.process.stdout.readline(4_000_000)
            if not line:
                self.close()
                raise InferenceError(
                    "Local inference worker stopped. Check model cache and inference dependencies."
                )
            result = json.loads(line)
            if "error" in result:
                raise InferenceError(result["error"])
            return result["text"]
        finally:
            self.lock.release()


def main():
    from imperial_thermo_ai.parser import QuestionParser

    protocol = sys.stdout
    sys.stdout = sys.stderr
    model = QuestionParser(model_id=sys.argv[1] or None)
    for line in sys.stdin:
        try:
            request = json.loads(line)
            result = {
                "text": model.generate(
                    request["messages"], max_time=request["max_time"]
                )
            }
        except (ImportError, OSError, RuntimeError, ValueError, TypeError) as exc:
            result = {
                "error": f"{type(exc).__name__}: local model could not process this request."
            }
        protocol.write(json.dumps(result) + "\n")
        protocol.flush()


if __name__ == "__main__":
    main()
