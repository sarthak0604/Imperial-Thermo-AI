"""Deploy the integrated website as a Google Cloud Run service."""

import argparse
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path


def deployment_command(args):
    env = {
        "HOST": "0.0.0.0",
        "AI_PROVIDER": "thermo",
        "THERMO_PLANNER": args.planner,
        ("PSI_PARSER_MODEL" if args.planner == "local" else "OPENAI_MODEL"): args.model,
        "THERMO_CONVERSATION_DB": "/tmp/thermo-conversations.sqlite3",
    }
    command = [
        "gcloud",
        "run",
        "deploy",
        args.service,
        "--source=.",
        f"--region={args.region}",
        "--cpu=4" if args.planner == "local" else "--cpu=2",
        "--memory=16Gi" if args.planner == "local" else "--memory=4Gi",
        "--port=8080",
        "--timeout=300",
        "--concurrency=8",
        "--scaling=auto",
        "--min=0",
        "--max=1",
        "--max-instances=1",
        "--session-affinity",
        "--command=/app/.venv/bin/python",
        "--args=/app/frontend/standin/server.py",
        "--set-env-vars=" + ",".join(f"{key}={value}" for key, value in env.items()),
        "--allow-unauthenticated" if args.public else "--no-allow-unauthenticated",
        "--quiet",
    ]
    if args.planner == "local":
        command.extend(
            [
                "--gpu=1",
                "--gpu-type=nvidia-l4",
                "--no-gpu-zonal-redundancy",
                "--no-cpu-throttling",
            ]
        )
    else:
        command.append("--gpu=0")
    if args.project:
        command.append(f"--project={args.project}")
    if args.service_account:
        command.append(f"--service-account={args.service_account}")
    if args.api_key_secret:
        command.append(f"--set-secrets=OPENAI_API_KEY={args.api_key_secret}")
    return command


def prepare_gpu_source(root, stage, gcloud, model):
    """Stage only upload-allowed files; augment the image without editing the checkout."""
    root = root.resolve()
    manifest = subprocess.run(
        [gcloud, "meta", "list-files-for-upload"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    for name in manifest:
        source = (root / name).resolve()
        relative = source.relative_to(root)
        target = stage / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    # Keep filtering identical in Cloud Build's second upload pass.
    for name in (".dockerignore", ".gcloudignore"):
        shutil.copy2(root / name, stage / name)
    dockerfile = stage / "Dockerfile"
    dockerfile.write_text(
        dockerfile.read_text()
        + f"""
# GPU website variant: all downloads happen on Cloud Build.
RUN uv sync --locked --no-dev --no-editable --extra search
RUN .venv/bin/python -c "import torch; assert torch.version.cuda, 'CUDA-enabled torch required'"
ENV HF_HOME=/opt/huggingface PSI_PARSER_MODEL={model}
RUN .venv/bin/python -c "import os; from huggingface_hub import snapshot_download; snapshot_download(os.environ['PSI_PARSER_MODEL'])"
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
"""
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", help="Defaults to the active gcloud project")
    parser.add_argument(
        "--region", default=os.environ.get("GOOGLE_CLOUD_REGION", "europe-west1")
    )
    parser.add_argument("--service", default="ic-dynamics")
    parser.add_argument(
        "--planner", choices=("local", "api", "retrieval"), default="local"
    )
    parser.add_argument(
        "--model", help="Defaults to Qwen/Qwen3-4B-Instruct-2507 for local inference"
    )
    parser.add_argument(
        "--api-key-secret",
        help="Secret Manager SECRET:VERSION (not the API key itself)",
    )
    parser.add_argument(
        "--service-account",
        help="Runtime service account with secret accessor permission",
    )
    parser.add_argument(
        "--public", action="store_true", help="Allow unauthenticated website visitors"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print the command without deploying"
    )
    args = parser.parse_args(argv)
    args.model = args.model or (
        "Qwen/Qwen3-4B-Instruct-2507" if args.planner == "local" else "gpt-4.1-mini"
    )
    if not re.fullmatch(r"[A-Za-z0-9_./-]+", args.model):
        parser.error("Model must be a model identifier, not a path or shell expression")
    if args.planner == "api" and not args.api_key_secret:
        parser.error(
            "API mode requires --api-key-secret SECRET:VERSION; use --planner retrieval for a key-free demo"
        )
    if args.api_key_secret and (
        ":" not in args.api_key_secret or "," in args.api_key_secret
    ):
        parser.error("--api-key-secret must be SECRET:VERSION")
    if "," in args.model:
        parser.error("--model cannot contain commas")
    root = Path.cwd()
    if (
        not (root / "Dockerfile").is_file()
        or not (root / "NASA Space Apps/frontend/standin/server.py").is_file()
    ):
        parser.error("Run from the repository root")
    command = deployment_command(args)
    print(shlex.join(command), flush=True)
    if args.dry_run:
        if args.planner == "local":
            print(
                "Deployment stages the filtered source with GPU dependencies and downloads model weights in Cloud Build (not locally)."
            )
        return 0
    executable = shutil.which("gcloud")
    if executable is None:
        parser.error("Install the Google Cloud CLI and run gcloud auth login")
    command[0] = executable
    if args.planner == "local":
        with tempfile.TemporaryDirectory(prefix="thermo-gpu-build-") as directory:
            stage = Path(directory)
            prepare_gpu_source(root, stage, executable, args.model)
            command[command.index("--source=.")] = f"--source={stage}"
            return subprocess.run(command, cwd=root, check=False).returncode
    return subprocess.run(command, cwd=root, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
