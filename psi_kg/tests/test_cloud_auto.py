import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from google.api_core.exceptions import NotFound, PreconditionFailed

from psi_graph import cloud_auto, cloud_runtime


def graph(title="test"):
    return {
        "schema_version": "1.0.0",
        "graph_id": "nasa-psi-1",
        "source_url": "https://psi.nasa.gov/physci/repo/data/investigations/PSI-1",
        "generated_at": "2026-11-14T00:00:00Z",
        "nodes": [
            {
                "id": "inv:PSI-1",
                "type": "Investigation",
                "properties": {
                    "title": title,
                    "summary": None,
                    "keywords": [],
                    "doi": None,
                    "source_url": "https://psi.nasa.gov/physci/repo/data/investigations/PSI-1",
                },
            }
        ],
        "edges": [],
    }


class Bucket:
    name = "test-bucket"

    def __init__(self):
        self.objects = {}
        self.calls = []

    def blob(self, name):
        return Blob(self, name)


class Blob:
    def __init__(self, bucket, name):
        self.bucket, self.name, self.generation = bucket, name, None

    def reload(self):
        if self.name not in self.bucket.objects:
            raise NotFound("missing")
        self.generation = self.bucket.objects[self.name][0]

    def download_as_bytes(self, if_generation_match=None):
        version, value = self.bucket.objects[self.name]
        if if_generation_match is not None and version != if_generation_match:
            raise PreconditionFailed("changed")
        return value

    def upload_from_string(self, data, content_type=None, if_generation_match=None):
        version = self.bucket.objects.get(self.name, (0, None))[0]
        if if_generation_match is not None and version != if_generation_match:
            raise PreconditionFailed("changed")
        self.bucket.calls.append((self.name, if_generation_match))
        self.bucket.objects[self.name] = (
            version + 1,
            data.encode() if isinstance(data, str) else data,
        )

    def upload_from_filename(self, path, **kwargs):
        self.upload_from_string(Path(path).read_bytes(), **kwargs)


def test_cloud_publish_create_update_and_backup(tmp_path):
    bucket = Bucket()

    def runner():
        path = tmp_path / "graphs/current.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(graph()))

    cloud_runtime.execute(
        bucket, tmp_path, Path("script.py"), [], "current.json", "create", runner
    )
    assert bucket.objects["graphs/current.json"][0] == 1
    assert ("graphs/current.json", 0) in bucket.calls
    cloud_runtime.execute(
        bucket, tmp_path, Path("script.py"), [], "current.json", "update", runner
    )
    assert bucket.objects["graphs/current.json"][0] == 2
    assert (
        bucket.objects["backups/current.json/1.json"][1] == json.dumps(graph()).encode()
    )
    with pytest.raises(RuntimeError, match="already exists"):
        cloud_runtime.execute(
            bucket, tmp_path, Path("script.py"), [], "current.json", "create", runner
        )


def test_cloud_failure_keeps_existing_graph_and_uploads_diagnostics(tmp_path):
    bucket = Bucket()
    original = json.dumps(graph()).encode()
    bucket.objects["graphs/current.json"] = (4, original)

    def runner():
        (tmp_path / "failure.json").write_text('{"error":"test failure"}')
        raise RuntimeError("scientific extraction failed")

    with pytest.raises(RuntimeError, match="scientific extraction"):
        cloud_runtime.execute(
            bucket, tmp_path, Path("script.py"), [], "current.json", "update", runner
        )
    assert bucket.objects["graphs/current.json"] == (4, original)
    assert any(name.endswith("/failure.json") for name in bucket.objects)


def test_concurrent_cloud_update_cannot_overwrite_newer_graph(tmp_path):
    bucket = Bucket()
    bucket.objects["graphs/current.json"] = (4, json.dumps(graph()).encode())
    newer = json.dumps(graph("newer")).encode()

    def runner():
        bucket.objects["graphs/current.json"] = (5, newer)

    with pytest.raises(PreconditionFailed):
        cloud_runtime.execute(
            bucket, tmp_path, Path("script.py"), [], "current.json", "update", runner
        )
    assert bucket.objects["graphs/current.json"] == (5, newer)


def test_persisted_file_uris_point_to_cloud_objects(tmp_path):
    value = {
        "storage_uri": (tmp_path / "runs/data file.csv").as_uri(),
        "source_url": "https://nasa.gov",
    }
    result = cloud_runtime.rebase_uris(value, tmp_path, "bucket", "executions/one")
    assert result["storage_uri"] == "gs://bucket/executions/one/runs/data file.csv"
    assert result["source_url"] == value["source_url"]


def test_one_command_preview_reuses_config_without_cloud_changes(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(
        cloud_auto, "__file__", str(tmp_path / "psi_graph/cloud_auto.py")
    )
    (tmp_path / "cloud_pipeline.py").write_text("")
    monkeypatch.setattr(cloud_auto.shutil, "which", lambda _: "gcloud")
    monkeypatch.setattr(
        cloud_auto,
        "project_setting",
        lambda _, key: "nasa26" if key == "project" else None,
    )
    monkeypatch.setattr(cloud_auto, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("GEMINI_API_KEY", "never-print-this-key")
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setattr(
        cloud_auto,
        "provision",
        lambda *a, **k: pytest.fail("Preview must not provision"),
    )
    assert (
        cloud_auto.main(
            [
                "--file",
                "cloud_pipeline.py",
                "--url",
                "PSI-1",
                "--mode",
                "create",
                "--graph",
                "current.json",
                "--dry-run",
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "nasa26" in output
    assert "--source=." in output
    assert "--execute-now" in output
    assert "ephemeral-disk" in output
    assert "never-print-this-key" not in output


def test_provision_scopes_permissions_and_uses_stdin_for_key(monkeypatch):
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return (
            "projects/project/secrets/key/versions/3"
            if command[1:4] == ["secrets", "versions", "add"]
            else ""
        )

    monkeypatch.setattr(cloud_auto, "run", run)
    monkeypatch.setattr(cloud_auto, "exists", lambda _: False)
    account, version = cloud_auto.provision(
        "gcloud", "project", "region", "bucket", "key", "private-key"
    )
    assert version == "3"
    assert account == "psi-kg-runner@project.iam.gserviceaccount.com"
    assert all("private-key" not in str(command) for command, _ in calls)
    assert any(kwargs.get("private_input") == "private-key" for _, kwargs in calls)
    assert any(
        "roles/storage.objectAdmin" in command
        and command[1:3] == ["storage", "buckets"]
        for command, _ in calls
    )
    assert not any(
        "roles/owner" in command or "roles/editor" in command for command, _ in calls
    )


def test_repository_launcher_routes_to_kg_and_preserves_old_option(monkeypatch):
    path = Path(__file__).resolve().parents[2] / "src/imperial_thermo_ai/cloud.py"
    spec = importlib.util.spec_from_file_location("root_cloud_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls = []
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda command, **kwargs: (
            calls.append(command) or SimpleNamespace(returncode=0)
        ),
    )
    monkeypatch.setattr(module.shutil, "which", lambda name: name)
    monkeypatch.setattr("builtins.input", lambda _: "")
    assert module.dispatch_knowledge_graph([]) == 0
    assert calls[0][-3:] == ["google", "--file", "cloud_pipeline.py"]
    monkeypatch.setattr("builtins.input", lambda _: "main")
    assert module.dispatch_knowledge_graph([]) is None
    assert len(calls) == 1


@pytest.mark.parametrize("enabled", [True, False])
def test_billing_check_is_read_only(monkeypatch, enabled):
    calls = []
    monkeypatch.setattr(
        cloud_auto,
        "run",
        lambda command: (
            calls.append(command) or json.dumps({"billingEnabled": enabled})
        ),
    )
    if enabled:
        cloud_auto.check_billing("gcloud", "nasa26")
    else:
        with pytest.raises(RuntimeError, match="Billing is disabled"):
            cloud_auto.check_billing("gcloud", "nasa26")
    assert calls == [
        ["gcloud", "billing", "projects", "describe", "nasa26", "--format=json"]
    ]


@pytest.mark.parametrize(
    "response", ["{}", "[]", "invalid", '{"billingEnabled": "false"}']
)
def test_billing_unknown_does_not_proceed(monkeypatch, response):
    monkeypatch.setattr(cloud_auto, "run", lambda _: response)
    with pytest.raises(RuntimeError):
        cloud_auto.check_billing("gcloud", "nasa26")


def test_billing_permission_error_is_not_reported_as_disabled(monkeypatch):
    def denied(_):
        raise RuntimeError("PERMISSION_DENIED")

    monkeypatch.setattr(cloud_auto, "run", denied)
    with pytest.raises(RuntimeError, match="Could not check billing") as error:
        cloud_auto.check_billing("gcloud", "nasa26")
    assert "Billing is disabled" not in str(error.value)


def test_unbilled_project_stops_before_setup_or_provision(monkeypatch, capsys):
    monkeypatch.setattr(cloud_auto.shutil, "which", lambda _: "gcloud")
    monkeypatch.setattr(cloud_auto, "run", lambda _: '{"billingEnabled": false}')
    monkeypatch.setattr(
        cloud_auto,
        "load_dotenv",
        lambda *a, **k: pytest.fail("No setup before billing"),
    )
    monkeypatch.setattr(
        cloud_auto, "provision", lambda *a, **k: pytest.fail("No provisioning")
    )
    monkeypatch.setattr("builtins.input", lambda _: pytest.fail("No extra prompts"))
    with pytest.raises(SystemExit) as error:
        cloud_auto.main(["--file", "cloud_pipeline.py", "--project", "nasa26"])
    assert error.value.code == 1
    output = capsys.readouterr().err
    assert "Billing is disabled" in output
    assert "psi-graph-manage" in output
    assert "LOCAL graph path" in output
    assert "Traceback" not in output


@pytest.mark.parametrize("owner", ["123456", "654321"])
def test_existing_bucket_ownership_uses_raw_metadata(monkeypatch, owner):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if command[1:4] == ["storage", "buckets", "describe"]:
            # Standardized gcloud metadata omits the owning project number.
            return json.dumps({"projectNumber": owner} if "--raw" in command else {})
        if command[1:3] == ["projects", "describe"]:
            return "123456"
        return ""

    monkeypatch.setattr(cloud_auto, "run", run)
    monkeypatch.setattr(cloud_auto, "exists", lambda _: True)
    if owner == "123456":
        assert cloud_auto.provision(
            "gcloud", "project", "region", "bucket", None, None
        ) == ("psi-kg-runner@project.iam.gserviceaccount.com", None)
        assert any("add-iam-policy-binding" in command for command in calls)
    else:
        with pytest.raises(RuntimeError, match="different project"):
            cloud_auto.provision("gcloud", "project", "region", "bucket", None, None)
        assert not any("add-iam-policy-binding" in command for command in calls)


def test_cloud_batch_resolves_names_before_deployment(tmp_path, monkeypatch, capsys):
    from psi_graph import studies

    monkeypatch.setattr(
        cloud_auto, "__file__", str(tmp_path / "psi_graph/cloud_auto.py")
    )
    (tmp_path / "cloud_pipeline.py").write_text("")
    monkeypatch.setattr(cloud_auto.shutil, "which", lambda _: "gcloud")
    monkeypatch.setattr(
        cloud_auto,
        "project_setting",
        lambda _, key: "nasa26" if key == "project" else None,
    )
    monkeypatch.setattr(cloud_auto, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr(
        studies,
        "catalogue",
        lambda: [
            {
                "id": "PSI-26",
                "title": "Burning and Suppression of Solids",
                "acronym": "BASS",
            }
        ],
    )
    monkeypatch.setattr(
        cloud_auto,
        "provision",
        lambda *a, **k: pytest.fail("Dry run must not provision"),
    )
    assert (
        cloud_auto.main(
            [
                "--file",
                "cloud_pipeline.py",
                "--provider",
                "local",
                "--study",
                "BASS",
                "--url",
                "PSI-117",
                "--url",
                "PSI-26",
                "--mode",
                "create",
                "--graph",
                "combined.json",
                "--dry-run",
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    start = output.index('{\n  "PSI_ENTRY_FILE"')
    env, _ = json.JSONDecoder().raw_decode(output[start:])
    arguments = json.loads(env["PSI_ENTRY_ARGS"])
    assert arguments[:2] == [studies.PAGE_URL + "PSI-117", studies.PAGE_URL + "PSI-26"]
    assert arguments.count(studies.PAGE_URL + "PSI-26") == 1
    assert env["PSI_GRAPH_NAME"] == "combined.json"
    assert "BASS" not in arguments
