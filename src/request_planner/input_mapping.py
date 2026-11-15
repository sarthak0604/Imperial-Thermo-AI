"""Assemble model-specific inputs from a checked, field-level extraction plan."""

from collections import defaultdict
import csv
from copy import deepcopy
import json
import re
from urllib.parse import urlsplit, urlunsplit

from .input_contracts import E, ROUTES, S, contract_for
from .input_sources import (
    MappingError, SUPPORTED_MEDIA, TEXT_MEDIA, convert, normalized_unit, parse_number,
    pointer_parts, verified_quote,
)


def mapping_from_request(request_json):
    if request_json is None:
        return None
    obj = json.loads(request_json)
    if not isinstance(obj, dict):
        raise MappingError("request_json must contain an object.")
    if "input_mapping" not in obj:
        return None
    mapping = obj["input_mapping"]
    if set(obj) != {"input_mapping"} or not isinstance(mapping, dict) or set(mapping) != {"assignments"}:
        raise MappingError("The raw-data request must contain only input_mapping.assignments.")
    items = mapping["assignments"]
    if not isinstance(items, list) or not 1 <= len(items) <= 500:
        raise MappingError("Supply one to 500 field assignments.")
    for item in items:
        if (not isinstance(item, dict) or set(item) != {"target", "source"}
                or not isinstance(item["source"], dict)):
            raise MappingError("Every assignment needs a target pointer and a source object.")
        pointer_parts(item["target"])
    return items


SOURCE_KEYS = {
    "csv": {"kind", "file_id", "column", "row", "rows", "where", "unit"},
    "json": {"kind", "file_id", "pointer", "unit"},
    "quote": {"kind", "file_id", "page", "quote", "token", "unit", "unit_quote"},
    "prompt": {"kind", "quote", "token", "unit", "unit_quote"},
    "config": {"kind", "value"},
    "copy": {"kind", "target"},
}


def validate_mapping(model_id, items, files, selected_ids, primary_id):
    contract = contract_for(model_id)
    referenced = set()
    assigned = set()
    for item in items:
        destination = pointer_parts(item["target"])
        if destination in assigned:
            raise MappingError(f"Duplicate assignment to {item['target']}.")
        assigned.add(destination)
        _field(contract, destination)
        source = item["source"]
        kind = source.get("kind")
        if not isinstance(kind, str) or kind not in SOURCE_KEYS or set(source) - SOURCE_KEYS[kind]:
            raise MappingError(f"Invalid source descriptor for {item['target']}.")
        if kind == "copy" and "#" in destination:
            raise MappingError("A copy writes a single field. Use explicit array indices.")
        if kind not in {"csv", "json", "quote"}:
            continue
        file_id = source.get("file_id")
        if not isinstance(file_id, str) or file_id not in files:
            raise MappingError("Use the ID of a retrieved source file.")
        file = files[file_id]
        valid_types = {"csv": {"text/csv"}, "json": {"application/json"}, "quote": TEXT_MEDIA}
        if file.media_type not in valid_types[kind] or file.role not in {"measurement", "documentation"}:
            raise MappingError(f"{file_id} cannot supply a {kind} value.")
        if kind == "quote" and "#" in destination:
            raise MappingError("Cite each documented array element with its own concrete target index.")
        referenced.add(file_id)
    if primary_id not in referenced or referenced != set(selected_ids):
        raise MappingError("Select exactly the evidence files referenced by the assignments.")


def _field(contract, path):
    if not all(path) or any(part == "*" for part in path) or path.count("#") > 1:
        raise MappingError("Use exact paths, with one optional # placeholder for a source column or array.")
    for name, result in contract.items():
        pattern = pointer_parts(name)
        if len(pattern) == len(path) and all(
            key == part
            or (key == "#" and (part == "#" or (part.isdecimal() and str(int(part)) == part)))
            or (key == "*" and not part.isdecimal() and part != "#")
            for key, part in zip(pattern, path)
        ):
            return result[0]
    raise MappingError(f"Unknown field for this model: /{'/'.join(path)}")


def _write(tree, path, value):
    for index, part in enumerate(path[:-1]):
        key = int(part) if isinstance(tree, list) else part
        child_type = list if path[index + 1].isdecimal() else dict
        if isinstance(tree, list):
            if key > len(tree):
                raise MappingError(f"Array indices must start at zero and be contiguous: /{'/'.join(path)}")
            if key == len(tree):
                tree.append(child_type())
            child = tree[key]
        else:
            child = tree.setdefault(key, child_type())
        if not isinstance(child, child_type):
            raise MappingError("Conflicting scalar and structured fields.")
        tree = child
    last = path[-1]
    if isinstance(tree, list):
        index = int(last)
        if index != len(tree):
            raise MappingError(f"Array indices must start at zero and be contiguous: /{'/'.join(path)}")
        tree.append(value)
    else:
        tree[last] = value


def _sort_path(path):
    return tuple((0, int(part)) if part.isdecimal() else (1, part) for part in path)


def _get(tree, path, default=None):
    for item in path:
        if isinstance(tree, dict) and item in tree:
            tree = tree[item]
        elif isinstance(tree, list) and item.isdecimal() and int(item) < len(tree):
            tree = tree[int(item)]
        else:
            return default
    return tree


def _csv_values(source, sources, *, whole_column, numeric):
    file_id, column = source["file_id"], source.get("column")
    names, rows = sources.table(file_id)
    if not isinstance(column, str) or column not in names:
        raise MappingError("The CSV column does not exist. Use its exact header.")
    selection = source.get("where")
    if selection is not None and (
        not isinstance(selection, dict) or set(selection) != {"column", "equals"}
        or selection["column"] not in names or not isinstance(selection["equals"], str)
    ):
        raise MappingError("Supply where.column and where.equals for an exact row filter.")
    if whole_column:
        if "row" in source:
            raise MappingError("A # target takes a column; a single row needs an explicit target index or scalar.")
        interval = source.get("rows", [0, len(rows)])
        if (not isinstance(interval, list) or len(interval) != 2
                or any(type(index) is not int for index in interval)
                or not 0 <= interval[0] < interval[1] <= len(rows)):
            raise MappingError("CSV rows must be a valid half-open [start, stop) interval.")
    elif "row" in source:
        index = source["row"]
        if type(index) is not int or not 0 <= index < len(rows):
            raise MappingError("CSV row must be a valid zero-based data row.")
        if "rows" in source:
            raise MappingError("Choose a single CSV row or an interval.")
        interval = [index, index + 1]
    else:
        if "rows" in source:
            raise MappingError("Use a # target for a range of CSV rows.")
        interval = [0, len(rows)]
    indices = []
    for index in range(*interval):
        row = rows[index]
        if selection and row.get(selection["column"]) != selection["equals"]:
            continue
        if None in row or any(value is None for value in row.values()):
            raise MappingError(f"CSV row {index} has the wrong column count.")
        indices.append(index)
    if not indices or (not whole_column and len(indices) != 1):
        raise MappingError("The CSV selection must identify the requested row or a nonempty column.")
    unit = next((value.unit for value in sources.files[file_id].variables or [] if value.name == column), None)
    if numeric:
        requested = source.get("unit")
        if not unit and requested is not None:
            suffix = re.search(r"(?:\[([^\[\]]+)\]|\s\((.+)\)|;\s*(.+))$", column)
            printed = next((group for group in suffix.groups() if group), None) if suffix else None
            if printed and normalized_unit(requested) == normalized_unit(printed):
                unit = printed
        if not unit:
            raise MappingError(f"Retrieve a verified unit for CSV column {column!r}.")
        if requested is not None and normalized_unit(requested) != normalized_unit(unit):
            raise MappingError(f"The requested source unit conflicts with the metadata for {column!r}.")
    values = [rows[index][column] for index in indices]
    locator = {"column": column, "rows": interval if whole_column else [indices[0], indices[0] + 1]}
    if selection:
        locator["where"] = selection
    return values if whole_column else values[0], unit, locator


def _source_url(file):
    if file.source_page_url:
        return str(file.source_page_url)
    url = urlsplit(str(file.retrieval_url))
    return urlunsplit((url.scheme, url.netloc, url.path, "", ""))


def _read_value(source, sources, raw_prompt, *, whole_column, numeric):
    kind = source["kind"]
    locator = {"kind": kind}
    if kind == "prompt":
        value, unit = verified_quote(raw_prompt, source, numeric=numeric)
        return value, unit, {**locator, "quote": source["quote"]}
    file_id = source["file_id"]
    file = sources.files[file_id]
    locator.update(file_id=file_id, investigation_id=file.investigation_id, url=_source_url(file))
    if kind == "csv":
        value, unit, where = _csv_values(source, sources, whole_column=whole_column, numeric=numeric)
        locator.update(where)
    elif kind == "json":
        value, unit = sources.json_source(file_id, source.get("pointer"), whole_column=whole_column)
        if "unit" in source and normalized_unit(source["unit"]) != normalized_unit(unit):
            raise MappingError("The declared JSON unit differs from the retrieved unit metadata.")
        locator["pointer"] = source["pointer"]
    else:
        page = source.get("page")
        value, unit = verified_quote(sources.document(file_id, page), source, numeric=numeric)
        locator.update(quote=source["quote"])
        if page is not None:
            locator["page"] = page
    return value, unit, locator


def _required_paths(tree, pattern, prefix=()):
    if not pattern:
        return [] if tree is not None else [prefix]
    key, *_ = pattern
    if key.isdecimal():
        if not isinstance(tree, list) or int(key) >= len(tree):
            return [prefix + pattern]
        return _required_paths(tree[int(key)], pattern[1:], prefix + (key,))
    if key in ("#", "*"):
        expected_type = list if key == "#" else dict
        if not isinstance(tree, expected_type) or not tree:
            return [prefix + pattern]
        values = enumerate(tree) if isinstance(tree, list) else tree.items()
        return [missing for index, value in values
                for missing in _required_paths(value, pattern[1:], prefix + (str(index),))]
    if not isinstance(tree, dict) or key not in tree:
        return [prefix + pattern]
    return _required_paths(tree[key], pattern[1:], prefix + (key,))


def _put_sources(model_id, payload, origins, files):
    groups = defaultdict(list)
    for path, origin in origins.items():
        file_id = origin.get("file_id")
        if not file_id or path[0] != "evidence":
            continue
        # Solvers with inline source fields expect them on these actual records.
        for depth in (3, 5):
            scope = path[:depth]
            if depth == 3 and len(path) > 3 and scope[1] == "runs":
                groups[scope].append(origin)
            if depth == 5 and len(path) > 5 and scope[1] == "materials" and scope[3] in {
                "calibrations", "cool_extinction_references",
            }:
                groups[scope].append(origin)
            if len(path) > 6 and depth == 5 and scope[3] == "calibrations" and path[5] == "reference":
                groups[path[:6]].append(origin)
    all_sources = []
    for file_id in dict.fromkeys(value["file_id"] for value in origins.values() if "file_id" in value):
        file = files[file_id]
        all_sources.append({"role": "assembled_input", "url": _source_url(file), "locator": file.title})
    for scope, citations in groups.items():
        record = _get(payload, scope)
        citations = [origin for origin in citations if tuple(origin["target_parts"]) not in {
            scope + ("source_url",), scope + ("source_locator",),
        }]
        if not citations:
            continue
        primary = citations[0]
        file = files[primary["file_id"]]
        record["source_url"] = primary["url"]
        suffix = f", p. {primary['page']}" if "page" in primary else ""
        record["source_locator"] = file.title + suffix

    audit = {}
    for key, item in origins.items():
        target = item.get("bulk_target", "/" + "/".join(key))
        if target not in audit:
            audit[target] = {k: v for k, v in item.items() if k not in {"target_parts", "bulk_target"}}
    summary = {
        "assembly": "Field mapping checked against the retrieved source",
        "illustrative": any(
            str(files[file_id].conditions.get("evidence_type", "")).casefold() in {"synthetic", "illustrative"}
            for file_id in dict.fromkeys(item["file_id"] for item in origins.values() if "file_id" in item)
        ),
        "field_sources": audit,
    }
    if model_id in ROUTES:
        payload["evidence"].update(provenance=summary, sources=all_sources)
    else:
        payload["investigation_context"] = summary
        payload["psi_citations"] = [source["url"] for source in all_sources]
    return summary


def _check_series(path, origin, series_origins):
    """Keep one timestamp grid when mapping entire columns into a time series."""
    if len(path) > 4 and path[0] == "evidence" and path[1] in {"runs", "fires"} and "#" in path:
        if path[1] == "runs" and path[3] != "samples":
            return
        if path[1] == "fires" and path[3] not in {"time_s", "hrr_W", "species"}:
            return
        group = path[:3]
        if origin["kind"] == "csv":
            signature = (origin["file_id"], origin["rows"], origin.get("where"))
        else:
            source_path = pointer_parts(origin["pointer"])
            array_parent = source_path[:source_path.index("#")] if "#" in source_path else source_path[:-1]
            signature = (origin["file_id"], array_parent)
        if series_origins.setdefault(group, signature) != signature:
            raise MappingError("Map synchronized series from the same source and row selection.")


def _check_synchronized_records(origins, files):
    """Reject separate observed series with no common run or different CSV rows in one sample."""
    groups = defaultdict(set)
    rows = {}
    for path, origin in origins.items():
        if len(path) < 5 or path[0] != "evidence" or "file_id" not in origin:
            continue
        if path[1] == "runs" and path[3] == "samples":
            sample = path[:5]
        elif path[1] == "fires" and path[3] in {"time_s", "hrr_W", "species"}:
            sample = path[:3] + (path[-1],)
        else:
            continue
        file_id = origin["file_id"]
        groups[path[:3]].add(file_id)
        if origin["kind"] == "csv":
            signature = (origin["rows"], origin.get("where"))
            if rows.setdefault((sample, file_id), signature) != signature:
                raise MappingError("Signals in one time sample must identify the same CSV row.")
    for file_ids in groups.values():
        if len(file_ids) > 1 and (
            len({files[file_id].investigation_id for file_id in file_ids}) != 1
            or not set.intersection(*(set(files[file_id].run_ids) for file_id in file_ids))
        ):
            raise MappingError("Separate files for synchronized signals need a shared verified run.")


def build_model_input(model_id, items, sources, raw_prompt):
    contract = contract_for(model_id)
    bound, origins, deferred = {}, {}, []
    series_origins = {}

    def bind(path, value, unit, kind, origin, *, already_converted=False):
        if path in bound:
            raise MappingError(f"Overlapping assignments to /{'/'.join(path)}.")
        if kind == "B" and type(value) is not bool:
            raise MappingError("This field takes a JSON Boolean.")
        if kind in {"S", "C"} and (not isinstance(value, str) or not value.strip() or len(value) > 1000):
            raise MappingError("This field takes a nonempty string.")
        if kind == "I" and (type(value) is not int or not 2 <= value <= 2001):
            raise MappingError("Plot resolution must be an integer from 2 to 2001.")
        gravity_label = kind == "g" and value in ("Earth", "ISS", "Moon", "Mars")
        if kind not in {"S", "C", "B", "I"} and not gravity_label:
            target_unit = kind.removeprefix("Q") if kind.startswith("Q") else kind
            if not already_converted:
                value = convert(parse_number(value), unit, target_unit)
            origin.update(source_unit=unit, model_unit=target_unit)
            if kind.startswith("Q"):
                value = {"value": value, "unit": target_unit.replace("m%", "%")}
        bound[path] = value
        origins[path] = {**origin, "target_parts": list(path)}

    for item in items:
        path, source = pointer_parts(item["target"]), item["source"]
        kind = _field(contract, path)
        origin_kind = source["kind"]
        try:
            if origin_kind == "copy":
                deferred.append((path, kind, pointer_parts(source.get("target"))))
                continue
            if origin_kind == "config":
                value = source.get("value")
                if "#" in path or (kind not in {"B", "C", "I"} and not (
                    kind == "g" and value in ("Earth", "ISS", "Moon", "Mars")
                )):
                    raise MappingError("Physical numbers need a source or a quote from the user request.")
                bind(path, value, None, kind, {"kind": "config", "value": value})
                continue
            is_array = "#" in path
            value, unit, origin = _read_value(source, sources, raw_prompt, whole_column=is_array,
                                              numeric=kind not in {"S", "C", "B", "I"})
            if is_array:
                if origin_kind not in {"csv", "json"} or not isinstance(value, list) or not value:
                    raise MappingError("An array target needs a nonempty CSV column or JSON array.")
                _check_series(path, origin, series_origins)
                origin["bulk_target"] = item["target"]
                index = path.index("#")
                for pos, member in enumerate(value):
                    concrete = path[:index] + (str(pos),) + path[index + 1:]
                    bind(concrete, member, unit, kind, dict(origin))
            else:
                bind(path, value, unit, kind, origin)
        except (MappingError, csv.Error, UnicodeError, OSError, ValueError, TypeError, OverflowError) as exc:
            raise MappingError(f"{item['target']}: {exc}") from exc

    while deferred:
        pending = []
        for path, kind, source_path in deferred:
            if source_path not in bound:
                pending.append((path, kind, source_path))
                continue
            source_kind = _field(contract, source_path)
            value = bound[source_path]
            if source_kind.startswith("Q"):
                value = value["value"]
            origin = {**origins[source_path], "copied_from": "/" + "/".join(source_path)}
            source_unit = origins[source_path].get("model_unit")
            bind(path, deepcopy(value), source_unit, kind, origin)
        if len(pending) == len(deferred):
            targets = ["/" + "/".join(source) for _, _, source in pending]
            raise MappingError("Unresolved copy sources: " + ", ".join(targets))
        deferred = pending

    if model_id in ROUTES:
        topic, analysis = ROUTES[model_id]
        payload = {"request": {"topic": topic, "analysis": analysis, "scenario": {}}, "evidence": {}}
    else:
        payload = {"function_id": model_id, "params": {}}
    for path in sorted(bound, key=_sort_path):
        _write(payload, path, bound[path])

    missing = {"/" + "/".join(path) for field, (_, required) in contract.items() if required
               for path in _required_paths(payload, pointer_parts(field))}
    _check_synchronized_records(origins, sources.files)
    _put_sources(model_id, payload, origins, sources.files)
    missing.update(conditional_missing(model_id, payload))
    for group in {path[:-1] for path in bound if path[-1].isdecimal()
                  and any(part.endswith("_range") or "_range_" in part
                          or part in {"bounds", "validity", "scenario_bounds", "time_window_s"} for part in path[:-1])}:
        if len(_get(payload, group)) != 2:
            missing.add("/" + "/".join(group) + " (needs two endpoints)")
    if missing:
        raise MappingError("Missing model inputs: " + ", ".join(sorted(missing)))
    return payload


def conditional_missing(model_id, payload):
    """Report missing fields for the major solver modes before invoking Python."""
    missing = set()

    def need(prefix, names):
        for name in names.split():
            missing.update("/" + "/".join(path) for path in _required_paths(
                payload, pointer_parts(prefix + "/" + name)
            ))

    scenario = payload.get("request", {}).get("scenario", {})
    evidence = payload.get("evidence", {})
    if model_id in {"THM-04", "THM-14", "THM-19"}:
        collection = "fires" if model_id == "THM-19" else "runs"
        for index, run in enumerate(evidence.get(collection, [])):
            root = f"/evidence/{collection}/{index}"
            if model_id == "THM-04":
                mode = run.get("measurement_method")
                if mode == "paired_oxygen_mass_flow":
                    need(root, "samples/#/inlet_o2_kg_s samples/#/outlet_o2_kg_s")
                elif mode == "exhaust_mass_flow":
                    need(root, "gas_basis samples/#/mass_flow_kg_s samples/#/o2_vol_frac samples/#/co2_vol_frac "
                         "samples/#/co_vol_frac inlet/o2_vol_frac inlet/co2_vol_frac inlet/co_vol_frac "
                         "inlet/water_vapor_vol_frac inlet/expansion_factor inlet/gas_molar_mass_kg_mol")
                need(root, "source_url source_locator")
                if any("reference_hrr_W" in row for row in run.get("samples", [])):
                    need(root, "samples/#/reference_hrr_W benchmark/source_url benchmark/source_locator")
            elif model_id == "THM-14":
                geometry = run.get("geometry", {})
                if geometry.get("method") == "view_factor":
                    need(root, "geometry/detector_area_m2 geometry/view_factor_f12")
                elif geometry.get("method") == "isotropic_point_source":
                    need(root, "geometry/source_distance_m geometry/incidence_angle_deg")
                if "gray_body" in geometry:
                    need(root + "/geometry/gray_body", "emitting_area_m2 emissivity temperature_k surroundings_temperature_k")
            elif "species" in run:
                need(root + "/species", "oxygen_consumption_kg_s/# co2_production_kg_s/# co_production_kg_s/# other_net_gas_mol_s/#")
                need(S + "/cabin/initial_mole_fractions", "oxygen carbon_dioxide carbon_monoxide")

    for index, profile in enumerate(evidence.get("profiles", [])):
        root = f"{E}/profiles/{index}"
        if profile.get("id") != scenario.get("profile_id"):
            continue
        if model_id == "THM-10":
            if profile.get("method") == "measured_rate":
                need(root, "regression_rate_mm2_s")
            elif profile.get("method") == "heat_transfer":
                need(S, "t_amb_k")
                need(root, "liquid_density_kg_m3 gas_conductivity_w_m_k gas_cp_j_kg_k validity/t_amb_k/#")
                if "spalding_heat_transfer_number" not in profile:
                    if profile.get("process") == "combustion":
                        need(root, "spalding_heat_transfer_number")
                    else:
                        need(root, "surface_temperature_k effective_vaporization_heat_j_kg")
            if "t_amb_k" in scenario:
                need(root, "validity/t_amb_k/#")
        elif model_id == "THM-12":
            for comp_index, component in enumerate(profile.get("components", [])):
                if component.get("volatile", True):
                    prefix = f"{root}/components/{comp_index}"
                    need(prefix, "reference_temperature_k reference_vapor_pressure_kpa vaporization_enthalpy_j_mol")
                    if "time_evolution" in scenario:
                        need(prefix, "transfer_conductance_mol_s_kpa")
            if "time_evolution" in scenario:
                need(S + "/time_evolution", "initial_total_moles duration_s")
            if "liquid_transport" in scenario:
                need(S + "/liquid_transport", "radius_m circulation_speed_m_s mass_diffusivity_m2_s")
        elif model_id == "THM-13" and "oxygen_diffusion" in profile:
            need(root + "/oxygen_diffusion", "diffusivity_m2_s length_m")
        elif model_id == "THM-18":
            if profile.get("mode") == "gas_dilution":
                need(S, "initial_temperature_K target_temperature_K agent_mole_fraction base_gas_mole_fractions/*")
                need(root, "agent_species oxygen_species species/*/cp_at_reference_J_mol_K "
                     "species/*/cp_reference_temperature_K species/*/temperature_range_K/#")
            elif profile.get("mode") == "water_mist":
                need(S, "water_mass_kg inlet_water_temperature_K liquid_endpoint_temperature_K evaporated_fraction")
                need(root, "liquid_cp_J_kg_K liquid_temperature_range_K/# vaporization_enthalpy_J_kg "
                     "phase_change_temperature_range_K/#")
        elif model_id == "THM-20" and "collision_kernel_m3_s" not in profile:
            need(root, "gas_mean_free_path_m cunningham_slip_factor")

    for mat_index, material in enumerate(evidence.get("materials", [])):
        for index, calibration in enumerate(material.get("calibrations", [])):
            root = f"{E}/materials/{mat_index}/calibrations/{index}"
            need(root, "source_locator" if model_id == "THM-16" else "source_url source_locator")
            if model_id == "THM-05":
                thermal = calibration.get("thermal", {})
                if "prefactors" in thermal:
                    need(root + "/thermal/prefactors", "thin_m2_s thick_dimensionless")
                else:
                    for phase in ("gas", "solid"):
                        need(root + f"/thermal/{phase}", "density_kg_m3 specific_heat_J_kg_K conductivity_W_m_K")
                if "flame_coefficient" not in thermal:
                    need(root + "/thermal", "ambient_temperature_K vaporization_temperature_K effective_flame_temperature_K")
            if model_id == "THM-06":
                need(root + "/reference", "source_url source_locator")
                if "areal_mass_kg_m2" not in calibration.get("thermal", {}):
                    need(root, "thermal/density_kg_m3 reference/sample_thickness_m")
                if "effective_heat_feedback_factor" not in calibration:
                    need(root + "/reference", "spread_rate_mm_s")
        for index, _ in enumerate(material.get("cool_extinction_references", [])):
            need(f"{E}/materials/{mat_index}/cool_extinction_references/{index}", "source_url source_locator")

    if model_id == "THM-17":
        for index, profile in enumerate(evidence.get("calibrations", [])):
            root = f"{E}/calibrations/{index}"
            for name in ("quench", "blowoff"):
                form = profile.get(name, {}).get("form")
                keys = {"linear": "intercept_pct slope_pct_per_axis_unit", "exponential": "base_pct amplitude_pct decay_per_axis_unit",
                        "table": "points/#/0 points/#/1"}.get(form)
                if keys:
                    need(root + "/" + name, keys)
            if profile.get("combination_rule") == "shared_baseline_excess_sum":
                need(root, "shared_baseline_pct")
    return missing
