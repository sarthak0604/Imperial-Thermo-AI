"""Deterministic identities, atomic persistence, and evidence normalization."""

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()[:20]


def normalized(value):
    return " ".join(unicodedata.normalize("NFKC", value).split())


def slug(value):
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    from .budget import active_budget

    encoded = (
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")
    if budget := active_budget.get():
        budget.free_check(len(encoded))
    temporary.write_bytes(encoded)
    temporary.replace(path)


def read_json(path):
    return json.loads(Path(path).read_text())


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()
