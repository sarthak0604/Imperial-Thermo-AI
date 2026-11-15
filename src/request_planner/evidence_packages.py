"""Explicitly approved local evidence packages, separate from graph inventory."""

import hashlib
import json
from math import sqrt
from functools import lru_cache
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
    title: str | None = None
    scenario: dict | None = None
    bundled: bool = False
    notes: str | None = None
    investigation_id: str | None = None


@lru_cache(maxsize=1)
def bundled_packages():
    from thermo_reference.build_demo import REFERENCE_ROOT, build_demo, read_json

    from .function_registry import function_root, input_contract, model_spec
    from .reviewed_scenarios import PACKAGE_INVESTIGATIONS

    packages = {}

    def register(package_id, model_id, title, payload, notes=None):
        raw = json.dumps(payload, sort_keys=True, allow_nan=False).encode("utf-8")
        evidence = payload.get("evidence", {})
        sources = evidence.get("sources", [])
        illustrative = evidence.get("illustrative", evidence.get("provenance", {}).get("illustrative", True))
        packages[package_id] = (EvidencePackage(
            id=package_id, model_id=model_id, title=title, bundled=True,
            payload_path=model_spec(model_id)["example"], sha256=hashlib.sha256(raw).hexdigest(),
            review_status="approved", provenance=sources or [{"locator": title}], illustrative=illustrative,
            notes=notes, investigation_id=PACKAGE_INVESTIGATIONS.get(package_id),
            scenario=payload.get("request", {}).get("scenario") or payload.get("params") or payload.get("inputs"),
        ), raw)

    for number in range(1, 21):
        model_id = f"THM-{number:02}"
        spec = model_spec(model_id)
        example = read_json(function_root().joinpath(spec["example"]))
        payload = example.get("example_request", example)
        if model_id == "THM-08":
            # Its example describes lunar gravity. The model expects a ratio to Earth gravity.
            payload["params"]["gravity_g"] = "Moon"
        if model_id == "THM-09":
            payload["params"].setdefault("u_flow_ms", input_contract(model_id)["defaults"]["u_flow_ms"])
        register("example-" + model_id.lower(), model_id, spec["description"], payload)
    for case in read_json(REFERENCE_ROOT / "demo_cases.json")["cases"]:
        _, payload = build_demo(case["id"])
        register(case["id"], case["model_id"], case["title"], payload, case["notes"])

    flex = json.loads(packages["flex_r377_decane"][1])
    register("flex_r377_regression", "THM-10", "FLEX R377 hot-stage droplet regression",
             flex_r377_regression(flex),
             "The prompt leaves the fuel and initial diameter open. This example uses n-decane run "
             "R377 and applies the published quasi-steady hot-stage D² slope.")
    return packages


def flex_r377_regression(flex):
    """Translate the reviewed FLEX stage endpoints into the THM-10 input contract."""
    calibration = next(run for material in flex["evidence"]["materials"]
                       for run in material["calibrations"] if run["id"] == "R377")
    initial = calibration["observed_initial_diameter_mm"]
    duration = calibration["hot_extinction_time_s"]
    rate = calibration["reported_hot_burning_rate_mm2_s"]
    end_squared = initial ** 2 - rate * duration
    profile_id = "flex_r377_hot_stage"
    operating_state = {
        "d0_mm": initial, "x_o2": calibration["oxygen_pct"] / 100,
        "pressure_kpa": calibration["pressure_kPa"], "t_amb_k": 298.15,
    }
    return {
        "request": {
            "topic": "droplet_combustion", "analysis": "estimate_droplet_regression",
            "scenario": {"profile_id": profile_id, "fuel_type": "n-decane",
                         "process": "combustion", **operating_state,
                         "time_limit_s": duration, "endpoint_diameter_mm": sqrt(end_squared)},
        },
        "evidence": {
            "profiles": [{
                "id": profile_id, "fuel_type": "n-decane", "process": "combustion",
                "method": "measured_rate",
                "validity": {name: [value, value] for name, value in operating_state.items()},
                "regression_rate_mm2_s": rate,
            }],
            "provenance": {"illustrative": False, "type": "published_run_reconstruction",
                           "notes": ["Published quasi-steady hot-stage slope, applied up to the reported hot extinction time. "
                                     "Nominal ambient temperature is unused by the supplied-slope model."]},
            "sources": [{"role": "calibration", "url": calibration["source_url"].split("#")[0] + "#page=4",
                         "locator": "NASA FLEX §3.1 and figure 1(a), R377 hot-stage burning-rate constant"}],
        },
    }


class EvidencePackageRegistry:
    def __init__(self, manifest=None):
        self.root = Path(manifest).resolve().parent if manifest else None
        custom = [
            EvidencePackage.model_validate({**entry, "bundled": False})
            for entry in json.loads(Path(manifest).read_text(encoding="utf-8-sig"))["packages"]
        ] if manifest else []
        existing = {p.id for p in custom}
        self.packages = custom + [p for p, _ in bundled_packages().values() if p.id not in existing]
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
        if package.bundled:
            return package, json.loads(bundled_packages()[package.id][1])
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
