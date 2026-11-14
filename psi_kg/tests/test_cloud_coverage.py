from argparse import Namespace
from pathlib import Path

import pytest

from psi_graph.cloud import commands
from psi_graph.common import file_hash
from psi_graph.coverage import audit


def test_coverage_detects_missing_raw_and_partial_parse(tmp_path):
    path = tmp_path / "data.csv"
    path.write_bytes(b"x\n1\n")
    entries = [
        {
            "id": "one",
            "key": "Analyzed/data.csv",
            "bytes_size": 4,
            "sortingCategory": "Analyzed Data",
        },
        {
            "id": "two",
            "key": "Raw/video.bin",
            "bytes_size": 150_000_000_000,
            "sortingCategory": "Raw Data",
        },
    ]
    resources = [
        {
            "nasa_file_id": "one",
            "local_path": str(path),
            "sha256": file_hash(path),
            "access_status": "accessible",
            "extraction_status": "partially_parsed",
        }
    ]
    result = audit(entries, resources, True)
    assert result["known_total_bytes"] == 150_000_000_004
    assert not result["all_listed_files_in_manifest"]
    assert not result["all_public_files_downloaded"]
    assert not result["all_listed_files_fully_parsed"]
    assert result["files"][0]["checksum_verified"]
    path.write_bytes(b"bad!")
    assert not audit(entries, resources, True)["files"][0]["downloaded"]


def test_cloud_command_uses_persistent_storage_and_secret_reference(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    Path("chosen.py").write_text("print('test')")
    args = Namespace(
        file="chosen.py",
        script_args=["--", "NASA URL"],
        provider="gemini",
        model="test-model",
        job="test",
        image="image",
        project="project",
        region="region",
        service_account="account",
        network="net",
        subnet="sub",
        nfs_server="10.0.0.1",
        nfs_share="/share",
        memory="8Gi",
        key_env="GEMINI_API_KEY",
        secret="secret-name",
    )
    env, deploy, execute = commands(args)
    assert env["PSI_ENTRY_FILE"] == "chosen.py"
    assert "type=nfs" in " ".join(deploy)
    assert "volume=data,mount-path=/data" in deploy
    assert "GEMINI_API_KEY=secret-name:latest" in deploy
    assert "--wait" in execute
    args.file = "../outside.py"
    with pytest.raises(ValueError):
        commands(args)


def test_nasa_resume_range_and_server_ignored_range(tmp_path, monkeypatch):
    import io

    from psi_graph import transfer
    from psi_graph.common import write_json

    class Response(io.BytesIO):
        def __init__(self, body, status=200, headers=None):
            super().__init__(body)
            self.status = status
            self.headers = headers or {}

    monkeypatch.setattr(
        transfer.nasa, "request", lambda *args: Response(b"https://example.test/data")
    )
    entry = {"id": "file", "version": 1, "key": "data.bin", "bytes_size": 6}
    part = tmp_path / "data.bin.part"
    state = tmp_path / "data.bin.transfer.json"
    part.write_bytes(b"abc")
    write_json(state, {"validator": '"v1"'})

    def partial(request, **kwargs):
        assert request.get_header("Range") == "bytes=3-"
        return Response(b"def", 206, {"Content-Range": "bytes 3-5/6", "ETag": '"v1"'})

    monkeypatch.setattr(transfer, "urlopen", partial)
    result = transfer.download_file("PSI-1", 1, entry, tmp_path)
    assert result.read_bytes() == b"abcdef"
    result.unlink()
    part.write_bytes(b"old")
    write_json(state, {"validator": '"v1"'})
    monkeypatch.setattr(
        transfer, "urlopen", lambda *a, **k: Response(b"newnew", 200, {"ETag": '"v2"'})
    )
    assert transfer.download_file("PSI-1", 1, entry, tmp_path).read_bytes() == b"newnew"


def test_incomplete_download_is_not_published(tmp_path, monkeypatch):
    import io

    from psi_graph import transfer

    class Response(io.BytesIO):
        status = 200
        headers = {"ETag": '"v1"'}

    monkeypatch.setattr(
        transfer.nasa, "request", lambda *a: Response(b"https://example.test/data")
    )
    monkeypatch.setattr(transfer, "urlopen", lambda *a, **k: Response(b"abc"))
    with pytest.raises(RuntimeError, match="Incomplete"):
        transfer.download_file(
            "PSI-1",
            1,
            {"id": "f", "version": 1, "key": "data", "bytes_size": 6},
            tmp_path,
        )
    assert not (tmp_path / "data").exists()
    assert (tmp_path / "data.part").read_bytes() == b"abc"
