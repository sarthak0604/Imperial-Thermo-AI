"""Run one registered calculation in a process the executor can terminate."""

import json
from pathlib import Path
import sys

from .function_registry import run_model


def main():
    source, destination = map(Path, sys.argv[1:3])
    try:
        task = json.loads(source.read_text())
        result = run_model(task["model_id"], task["payload"])
        content = json.dumps({"result": result}, allow_nan=False)
    except Exception as exc:
        content = json.dumps({"error": f"{type(exc).__name__}: {str(exc)[:500]}"})
    destination.write_text(content)


if __name__ == "__main__":
    main()
