"""Map plain-language single scenarios to reviewed evidence and typed overrides."""

from dataclasses import dataclass
import re

# A quantity matcher always retains the literal source text. Thousands separators
# are part of the number, so "1,260 K" cannot be misread as 260 K.
VALUE = r"(?<![\w.+-])(?P<value>[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|[+-]?\.\d+)"
FLOW = rf"{VALUE}\s*(?P<unit>cm/s|m/s)\b"
TEMP = rf"{VALUE}\s*(?P<unit>°\s*C|K)\b"
TIME = rf"{VALUE}\s*(?:seconds?|s)\b"
O2_MASS = rf"{VALUE}\s*%\s*(?:oxygen|O2)\s+by mass\b"
O2_MOLE = rf"{VALUE}\s*%\s*(?:oxygen|O2)\b(?!\s+by mass)"
LENGTH = rf"{VALUE}\s*(?P<unit>cm|m)\b(?!\s*/)"
SCENARIO = "/request/scenario/"


@dataclass(frozen=True)
class Condition:
    path: str
    pattern: str
    unit: str
    occurrence: int = 0
    count: int = 1

    def binding(self, prompt):
        matches = list(re.finditer(self.pattern, prompt, re.I))
        if len(matches) != self.count:
            return None
        match = matches[self.occurrence]
        options = match.groupdict()
        if "name" in options:
            value = options["name"]
        elif options.get("half"):
            value = 0.5
        else:
            value = float(options["value"].replace(",", ""))
            source_unit = (options.get("unit") or "").casefold().replace(" ", "")
            if self.unit in {"1", "mol/mol"}:
                value /= 100
            elif self.unit == "K" and source_unit == "°c":
                value += 273.15
            elif self.unit == "m" and source_unit == "cm":
                value /= 100
            elif self.unit == "m/s" and source_unit == "cm/s":
                value /= 100
            elif self.unit == "cm/s" and source_unit == "m/s":
                value *= 100
            elif self.unit == "kg" and source_unit in {"g", "gram", "grams"}:
                value /= 1000
            elif self.unit == "kW/m2" and source_unit == "w":
                value /= 1000
        return {"target_pointer": self.path, "value": value, "quote": match.group(),
                "unit": self.unit}, match.span()


@dataclass(frozen=True)
class Scenario:
    model_id: str
    package_id: str | None
    cues: tuple[str, ...]
    conditions: tuple[Condition, ...] = ()
    identifiers: str = ""
    investigation_id: str | None = None

    def match(self, prompt):
        if not all(re.search(pattern, prompt, re.I) for pattern in self.cues):
            return None
        bindings, spans = [], set()
        for condition in self.conditions:
            bound = condition.binding(prompt)
            if bound is None:
                return None
            binding, span = bound
            bindings.append(binding)
            spans.add(span)
        remaining = prompt
        for start, end in sorted(spans, reverse=True):
            remaining = remaining[:start] + " " + remaining[end:]
        known = self.model_id + (f"|{self.identifiers}" if self.identifiers else "")
        if re.search(r"\d", re.sub(r"\b(?:" + known + r")\b", "", remaining, flags=re.I)):
            return None
        return bindings


SCENARIOS = [
    Scenario("THM-03", None, (r"\bmixture fraction\b", r"\bstoichiometric\b"),
             (Condition("/params/fuel_formula",
                        r"\bpure\s+(?P<name>[a-z][a-z0-9-]*(?:\s+[a-z][a-z0-9-]*)??)"
                        r"(?=\s+(?:burning|in|with|and|fuel)\b|[,.;?]|$)", ""),
              Condition("/params/y_ox_stream", O2_MASS, "1")), "O2"),
    Scenario("THM-06", "saffire_ii_sibal_spread",
             (r"\bsaffire[ ‑–-]*(?:ii|2)\b", r"\bsibal\b", r"\b(?:spread|propagat)\w*\b",
              r"\b(?:with (?:the )?airflow|concurrent|downstream)\b"),
             (Condition(SCENARIO + "ambient/air_speed/value", FLOW, "cm/s"),),
             "saffire[ ‑–-]*2", "PSI-99"),
    Scenario("THM-08", "example-thm-08", (r"\bbuoyanc\w*\b", r"\bventilation\b"),
             (Condition("/params/gravity_g", r"\b(?P<name>Moon|Mars|Earth)\b", "g"),
              Condition("/params/u_forced_ms", FLOW, "m/s"),
              Condition("/params/char_length_m", LENGTH, "m"),
              Condition("/params/delta_t_k", rf"{VALUE}\s*K\b", "K"))),
    Scenario("THM-09", "example-thm-09", (r"\bspalding\b", r"\bpmma\b"),
             (Condition("/params/y_o2_amb", O2_MASS, "1"),
              Condition("/params/u_flow_ms", FLOW, "m/s")), "O2"),
    Scenario("THM-10", "flex_r377_regression",
             (r"\b(?:droplet|drop)\b", r"\b(?:burn\w*|combustion)\b",
              r"\b(?:shrink\w*|regression|diameter)\b", r"\b(?:space|microgravity|R377)\b"),
             (Condition(SCENARIO + "time_limit_s", TIME, "s"),), "R377", "PSI-69"),
    Scenario("THM-11", "flex_r377_decane", (r"\bflex\b", r"\bR377\b", r"\bcool flame\b"),
             identifiers="R377", investigation_id="PSI-69"),
    Scenario("THM-13", "example-thm-13",
             (r"\b(?:illustrative|demo)\b", r"\bpmma\b", r"\bmicrogravity\b", r"\bradiati\w*\b"),
             (Condition(SCENARIO + "u_flow_ms", FLOW, "m/s"), Condition(SCENARIO + "x_o2", O2_MOLE, "1")),
             "O2"),
    Scenario("THM-14", "example-thm-14", (r"\b(?:demo|synthetic|illustrative)\b", r"\bradiometer\b",
                                            r"\b(?:radiated|radiative fraction)\b")),
    Scenario("THM-15", "example-thm-15",
             (r"\b(?:demo|illustrative)\b", r"\bethylene\b", r"\bsoot\b"),
             (Condition(SCENARIO + "flame_temperature_K", rf"{VALUE}\s*K\b", "K"),
              Condition(SCENARIO + "residence_time_s", TIME, "s"),
              Condition(SCENARIO + "carbon_to_oxygen_atomic_ratio",
                        rf"\b(?:carbon[- ]to[- ]oxygen|C/O)(?:\s+atomic)?\s+ratio\s*(?:of|=|:)?\s*{VALUE}", ""))),
    Scenario("THM-16", "example-thm-16", (r"\b(?:demo|illustrative)\b", r"\bslab\b",
                                            r"\b(?:ignit\w*|surface temperature)\b"),
             (Condition(SCENARIO + "exposure/heat_flux/value", rf"{VALUE}\s*(?P<unit>kW|W)\s*/\s*m[²2]", "kW/m2"),
              Condition(SCENARIO + "exposure/heating_time/value", TIME, "s"))),
    Scenario("THM-17", "bass_ii_pmma_rod_extinction",
             (r"\bbass[ ‑–-]*ii\b", r"\bpmma\b", r"\brod\b", r"\boxygen\b",
              r"\b(?:same direction|concurrent|downstream)\b"),
             (Condition(SCENARIO + "air_speed_m_s", FLOW, "m/s"),), investigation_id="PSI-25"),
    Scenario("THM-18", "water_mist_100c_budget", (r"\bwater mist\b", r"\b(?:absorb\w*|heat sink|thermal budget)\b"),
             (Condition(SCENARIO + "water_mass_kg", rf"{VALUE}\s*(?P<unit>kg|grams?|g)\b", "kg"),
              Condition(SCENARIO + "inlet_water_temperature_K", TEMP, "K", count=2),
              Condition(SCENARIO + "liquid_endpoint_temperature_K", TEMP, "K", occurrence=1, count=2),
              Condition(SCENARIO + "evaporated_fraction", rf"(?:(?P<half>\bhalf\b)|{VALUE}\s*%)\s+(?:of (?:it|the water)\s+)?evaporat\w*", "1"))),
    Scenario("THM-19", "example-thm-19", (r"\b(?:demo|illustrative)\b", r"\bfire\b",
                                            r"\b(?:sealed|closed)\b", r"\bcabin\b"),
             (Condition(SCENARIO + "cabin/volume_m3", rf"{VALUE}\s*m[³3]", "m3"),)),
    Scenario("THM-20", "example-thm-20", (r"\b(?:demo|illustrative)\b", r"\bsmoke\b", r"\bduct\b"),
             (Condition(SCENARIO + "duct_length_m", LENGTH, "m"),
              Condition(SCENARIO + "air_speed_m_s", FLOW, "m/s"))),
]


PACKAGE_INVESTIGATIONS = {
    scenario.package_id: scenario.investigation_id
    for scenario in SCENARIOS if scenario.investigation_id
}


def match_scenario(prompt):
    """Select only unambiguous scenarios, deferring other requests to retrieval."""
    if re.search(r"\b(?:measured|dataset|csv|definition|define|without|excluding|versus|instead)\b", prompt, re.I):
        return None
    explicit = {match.upper() for match in re.findall(r"\bTHM-\d+\b", prompt, re.I)}
    # A specific fuel or run name must never be replaced by the default R377.
    incompatible_drop = re.search(r"\b(?:methanol|ethanol|heptane|propane|R(?!377\b)\d+)\b", prompt, re.I)
    matches = []
    for scenario in SCENARIOS:
        if (explicit - {scenario.model_id}) or (scenario.model_id == "THM-10" and incompatible_drop):
            continue
        bindings = scenario.match(prompt)
        if bindings is not None:
            matches.append((scenario, bindings))
    return matches[0] if len(matches) == 1 else None
