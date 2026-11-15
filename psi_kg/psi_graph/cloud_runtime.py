"""Run an entry file on scratch disk, persist results, and atomically publish to GCS."""

import json
import os
import runpy
import sys
import uuid
from pathlib import Path
from urllib.parse import unquote

from .common import read_json


def rebase_uris(value, work, bucket, prefix):
    if isinstance(value, dict):
        return {k: rebase_uris(v, work, bucket, prefix) for k, v in value.items()}
    if isinstance(value, list):
        return [rebase_uris(v, work, bucket, prefix) for v in value]
    if isinstance(value, str) and value.startswith(work.as_uri() + "/"):
        return (
            "gs://"
            + bucket
            + "/"
            + prefix
            + "/"
            + unquote(value[len(work.as_uri()) + 1 :])
        )
    return value


def execute(bucket, work, script, arguments, graph_name="", mode="create", runner=None):
    from google.api_core.exceptions import NotFound

    runner = runner or (lambda: runpy.run_path(str(script), run_name="__main__"))
    prefix = "executions/" + uuid.uuid4().hex
    target = bucket.blob("graphs/" + graph_name) if graph_name else None
    generation = 0
    graph_path = work / "graphs" / graph_name if graph_name else None
    if target:
        try:
            target.reload()
            generation = int(target.generation)
        except NotFound:
            generation = 0
        if mode == "create" and generation:
            raise RuntimeError(
                "Cloud graph already exists; choose Update or a new filename"
            )
        if mode == "update" and not generation:
            raise RuntimeError("Cloud graph does not exist; choose Create first")
        if generation:
            graph_path.parent.mkdir(parents=True, exist_ok=True)
            graph_path.write_bytes(
                target.download_as_bytes(if_generation_match=generation)
            )
    previous_argv, previous_cwd = sys.argv, Path.cwd()
    code = 0
    try:
        os.chdir(work)
        sys.argv = [str(script), *arguments]
        try:
            runner()
        except SystemExit as error:
            code = (
                error.code
                if isinstance(error.code, int)
                else (0 if error.code is None else 1)
            )
            if code:
                raise RuntimeError(
                    f"Selected script exited with status {code}"
                ) from None
    finally:
        sys.argv = previous_argv
        os.chdir(previous_cwd)
        # Unique execution prefix: a failed job retains diagnostics, never replaces the current graph.
        for path in sorted(work.rglob("*")):
            relative = path.relative_to(work)
            if (
                path.is_symlink()
                or not path.is_file()
                or any(part.startswith(".") for part in relative.parts)
            ):
                continue
            blob = bucket.blob(prefix + "/" + relative.as_posix())
            if path.suffix == ".json":
                value = rebase_uris(read_json(path), work, bucket.name, prefix)
                blob.upload_from_string(
                    json.dumps(value, ensure_ascii=False),
                    content_type="application/json",
                    if_generation_match=0,
                )
            else:
                blob.upload_from_filename(str(path), if_generation_match=0)
        print(f"Execution artifacts: gs://{bucket.name}/{prefix}/", flush=True)
    if target:
        from .manage import check

        graph = rebase_uris(read_json(graph_path), work, bucket.name, prefix)
        check(graph)
        # Preserve the previous version independently of bucket versioning settings.
        if generation:
            bucket.blob(f"backups/{graph_name}/{generation}.json").upload_from_string(
                target.download_as_bytes(if_generation_match=generation),
                content_type="application/json",
            )
        target.upload_from_string(
            json.dumps(graph, ensure_ascii=False),
            content_type="application/json",
            if_generation_match=generation,
        )
        print(f"Published graph: gs://{bucket.name}/graphs/{graph_name}", flush=True)
    return code


def main():
    from google.cloud import storage

    root = Path("/app")
    work = Path("/data")
    script = (root / os.environ.get("PSI_ENTRY_FILE", "cloud_pipeline.py")).resolve()
    if (
        not script.is_relative_to(root)
        or script.suffix != ".py"
        or not script.is_file()
    ):
        raise ValueError("Entry file must be a Python file inside /app")
    if not work.is_mount():
        raise RuntimeError("Cloud scratch /data mount is missing")
    bucket = storage.Client().bucket(os.environ["PSI_BUCKET"])
    return execute(
        bucket,
        work,
        script,
        json.loads(os.environ.get("PSI_ENTRY_ARGS", "[]")),
        os.environ.get("PSI_GRAPH_NAME", ""),
        os.environ.get("PSI_GRAPH_MODE", "create"),
    )
