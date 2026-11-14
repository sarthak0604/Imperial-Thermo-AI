#!/usr/bin/env python3
"""List and download NASA PSI investigation files (Python 3.9+, no packages).

Examples:
    python3 nasa_psi_download.py
    python3 nasa_psi_download.py --filter .csv
    python3 nasa_psi_download.py --download-first --preview
    python3 nasa_psi_download.py --filter Kavg --download-first --preview
    python3 nasa_psi_download.py --filter .csv --download-all
    python3 nasa_psi_download.py --save-metadata

The default investigation is:
https://psi.nasa.gov/physci/repo/data/investigations/PSI-117

This JavaScript-rendered website does not expose its data links in the initial
HTML. This script calls the same metadata, file-tree, and download endpoints
as the website, then follows NASA's temporary download URL. Endpoints verified
in November 2026; NASA may change them. Only public files are supported.
Downloads go into ./nasa_downloads/PSI-117/ by default. Existing files are never
overwritten. Import get_metadata(), list_files(), and download_file() to reuse
the code in your own project.
"""

import argparse
import csv
import json
import os
from pathlib import Path, PurePosixPath
import re
import ssl
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen


BASE_URL = "https://psi.nasa.gov/geode-py/ws"
DEFAULT_PAGE = "https://psi.nasa.gov/physci/repo/data/investigations/PSI-117"
TIMEOUT = 60


def tls_context():
    """Use verified TLS, including macOS's CA bundle if Python has none."""
    context = ssl.create_default_context()
    if not context.get_ca_certs() and Path("/etc/ssl/cert.pem").is_file():
        context.load_verify_locations(cafile="/etc/ssl/cert.pem")
    return context


def request(url, payload=None):
    """Open an HTTP response; callers must close it (use a with statement)."""
    headers = {"User-Agent": "NASA-PSI-Python-Downloader/1.0"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    return urlopen(Request(url, data=data, headers=headers), timeout=TIMEOUT,
                   context=tls_context())


def read_json(url, payload=None):
    with request(url, payload) as response:
        try:
            return json.load(response)
        except (ValueError, UnicodeError) as exc:
            raise RuntimeError("NASA returned an unexpected response instead of JSON.") from exc


def investigation_id(page_or_id):
    """Accept an investigation URL or an accession such as PSI-117."""
    value = page_or_id.strip()
    if value.startswith("https://"):
        parsed = urlparse(value)
        if parsed.hostname != "psi.nasa.gov":
            raise ValueError("The page URL must be on psi.nasa.gov.")
        value = parsed.path.rstrip("/").split("/")[-1]
    if not re.fullmatch(r"PSI-\d+", value, re.IGNORECASE):
        raise ValueError("Supply a NASA investigation URL or an ID such as PSI-117.")
    return value.upper()


def get_metadata(accession):
    return read_json(f"{BASE_URL}/repo/investigations/{quote(accession)}")


def list_files(accession, study_version):
    """Walk the current file tree, including nested data categories.

    The website's POST /files/v2 is a read-only listing operation. Do not use
    the metadata's 'added' list: it only describes the latest revision.
    """
    tree = read_json(f"{BASE_URL}/files/v2", {
        "folder": "psi-data/",
        "fileType": "study",
        "studyId": accession,
        "version": study_version,
        "obfuscationcode": "",
    })
    if not isinstance(tree, dict) or not isinstance(tree.get("files"), list):
        raise RuntimeError("NASA's file-list response has changed or is unavailable.")

    def walk(nodes):
        for node in nodes:
            if node.get("visible") is False:
                continue
            if node.get("directory") is False and node.get("id"):
                yield node
            yield from walk(node.get("files", []))

    unique = {node["id"]: node for node in walk(tree["files"])}
    return sorted(unique.values(), key=lambda node: node["key"].casefold())


def download_file(accession, study_version, entry, output_dir):
    """Resolve a fresh download link, stream to disk, and check the byte count."""
    if entry.get("restricted") or entry.get("restrictedAccess"):
        raise RuntimeError("This file requires access through NASA's website.")
    params = urlencode({
        "file": entry["id"],
        "version": entry["version"],
        "studyVersion": study_version,
        "redirect": "false",
    })
    with request(f"{BASE_URL}/studies/{quote(accession)}/download?{params}") as response:
        url = response.read().decode("utf-8").strip()
    # The current API returns plain text; also accept a JSON-quoted URL.
    if url.startswith('"'):
        url = json.loads(url)
    if not isinstance(url, str) or urlparse(url).scheme != "https":
        raise RuntimeError("NASA did not return an HTTPS download URL.")

    # Keep remote paths from writing outside the chosen output directory.
    name = PurePosixPath(entry["key"]).name
    if name in ("", ".", "..") or "\\" in name or ":" in name:
        raise ValueError("The server returned an unsafe filename.")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / name
    if destination.exists():
        raise FileExistsError(f"Already exists (not overwritten): {destination}")

    temporary = None
    try:
        with request(url) as response:
            if "text/html" in response.headers.get("Content-Type", "").lower():
                raise RuntimeError("Received an HTML page instead of the requested data file.")
            with tempfile.NamedTemporaryFile(dir=output_dir, delete=False) as stream:
                temporary = Path(stream.name)
                count = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    stream.write(chunk)
                    count += len(chunk)
        expected = entry.get("bytes_size")
        if expected is not None and count != int(expected):
            raise RuntimeError(f"Incomplete download: expected {expected} bytes, received {count}.")
        # A hard link publishes the completed file without replacing an existing one.
        os.link(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return destination


def preview_csv(path):
    """Read the first five CSV rows using Python's built-in csv module."""
    if path.suffix.lower() != ".csv":
        return
    print("  First five CSV rows:")
    with path.open(newline="", encoding="utf-8-sig", errors="replace") as stream:
        for _, row in zip(range(5), csv.reader(stream)):
            print(" ", row)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--page", default=DEFAULT_PAGE, help="Investigation URL or PSI ID")
    parser.add_argument("--filter", default="", help="Case-insensitive filename/path substring")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--download-first", action="store_true",
                       help="Download the smallest matching public file; prefer CSV")
    group.add_argument("--download-all", action="store_true", help="Download all matching public files")
    parser.add_argument("--output", type=Path, default=Path("nasa_downloads"))
    parser.add_argument("--preview", action="store_true", help="Print five rows of downloaded CSVs")
    parser.add_argument("--save-metadata", action="store_true", help="Save metadata and file listing as JSON")
    args = parser.parse_args()

    accession = investigation_id(args.page)
    metadata = get_metadata(accession)
    version = metadata["version"]
    files = list_files(accession, version)
    matches = [f for f in files if args.filter.casefold() in f["key"].casefold()]
    print(f"{accession}: {metadata.get('title', '')}")
    print(f"{len(matches)} matching files ({len(files)} total), investigation version {version}\n")
    for index, entry in enumerate(matches, 1):
        restricted = " [restricted]" if entry.get("restricted") or entry.get("restrictedAccess") else ""
        print(f"{index:3}. {entry.get('size', '?'):>10}  {entry['key']}{restricted}")

    output_dir = args.output / accession
    if args.save_metadata:
        output_dir.mkdir(parents=True, exist_ok=True)
        for name, data in (("metadata.json", metadata), ("files.json", files)):
            with (output_dir / name).open("x", encoding="utf-8") as stream:
                json.dump(data, stream, indent=2, ensure_ascii=False)
        print(f"\nSaved JSON to {output_dir.resolve()}")

    if not (args.download_first or args.download_all):
        print("\nAdd --download-first --preview to download and inspect a small CSV.")
        return 0
    selected = [f for f in matches if not (f.get("restricted") or f.get("restrictedAccess"))]
    if not selected:
        raise RuntimeError("No matching public files available for download.")
    if args.download_first:
        selected = [min(selected, key=lambda f: (
            not f["key"].lower().endswith(".csv"), f.get("bytes_size", float("inf"))))]
    failures = 0
    for entry in selected:
        try:
            path = download_file(accession, version, entry, output_dir)
            print(f"\nDownloaded: {path.resolve()}")
            if args.preview:
                preview_csv(path)
        except (OSError, ValueError, RuntimeError) as exc:
            failures += 1
            print(f"Download failed for {entry['key']}: {exc}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except HTTPError as exc:
        print(f"NASA returned HTTP {exc.code}. Check availability/access at {DEFAULT_PAGE}", file=sys.stderr)
        sys.exit(1)
    except (URLError, OSError, ValueError, KeyError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
