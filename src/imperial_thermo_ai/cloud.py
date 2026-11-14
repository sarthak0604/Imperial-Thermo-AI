"""Build and run the current checkout as a Google Cloud Run job."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess


RESOURCE_DEFAULTS = {
    "none": (1, "2Gi"),
    "nvidia-l4": (4, "16Gi"),
    "nvidia-rtx-pro-6000": (20, "80Gi"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", help="Google Cloud project (defaults to the active gcloud project)")
    parser.add_argument(
        "--region",
        default=os.environ.get("GOOGLE_CLOUD_REGION", "europe-west1"),
        help="Cloud Run region (default: GOOGLE_CLOUD_REGION or europe-west1)",
    )
    parser.add_argument("--cpu", type=int, help="vCPUs per task (default depends on GPU)")
    parser.add_argument("--memory", metavar="SIZE", help="RAM per task, such as 8Gi or 512Mi")
    parser.add_argument(
        "--gpu",
        choices=RESOURCE_DEFAULTS,
        default="none",
        help="GPU model to attach to each task (default: none)",
    )
    args = parser.parse_args()

    default_cpu, default_memory = RESOURCE_DEFAULTS[args.gpu]
    cpu = default_cpu if args.cpu is None else args.cpu
    memory = default_memory if args.memory is None else args.memory

    gcloud = shutil.which("gcloud")
    if gcloud is None:
        parser.error("Install the Google Cloud CLI and run gcloud auth login.")

    root = Path.cwd().resolve()
    if not (root / "Dockerfile").is_file() or not (root / "pyproject.toml").is_file():
        parser.error("Run this command with uv from the repository checkout.")

    command = [
        gcloud, "run", "jobs", "deploy", "imperial-thermo-ai",
        "--source=.", f"--region={args.region}", f"--cpu={cpu}", f"--memory={memory}",
        "--max-retries=0", "--task-timeout=10m", "--wait", "--quiet",
    ]
    if args.gpu == "none":
        command.append("--gpu=0")
    else:
        command.extend(["--gpu=1", f"--gpu-type={args.gpu}", "--no-gpu-zonal-redundancy"])
    if args.project:
        command.append(f"--project={args.project}")

    return subprocess.run(command, cwd=root, check=False).returncode
