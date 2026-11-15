"""Build and run the current checkout as a Google Cloud Run job."""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

RESOURCE_DEFAULTS = {
    "none": (1, "2Gi"),
    "nvidia-l4": (4, "16Gi"),
    "nvidia-rtx-pro-6000": (20, "80Gi"),
}


def dispatch_knowledge_graph(argv):
    """Route the KG choice into its isolated uv project, preserving the old launcher."""
    forwarded = list(argv)
    selected = None
    for index, argument in enumerate(forwarded):
        if argument == "--file":
            if index + 1 >= len(forwarded):
                return None
            selected = forwarded[index + 1]
            del forwarded[index : index + 2]
            break
        if argument.startswith("--file="):
            selected = argument.split("=", 1)[1]
            del forwarded[index]
            break
    if not argv:
        selected = (
            input(
                "Python file [psi_kg/cloud_pipeline.py] "
                "(enter main for the previous application): "
            ).strip()
            or "psi_kg/cloud_pipeline.py"
        )
    if selected in ("main", "src/imperial_thermo_ai/main.py"):
        return None
    if selected is None:
        return None
    if selected.startswith("psi_kg/") or selected == "cloud_pipeline.py":
        root = Path(__file__).resolve().parents[2]
        entry = selected.removeprefix("psi_kg/")
        return subprocess.run(
            [
                shutil.which("uv") or "uv",
                "run",
                "--project",
                str(root / "psi_kg"),
                "google",
                "--file",
                entry,
                *forwarded,
            ],
            cwd=root / "psi_kg",
            env={k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"},
            check=False,
        ).returncode
    if not argv:
        sys.argv.extend(["--file", selected])
    return None


def main() -> int:
    dispatched = dispatch_knowledge_graph(sys.argv[1:])
    if dispatched is not None:
        return dispatched
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project", help="Google Cloud project (defaults to the active gcloud project)"
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("GOOGLE_CLOUD_REGION", "europe-west1"),
        help="Cloud Run region (default: GOOGLE_CLOUD_REGION or europe-west1)",
    )
    parser.add_argument(
        "--cpu", type=int, help="vCPUs per task (default depends on GPU)"
    )
    parser.add_argument(
        "--memory", metavar="SIZE", help="RAM per task, such as 8Gi or 512Mi"
    )
    parser.add_argument(
        "--gpu",
        choices=RESOURCE_DEFAULTS,
        default="none",
        help="GPU model to attach to each task (default: none)",
    )
    parser.add_argument(
        "--file",
        help="Python entry file: psi_kg/cloud_pipeline.py or a file under src/",
    )
    parser.add_argument("script_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    default_cpu, default_memory = RESOURCE_DEFAULTS[args.gpu]
    cpu = default_cpu if args.cpu is None else args.cpu
    memory = default_memory if args.memory is None else args.memory

    gcloud = shutil.which("gcloud")
    if gcloud is None:
        parser.error("Install the Google Cloud CLI and run gcloud auth login.")

    root = Path(__file__).resolve().parents[2]
    if not (root / "Dockerfile").is_file():
        parser.error("Run this command with uv from the repository checkout.")

    command = [
        gcloud,
        "run",
        "jobs",
        "deploy",
        "imperial-thermo-ai",
        "--source=.",
        f"--region={args.region}",
        f"--cpu={cpu}",
        f"--memory={memory}",
        "--max-retries=0",
        "--task-timeout=10m",
        "--wait",
        "--quiet",
    ]
    if args.gpu == "none":
        command.append("--gpu=0")
    else:
        command.extend(
            ["--gpu=1", f"--gpu-type={args.gpu}", "--no-gpu-zonal-redundancy"]
        )
    if args.project:
        command.append(f"--project={args.project}")

    if args.file and args.file != "main":
        selected = (root / args.file).resolve()
        if (
            not selected.is_relative_to(root / "src")
            or not selected.is_file()
            or selected.suffix != ".py"
        ):
            parser.error(
                "Application entry files must be .py files under src/; use psi_kg/cloud_pipeline.py for graph generation"
            )
        command.append("--command=/app/.venv/bin/python")
        forwarded = (
            args.script_args[1:] if args.script_args[:1] == ["--"] else args.script_args
        )
        values = ["/app/" + selected.relative_to(root).as_posix(), *forwarded]
        delimiter = "|"
        while any(delimiter in value for value in values):
            delimiter += "|"
        command.append("--args=^" + delimiter + "^" + delimiter.join(values))
    else:
        command.extend(["--command=/app/.venv/bin/main", "--args="])
    return subprocess.run(command, cwd=root, check=False).returncode
