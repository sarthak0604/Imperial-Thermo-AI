"""Source-preserving quantity metadata. No inferred units or run identities."""

import math
import re


# Explicit prompt units for scenario parameters. The named slots define the
# solver units. A bare number can still be validated by the calling contract.
NUMBER = r"(?<![\w.+-])(?P<value>[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?)"
OXYGEN = r"(?:oxygen|O2|O₂)"
PERCENT = r"(?:mol\s*%|vol\s*%|%|percent\b)"
FRACTION = re.compile(
    rf"{NUMBER}\s*{PERCENT}\s*(?:of\s+)?{OXYGEN}\b"
    rf"|\b{OXYGEN}\b(?:\s+(?:mole\s+fraction|content|concentration|level))?"
    rf"\s*(?:is\b|of\b|at\b|=|:)?\s*{NUMBER.replace('value', 'after')}\s*(?P<percent>{PERCENT})?",
    re.I,
)
MASS_FRACTION = re.compile(
    rf"{NUMBER}\s*{PERCENT}\s*(?:of\s+)?{OXYGEN}\s+by\s+mass\b"
    rf"|\b{OXYGEN}\s+mass\s+fraction\s*(?:is\b|of\b|=|:)?"
    rf"\s*{NUMBER.replace('value', 'after')}\s*(?P<percent>{PERCENT})?",
    re.I,
)
QUANTITY_UNITS = {
    "u_flow_ms": (r"cm\s*/\s*s|m\s*/\s*s", {"m/s": 1, "cm/s": 0.01}),
    "pressure_kpa": (r"kPa|Pa|atm|bar|psi", {"kpa": 1, "pa": 0.001, "atm": 101.325, "bar": 100, "psi": 6.894757}),
    "activation_energy_j": (r"kJ\s*/\s*mol|J\s*/\s*mol", {"j/mol": 1, "kj/mol": 1000}),
}


def user_quantity_spans(field, text):
    """Return canonical values and exact character spans for recognized units."""
    if field in {"y_ox_stream", "y_o2_amb"}:
        return [
            (float(m["value"] or m["after"]) / (100 if m["value"] or m["percent"] else 1), m.span())
            for m in MASS_FRACTION.finditer(text)
        ]
    if field in {"x_o2", "o2_mole_frac"}:
        if re.search(r"\b(?:mass fraction|by mass|weight percent|wt\s*%)\b", text, re.I):
            return []
        return [
            (float(m["value"] or m["after"]) / (100 if m["value"] or m["percent"] else 1), m.span())
            for m in FRACTION.finditer(text)
        ]
    if field not in QUANTITY_UNITS:
        return []
    pattern, factors = QUANTITY_UNITS[field]
    return [
        (float(m["value"]) * factors[re.sub(r"\s+", "", m["unit"].casefold())], m.span())
        for m in re.finditer(rf"{NUMBER}\s*(?P<unit>{pattern})\b", text, re.I)
    ]


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
