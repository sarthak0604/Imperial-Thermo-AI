"""SI-assisted parsing for a fully specified THM-01 scenario."""

import re

from .operations import scenario

NUMBER = r"(?<![\w.+-])(\d+(?:\.\d+)?)"
REQUEST = re.compile(
    rf"(?:calculate|what is)\s+(?:the\s+)?adiabatic flame temperature\s+"
    rf"for\s+(methane|CH4|hydrogen|H2|propane|C3H8)\s+with\s+"
    rf"{NUMBER}\s*%\s+oxygen\s+in\s+(nitrogen|N2)\s+at\s+"
    rf"{NUMBER}\s*kPa\s+and\s+{NUMBER}\s*K\s*,?\s+"
    rf"(?:with\s+)?(?:an?\s+)?equivalence ratio(?:\s+of)?\s+{NUMBER}\s*[?.]?",
    re.I,
)

FUEL = r"(?:methane|CH4|hydrogen|H2|propane|C3H8)"
AIR_REQUEST = re.compile(
    rf"(?:plot|compare|calculate)\s+(?:the\s+)?(?:adiabatic flame temperatures?|peak flame temperatures?)\s+"
    rf"for\s+(?P<fuels>{FUEL}(?:(?:,\s*(?:and\s+)?|\s+and\s+){FUEL}){{0,2}})\s+"
    r"in\s+(?:ordinary|standard)\s+air\s+at\s+"
    r"(?:room temperature and sea[- ]level pressure|sea[- ]level pressure and room temperature)"
    r"\s*[?.]?",
    re.I,
)


TEMPERATURE_INTENT = re.compile(
    r"\b(?:adiabatic flame temperature|how hot.{0,90}\bflame)\b", re.I
)
CONDITION_PATTERNS = {
    "pressure_kpa": re.compile(rf"{NUMBER}\s*kPa\b", re.I),
    "t_init_k": re.compile(rf"{NUMBER}\s*K\b", re.I),
    "o2_mole_frac": re.compile(rf"{NUMBER}\s*(?:mol\s*)?%\s*(?:oxygen|O2)\b", re.I),
    "equivalence_ratio": re.compile(rf"\b(?:equivalence ratio|phi|φ)\s*(?:of|=|:)?\s*{NUMBER}", re.I),
}
NITROGEN_BALANCE = re.compile(
    r"\b(?:in|balance|rest|remainder|diluted (?:with|by))\s+(?:is\s+)?(?:nitrogen|N2)\b"
    r"|\bnitrogen[- ]diluted\b", re.I
)


def explicit_inputs(question):
    """Extract a single explicit scenario regardless of the order of its values."""
    if not TEMPERATURE_INTENT.search(question) or not NITROGEN_BALANCE.search(question):
        return None
    if re.search(
        r"\b(?:compare|versus|sweep|vary|between|measured|dataset|csv|PSI|except|without|"
        r"non[- ]?stoichiometric|nonadiabatic|non[- ]adiabatic|heat loss|heat losses|"
        r"helium|argon|carbon dioxide|CO2|mass fraction|weight percent|wt)\b", question, re.I
    ):
        return None
    fuels = set(re.findall(rf"\b({FUEL})\b", question, re.I))
    aliases = {"METHANE": "CH4", "HYDROGEN": "H2", "PROPANE": "C3H8"}
    fuels = {aliases.get(fuel.upper(), fuel.upper()) for fuel in fuels}
    if len(fuels) != 1:
        return None
    params = {}
    consumed = []
    for field, pattern in CONDITION_PATTERNS.items():
        matches = list(pattern.finditer(question))
        if len(matches) > 1:
            return None
        if matches:
            match = matches[0]
            params[field] = float(match.group(1))
            consumed.append(match.span())
    remaining = question
    for start, end in sorted(consumed, reverse=True):
        remaining = remaining[:start] + " " + remaining[end:]
    remaining = re.sub(rf"\b{FUEL}\b|\bN2\b|\bO2\b|\bTHM-01\b", "", remaining, flags=re.I)
    if re.search(r"\d", remaining):
        return None
    if not {"pressure_kpa", "t_init_k", "o2_mole_frac"} <= params.keys():
        return None
    if re.search(r"\bstoichiometric\b", question, re.I):
        if params.get("equivalence_ratio", 1) != 1:
            return None
        params["equivalence_ratio"] = 1.0
    if "equivalence_ratio" not in params:
        return None
    params["o2_mole_frac"] /= 100
    return {**params, "fuel_species": next(iter(fuels)), "diluent_gas": "N2"}


def flame_temperature_inputs(prompt):
    question = " ".join(prompt.split())
    explicit = explicit_inputs(question)
    if explicit is not None:
        return explicit
    match = REQUEST.fullmatch(question)
    if not match:
        air = AIR_REQUEST.fullmatch(prompt.strip())
        if air is None:
            return None
        names = {"methane": "CH4", "hydrogen": "H2", "propane": "C3H8"}
        fuels = [names.get(f.casefold(), f.upper()) for f in re.findall(FUEL, air["fuels"], re.I)]
        return {
            "fuel_species": list(dict.fromkeys(fuels)),
            "o2_mole_frac": 0.21, "diluent_gas": "N2", "pressure_kpa": 101.325,
            "t_init_k": 298.15, "equivalence_ratio": 1.0,
        }
    fuel, oxygen, _, pressure, initial_temperature, ratio = match.groups()
    return {
        "fuel_species": fuel.upper(),
        "o2_mole_frac": float(oxygen) / 100,
        "diluent_gas": "N2",
        "pressure_kpa": float(pressure),
        "t_init_k": float(initial_temperature),
        "equivalence_ratio": float(ratio),
    }


def calculate_flame_temperature(params):
    fuels = params["fuel_species"]
    if not isinstance(fuels, list):
        return [scenario({
            "model_id": "THM-01", "params": params,
            "input_origins": dict.fromkeys(params, "user"),
        })["result"]]
    defaults = {key: value for key, value in params.items() if key != "fuel_species"}
    return [scenario({
        "model_id": "THM-01", "params": {**params, "fuel_species": fuel},
        "input_origins": {**dict.fromkeys(defaults, "default"), "fuel_species": "user"},
        "allowed_defaults": defaults,
    })["result"] for fuel in fuels]
