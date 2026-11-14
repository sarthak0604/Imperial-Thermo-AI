"""Full-coverage parsers with bounded-memory numerical inspection.

All CSV/XLSX rows are read. LLM text retains every nonnumeric cell, headers,
units, and deterministic per-column statistics; raw numbers remain in files.
PDF pages retain locators; visual figures are explicitly marked unparsed.
"""

import csv
import json
import math
import zipfile
from pathlib import Path, PurePosixPath

from bs4 import BeautifulSoup
from openpyxl import load_workbook
from pypdf import PdfReader

from .common import digest, file_hash, read_json, write_json

PARSER_VERSION = "1.0.4"


def section(locator, text):
    return {"locator": locator, "text": text}


def table(rows, name, retain_rows=False):
    stats = []
    text = []
    count = 0
    for rownum, row in enumerate(rows, 1):
        count += 1
        while len(stats) < len(row):
            stats.append(
                {
                    "numeric_count": 0,
                    "missing_count": 0,
                    "min": None,
                    "max": None,
                    "mean": 0.0,
                }
            )
        labels = []
        for col, value in enumerate(row):
            item = stats[col]
            if value is None or str(value).strip() == "":
                item["missing_count"] += 1
                continue
            try:
                number = float(value)
                if not math.isfinite(number):
                    item["missing_count"] += 1
                    continue
                item["numeric_count"] += 1
                item["min"] = (
                    number if item["min"] is None else min(item["min"], number)
                )
                item["max"] = (
                    number if item["max"] is None else max(item["max"], number)
                )
                item["mean"] += (number - item["mean"]) / item["numeric_count"]
            except (TypeError, ValueError):
                labels.append(f"column {col + 1}: {value}")
        # Preserve full first row, including numeric headings and ALL text cells.
        if rownum == 1:
            text.append(
                section(
                    f"{name}, row 1",
                    " | ".join(
                        f"column {i + 1}: {v}"
                        for i, v in enumerate(row)
                        if v is not None
                    ),
                )
            )
        elif labels or retain_rows:
            text.append(
                section(
                    f"{name}, row {rownum}",
                    " | ".join(
                        f"column {i + 1}: {v}"
                        for i, v in enumerate(row)
                        if v is not None and str(v).strip()
                    ),
                )
            )
    for item in stats:
        if not item["numeric_count"]:
            item["mean"] = None
    profile = {"rows": count, "columns": len(stats), "column_statistics": stats}
    text.append(
        section(
            f"{name}, computed profile (all {count} rows)",
            json.dumps(profile, ensure_ascii=False),
        )
    )
    return text, profile


def parse_file(path):
    suffix = path.suffix.lower()
    sections, details, warnings = [], {}, []
    if suffix == ".pdf":
        reader = PdfReader(path)
        missing = []
        for num, page in enumerate(reader.pages, 1):
            try:
                text = page.extract_text() or ""
                if text.strip():
                    sections.append(section(f"page {num}", text))
                else:
                    missing.append(num)
            except Exception as exc:
                missing.append(num)
                warnings.append(f"page {num}: {type(exc).__name__}")
        details = {
            "pages": len(reader.pages),
            "pages_without_extractable_text": missing,
            "figure_digitization": False,
        }
        # Text extraction is not a claim of parsing plotted values, equations or images.
        warnings.append(
            "PDF text extracted; raster figures, plotted data and visual-only equations are not digitized."
        )
        return sections, details, warnings, "partially_parsed"
    if suffix in (".csv", ".tsv"):
        with path.open(encoding="utf-8-sig", errors="replace", newline="") as f:
            sections, details = table(
                csv.reader(f, delimiter="\t" if suffix == ".tsv" else ","), "table"
            )
    elif suffix in (".xlsx", ".xlsm"):
        workbook = load_workbook(path, read_only=True, data_only=True)
        for sheet in workbook:
            texts, profile = table(
                sheet.iter_rows(values_only=True),
                f"sheet {sheet.title}",
                retain_rows=True,
            )
            sections.extend(texts)
            details[sheet.title] = profile
        workbook.close()
    elif suffix in (".html", ".htm"):
        soup = BeautifulSoup(path.read_text(errors="replace"), "html.parser")
        main = soup.select_one("main")
        if main is not None:
            soup = main
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        text = soup.get_text("\n", strip=True)
        if "Please wait while you are being redirected" in text:
            return (
                [],
                {},
                [
                    "Redirect-only HTML; no scientific article text was obtained at this URL."
                ],
                "inaccessible",
            )
        sections.append(section("HTML body", text))
        warnings.append(
            "HTML text only; full article access is not inferred from a publisher landing page."
        )
        return sections, details, warnings, "partially_parsed"
    elif suffix in (".txt", ".md", ".json", ".xml", ".yaml", ".yml", ".dat", ".asc"):
        with path.open(encoding="utf-8-sig", errors="replace") as f:
            block, start = [], 1
            for n, line in enumerate(f, 1):
                block.append(line)
                if len(block) == 200:
                    sections.append(section(f"lines {start}-{n}", "".join(block)))
                    block, start = [], n + 1
            if block:
                sections.append(
                    section(f"lines {start}-{start + len(block) - 1}", "".join(block))
                )
    elif suffix in (".h5", ".hdf5", ".hdf", ".nc"):
        import h5py
        import numpy as np

        with h5py.File(path, "r") as f:

            def inspect(name, obj):
                if not isinstance(obj, h5py.Dataset):
                    return
                info = {
                    "shape": list(obj.shape),
                    "dtype": str(obj.dtype),
                    "attributes": {str(k): str(v) for k, v in obj.attrs.items()},
                }
                if np.issubdtype(obj.dtype, np.number):
                    n, total, lo, hi = 0, 0.0, None, None
                    blocks = (
                        [()]
                        if not obj.shape
                        else (
                            (slice(start, min(start + 1024, obj.shape[0])),)
                            for start in range(0, obj.shape[0], 1024)
                        )
                    )
                    for idx in blocks:
                        arr = np.asarray(obj[idx]).ravel()
                        arr = arr[np.isfinite(arr)]
                        if arr.size:
                            n += arr.size
                            total += float(arr.sum())
                            lo = (
                                float(arr.min())
                                if lo is None
                                else min(lo, float(arr.min()))
                            )
                            hi = (
                                float(arr.max())
                                if hi is None
                                else max(hi, float(arr.max()))
                            )
                    info.update(
                        count=int(n), min=lo, max=hi, mean=total / n if n else None
                    )
                sections.append(section(f"dataset {name}", json.dumps(info)))

            f.visititems(inspect)
    elif suffix == ".mat":
        from scipy.io import whosmat

        details["arrays"] = whosmat(path)
        sections.append(section("MAT array inventory", json.dumps(details)))
        warnings.append("MAT array inventory only; values not inspected.")
        return sections, details, warnings, "partially_parsed"
    else:
        return [], {}, ["Unsupported format: " + suffix], "unsupported"
    status = "parsed" if sections else "partially_parsed"
    return sections, details, warnings, status


def extract_archive(record, output):
    children = []
    root = output / "archive_members" / digest(record["id"])
    with zipfile.ZipFile(record["local_path"]) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            name = PurePosixPath(info.filename)
            if (
                name.is_absolute()
                or ".." in name.parts
                or "\\" in info.filename
                or (info.external_attr >> 16) & 0o170000 == 0o120000
            ):
                raise ValueError("Unsafe archive member: " + info.filename)
            destination = root.joinpath(*name.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as src, destination.open("wb") as target:
                for chunk in iter(lambda: src.read(1024 * 1024), b""):
                    target.write(chunk)
            source = (
                record["source_url"]
                + "#member="
                + __import__("urllib.parse", fromlist=["quote"]).quote(
                    info.filename, safe=""
                )
            )
            children.append(
                dict(
                    id="res:" + record["id"].split(":")[1] + ":" + digest(source),
                    title=info.filename,
                    filename=name.name,
                    source_url=source,
                    storage_uri=destination.resolve().as_uri(),
                    local_path=str(destination.resolve()),
                    file_format=destination.suffix[1:].lower(),
                    resource_type="metadata"
                    if record["resource_type"] == "metadata"
                    else "supporting_file",
                    size_bytes=destination.stat().st_size,
                    sha256=file_hash(destination),
                    access_status="accessible",
                    extraction_status="pending",
                    parent_resource_id=record["id"],
                    discovered_via=record["source_url"],
                )
            )
    return children


def parse_resources(resources, metadata, source_url, output):
    documents = []
    # Metadata fields remain separately locatable; omit duplicate file revision lists.
    sections = [
        section(
            "metadata." + key,
            json.dumps(value, ensure_ascii=False)
            if not isinstance(value, str)
            else value,
        )
        for key, value in metadata.items()
        if key not in ("added", "modified", "removed", "contacts") and value
    ]
    documents.append(
        dict(
            id="metadata:" + metadata["accession"],
            source_url=source_url,
            title=metadata["title"],
            resource_type="investigation_metadata",
            sections=sections,
        )
    )
    seen = {r["id"] for r in resources}
    index = 0
    while index < len(resources):
        record = resources[index]
        index += 1
        if record["access_status"] != "accessible":
            # Explicit bibliographic evidence, never pretend to have read the full paper.
            if record.get("publication"):
                documents.append(
                    dict(
                        id=record["id"],
                        source_url=record["source_url"],
                        title=record["title"],
                        resource_type="citation",
                        sections=[
                            section(
                                "NASA publication citation (not full text)",
                                json.dumps(record["publication"], ensure_ascii=False),
                            )
                        ],
                    )
                )
            continue
        cache = output / "parsed" / (digest(record["id"]) + ".json")
        try:
            if record["file_format"] == "zip":
                children = extract_archive(record, output)
                for child in children:
                    if child["id"] not in seen:
                        resources.append(child)
                        seen.add(child["id"])
                sections = [
                    section(
                        "archive inventory", "\n".join(c["title"] for c in children)
                    )
                ]
                details, warnings, status = {"members": len(children)}, [], "parsed"
            elif (
                cache.exists()
                and (old := read_json(cache)).get("sha256") == record["sha256"]
                and old.get("parser_version") == PARSER_VERSION
            ):
                sections, details, warnings, status = (
                    old[k] for k in ("sections", "details", "warnings", "status")
                )
            else:
                sections, details, warnings, status = parse_file(
                    Path(record["local_path"])
                )
            result = dict(
                id=record["id"],
                title=record["title"],
                source_url=record["source_url"],
                resource_type=record["resource_type"],
                sha256=record["sha256"],
                parser_version=PARSER_VERSION,
                sections=sections,
                details=details,
                warnings=warnings,
                status=status,
            )
            write_json(cache, result)
            record.update(
                extraction_status=status,
                extraction_warnings=warnings,
                parse_details=details,
                parsed_path=str(cache.resolve()),
            )
            if status == "inaccessible":
                record["access_status"] = "redirect_only"
                record.pop("storage_uri", None)
            if sections:
                documents.append(result)
            print(f"parse {status}: {record['filename']}", flush=True)
        except Exception as exc:
            record.update(
                extraction_status="failed",
                extraction_error=f"{type(exc).__name__}: {str(exc)[:300]}",
            )
    write_json(output / "documents.json", documents)
    write_json(
        output / "resources_manifest.json",
        dict(source_url=source_url, resources=resources),
    )
    return documents


def chunks(document, budget=45000):
    """Bound request size without dropping sections or imposing a total-content cap."""
    current, size = [], 0
    for original in document["sections"]:
        text = original["text"]
        for offset in range(0, max(1, len(text)), budget):
            part = section(original["locator"], text[offset : offset + budget])
            if current and size + len(part["text"]) > budget:
                yield current
                current, size = [], 0
            current.append(part)
            size += len(part["text"])
    if current:
        yield current
