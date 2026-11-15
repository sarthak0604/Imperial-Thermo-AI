"""Source-preserving quantity metadata. No inferred units or run identities."""

import math
import re


def descriptor(name, unit=None):
    text = name.casefold().replace("_", " ")
    out = {
        "quantity": None,
        "basis": None,
        "stage": None,
        "species": None,
        "unit": unit,
    }
    if re.search(r"oxygen|\bo2\b|\bo initial", text):
        out.update(quantity="fraction", species="O2")
        for words, basis in [
            ("mole", "mole"),
            ("mass fraction", "mass"),
            ("by vol", "volume"),
            ("vol frac", "volume"),
        ]:
            if words in text:
                out["basis"] = basis
        if "initial" in text:
            out["stage"] = "initial"
        elif "final" in text:
            out["stage"] = "final"
    elif "pressure" in text:
        out["quantity"] = "pressure"
    elif "temperature" in text:
        out["quantity"] = "temperature"
    return out


DESTINATIONS = {
    "y_ox_stream": {"quantity": "fraction", "basis": "mass", "species": "O2"},
    "o2_mole_frac": {"quantity": "fraction", "basis": "mole", "species": "O2"},
    "x_o2": {"quantity": "fraction", "basis": "mole", "species": "O2"},
    "o2_vol_frac": {"quantity": "fraction", "basis": "volume", "species": "O2"},
}


def validate_quantity(column, target):
    expected = DESTINATIONS.get(target)
    if not expected:
        return
    actual = descriptor(column.name, column.unit)
    for key, value in expected.items():
        if actual.get(key) != value:
            raise ValueError(
                f"Quantity {key} for {column.name!r} must be verified as {value} before binding to {target}"
            )


def normalize_graph(graph):
    """Add separate typed facts only for source headers with explicit meanings."""
    for node in graph.get("nodes", []):
        if node["type"] != "Experiment":
            continue
        props = node["properties"]
        raw = props.get("conditions", {})
        normalized = {}
        if raw.get("source_quality_notes"):
            props["normalized"] = normalized
            continue
        for header, value in raw.items():
            if not isinstance(value, (int, float, str)):
                continue
            try:
                number = float(value)
            except ValueError:
                continue
            if not math.isfinite(number):
                continue
            meta = descriptor(header)
            field = meta["quantity"]
            if field == "fraction" and meta["basis"]:
                field = "oxygen_" + (meta["stage"] or "unspecified")
                meta["unit"] = (
                    "%"
                    if "%" in header
                    else "1"
                    if "fraction" in header.casefold()
                    else None
                )
            elif field == "pressure":
                meta["unit"] = next(
                    (
                        unit
                        for token, unit in [
                            ("mmhg", "mmHg"),
                            ("kpa", "kPa"),
                            ("atm", "atm"),
                            ("pa", "Pa"),
                        ]
                        if token in header.casefold()
                    ),
                    None,
                )
            else:
                continue
            if meta["unit"] is None:
                continue
            normalized[field] = {
                "value": number,
                **meta,
                "raw_header": header,
                "source_row": raw.get("source_row"),
                "source_url": props.get("source_url"),
            }
        props["normalized"] = normalized
