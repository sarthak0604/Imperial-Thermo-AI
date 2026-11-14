"""Render or deploy a Cloud Run Job for a chosen Python file."""

import argparse
import json
import shlex
import subprocess
import tempfile
from pathlib import Path


def commands(args):
    script = Path(args.file)
    if (
        script.is_absolute()
        or ".." in script.parts
        or script.suffix != ".py"
        or not script.is_file()
    ):
        raise ValueError(
            "--file must name an existing relative Python file in this build directory"
        )
    env = {
        "PSI_ENTRY_FILE": script.as_posix(),
        "PSI_ENTRY_ARGS": json.dumps(
            args.script_args[1:] if args.script_args[:1] == ["--"] else args.script_args
        ),
        "LLM_PROVIDER": args.provider,
        "LLM_MODEL": args.model,
    }
    # gcloud's env-vars-file accepts JSON (a YAML subset); API keys use Secret Manager.
    deploy = [
        "gcloud",
        "run",
        "jobs",
        "deploy",
        args.job,
        "--image",
        args.image,
        "--project",
        args.project,
        "--region",
        args.region,
        "--service-account",
        args.service_account,
        "--network",
        args.network,
        "--subnet",
        args.subnet,
        "--vpc-egress",
        "private-ranges-only",
        "--add-volume",
        f"name=data,type=nfs,location={args.nfs_server}:{args.nfs_share}",
        "--add-volume-mount",
        "volume=data,mount-path=/data",
        "--tasks",
        "1",
        "--parallelism",
        "1",
        "--max-retries",
        "0",
        "--task-timeout",
        "168h",
        "--memory",
        args.memory,
        "--cpu",
        "2",
        "--set-secrets",
        f"{args.key_env}={args.secret}:latest",
    ]
    execute = [
        "gcloud",
        "run",
        "jobs",
        "execute",
        args.job,
        "--project",
        args.project,
        "--region",
        args.region,
        "--wait",
    ]
    return env, deploy, execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default="cloud_pipeline.py")
    for option in (
        "project",
        "region",
        "image",
        "service-account",
        "network",
        "subnet",
        "nfs-server",
        "nfs-share",
        "secret",
        "model",
    ):
        parser.add_argument("--" + option, required=True)
    parser.add_argument("--job", default="psi-knowledge-graph")
    parser.add_argument("--provider", default="gemini")
    parser.add_argument("--key-env", default="GEMINI_API_KEY")
    parser.add_argument("--memory", default="8Gi")
    parser.add_argument(
        "--deploy",
        action="store_true",
        help="Deploy and execute; default only prints commands",
    )
    parser.add_argument("script_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    env, deploy, execute = commands(args)
    if not args.deploy:
        print("Build the image from this directory first:")
        print(
            shlex.join(
                [
                    "gcloud",
                    "builds",
                    "submit",
                    "--project",
                    args.project,
                    "--tag",
                    args.image,
                    ".",
                ]
            )
        )
        print("Environment configuration (no API secret):", json.dumps(env, indent=2))
        print(shlex.join(deploy + ["--env-vars-file", "cloud-env.json"]))
        print(shlex.join(execute))
        print(
            "Rerun this command with --deploy before the -- separator to deploy and execute."
        )
        return 0
    with tempfile.TemporaryDirectory() as folder:
        config = Path(folder) / "env.json"
        config.write_text(json.dumps(env))
        subprocess.run(deploy + ["--env-vars-file", str(config)], check=True)
    subprocess.run(execute, check=True)
    return 0
