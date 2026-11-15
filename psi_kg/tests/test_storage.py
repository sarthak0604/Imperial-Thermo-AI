import sys
from pathlib import Path

import pytest

from psi_graph import pipeline
from psi_graph.common import file_hash, read_json, write_json
from psi_graph.storage import source_storage


def record_for(path):
    return dict(
        id="res:PSI-1:csv",
        title="data.csv",
        filename="data.csv",
        resource_type="dataset",
        file_format="csv",
        source_url="https://example.test/data.csv",
        local_path=str(path),
        storage_uri=path.as_uri(),
        size_bytes=path.stat().st_size,
        sha256=file_hash(path),
        access_status="accessible",
        extraction_status="pending",
        nasa_file_id="csv",
        nasa_file_version=1,
    )


@pytest.mark.parametrize("keep", [True])
def test_prepare_reads_contents_and_respects_retention(tmp_path, monkeypatch, keep):
    metadata = dict(accession="PSI-1", title="Test study", version=1)
    records = []

    def discover(url, output, refresh):
        write_json(
            output / "files.json",
            [{"id": "csv", "key": "data.csv", "version": 1, "bytes_size": 12}],
        )
        return metadata, records

    def download(resources, metadata, output, workers, storage_output=None):
        raw = (storage_output or output) / "downloads"
        raw.mkdir()
        path = raw / "data.csv"
        path.write_bytes(b"T (K)\n300\n301\n")
        resources.append(record_for(path))
        write_json(
            output / "files.json",
            [
                {
                    "id": "csv",
                    "key": "data.csv",
                    "version": 1,
                    "bytes_size": path.stat().st_size,
                }
            ],
        )

    monkeypatch.setattr(pipeline, "discover", discover)
    monkeypatch.setattr(pipeline, "discover_open_versions", lambda r, *a: r)
    monkeypatch.setattr(pipeline, "download_all", download)
    monkeypatch.setattr(pipeline, "discover_document_links", lambda *a: [])
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "psi-graph",
            "PSI-1",
            "--stage",
            "prepare",
            "--output",
            str(tmp_path),
            *(["--keep-originals"] if keep else []),
        ],
    )
    assert pipeline.main() == 0
    output = tmp_path / "PSI-1"
    documents = read_json(output / "documents.json")
    assert documents[1]["details"]["rows"] == 3
    saved = read_json(output / "resources_manifest.json")["resources"][0]
    if keep:
        assert Path(saved["local_path"]).is_file()
    else:
        assert saved["storage_uri"] is None
        assert saved["local_path"] is None
        assert saved["original_verified_before_discard"]
        assert not list(output.glob(".originals-*"))
        assert not list(output.rglob("*.csv"))
    coverage = read_json(output / "coverage_report.json")
    assert coverage["all_public_files_fetched_and_verified"]
    assert coverage["all_public_files_downloaded"] is keep
    assert coverage["all_listed_files_fully_parsed"]


def test_failure_removes_originals_and_members_but_preserves_evidence(tmp_path):
    resources = []
    (tmp_path / "documents.json").write_text("[]")
    with pytest.raises(RuntimeError, match="parse error"):
        with source_storage(tmp_path, resources, "https://example.test/study") as raw:
            for name in ("data.csv", "archive_members/child.csv"):
                path = raw / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("x\n1")
                resources.append(record_for(path))
            (raw / "interrupted.part").write_text("partial")
            raise RuntimeError("parse error")
    assert not list(tmp_path.glob(".originals-*"))
    assert (tmp_path / "documents.json").exists()
    assert all(
        r["storage_uri"] is None
        for r in read_json(tmp_path / "resources_manifest.json")["resources"]
    )


def test_existing_originals_are_not_deleted(tmp_path):
    existing = tmp_path / "existing.csv"
    existing.write_text("x\n1")
    resource = record_for(existing)
    with source_storage(tmp_path, [resource], "https://example.test"):
        pass
    assert existing.exists()
    assert resource["storage_uri"] == existing.as_uri()
