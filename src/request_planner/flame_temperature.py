"""SI-assisted parsing for a fully specified THM-01 scenario."""

import re

from .operations import scenario

NUMBER = r"(\d+(?:\.\d+)?)"
REQUEST = re.compile(
    rf"(?:calculate|what is)\s+(?:the\s+)?adiabatic flame temperature\s+"
    rf"for\s+(methane|CH4|hydrogen|H2|propane|C3H8)\s+with\s+"
    rf"{NUMBER}\s*%\s+oxygen\s+in\s+(nitrogen|N2)\s+at\s+"
    rf"{NUMBER}\s*kPa\s+and\s+{NUMBER}\s*K\s*,?\s+"
    rf"(?:with\s+)?(?:an?\s+)?equivalence ratio(?:\s+of)?\s+{NUMBER}\s*[?.]?",
    re.I,
)


def flame_temperature_inputs(prompt):
    match = REQUEST.fullmatch(prompt.strip())
    if not match:
        return None
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
    return scenario({
        "model_id": "THM-01",
        "params": params,
        "input_origins": dict.fromkeys(params, "user"),
    })["result"]
