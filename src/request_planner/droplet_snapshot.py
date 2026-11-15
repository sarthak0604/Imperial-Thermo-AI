"""Bind explicit methanol-water snapshot conditions to the reference profile."""

import re

from imperial_thermo_ai.quantities import NUMBER, user_quantity_spans

MIXTURE = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s+"
    r"(methanol|water)\s*[-–—/]\s*(methanol|water)\s+droplet\s+(?:by mole|on a mole basis)\b",
    re.I,
)
TEMPERATURE = re.compile(rf"{NUMBER}\s*(?P<unit>°\s*C|K)\b", re.I)
ATMOSPHERE = re.compile(r"\b(?:one|1)\s+atmosphere\b", re.I)
GAS = re.compile(r"\b(?:surrounding gas|ambient gas|gas phase)\b", re.I)


def snapshot_bindings(prompt):
    """Return only fully specified, single-state queries about transfer direction."""
    models = {m.upper() for m in re.findall(r"\bTHM-\d+\b", prompt, re.I)}
    if (models - {"THM-12"} or not re.search(r"\b(?:evaporat\w*|condens\w*|uptake)\b", prompt, re.I)
            or re.search(r"\b(?:dataset|PSI-\d+|measured|experiment|time evolution|non.?ideal|"
                         r"activity coefficient|transfer rate|how fast|sweep|versus|by mass)\b", prompt, re.I)):
        return []
    mix, gas = MIXTURE.search(prompt), GAS.search(prompt)
    if not mix or not gas or mix.end() > gas.start():
        return []
    a, b = (float(mix[i]) for i in (1, 2))
    first, second = (mix[i].casefold() for i in (3, 4))
    if first == second or a <= 0 or b <= 0 or a + b != 100:
        return []
    state = prompt[:gas.start()]
    temperatures = list(TEMPERATURE.finditer(state))
    pressures = user_quantity_spans("pressure_kpa", state)
    pressures += [(101.325, m.span()) for m in ATMOSPHERE.finditer(state)]
    if len(temperatures) != 1 or len(pressures) != 1:
        return []
    temperature = temperatures[0]
    value = float(temperature["value"])
    if temperature["unit"].startswith("°"):
        value += 273.15
    pressure, pressure_span = pressures[0]
    bindings = []
    consumed = set()

    def add(path, value, unit, span):
        start, end = span
        bindings.append({"target_pointer": "/request/scenario/" + path, "value": value,
                         "unit": unit, "quote": prompt[start:end]})
        consumed.add(span)

    add(f"liquid_fractions/{first}", a / 100, "mol/mol", mix.span())
    add(f"liquid_fractions/{second}", b / 100, "mol/mol", mix.span())
    add("t_surface_k", value, "K", temperature.span())
    add("pressure_kpa", pressure, "kPa", pressure_span)
    for species in ("methanol", "water"):
        pattern = rf"{NUMBER}\s*kPa\s*(?:of\s+)?{species}\b|\bno\s+{species}\b"
        matches = list(re.finditer(pattern, prompt[gas.end():], re.I))
        if len(matches) != 1:
            return []
        match = matches[0]
        add(f"ambient_partial_pressures_kpa/{species}", float(match["value"] or 0), "kPa",
            (gas.end() + match.start(), gas.end() + match.end()))

    remaining = prompt
    for start, end in sorted(consumed, reverse=True):
        remaining = remaining[:start] + " " + remaining[end:]
    if re.search(r"\d", re.sub(r"\bTHM-12\b", "", remaining, flags=re.I)):
        return []
    return bindings
