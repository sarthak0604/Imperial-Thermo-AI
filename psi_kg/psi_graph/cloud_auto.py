"""One-command Cloud Run execution using the user's existing gcloud configuration."""

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

from dotenv import load_dotenv

from .providers import KEYS
from .studies import select_studies


def run(command, *, private_input=None, cwd=None):
    result = subprocess.run(
        command, input=private_input, text=True, capture_output=True, cwd=cwd
    )
    if result.returncode:
        detail = (
            "Secret upload failed; credential details suppressed."
            if private_input is not None
            else result.stderr.strip()
        )
        raise RuntimeError(
            f"Cloud command failed ({result.returncode}): {shlex.join(command)}\n{detail}"
        )
    return result.stdout.strip()


def exists(command):
    result = subprocess.run(command, text=True, capture_output=True)
    if not result.returncode:
        return True
    if any(
        marker in result.stderr.lower()
        for marker in ("not_found", "not found", "does not exist", "404")
    ):
        return False
    raise RuntimeError("Cannot inspect cloud resource: " + result.stderr.strip())


def project_setting(gcloud, setting):
    value = run([gcloud, "config", "get-value", setting])
    return None if value in ("", "(unset)") else value


def check_billing(gcloud, project):
    """Read billing status without enabling services or changing billing."""
    try:
        info = json.loads(
            run([gcloud, "billing", "projects", "describe", project, "--format=json"])
        )
    except (RuntimeError, ValueError) as error:
        raise RuntimeError(
            f"Could not check billing for project {project}. "
            "Check your gcloud login and billing-view permissions.\n" + str(error)
        ) from None
    if not isinstance(info, dict) or type(info.get("billingEnabled")) is not bool:
        raise RuntimeError(
            f"Google Cloud returned an unknown billing status for {project}."
        )
    if not info["billingEnabled"]:
        raise RuntimeError(
            f"Billing is disabled for Google Cloud project {project}.\n"
            "Cloud Run requires a linked, active billing account, including for free allowances. "
            "Gemini API free access is separate.\n"
            f"To enable cloud execution, review billing for this project: "
            f"https://console.cloud.google.com/billing/linkedaccount?project={project}\n"
            "An eligible Google Cloud Free Trial can provide credits; paid accounts can incur charges."
        )


def provision(gcloud, project, region, bucket, secret, key, existing_secret=False):
    scope = ["--project", project, "--quiet"]
    print(
        "Preparing cloud APIs, private results bucket, and runtime identity...",
        flush=True,
    )
    run(
        [
            gcloud,
            "services",
            "enable",
            "run.googleapis.com",
            "cloudbuild.googleapis.com",
            "artifactregistry.googleapis.com",
            *(["secretmanager.googleapis.com"] if secret else []),
            "storage.googleapis.com",
            "iam.googleapis.com",
            *scope,
        ]
    )
    account = f"psi-kg-runner@{project}.iam.gserviceaccount.com"
    if not exists([gcloud, "iam", "service-accounts", "describe", account, *scope]):
        run(
            [
                gcloud,
                "iam",
                "service-accounts",
                "create",
                "psi-kg-runner",
                "--display-name",
                "NASA PSI graph runner",
                *scope,
            ]
        )
    bucket_url = "gs://" + bucket
    if not exists([gcloud, "storage", "buckets", "describe", bucket_url, *scope]):
        run(
            [
                gcloud,
                "storage",
                "buckets",
                "create",
                bucket_url,
                "--location",
                region,
                "--uniform-bucket-level-access",
                "--public-access-prevention",
                *scope,
            ]
        )
    else:
        bucket_info = json.loads(
            run(
                [
                    gcloud,
                    "storage",
                    "buckets",
                    "describe",
                    bucket_url,
                    "--raw",
                    "--format=json",
                    *scope,
                ]
            )
        )
        owner = str(
            bucket_info.get("projectNumber") or bucket_info.get("project_number") or ""
        )
        project_number = run(
            [gcloud, "projects", "describe", project, "--format=value(projectNumber)"]
        )
        if owner != project_number:
            raise RuntimeError(
                "Results bucket belongs to a different project; choose --bucket explicitly in this project."
            )
    run(
        [
            gcloud,
            "storage",
            "buckets",
            "add-iam-policy-binding",
            bucket_url,
            "--member",
            "serviceAccount:" + account,
            "--role",
            "roles/storage.objectAdmin",
            *scope,
        ]
    )
    if secret is None:
        return account, None
    if existing_secret:
        version = "latest"
    else:
        if not exists([gcloud, "secrets", "describe", secret, *scope]):
            run(
                [
                    gcloud,
                    "secrets",
                    "create",
                    secret,
                    "--replication-policy",
                    "automatic",
                    *scope,
                ]
            )
        version = run(
            [
                gcloud,
                "secrets",
                "versions",
                "add",
                secret,
                "--data-file=-",
                "--format=value(name)",
                *scope,
            ],
            private_input=key,
        ).rsplit("/", 1)[-1]
        if not version.isdigit():
            raise RuntimeError("Secret Manager did not return a usable version")
    run(
        [
            gcloud,
            "secrets",
            "add-iam-policy-binding",
            secret,
            "--member",
            "serviceAccount:" + account,
            "--role",
            "roles/secretmanager.secretAccessor",
            *scope,
        ]
    )
    return account, version


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument(
        "--file", help="Python file relative to psi_kg (default: cloud_pipeline.py)"
    )
    parser.add_argument(
        "--image",
        help="Reuse an already-built container image instead of rebuilding source",
    )
    parser.add_argument("--project")
    parser.add_argument("--region")
    parser.add_argument(
        "--bucket", help="Optional existing results bucket in the same project"
    )
    parser.add_argument(
        "--secret",
        help="Optional existing Secret Manager secret; otherwise sync local API key",
    )
    parser.add_argument(
        "--env-file", type=Path, default=Path.home() / ".config/imperial-thermo-ai/.env"
    )
    parser.add_argument("--provider", choices=KEYS)
    parser.add_argument("--model")
    parser.add_argument(
        "--url",
        action="append",
        default=[],
        help="PSI URL or ID; repeat for multiple studies",
    )
    parser.add_argument(
        "--study",
        action="append",
        default=[],
        help="Study name, acronym, PSI ID or URL; repeat for multiple studies",
    )
    parser.add_argument("--mode", choices=["create", "update"])
    parser.add_argument("--graph", help="Cloud graph filename, e.g. current.json")
    parser.add_argument("--job", default="psi-knowledge-graph-auto")
    parser.add_argument("--cpu", help="Default: 8 for local Qwen, 2 for API providers")
    parser.add_argument(
        "--memory", help="Default: 32Gi for local Qwen, 8Gi for API providers"
    )
    parser.add_argument(
        "--scratch-size",
        default=None,
        help="Temporary cloud disk (default: 10Gi); larger sizes require an approved per-instance quota increase",
    )
    parser.add_argument(
        "--gpu",
        choices=["auto", "l4", "none"],
        default="auto",
        help="Default: L4 for local Qwen, none for API providers; none explicitly selects CPU",
    )
    parser.add_argument("--keep-originals", action="store_true")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview only; do not create resources, upload a key, or deploy",
    )
    parser.add_argument("script_args", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    gcloud = shutil.which("gcloud")
    if not gcloud:
        parser.error(
            "Google Cloud CLI is required; reuse your existing gcloud installation/login."
        )
    script = (
        args.file
        or input("Python file [cloud_pipeline.py]: ").strip()
        or "cloud_pipeline.py"
    )
    script_path = (root / script).resolve()
    # Root Python files are included in the existing build allowlist.
    if (
        script_path.parent != root
        or script_path.suffix != ".py"
        or not script_path.is_file()
    ):
        parser.error(
            "Choose a Python file directly inside psi_kg so it is included in the cloud image."
        )
    project = args.project or project_setting(gcloud, "project")
    if not project:
        parser.error(
            "No active project. Run gcloud config set project YOUR_PROJECT once."
        )
    if not args.dry_run:
        try:
            check_billing(gcloud, project)
        except RuntimeError as error:
            message = (
                str(error)
                + "\nNo cloud resources were created or billing settings changed.\n"
            )
            if script_path.name == "cloud_pipeline.py":
                local = [
                    "uv",
                    "run",
                    "--extra",
                    "local",
                    "--project",
                    str(root),
                    "psi-graph-manage",
                    "--env-file",
                    str(args.env_file.expanduser()),
                ]
                for option in ("provider", "model"):
                    if getattr(args, option):
                        local.extend(["--" + option, getattr(args, option)])
                for study in args.url + args.study:
                    local.extend(["--study", study])
                if args.keep_originals:
                    local.append("--keep-originals")
                message += (
                    "To run on your computer instead (API quotas apply only to API providers):\n"
                    + "cd "
                    + shlex.quote(str(root))
                    + "\n"
                    + shlex.join(local)
                    + "\n"
                    "This asks you to choose create/update and a LOCAL graph path. "
                    "It does not update a cloud graph.\n"
                )
            parser.exit(1, message)
    region = (
        args.region
        or os.environ.get("GOOGLE_CLOUD_REGION")
        or project_setting(gcloud, "run/region")
        or "europe-west1"
    )
    load_dotenv(args.env_file, override=False)
    provider = args.provider or os.environ.get("LLM_PROVIDER", "local")
    if provider not in KEYS:
        parser.error("Unsupported LLM_PROVIDER")
    model = (
        args.model
        or os.environ.get("LLM_MODEL")
        or (os.environ.get("GEMINI_MODEL") if provider == "gemini" else None)
    )
    if provider == "local":
        from .local_model import DEFAULT_MODEL

        model = model or DEFAULT_MODEL
        if args.secret:
            parser.error("--secret is not used with the local model provider")
    use_gpu = args.gpu == "l4" or (args.gpu == "auto" and provider == "local")
    if use_gpu and provider != "local":
        parser.error(
            "An L4 is only used by --provider local; API providers run inference remotely"
        )
    args.cpu = args.cpu or ("8" if provider == "local" else "2")
    args.memory = args.memory or ("32Gi" if provider == "local" else "8Gi")
    args.scratch_size = args.scratch_size or "10Gi"
    if use_gpu:
        try:
            cpu = int(args.cpu)
            memory = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)(Gi|Mi)", args.memory)
            gib = float(memory[1]) / (1024 if memory[2] == "Mi" else 1) if memory else 0
            if cpu < 4 or gib < 16:
                raise ValueError
        except ValueError:
            parser.error(
                "L4 requires at least 4 CPUs and 16Gi RAM (use e.g. --cpu 8 --memory 32Gi)"
            )
    key_name = KEYS[provider][0] if KEYS[provider] else None
    key = next(
        (os.environ.get(name) for name in KEYS[provider] if os.environ.get(name)), None
    )
    if provider != "local" and (not model or (not key and not args.secret)):
        if args.dry_run:
            print(
                "LLM configuration is incomplete; an actual run will prompt for it securely."
            )
            model = model or "<choose-model-at-run>"
        elif provider == "gemini" and not args.secret:
            from .setup_gemini import configure, safe_error

            print("Completing Gemini setup before starting cloud resources...")
            try:
                configure(args.env_file.expanduser(), args.model, show_next_step=False)
            except (KeyboardInterrupt, EOFError):
                parser.exit(
                    1, "Gemini setup cancelled; no cloud resources were created.\n"
                )
            except Exception as error:
                parser.error(safe_error(error) + " No cloud resources were created.")
            load_dotenv(args.env_file.expanduser(), override=True)
            model = os.environ.get("LLM_MODEL")
            key = os.environ.get("GEMINI_API_KEY")
        else:
            import getpass

            model = model or input("LLM model ID: ").strip()
            if not key and not args.secret:
                key = getpass.getpass(
                    "Provider API key (hidden, used for this cloud run): "
                ).strip()
            if not model or (not key and not args.secret):
                parser.error(
                    "A model and credential are required for scientific extraction."
                )
    script_args = (
        args.script_args[1:] if args.script_args[:1] == ["--"] else args.script_args
    )
    graph_name = ""
    if script_path.name == "cloud_pipeline.py":
        if script_args:
            parser.error(
                "Use --study/--url, --mode and --graph for cloud_pipeline.py; trailing arguments are for custom scripts."
            )
        mode = args.mode
        if not mode:
            answer = input(
                "1: Update current cloud graph\n2: Create new cloud graph\nChoose 1 or 2: "
            ).strip()
            if answer not in ("1", "2"):
                parser.error("Choose 1 or 2")
            mode = "update" if answer == "1" else "create"
        try:
            urls = select_studies(args.url + args.study)
        except (ValueError, RuntimeError) as error:
            parser.error(str(error))
        graph_name = (
            args.graph
            or input("Cloud graph filename [current.json]: ").strip()
            or "current.json"
        )
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.json", graph_name):
            parser.error(
                "Use a graph filename ending in .json, without directory separators."
            )
        script_args = [
            *urls,
            "--mode",
            mode,
            "--graph",
            "/data/graphs/" + graph_name,
            "--runs",
            "/data/runs",
        ]
        if args.keep_originals:
            script_args.append("--keep-originals")
    else:
        mode = "create"
    bucket = (
        args.bucket
        or f"{project}-psi-kg-{hashlib.sha256(project.encode()).hexdigest()[:8]}"
    )
    secret = (args.secret or f"psi-kg-{provider}-key") if provider != "local" else None
    account = f"psi-kg-runner@{project}.iam.gserviceaccount.com"
    env = dict(
        PSI_ENTRY_FILE=script_path.name,
        PSI_ENTRY_ARGS=json.dumps(script_args),
        PSI_BUCKET=bucket,
        PSI_GRAPH_NAME=graph_name,
        PSI_GRAPH_MODE=mode,
        LLM_PROVIDER=provider,
        LLM_MODEL=model,
    )
    if provider == "local":
        env["HF_HOME"] = "/data/.huggingface"
        env["LLM_DEVICE"] = "cuda" if use_gpu else "cpu"
        for name in ("LLM_CONTEXT_TOKENS", "LLM_MAX_NEW_TOKENS"):
            if os.environ.get(name):
                env[name] = os.environ[name]
    if os.environ.get("LLM_MIN_REQUEST_INTERVAL_SECONDS"):
        env["LLM_MIN_REQUEST_INTERVAL_SECONDS"] = os.environ[
            "LLM_MIN_REQUEST_INTERVAL_SECONDS"
        ]
    if os.environ.get("LLM_BASE_URL"):
        env["LLM_BASE_URL"] = os.environ["LLM_BASE_URL"]
    command = [
        gcloud,
        *(["beta"] if use_gpu else []),
        "run",
        "jobs",
        "deploy",
        args.job,
        *(["--image", args.image] if args.image else ["--source=."]),
        "--project",
        project,
        "--region",
        region,
        "--service-account",
        account,
        "--cpu",
        args.cpu,
        "--memory",
        args.memory,
        *(
            ["--gpu=1", "--gpu-type=nvidia-l4", "--no-gpu-zonal-redundancy"]
            if use_gpu
            else ["--gpu=0"]
        ),
        "--tasks=1",
        "--parallelism=1",
        "--max-retries=0",
        "--task-timeout=12h" if use_gpu else "--task-timeout=168h",
        "--add-volume",
        f"name=scratch,type=ephemeral-disk,size={args.scratch_size}",
        "--add-volume-mount",
        "volume=scratch,mount-path=/data",
        "--execute-now",
        "--wait",
        "--quiet",
    ]
    print(f"Project: {project}; region: {region}; file: {script_path.name}", flush=True)
    accelerator = "NVIDIA L4 (24 GB VRAM)" if use_gpu else "none"
    print(
        f"GPU: {accelerator}; CPUs: {args.cpu}; system RAM: {args.memory}", flush=True
    )
    print(
        f"Saved results: gs://{bucket}/ ; temporary disk: {args.scratch_size}",
        flush=True,
    )
    secret_flags = (
        ["--set-secrets", key_name + "=" + secret + ":VERSION"]
        if secret
        else ["--clear-secrets"]
    )
    if args.dry_run:
        print(json.dumps(env, indent=2))
        print(
            shlex.join(
                command
                + [
                    *secret_flags,
                    "--env-vars-file",
                    "<temporary-config>",
                ]
            )
        )
        print("Preview only: no cloud resources or credentials changed.")
        return 0
    account, version = provision(
        gcloud, project, region, bucket, secret, key, bool(args.secret)
    )
    with tempfile.TemporaryDirectory() as folder:
        config = Path(folder) / "env.json"
        config.write_text(json.dumps(env))
        print(
            "Deploying the existing image and running it on Google Cloud..."
            if args.image
            else "Building the current code and running it on Google Cloud...",
            flush=True,
        )
        # The only key reference in command arguments is a Secret Manager resource/version.
        result = subprocess.run(
            command
            + [
                *(
                    ["--set-secrets", f"{key_name}={secret}:{version}"]
                    if secret
                    else ["--clear-secrets"]
                ),
                "--env-vars-file",
                str(config),
            ],
            cwd=root,
            check=False,
        )
    if result.returncode:
        print(
            "Cloud job failed; inspect Cloud Run logs. No local successful graph copy was written."
        )
        return result.returncode
    if graph_name:
        destination = root / "cloud_results"
        destination.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=destination) as folder:
            downloaded = Path(folder) / graph_name
            run(
                [
                    gcloud,
                    "storage",
                    "cp",
                    f"gs://{bucket}/graphs/{graph_name}",
                    str(downloaded),
                    "--project",
                    project,
                ]
            )
            from .common import read_json
            from .manage import check

            check(read_json(downloaded))
            local = destination / graph_name
            if local.exists():
                backup = destination / (graph_name + ".previous")
                shutil.copy2(local, backup)
            downloaded.replace(local)
        print(f"Graph copied to {destination / graph_name}")
    return 0
