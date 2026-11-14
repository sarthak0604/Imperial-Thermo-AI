"""Audit NASA's current file inventory against downloaded and parsed resources."""

import argparse
from collections import Counter
from pathlib import Path

from .common import file_hash, now, read_json, write_json
from .nasa_access import get_metadata, investigation_id, list_files


def audit(files, resources, verify_hashes=False):
    records = {r["nasa_file_id"]: r for r in resources if r.get("nasa_file_id")}
    rows = []
    for entry in files:
        record = records.get(entry["id"], {})
        path = Path(record.get("local_path") or "/nonexistent")
        expected = entry.get("bytes_size")
        present = path.is_file()
        size_ok = present and (expected is None or path.stat().st_size == int(expected))
        checksum = (
            bool(
                size_ok and record.get("sha256") and file_hash(path) == record["sha256"]
            )
            if verify_hashes
            else None
        )
        version_ok = (
            entry.get("version") is None
            or record.get("nasa_file_version") == entry["version"]
        )
        downloaded = bool(
            version_ok
            and size_ok
            and record.get("access_status") == "accessible"
            and checksum is not False
        )
        rows.append(
            dict(
                nasa_file_id=entry["id"],
                path=entry["key"],
                category=entry.get("sortingCategory"),
                expected_bytes=expected,
                restricted=bool(
                    entry.get("restricted") or entry.get("restrictedAccess")
                ),
                in_manifest=bool(record),
                downloaded=downloaded,
                fetched_and_verified=downloaded
                or bool(
                    version_ok
                    and record.get("original_retention") == "discarded"
                    and record.get("original_verified_before_discard")
                ),
                original_retention=record.get(
                    "original_retention", "retained" if present else "unavailable"
                ),
                checksum_verified=checksum,
                extraction_status=record.get("extraction_status", "missing"),
            )
        )
    children = [r for r in resources if r.get("parent_resource_id")]
    public = [r for r in rows if not r["restricted"]]
    return dict(
        generated_at=now(),
        nasa_files=len(rows),
        known_total_bytes=sum(int(r["expected_bytes"] or 0) for r in rows),
        files_with_unknown_size=sum(r["expected_bytes"] is None for r in rows),
        categories=dict(Counter(r["category"] for r in rows)),
        all_listed_files_in_manifest=all(r["in_manifest"] for r in rows),
        all_public_files_downloaded=all(r["downloaded"] for r in public),
        all_public_files_fetched_and_verified=all(
            r["fetched_and_verified"] for r in public
        ),
        all_listed_files_fully_parsed=bool(rows)
        and all(
            r["fetched_and_verified"] and r["extraction_status"] == "parsed"
            for r in rows
        )
        and all(r.get("extraction_status") == "parsed" for r in children),
        archive_members=len(children),
        files=rows,
        scope="Current NASA public file-tree inventory, not proof that NASA exposes every experimental raw file. Parsed numeric profiles are not full scientific reanalysis.",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--output", type=Path, default=Path("output"))
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    accession = investigation_id(args.url)
    folder = args.output / accession
    if args.offline:
        files = read_json(folder / "files.json")
    else:
        metadata = get_metadata(accession)
        files = list_files(accession, metadata["version"])
    resources = read_json(folder / "resources_manifest.json")["resources"]
    result = audit(files, resources, verify_hashes=True)
    write_json(folder / "coverage_report.json", result)
    for key, value in result.items():
        if key != "files":
            print(f"{key}: {value}")
    return (
        0
        if result["all_listed_files_in_manifest"]
        and result["all_public_files_fetched_and_verified"]
        else 1
    )
