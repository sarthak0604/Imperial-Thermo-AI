"""Download, checkpoint and discard one original/member at a time."""

import shutil
from pathlib import Path

from .budget import StorageBudget, StorageLimitError, active_budget
from .common import digest, now, read_json, write_json
from .discovery import discover_document_links, download_one
from .parsing import PARSER_VERSION, iter_archive, parse_resources, section
from .storage import source_storage


def prepare_incrementally(
    resources,
    metadata,
    source_url,
    output,
    *,
    max_temp_gb=50,
    min_free_gb=5,
    on_document=None,
):
    write_json(
        output / "preparation_state.json", {"complete": False, "started_at": now()}
    )
    documents = []
    seen_documents = set()
    seen_urls = {r["source_url"] for r in resources}
    queue = list(resources)

    def checkpoint():
        write_json(output / "documents.json", documents)
        write_json(
            output / "resources_manifest.json",
            dict(source_url=source_url, generated_at=now(), resources=resources),
        )

    def add_links(new_documents):
        for child in discover_document_links(new_documents, resources, metadata):
            enqueue(child)

    def enqueue(record):
        if record["source_url"] not in seen_urls:
            seen_urls.add(record["source_url"])
            resources.append(record)
            queue.append(record)

    def accept(document):
        if document["id"] in seen_documents:
            return
        seen_documents.add(document["id"])
        documents.append(document)
        checkpoint()  # Persist source evidence before any model call or deletion.
        add_links([document])
        if on_document is not None and document["sections"]:
            on_document(document)

    with source_storage(output, resources, source_url) as raw:
        budget = StorageBudget(raw, int(max_temp_gb * 1e9), int(min_free_gb * 1e9))
        token = active_budget.set(budget)
        try:
            budget.check(0)
            print(
                f"Incremental storage: {max_temp_gb:g} GB original-file cap; "
                f"{min_free_gb:g} GB free-space reserve; one download at a time",
                flush=True,
            )

            def discard(record):
                local = record.get("local_path")
                if not local:
                    return
                path = Path(local)
                if not path.resolve().is_relative_to(raw.resolve()):
                    return  # Never remove originals explicitly retained by an older run.
                size = path.stat().st_size
                verified = size == record.get("size_bytes") and bool(
                    record.get("sha256")
                )
                path.unlink()
                record.update(
                    local_path=None,
                    storage_uri=None,
                    original_retention="discarded",
                    original_verified_before_discard=verified,
                    original_discarded_at=now(),
                )
                checkpoint()
                print(
                    f"cleanup: {record['title']} ({size / 1e9:.3f} GB); "
                    f"{budget.used / 1e9:.3f} GB originals remain",
                    flush=True,
                )

            def process(record):
                if (
                    record.get("file_format") == "zip"
                    and record.get("access_status") == "accessible"
                ):
                    titles = []
                    names = set()
                    for child in iter_archive(record, raw):
                        if child["title"] in names:
                            raise RuntimeError(
                                "Duplicate archive member name: " + child["title"]
                            )
                        names.add(child["title"])
                        resources.append(child)
                        seen_urls.add(child["source_url"])
                        titles.append(child["title"])
                        process(
                            child
                        )  # Depth first; deletes member before extracting the next.
                    document = dict(
                        id=record["id"],
                        title=record["title"],
                        source_url=record["source_url"],
                        resource_type=record["resource_type"],
                        sha256=record["sha256"],
                        parser_version=PARSER_VERSION,
                        sections=[section("archive inventory", "\n".join(titles))],
                        details={"members": len(titles)},
                        warnings=[],
                        status="parsed",
                    )
                    cache = output / "parsed" / (digest(record["id"]) + ".json")
                    write_json(cache, document)
                    record.update(
                        extraction_status="parsed",
                        extraction_warnings=[],
                        parse_details=document["details"],
                        parsed_path=str(cache.resolve()),
                    )
                    accept(document)
                else:
                    parsed = parse_resources(
                        [record],
                        metadata,
                        source_url,
                        output,
                        storage_output=raw,
                        persist=False,
                    )
                    for document in parsed:
                        accept(document)
                    if record.get("extraction_status") == "failed":
                        checkpoint()
                        raise RuntimeError(
                            "Parsing failed: "
                            + record["title"]
                            + "; see resources_manifest.json"
                        )
                checkpoint()
                discard(record)

            for document in parse_resources(
                [], metadata, source_url, output, persist=False
            ):
                accept(document)
            index = 0
            while index < len(queue):
                record = queue[index]
                index += 1
                print(
                    f"Processing file {index}/{len(queue)}: {record['title']}",
                    flush=True,
                )
                # Reuse saved, version-matching parsed evidence for discarded ordinary files.
                cache = Path(record.get("parsed_path") or "/nonexistent")
                if (
                    record.get("file_format") != "zip"
                    and record.get("original_verified_before_discard")
                    and record.get("original_retention") == "discarded"
                    and cache.is_file()
                ):
                    old = read_json(cache)
                    if (
                        old.get("sha256") == record.get("sha256")
                        and old.get("parser_version") == PARSER_VERSION
                        and old.get("status") != "failed"
                    ):
                        if old.get("sections"):
                            accept(old)
                        continue
                file_root = raw / "per_file" / digest(record["id"])
                file_root.mkdir(parents=True, exist_ok=True)
                try:
                    for child in download_one(record, metadata, file_root):
                        enqueue(child)
                    process(record)
                    # Also remove partial downloads/redirect responses after exhausted retries.
                    shutil.rmtree(file_root)
                except StorageLimitError as exc:
                    record["storage_error"] = str(exc)
                    raise StorageLimitError(
                        f"Cannot process {record['title']}: {exc}"
                    ) from None
            checkpoint()
        finally:
            # Allow cleanup/manifest persistence even when the reserve caused a stop.
            active_budget.reset(token)
            checkpoint()
            write_json(
                output / "storage_report.json",
                dict(
                    max_temp_gb=max_temp_gb,
                    min_free_gb=min_free_gb,
                    peak_original_bytes=budget.peak,
                    cleanup="after_each_file_and_archive_member",
                    note="Parsed evidence, model weights and other runs are outside the original-file cap; free disk space is checked separately.",
                ),
            )
    write_json(
        output / "preparation_state.json", {"complete": True, "completed_at": now()}
    )
    return documents
