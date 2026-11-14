"""Use the canonical nasa_access adapter; resolve public linked literature."""

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import unquote, urlencode, urljoin, urlparse

from bs4 import BeautifulSoup

from . import nasa_access as nasa
from .common import digest, file_hash, now, read_json, write_json
from .transfer import download_file


def resolver_url(accession, version, entry):
    return f"{nasa.BASE_URL}/studies/{accession}/download?" + urlencode(
        {
            "file": entry["id"],
            "version": entry["version"],
            "studyVersion": version,
            "redirect": "true",
        }
    )


def discover(url, output, refresh=False):
    accession = nasa.investigation_id(url)
    output.mkdir(parents=True, exist_ok=True)
    if refresh or not (output / "metadata.json").exists():
        write_json(output / "metadata.json", nasa.get_metadata(accession))
    metadata = read_json(output / "metadata.json")
    if refresh or not (output / "files.json").exists():
        write_json(
            output / "files.json", nasa.list_files(accession, metadata["version"])
        )
    files = read_json(output / "files.json")
    previous = (
        {r["id"]: r for r in read_json(output / "resources_manifest.json")["resources"]}
        if (output / "resources_manifest.json").exists()
        else {}
    )
    resources = []
    for entry in files:
        source = resolver_url(accession, metadata["version"], entry)
        rid = "res:" + accession + ":" + digest(entry["id"])
        record = previous.get(rid, {})
        if record and (
            record.get("nasa_file_version") != entry["version"]
            or record.get("investigation_version") != metadata["version"]
        ):
            for field in ("local_path", "storage_uri", "sha256", "parsed_path"):
                record.pop(field, None)
            record.update(access_status="not_verified", extraction_status="pending")
        record.update(
            id=rid,
            title=Path(entry["key"]).name,
            filename=Path(entry["key"]).name,
            source_url=source,
            file_format=Path(entry["key"]).suffix[1:].lower(),
            resource_type={
                "Presentations": "presentation",
                "Reports": "report",
                "Analyzed Data": "dataset",
                "Raw Data": "dataset",
                "metadata": "metadata",
            }.get(entry.get("sortingCategory"), "supporting_file"),
            nasa_file_id=entry["id"],
            nasa_path=entry["key"],
            nasa_file_version=entry["version"],
            investigation_version=metadata["version"],
            size_bytes=entry.get("bytes_size"),
            discovered_via=url,
            entry=entry,
        )
        record.setdefault("access_status", "not_verified")
        record.setdefault("extraction_status", "pending")
        resources.append(record)
    # A DOI is a verified bibliographic link, not a guessed download URL.
    for index, publication in enumerate(metadata.get("publications", [])):
        doi = publication.get("doi", "").strip()
        source = (
            f"https://doi.org/{doi}"
            if doi
            else f"{nasa.BASE_URL}/repo/investigations/{accession}#publications/{index}"
        )
        rid = "res:" + accession + ":" + digest(source)
        record = previous.get(rid, {})
        record.update(
            id=rid,
            title=publication["title"],
            filename=None,
            source_url=source,
            file_format=None,
            resource_type="paper",
            size_bytes=None,
            discovered_via=url,
            doi=doi or None,
            publication=publication,
        )
        record.setdefault("access_status", "not_verified" if doi else "citation_only")
        record.setdefault("extraction_status", "pending" if doi else "metadata_only")
        resources.append(record)
    retained = {r["id"] for r in resources}
    for r in previous.values():
        if (
            r["id"] not in retained
            and not r.get("parent_resource_id")
            and not r.get("entry")
        ):
            resources.append(r)
    return metadata, resources


def fetch_external(record, output):
    """Cache the actual publisher response. Follow article PDF and OA repository links."""
    folder = output / "downloads" / digest(record["source_url"])
    folder.mkdir(parents=True, exist_ok=True)
    next_url, visited = record["source_url"], set()
    while True:
        if next_url in visited:
            raise RuntimeError("Publisher redirect loop")
        visited.add(next_url)
        with nasa.request(next_url) as response:
            record["resolved_url"] = response.url
            content_type = response.headers.get("Content-Type", "").lower()
            fmt = (
                "pdf"
                if "pdf" in content_type
                else "html"
                if "html" in content_type
                else Path(urlparse(response.url).path).suffix[1:] or "txt"
            )
            filename = "document." + fmt
            path = folder / filename
            with path.open("wb") as f:
                for block in iter(lambda: response.read(1024 * 1024), b""):
                    f.write(block)
        if fmt != "html":
            break
        soup = BeautifulSoup(path.read_text(errors="replace"), "html.parser")
        redirect = soup.select_one("input#redirectURL")
        refresh = soup.find("meta", attrs={"http-equiv": re.compile("refresh", re.I)})
        if redirect and redirect.get("value"):
            next_url = urljoin(record["resolved_url"], unquote(redirect["value"]))
        elif refresh and (
            match := re.search(
                r"url\s*=\s*['\"]?([^'\"]+)", refresh.get("content", ""), re.I
            )
        ):
            next_url = urljoin(record["resolved_url"], match.group(1).strip())
        else:
            break
        if urlparse(next_url).scheme != "https":
            raise RuntimeError("Non-HTTPS publisher redirect")
    record.update(filename=filename, file_format=fmt, size_bytes=path.stat().st_size)
    children = []
    if fmt == "html":
        soup = BeautifulSoup(path.read_text(errors="replace"), "html.parser")
        # Avoid treating login/CAPTCHA/error HTML as a parsed scientific paper.
        text = soup.get_text(" ", strip=True)
        if any(
            marker in text[:3000].lower()
            for marker in [
                "verify you are human",
                "just a moment...",
                "access denied",
                "checking your browser",
            ]
        ):
            raise RuntimeError(
                "Publisher returned an access challenge instead of article content"
            )
        links = [m.get("content") for m in soup.select('meta[name="citation_pdf_url"]')]
        links += [
            urljoin(record["resolved_url"], a["href"])
            for a in soup.select("a[href]")
            if re.search(r"\.pdf(?:$|\?)|/pdf(?:/|$|\?)", a["href"], re.I)
        ]
        for link in sorted(set(filter(None, links))):
            absolute = urljoin(record["resolved_url"], link)
            if urlparse(absolute).scheme != "https":
                continue
            children.append(
                dict(
                    id="res:" + record["id"].split(":")[1] + ":" + digest(absolute),
                    title=record["title"],
                    filename=None,
                    source_url=absolute,
                    file_format=None,
                    resource_type="paper",
                    size_bytes=None,
                    discovered_via=record["source_url"],
                    doi=record.get("doi"),
                    access_status="not_verified",
                    extraction_status="pending",
                )
            )
    record.update(
        storage_uri=path.resolve().as_uri(),
        local_path=str(path.resolve()),
        sha256=file_hash(path),
        access_status="accessible",
        accessed_at=now(),
        download_adapter_version=2,
    )
    record.pop("error", None)
    return children


def download_one(record, metadata, output):
    path = Path(record.get("local_path", ""))
    if record.get("parent_resource_id"):
        # Archive members are retrieved through their parent ZIP, never their URL fragment.
        if path.is_file() and file_hash(path) == record.get("sha256"):
            return []
        record.update(
            access_status="inaccessible",
            extraction_status="failed",
            error="Archive member missing; reparse parent archive",
        )
        return []
    if (
        record.get("sha256")
        and path.is_file()
        and file_hash(path) == record["sha256"]
        and ("entry" in record or record.get("download_adapter_version") == 2)
    ):
        record.update(
            filename=path.name,
            file_format=path.suffix.lstrip(".").lower(),
            size_bytes=path.stat().st_size,
        )
        return linked_resources(record) if record.get("file_format") == "html" else []
    if record["access_status"] == "citation_only":
        return []
    for attempt in range(3):
        try:
            if "entry" in record:
                entry = record["entry"]
                if entry.get("restricted") or entry.get("restrictedAccess"):
                    record.update(
                        access_status="restricted", extraction_status="inaccessible"
                    )
                    return []
                # Versioned paths prevent a same-size older file from being reused.
                version_key = f"{entry['id']}:{entry['version']}:{metadata['version']}"
                folder = output / "downloads" / digest(version_key)
                path = folder / record["filename"]
                if not path.exists():
                    path = download_file(
                        metadata["accession"], metadata["version"], entry, folder
                    )
                if path.stat().st_size != entry.get("bytes_size", path.stat().st_size):
                    raise RuntimeError("Cached size does not match NASA file listing")
                record.update(
                    storage_uri=path.resolve().as_uri(),
                    local_path=str(path.resolve()),
                    sha256=file_hash(path),
                    access_status="accessible",
                    accessed_at=now(),
                    size_bytes=path.stat().st_size,
                )
                record.pop("error", None)
                return []
            return fetch_external(record, output)
        except Exception as exc:
            status = getattr(exc, "code", None)
            # Never log secret-bearing headers or temporary signed URLs.
            record.update(
                access_status="inaccessible",
                extraction_status="inaccessible",
                error=f"{type(exc).__name__}: HTTP {status}"
                if status
                else type(exc).__name__,
            )
            for field in ("storage_uri", "local_path", "sha256"):
                record.pop(field, None)
            if status in (401, 403, 404, 410, 451):
                break
            time.sleep(2**attempt)
    return []


def download_all(resources, metadata, output, workers=4, storage_output=None):
    seen = {r["source_url"] for r in resources}
    pending = resources[:]
    while pending:
        children = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            jobs = {
                pool.submit(download_one, r, metadata, storage_output or output): r
                for r in pending
            }
            for future in as_completed(jobs):
                r = jobs[future]
                children.extend(future.result())
                print(f"download {r['access_status']}: {r['title']}", flush=True)
                write_json(
                    output / "resources_manifest.json",
                    dict(
                        source_url=f"https://psi.nasa.gov/physci/repo/data/investigations/{metadata['accession']}",
                        generated_at=now(),
                        resources=resources,
                    ),
                )
        pending = []
        for child in children:
            if child["source_url"] not in seen:
                seen.add(child["source_url"])
                resources.append(child)
                pending.append(child)
    return resources


def discover_open_versions(resources, metadata, output):
    """Ask NASA NTRS for the investigation's explicitly listed publication DOIs.

    Only exact DOI matches qualify; no crawling of unrelated investigations or
    arbitrary bibliography links. Every response is saved for provenance.
    """
    found = []
    seen = {r["source_url"] for r in resources}
    audit = []
    seen_dois = set()
    for r in list(resources):
        doi = r.get("doi")
        if not doi or r.get("resource_type") != "paper" or doi in seen_dois:
            continue
        seen_dois.add(doi)
        url = "https://ntrs.nasa.gov/api/citations/search?" + urlencode({"q": doi})
        try:
            cache = output / "discovery" / (digest(url) + ".json")
            data = read_json(cache) if cache.exists() else nasa.read_json(url)
            write_json(cache, data)
            matches = data.get("results", [])
            for match in matches:
                if doi.casefold() not in json.dumps(match).casefold():
                    continue
                for d in match.get("downloads", []):
                    link = d.get("links", {}).get("pdf") or d.get("links", {}).get(
                        "original"
                    )
                    if not link:
                        continue
                    link = urljoin("https://ntrs.nasa.gov", link)
                    if link in seen:
                        continue
                    seen.add(link)
                    found.append(
                        dict(
                            id="res:" + metadata["accession"] + ":" + digest(link),
                            title=r["title"],
                            filename=None,
                            source_url=link,
                            file_format=None,
                            resource_type="paper",
                            size_bytes=None,
                            doi=doi,
                            discovered_via=url,
                            access_status="not_verified",
                            extraction_status="pending",
                        )
                    )
            audit.append(dict(source_url=url, status="searched", matches=len(matches)))
        except Exception as exc:
            audit.append(
                dict(source_url=url, status="failed", error=type(exc).__name__)
            )
    write_json(output / "discovery_report.json", audit)
    return resources + found


def discover_document_links(documents, resources, metadata):
    """Follow explicit links in data indexes/metadata, excluding cited background bibliographies."""
    seen = {r["source_url"] for r in resources}
    added = []
    for doc in documents:
        if doc["resource_type"] not in (
            "metadata",
            "investigation_metadata",
        ) and not doc["title"].lower().endswith((".xlsx", ".txt")):
            continue
        for section in doc["sections"]:
            for raw in re.findall(r'https://[^\s<>"|]+', section["text"]):
                link = raw.rstrip(".,;)]}")
                parsed = urlparse(link)
                if parsed.hostname in ("doi.org", "dx.doi.org"):
                    link = "https://doi.org/" + parsed.path.lstrip("/")
                elif not re.search(
                    r"\.(?:pdf|csv|xlsx|txt|zip|h5|nc)(?:$|\?)", link, re.I
                ):
                    continue
                if link in seen:
                    continue
                seen.add(link)
                doi = (
                    parsed.path.lstrip("/")
                    if parsed.hostname in ("doi.org", "dx.doi.org")
                    else None
                )
                added.append(
                    dict(
                        id="res:" + metadata["accession"] + ":" + digest(link),
                        title=doi or Path(parsed.path).name,
                        filename=None,
                        source_url=link,
                        file_format=None,
                        resource_type="paper" if doi else "supporting_file",
                        size_bytes=None,
                        doi=doi,
                        discovered_via=doc["source_url"],
                        discovery_locator=section["locator"],
                        access_status="not_verified",
                        extraction_status="pending",
                    )
                )
    return added


def linked_resources(record):
    soup = BeautifulSoup(
        Path(record["local_path"]).read_text(errors="replace"), "html.parser"
    )
    if record.get("title") == record.get("doi"):
        heading = soup.find("meta", attrs={"name": "citation_title"}) or soup.find("h1")
        if heading:
            record["title"] = heading.get("content") or heading.get_text(
                " ", strip=True
            )
    links = [m.get("content") for m in soup.select('meta[name="citation_pdf_url"]')]
    links += [
        a["href"]
        for a in soup.select("a[href]")
        if re.search(r"\.pdf(?:$|\?)|/pdf|/article/am/", a["href"], re.I)
    ]
    result = []
    for link in sorted(set(filter(None, links))):
        url = urljoin(record.get("resolved_url", record["source_url"]), link)
        if urlparse(url).scheme == "https":
            result.append(
                dict(
                    id="res:" + record["id"].split(":")[1] + ":" + digest(url),
                    title=record["title"],
                    filename=None,
                    source_url=url,
                    file_format=None,
                    resource_type="paper",
                    size_bytes=None,
                    discovered_via=record["source_url"],
                    doi=record.get("doi"),
                    access_status="not_verified",
                    extraction_status="pending",
                )
            )
    return result
