"""Explicit allowlist of repository functions, never model-supplied module paths."""

from importlib import resources, util
import json
from pathlib import Path


LEGACY = {1, 2, 3, 7, 8, 9}
TITLES = [
    "Adiabatic flame temperature and equilibrium", "Mixture transport and Lewis number",
    "Stoichiometric mixture fraction", "Oxygen-consumption heat release",
    "Opposed-flow flame spread", "Concurrent-flow flame spread", "Damkohler blowoff",
    "Partial-gravity mixed convection", "Spalding mass transfer",
    "Droplet regression", "Two-stage cool flame", "Multicomponent evaporation",
    "Radiative quenching", "Radiative heat fraction", "Soot inception",
    "Solid ignition and conduction", "Limiting oxygen", "Suppression heat capacity",
    "Closed cabin response", "Smoke aerosol transport",
]


def model_spec(model_id):
    if model_id not in {f"THM-{n:02}" for n in range(1, 21)}:
        raise ValueError("Unknown THM function")
    number = int(model_id[-2:])
    legacy = number in LEGACY
    return {
        "model_id": model_id, "description": TITLES[number - 1],
        "module": f"{model_id}.py" if legacy else f"{model_id}/thm_{number:02}.py",
        "example": f"{model_id}_example.json" if legacy else f"{model_id}/{model_id}_input.json",
        "entrypoint": "run_from_json_payload" if legacy else "run_request",
        "requires_evidence": not legacy,
    }


def function_root():
    try:
        return resources.files("thermo_functions")
    except ModuleNotFoundError:
        return Path(__file__).resolve().parents[1] / "Functions"


def _shape(value, key=""):
    if key in {"topic", "analysis"}:
        return value
    if isinstance(value, dict):
        return {k: _shape(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [_shape(value[0])] if value else []
    return f"<{type(value).__name__}>"


def operation_catalog():
    catalog = []
    for n in range(1, 21):
        spec = model_spec(f"THM-{n:02}")
        template = json.loads(function_root().joinpath(spec["example"]).read_text())
        payload = template.get("example_request", template)
        catalog.append({
            "model_id": spec["model_id"], "description": spec["description"],
            "input_shape": _shape(payload),
            "requires_downloaded_evidence": spec["requires_evidence"],
            "dependencies": ["numpy", "scipy"] if n == 16 else [],
        })
    return catalog


def run_model(model_id, payload):
    spec = model_spec(model_id)
    # The path comes solely from the allowlist above.
    with resources.as_file(function_root().joinpath(spec["module"])) as path:
        module_spec = util.spec_from_file_location(f"thermo_{model_id.replace('-', '_')}", path)
        module = util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        return getattr(module, spec["entrypoint"])(payload)
