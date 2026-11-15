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
            "input_contract": input_contract(spec["model_id"]),
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


PUBLIC_FUNCTIONS = {
    'THM-01': 'calc_adiabatic_flame_temp_equilibrium',
    'THM-02': 'compute_mixture_transport_and_lewis_number',
    'THM-03': 'calc_stoichiometric_mixture_fraction_zst',
    'THM-07': 'evaluate_damkohler_blowoff_extinction',
    'THM-08': 'calc_mixed_convection_richardson_scaling',
    'THM-09': 'calc_spalding_mass_transfer_b_number',
}


def input_contract(model_id):
    """Read actual implementation signatures; examples do not define defaults."""
    import ast
    spec = model_spec(model_id)
    tree = ast.parse(function_root().joinpath(spec['module']).read_text())
    candidates = [node for node in tree.body if isinstance(node, ast.FunctionDef) and
                  node.name == PUBLIC_FUNCTIONS.get(model_id)]
    if not candidates:
        candidates = [node for node in tree.body if isinstance(node, ast.FunctionDef) and
                      node.name.startswith(('calc_', 'evaluate_')) and len(node.args.args) > 1]
    if spec['requires_evidence']:
        return {'required_sections': ['request', 'evidence'], 'validator': spec['entrypoint'],
                'calibration_policy': 'Sourced evidence with matching setup/run and applicable domain is required.',
                'example_is_evidence': False}
    if not candidates:
        return {'validator': spec['entrypoint'], 'required_inputs': 'See implementation validator', 'defaults': {}}
    node = candidates[0]
    defaults = {}
    args = node.args.args
    for arg, default in zip(args[len(args)-len(node.args.defaults):], node.args.defaults):
        try:
            defaults[arg.arg] = ast.literal_eval(default)
        except ValueError:
            defaults[arg.arg] = ast.unparse(default)
    for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
        if default is not None:
            try:
                defaults[arg.arg] = ast.literal_eval(default)
            except ValueError:
                defaults[arg.arg] = ast.unparse(default)
    names = [arg.arg for arg in args + node.args.kwonlyargs]
    return {'callable': node.name, 'required_inputs': [name for name in names if name not in defaults],
            'defaults': defaults, 'documentation': ast.get_docstring(node), 'validator': spec['entrypoint']}


def capability_matrix(graph):
    """Describe actual snapshot inputs separately from installed function availability."""
    props = [n['properties'] for n in graph['nodes'] if n['type'] == 'Resource']
    json_files = sum(str(p.get('file_format', '')).casefold() == 'json' for p in props)
    return [{'model_id': f'THM-{n:02}', 'implemented': True,
             'requires_evidence': model_spec(f'THM-{n:02}')['requires_evidence'],
             'scenario_only': n in LEGACY, 'json_resource_count': json_files,
             'verified_run_mapping_count': sum(bool(p.get('run_ids_verified')) for p in props),
             'missing_evidence': [] if n in LEGACY or json_files else ['No function-compatible JSON evidence resources in this graph.']}
            for n in range(1,21)]
