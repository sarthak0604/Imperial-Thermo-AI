import io
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from psi_graph import incremental, pipeline, transfer
from psi_graph.budget import (
    StorageBudget,
    StorageLimitError,
    active_budget,
    guarded_write,
)
from psi_graph.common import file_hash, read_json, write_json

META = dict(accession="PSI-1", title="Test study", version=1)
URL = "https://psi.nasa.gov/physci/repo/data/investigations/PSI-1"


def record(name, data):
    return dict(
        id="res:PSI-1:" + name,
        title=name,
        filename=name,
        source_url="https://example.test/" + name,
        file_format=Path(name).suffix[1:],
        resource_type="dataset",
        size_bytes=len(data),
        access_status="not_verified",
        extraction_status="pending",
    )


def fake_download(monkeypatch, payloads, before=None):
    def download(r, metadata, output):
        if before:
            before(r, output)
        path = output / r["filename"]
        with path.open("wb") as f:
            guarded_write(f, payloads[r["filename"]])
        r.update(
            local_path=str(path),
            storage_uri=path.as_uri(),
            sha256=file_hash(path),
            access_status="accessible",
        )
        return []

    monkeypatch.setattr(incremental, "download_one", download)


def test_cleanup_between_downloads_and_evidence_before_delete(tmp_path, monkeypatch):
    payloads = {"a.csv": b"x\n1\n", "b.csv": b"y\n2\n"}
    records = [record(n, b) for n, b in payloads.items()]
    callbacks = []

    def before(r, raw):
        assert not list(raw.rglob("*.csv"))

    fake_download(monkeypatch, payloads, before)

    def extracted(doc):
        assert doc in read_json(tmp_path / "documents.json")
        callbacks.append(doc["id"])

    docs = incremental.prepare_incrementally(
        records,
        META,
        URL,
        tmp_path,
        max_temp_gb=5e-9,
        min_free_gb=1e-9,
        on_document=extracted,
    )
    assert len(docs) == 3
    assert len(callbacks) == 3
    assert all(r["original_verified_before_discard"] for r in records)
    assert not list(tmp_path.rglob("*.csv"))
    assert read_json(tmp_path / "storage_report.json")["peak_original_bytes"] <= 5
    assert len(read_json(tmp_path / "documents.json")) == 3


def zipped(entries):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as z:
        for n, b in entries.items():
            z.writestr(n, b)
    return stream.getvalue()


def test_zip_members_and_nested_archives_are_deleted_depth_first(tmp_path, monkeypatch):
    inner = zipped({"nested.csv": b"x\n" + b"1\n" * 100})
    archive = zipped(
        {
            "a.csv": b"x\n" + b"2\n" * 100,
            "nested.zip": inner,
            "b.csv": b"x\n" + b"3\n" * 100,
        }
    )
    records = [record("source.zip", archive)]
    fake_download(monkeypatch, {"source.zip": archive})
    original = incremental.parse_resources

    def parse(records, *args, **kwargs):
        if records:
            raw = Path(records[0]["local_path"]).parents
            # Each parse sees only one ordinary member; enclosing ZIPs are still present.
            scratch = next(p for p in raw if p.name.startswith(".originals-"))
            assert len(list(scratch.rglob("*.csv"))) == 1
        return original(records, *args, **kwargs)

    monkeypatch.setattr(incremental, "parse_resources", parse)
    cap = len(archive) + len(inner) + 202
    docs = incremental.prepare_incrementally(
        records, META, URL, tmp_path, max_temp_gb=cap / 1e9, min_free_gb=1e-9
    )
    assert len([d for d in docs if d["title"].endswith(".csv")]) == 3
    assert len(records) == 5
    assert all(r["original_retention"] == "discarded" for r in records)
    assert not list(tmp_path.glob(".originals-*"))
    assert read_json(tmp_path / "storage_report.json")["peak_original_bytes"] <= cap


def test_archive_member_cap_counts_compressed_parent(tmp_path, monkeypatch):
    archive = zipped({"huge.txt": b"x" * 1000})
    records = [record("source.zip", archive)]
    fake_download(monkeypatch, {"source.zip": archive})
    with pytest.raises(StorageLimitError, match="source.zip"):
        incremental.prepare_incrementally(
            records,
            META,
            URL,
            tmp_path,
            max_temp_gb=(len(archive) + 999) / 1e9,
            min_free_gb=1e-9,
        )
    assert not list(tmp_path.glob(".originals-*"))
    assert (
        "storage_error"
        in read_json(tmp_path / "resources_manifest.json")["resources"][0]
    )


def test_low_space_preserves_saved_evidence_and_stops(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "psi_graph.budget.shutil.disk_usage", lambda _: SimpleNamespace(free=10)
    )
    with pytest.raises(StorageLimitError, match="Insufficient free disk"):
        incremental.prepare_incrementally(
            [], META, URL, tmp_path, max_temp_gb=1, min_free_gb=20e-9
        )
    assert not list(tmp_path.glob(".originals-*"))


def test_callback_failure_cleans_original_but_keeps_parsed_source(
    tmp_path, monkeypatch
):
    records = [record("a.csv", b"x\n1\n")]
    fake_download(monkeypatch, {"a.csv": b"x\n1\n"})

    def fail(doc):
        if doc["title"] == "a.csv":
            raise RuntimeError("model failed")

    with pytest.raises(RuntimeError, match="model failed"):
        incremental.prepare_incrementally(
            records, META, URL, tmp_path, on_document=fail
        )
    assert len(read_json(tmp_path / "documents.json")) == 2
    assert records[0]["parsed_path"]
    assert records[0]["local_path"] is None
    assert not list(tmp_path.glob(".originals-*"))


def test_known_oversized_file_fails_before_network(tmp_path, monkeypatch):
    def no_network(*args, **kwargs):
        pytest.fail("Oversized known file must not start downloading")

    monkeypatch.setattr(transfer.nasa, "request", no_network)
    token = active_budget.set(StorageBudget(tmp_path, 5, 1))
    try:
        with pytest.raises(StorageLimitError):
            transfer.download_file(
                "PSI-1", 1, dict(id="x", version=1, key="x.csv", bytes_size=6), tmp_path
            )
    finally:
        active_budget.reset(token)


def test_unknown_length_cannot_cross_cap(tmp_path, monkeypatch):
    class Response(io.BytesIO):
        status = 200
        headers = {}

    monkeypatch.setattr(
        transfer.nasa, "request", lambda *a: Response(b"https://example.test/data")
    )
    monkeypatch.setattr(transfer, "urlopen", lambda *a, **k: Response(b"123456"))
    token = active_budget.set(StorageBudget(tmp_path, 5, 1))
    try:
        with pytest.raises(StorageLimitError):
            transfer.download_file(
                "PSI-1", 1, dict(id="x", version=1, key="x.csv"), tmp_path
            )
        assert not (tmp_path / "x.csv").exists()
        assert (tmp_path / "x.csv.part").stat().st_size <= 5
    finally:
        active_budget.reset(token)


def test_prepare_cli_uses_incremental_default(tmp_path, monkeypatch):
    data = b"x\n1\n"
    records = [record("a.csv", data)]
    records[0].update(nasa_file_id="a", nasa_file_version=1)

    def discover(*args):
        output = args[1]
        write_json(
            output / "files.json",
            [dict(id="a", key="a.csv", version=1, bytes_size=len(data))],
        )
        return META, records

    monkeypatch.setattr(pipeline, "discover", discover)
    monkeypatch.setattr(pipeline, "discover_open_versions", lambda r, *a: r)
    fake_download(monkeypatch, {"a.csv": data})
    monkeypatch.setattr(
        sys,
        "argv",
        ["psi-graph", "PSI-1", "--stage", "prepare", "--output", str(tmp_path)],
    )
    assert pipeline.main() == 0
    coverage = read_json(tmp_path / "PSI-1/coverage_report.json")
    assert coverage["all_public_files_fetched_and_verified"]
    assert not coverage["all_public_files_downloaded"]
    assert coverage["all_listed_files_fully_parsed"]


def test_resuming_parsed_file_does_not_download_again(tmp_path, monkeypatch):
    records = [record("a.csv", b"x\n1\n")]
    fake_download(monkeypatch, {"a.csv": b"x\n1\n"})
    first = incremental.prepare_incrementally(records, META, URL, tmp_path)
    monkeypatch.setattr(
        incremental, "download_one", lambda *a: pytest.fail("Already parsed")
    )
    second = incremental.prepare_incrementally(records, META, URL, tmp_path)
    assert first == second


def test_incomplete_preparation_cannot_be_generated(tmp_path, monkeypatch):
    out = tmp_path / "PSI-1"
    write_json(out / "preparation_state.json", {"complete": False})
    monkeypatch.setattr(pipeline, "LLM", lambda *a, **k: object())
    monkeypatch.setattr(
        sys,
        "argv",
        ["psi-graph", "PSI-1", "--stage", "generate", "--output", str(tmp_path)],
    )
    with pytest.raises(RuntimeError, match="Preparation is incomplete"):
        pipeline.main()


def test_external_download_obeys_storage_cap(tmp_path, monkeypatch):
    from psi_graph import discovery

    class Response(io.BytesIO):
        url = "https://example.test/data.csv"
        headers = {"Content-Type": "text/csv"}

    monkeypatch.setattr(discovery.nasa, "request", lambda *a: Response(b"123456"))
    token = active_budget.set(StorageBudget(tmp_path, 5, 1))
    try:
        with pytest.raises(StorageLimitError):
            discovery.download_one(record("data.csv", b"123456"), META, tmp_path)
    finally:
        active_budget.reset(token)


def test_changing_source_hash_does_not_reuse_old_parsed_evidence(tmp_path, monkeypatch):
    records = [record("a.csv", b"x\n1\n")]
    fake_download(monkeypatch, {"a.csv": b"x\n1\n"})
    incremental.prepare_incrementally(records, META, URL, tmp_path)
    records[0]["sha256"] = "changed"
    fake_download(monkeypatch, {"a.csv": b"x\n2\n"})
    docs = incremental.prepare_incrementally(records, META, URL, tmp_path)
    assert docs[1]["details"]["column_statistics"][0]["max"] == 2


def test_model_contributions_accumulate_across_files(tmp_path):
    from psi_graph.science import Extraction, extract_all

    class Client:
        def call(self, *args):
            return Extraction(studies=[], resources=[], caveats=[])

    results, failures = [], []
    for number in (1, 2):
        doc = dict(
            id=f"doc-{number}",
            title=f"file-{number}",
            resource_type="dataset",
            sections=[{"locator": "row 1", "text": "Temperature (K)"}],
        )
        extract_all(Client(), [doc], [], tmp_path, results=results, failures=failures)
    assert [r["document_id"] for r in read_json(tmp_path / "extractions.json")] == [
        "doc-1",
        "doc-2",
    ]


def test_resumed_download_counts_only_remaining_bytes(tmp_path, monkeypatch):
    class Response(io.BytesIO):
        def __init__(self, body, status=200, headers=None):
            super().__init__(body)
            self.status = status
            self.headers = headers or {}

    (tmp_path / "data.csv.part").write_bytes(b"abc")
    write_json(tmp_path / "data.csv.transfer.json", {"validator": '"v1"'})
    monkeypatch.setattr(
        transfer.nasa, "request", lambda *a: Response(b"https://example.test/data")
    )
    monkeypatch.setattr(
        transfer,
        "urlopen",
        lambda *a, **k: Response(
            b"def",
            206,
            {"Content-Range": "bytes 3-5/6", "Content-Length": "3", "ETag": '"v1"'},
        ),
    )
    token = active_budget.set(StorageBudget(tmp_path, 6, 1))
    try:
        result = transfer.download_file(
            "PSI-1", 1, dict(id="x", version=1, key="data.csv", bytes_size=6), tmp_path
        )
        assert result.read_bytes() == b"abcdef"
    finally:
        active_budget.reset(token)


def test_failed_transfer_partials_are_removed_before_next_download(
    tmp_path, monkeypatch
):
    resources = [record("a.csv", b"123"), record("b.csv", b"x\n1\n")]

    def download(r, metadata, folder):
        scratch = next(p for p in folder.parents if p.name.startswith(".originals-"))
        assert not list(scratch.rglob("*.part"))
        if r["filename"] == "a.csv":
            with (folder / "a.csv.part").open("wb") as stream:
                guarded_write(stream, b"12")
            r.update(access_status="inaccessible", extraction_status="inaccessible")
        else:
            path = folder / "b.csv"
            with path.open("wb") as stream:
                guarded_write(stream, b"x\n1\n")
            r.update(
                local_path=str(path),
                storage_uri=path.as_uri(),
                sha256=file_hash(path),
                access_status="accessible",
            )
        return []

    monkeypatch.setattr(incremental, "download_one", download)
    incremental.prepare_incrementally(resources, META, URL, tmp_path)
    assert not list(tmp_path.glob(".originals-*"))
