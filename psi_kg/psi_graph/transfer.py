"""Resume versioned NASA downloads without loading the file into memory."""

import json
import os
import re
from pathlib import Path, PurePosixPath
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

from . import nasa_access as nasa
from .budget import active_budget, guarded_write
from .common import read_json, write_json


def download_file(accession, study_version, entry, output_dir):
    if entry.get("restricted") or entry.get("restrictedAccess"):
        raise RuntimeError("NASA file is restricted")
    expected = entry.get("bytes_size")
    if (budget := active_budget.get()) and expected is not None:
        part = Path(output_dir) / (PurePosixPath(entry["key"]).name + ".part")
        state = part.with_name(PurePosixPath(entry["key"]).name + ".transfer.json")
        budget.track(part)
        resumable = (
            part.stat().st_size
            if part.exists() and state.exists() and read_json(state).get("validator")
            else 0
        )
        budget.check(max(0, int(expected) - resumable))
    url = resolve_download_url(accession, study_version, entry)
    name = PurePosixPath(entry["key"]).name
    if name in ("", ".", "..") or "\\" in name or ":" in name:
        raise ValueError("Unsafe NASA filename")
    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    return _transfer(url, entry, folder, name)


def resolve_download_url(accession, study_version, entry):
    params = urlencode(
        dict(
            file=entry["id"],
            version=entry["version"],
            studyVersion=study_version,
            redirect="false",
        )
    )
    with nasa.request(
        f"{nasa.BASE_URL}/studies/{quote(accession)}/download?{params}"
    ) as response:
        url = response.read().decode().strip()
    if url.startswith('"'):
        url = json.loads(url)
    if urlparse(url).scheme != "https":
        raise ValueError("NASA did not return an HTTPS download URL")
    return url


def _transfer(url, entry, folder, name):
    destination = folder / name
    part = folder / (name + ".part")
    state = folder / (name + ".transfer.json")
    if destination.exists():
        raise FileExistsError(destination)
    expected = entry.get("bytes_size")
    if expected is not None:
        expected = int(expected)
    saved = read_json(state) if state.exists() else {}
    validator = saved.get("validator")
    offset = part.stat().st_size if part.exists() and validator else 0
    budget = active_budget.get()
    if budget:
        budget.track(part)
    headers = {"User-Agent": "NASA-PSI-KG/1.0"}
    if offset:
        headers.update(Range=f"bytes={offset}-", **{"If-Range": validator})
    with urlopen(
        Request(url, headers=headers), timeout=120, context=nasa.tls_context()
    ) as response:
        status = response.status
        if "text/html" in response.headers.get("Content-Type", "").lower():
            raise RuntimeError("Received HTML instead of a scientific file")
        if status == 206:
            match = re.fullmatch(
                r"bytes (\d+)-(\d+)/(\d+)", response.headers.get("Content-Range", "")
            )
            if (
                not match
                or int(match[1]) != offset
                or (expected is not None and int(match[3]) != expected)
            ):
                raise RuntimeError(
                    "Invalid partial response; refusing to join inconsistent bytes"
                )
            total = int(match[3])
        elif status == 200:
            offset = 0  # Server ignored Range or content validator changed.
            total = expected
        else:
            raise RuntimeError(f"Unexpected HTTP status {status}")
        etag = response.headers.get("ETag")
        validator = (
            etag
            if etag and not etag.startswith("W/")
            else response.headers.get("Last-Modified")
        )
        count = offset
        with part.open("ab" if offset else "wb") as stream:
            if budget:
                advertised = response.headers.get("Content-Length")
                if advertised is not None:
                    budget.check(int(advertised))
            write_json(state, {"validator": validator})
            while block := response.read(1024 * 1024):
                guarded_write(stream, block)
                count += len(block)
        if total is not None and count != total:
            raise RuntimeError(
                f"Incomplete download: expected {total}, received {count}; partial file retained"
            )
    # NFS supports hard links; publish only after the stream completes and size matches.
    os.link(part, destination)
    part.unlink()
    if budget:
        budget.track(destination)
    state.unlink(missing_ok=True)
    return destination
