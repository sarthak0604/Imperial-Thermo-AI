"""Explicitly approved local evidence packages, separate from graph inventory."""

import hashlib
import json
from pathlib import Path

from pydantic import Field

from .models import Contract


class EvidencePackage(Contract):
    id: str
    model_id: str
    payload_path: str
    sha256: str = Field(pattern="^[a-f0-9]{64}$")
    review_status: str
    provenance: list[dict] = Field(min_length=1)
    illustrative: bool = False


class EvidencePackageRegistry:
    def __init__(self, manifest):
        self.root = Path(manifest).resolve().parent
        self.packages = [
            EvidencePackage.model_validate(x)
            for x in json.loads(Path(manifest).read_text())["packages"]
        ]
        if len({p.id for p in self.packages}) != len(self.packages):
            raise ValueError("Duplicate evidence package IDs.")

    def load(self, package_id, model_id):
        matches = [
            p for p in self.packages if p.id == package_id and p.model_id == model_id
        ]
        if len(matches) != 1 or matches[0].review_status != "approved":
            raise ValueError(
                "An approved, model-compatible evidence package is required."
            )
        package = matches[0]
        path = (self.root / package.payload_path).resolve()
        if not path.is_relative_to(self.root) or path.stat().st_size > 10_000_000:
            raise ValueError("Evidence package path or size is invalid.")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != package.sha256:
            raise ValueError("Evidence package checksum changed.")
        payload = json.loads(raw)
        if not isinstance(payload.get("evidence"), dict):
            raise TypeError("Package must contain sourced evidence.")
        return package, payload
