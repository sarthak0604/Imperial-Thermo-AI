"""Fill supported gaps using the versioned thermo property library."""

import json
import math
import re
from copy import deepcopy
from functools import lru_cache

from thermo_reference.build_demo import REFERENCE_ROOT, index_records


@lru_cache(maxsize=1)
def records():
    return index_records(json.loads((REFERENCE_ROOT / "properties.json").read_text(encoding="utf-8-sig"))["records"])


def reference_origin(record, path, value=None):
    return {
        "kind": "reference_property", "target_pointer": path, "record_id": record["id"],
        "value": deepcopy(record["value"] if value is None else value),
        "unit": record["unit"], "conditions": record["conditions"], "sources": record["sources"],
    }


def scenario_origin(path, value, unit, reason):
    return {"kind": "scenario_assumption", "target_pointer": path, "value": value, "unit": unit,
            "assumption": reason, "illustrative": True}


def is_iss_methane_lewis(prompt):
    """Recognize a nominal worked example without replacing stated physical inputs."""
    # A copied expected dimensionless result is prose, not a thermodynamic state.
    prompt = prompt.split("\t", 1)[0]
    return bool(
        re.search(r"\blewis number\b", prompt, re.IGNORECASE)
        and re.search(r"\b(?:methane|CH4)\b", prompt, re.IGNORECASE)
        and re.search(r"\bISS\b", prompt, re.IGNORECASE)
        and re.search(r"\b(?:nitrogen|N2)\b", prompt, re.IGNORECASE)
        and not re.search(
            r"\b(?:non[- ]?premixed|diffusion flame|lean|rich|helium|argon|propane|hydrogen|"
            r"methanol|dataset|measurements?|measured|experiment|psi[- ]\d|compare|versus|"
            r"temperature|pressure|equivalence ratio|mole fractions?)\b|"
            r"\d\s*(?:[%°]|K\b|kPa\b|atm\b|psi\b)", prompt, re.IGNORECASE,
        )
    )


ISS_METHANE_DILUTION = 0.18


def iss_methane_state(payload, provenance, *, diluted=False):
    params = payload["params"]
    base = records()
    pressure = base["iss_cabin_pressure_nominal"]
    oxygen = base["iss_oxidizer_o2_nominal"]
    if "pressure_kpa" not in params:
        params["pressure_kpa"] = pressure["value"]
        provenance.append(reference_origin(pressure, "/params/pressure_kpa"))
    if "temp_k" not in params:
        params["temp_k"] = 295.0
        provenance.append(scenario_origin("/params/temp_k", 295.0, "K", "Assumed 295 K for the unburned reactants."))
    if "mole_fracs" not in params:
        ox = ISS_METHANE_DILUTION if diluted else oxygen["value"]
        methane = ox / 2
        total = 1 + methane
        mixture = {"CH4": methane / total, "O2": ox / total, "N2": (1 - ox) / total}
        params["mole_fracs"] = mixture
        if diluted:
            provenance.append(scenario_origin(
                "/scenario/oxidizer_oxygen_mole_fraction", ox, "mol/mol",
                f"Illustrative sensitivity case at {ox:.0%} oxygen in the oxidizer, with nitrogen as the balance.",
            ))
        else:
            provenance.append(reference_origin(oxygen, "/scenario/oxidizer_oxygen_mole_fraction"))
        provenance.append(scenario_origin(
            "/params/mole_fracs", mixture, "mol/mol",
            "Assumed a dry, stoichiometric methane mixture with nitrogen as the oxidizer balance.",
        ))
    if "target_species" not in params:
        params["target_species"] = "CH4"
        provenance.append(scenario_origin("/params/target_species", "CH4", None, "Calculated Lewis number for methane."))


def condition_range(value, limits):
    return type(value) in (int, float) and isinstance(limits, list) and len(limits) == 2 and limits[0] <= value <= limits[1]


def fill_properties(model_id, payload, provenance):
    """Fill missing properties with explicit species, units and applicability checks."""
    if model_id not in {"THM-12", "THM-18"}:
        return
    evidence = payload["evidence"]
    scenario = payload["request"]["scenario"]
    matches = [(i, p) for i, p in enumerate(evidence.get("profiles", [])) if p.get("id") == scenario.get("profile_id")]
    if len(matches) != 1:
        return
    index, profile = matches[0]
    root = f"/evidence/profiles/{index}"
    added = []

    def fill(container, key, field, record, value):
        if key in container and container[key] is not None:
            return
        container[key] = deepcopy(value)
        added.append(reference_origin(record, field, value))

    if model_id == "THM-12":
        for i, component in enumerate(profile.get("components", [])):
            if component.get("volatile") is False:
                continue
            species = str(component.get("id", "")).casefold()
            candidates = [r for r in records().values()
                          if r["material"] == species and r["phase"] == "liquid"
                          and r["usage"] == "compatible_reference"
                          and r["conditions"].get("temperature_K") == 298.15]
            reference_temperature = component.get("reference_temperature_k")
            if not candidates or reference_temperature not in (None, 298.15):
                continue
            if reference_temperature is None and any(component.get(key) is not None for key in (
                    "reference_vapor_pressure_kpa", "vaporization_enthalpy_j_mol")):
                # A supplied property must keep its own documented reference temperature.
                continue
            fill(component, "reference_temperature_k", f"{root}/components/{i}/reference_temperature_k",
                 {**candidates[0], "unit": "K"}, 298.15)
            fields = {"saturation_vapor_pressure": ("reference_vapor_pressure_kpa", "kPa"),
                      "vaporization_enthalpy": ("vaporization_enthalpy_j_mol", "J/mol")}
            for record in candidates:
                field = fields.get(record["property"])
                if field and record["unit"] == field[1]:
                    fill(component, field[0], f"{root}/components/{i}/{field[0]}", record, record["value"])
    elif scenario.get("mode") == profile.get("mode") == "gas_dilution":
        gas_keys = {key for key, fraction in scenario.get("base_gas_mole_fractions", {}).items() if fraction != 0}
        gas_keys.add(profile.get("agent_species"))
        for record in records().values():
            species = record["material"]
            conditions = record["conditions"]
            if (species not in gas_keys or record["property"] != "molar_isobaric_heat_capacity"
                    or record["phase"] != "gas" or record["usage"] != "compatible_reference"
                    or not condition_range(scenario.get("pressure_kPa"), conditions.get("demo_pressure_range_kPa"))
                    or not all(condition_range(scenario.get(key), conditions.get("temperature_range_K"))
                               for key in ("initial_temperature_K", "target_temperature_K"))):
                continue
            if profile.get("species") is None:
                profile["species"] = {}
            gases = profile["species"]
            gas = gases.get(species)
            # Use the fit as a unit. Partial sourced fits need their own missing coefficients.
            if gas is None or not any(value is not None for value in gas.values()):
                gases[species] = deepcopy(record["value"])
                added.append(reference_origin(record, f"{root}/species/{species}"))
    elif scenario.get("mode") == profile.get("mode") == "water_mist":
        latent = records()["water_dhvap_sat_373_15k"]
        conditions = latent["conditions"]
        pressure, endpoint = scenario.get("pressure_kPa"), scenario.get("liquid_endpoint_temperature_K")
        if (type(pressure) in (float, int) and math.isclose(pressure, conditions["pressure_kPa"], abs_tol=0.001)
                and endpoint == conditions["temperature_K"]):
            fill(profile, "vaporization_enthalpy_J_kg", f"{root}/vaporization_enthalpy_J_kg",
                 latent, latent["value"])
            cp = records()["water_liquid_cp_mean_293_373k"]
            if [scenario.get("inlet_water_temperature_K"), endpoint] == cp["conditions"]["temperature_range_K"]:
                fill(profile, "liquid_cp_J_kg_K", f"{root}/liquid_cp_J_kg_K", cp, cp["value"])
    for binding in added:
        for entry in binding["sources"]:
            source = {"role": "reference_property", **entry}
            if source not in evidence.setdefault("sources", []):
                evidence["sources"].append(source)
    provenance.extend(added)
