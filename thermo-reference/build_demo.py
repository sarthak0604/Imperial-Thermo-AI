"""Build runnable THM input JSON from reviewed demo records.

Developed with SI assistance from OpenAI Codex.
"""

import argparse
from importlib.util import module_from_spec, spec_from_file_location
import json
from math import isclose
from pathlib import Path


REFERENCE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = REFERENCE_ROOT.parent


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def index_records(rows):
    indexed = {}
    for row in rows:
        key = row["id"]
        if key in indexed:
            raise ValueError(f"Duplicate record ID: {key}")
        indexed[key] = row
    return indexed


def get_member(container, key):
    return container[int(key)] if isinstance(container, list) else container[key]


def parent_and_key(obj, pointer):
    """Resolve a JSON Pointer to its containing object and final key."""
    if not pointer.startswith("/"):
        raise ValueError(f"Use a JSON Pointer beginning with '/': {pointer}")
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")]
    for part in parts[:-1]:
        obj = get_member(obj, part)
    key = int(parts[-1]) if isinstance(obj, list) else parts[-1]
    return obj, key


def build_demo(case_id):
    """Return the catalog entry and a fresh JSON-ready dict for one demo."""
    catalog = read_json(REFERENCE_ROOT / "demo_cases.json")
    cases = index_records(catalog["cases"])
    case = cases[case_id]
    base = REPO_ROOT / case["base_payload"]
    if not base.is_file():
        from request_planner.function_registry import function_root, model_spec

        base = function_root().joinpath(model_spec(case["model_id"])["example"])
    payload = read_json(base)

    for pointer in case.get("remove", []):
        parent, key = parent_and_key(payload, pointer)
        del parent[key]
    # Manifest sets are ordered by increasing path depth so parents land before children.
    for pointer, value in sorted(case.get("set", {}).items(), key=lambda item: item[0].count("/")):
        parent, key = parent_and_key(payload, pointer)
        parent[key] = value

    if "bindings" in case:
        records = index_records(read_json(REFERENCE_ROOT / "properties.json")["records"])
        evidence = payload["evidence"]
        field_provenance = evidence["provenance"].setdefault("property_bindings", {})
        sources = evidence["sources"]
        for pointer, record_id in case["bindings"].items():
            record = records[record_id]
            if record["usage"] == "sensitivity_only":
                raise ValueError(f"Record {record_id} needs an explicit sensitivity scenario.")
            parent, key = parent_and_key(payload, pointer)
            parent[key] = record["value"]
            field_provenance[pointer] = {
                "property_record_id": record_id, "kind": record["kind"],
                "unit": record["unit"], "conditions": record["conditions"],
                "sources": record["sources"],
            }
            for source in record["sources"]:
                entry = {"role": "reference_property", **source}
                if entry not in sources:
                    sources.append(entry)

    return case, payload


def check_demo(case_id):
    case, payload = build_demo(case_id)
    model_id = case["model_id"]
    model_dir = (REPO_ROOT / case["base_payload"]).parent
    module_name = f"thm_{model_id[-2:]}"
    spec = spec_from_file_location(module_name, model_dir / f"{module_name}.py")
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load {model_id} from {model_dir}.")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.run_request(payload)
    for path, expected in case["expected"].items():
        parent, key = parent_and_key(result, path)
        actual = parent[key]
        if type(expected) in (int, float):
            matches = type(actual) in (int, float) and isclose(actual, expected, rel_tol=1e-8, abs_tol=1e-9)
        else:
            matches = actual == expected
        if not matches:
            raise ValueError(f"{case_id} {path}: expected {expected!r}, received {actual!r}")
    return result


def main():
    catalog = read_json(REFERENCE_ROOT / "demo_cases.json")
    case_ids = tuple(index_records(catalog["cases"]))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_id", nargs="?", choices=case_ids)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--list", action="store_true", help="list available demo IDs")
    action.add_argument("--check", action="store_true", help="run and check one demo or all demos")
    args = parser.parse_args()

    if args.list:
        for case in catalog["cases"]:
            print(f'{case["id"]}: {case["model_id"]} — {case["title"]}')
    elif args.check:
        try:
            for case_id in (args.case_id,) if args.case_id else case_ids:
                check_demo(case_id)
                print(f"{case_id}: verified")
        except (ImportError, KeyError, OSError, TypeError, ValueError) as error:
            parser.exit(1, f"{error}\n")
    elif args.case_id:
        try:
            _, payload = build_demo(args.case_id)
            print(json.dumps(payload, indent=2, allow_nan=False))
        except (KeyError, OSError, TypeError, ValueError) as error:
            parser.exit(1, f"{error}\n")
    else:
        parser.error("choose a demo ID, --list, or --check")


if __name__ == "__main__":
    main()
