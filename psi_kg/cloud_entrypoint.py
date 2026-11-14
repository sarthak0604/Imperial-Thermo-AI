"""Container runner: chosen Python file runs on Cloud Run, using persistent /data."""

import json
import os
import runpy
import sys
from pathlib import Path

root = Path("/app")
script = (root / os.environ.get("PSI_ENTRY_FILE", "cloud_pipeline.py")).resolve()
if not script.is_relative_to(root) or script.suffix != ".py" or not script.is_file():
    raise ValueError(
        "Entry file must be a Python file inside the container /app directory"
    )
data = Path("/data")
if not data.is_mount():
    raise RuntimeError(
        "Persistent /data volume is missing; refusing to download onto container memory"
    )
lock = data / ".psi-job.lock"
try:
    lock.mkdir()
except FileExistsError:
    raise RuntimeError(
        "Another job owns /data/.psi-job.lock. If a previous job crashed, confirm it has stopped before removing this directory."
    ) from None
try:
    os.chdir(data)
    sys.argv = [str(script), *json.loads(os.environ.get("PSI_ENTRY_ARGS", "[]"))]
    runpy.run_path(str(script), run_name="__main__")
finally:
    lock.rmdir()
