"""Reviewed field mappings for the published PSI-69 FLEX table (version 1)."""

import csv
import math
import re
from urllib.parse import parse_qs, urlsplit


FLEX_FILE = "PSI-69_Experimental table_FLEX.csv"
FLEX_REPORT = "https://ntrs.nasa.gov/citations/20150023456"
FLEX_PAGE = "https://psi.nasa.gov/physci/repo/data/investigations/PSI-69"
FLEX_TEST = "FLEX Test #"
PRESSURE = "Ambient pressure; mmHg"
INITIAL_DIAMETER = "Droplet initial diameter; mm"
END_DIAMETER = "Visible flame extinction diameter; mm"
BURN_RATE = "Burning rate; mm"  # NASA/TP-2015-216046, Table IX, specifies mm²/s.
BURN_TIME = "Burn time; s"
GAS_COLUMNS = {
    "O2": "O initial ambient composition; mole fraction",
    "N2": "N initial ambient composition; mole fraction",
    "CO2": "CO initial ambient composition; mole fraction",
    "He": "He initial ambient composition; mole fraction",
}
# Preserve the table's literal headers. The NASA report identifies O, N and CO
# in those headers as O2, N2 and CO2 respectively.
THM10_COLUMNS = {
    FLEX_TEST, "FLEX Identifier", "Fuel", PRESSURE, GAS_COLUMNS["O2"],
    INITIAL_DIAMETER, END_DIAMETER, BURN_RATE, BURN_TIME, "Test end",
}
THM02_COLUMNS = {FLEX_TEST, "FLEX Identifier", PRESSURE, *GAS_COLUMNS.values()}


def supports_flex_table(file, model_id):
    """Recognize the specific public table whose units and columns were reviewed."""
    if (model_id not in {"THM-02", "THM-10"} or file.investigation_id != "PSI-69"
            or file.role != "measurement" or file.media_type != "text/csv" or not file.retrieval_url):
        return False
    url = urlsplit(str(file.retrieval_url))
    query = parse_qs(url.query)
    return (
        url.hostname == "psi.nasa.gov"
        and url.path.rstrip("/") == "/geode-py/ws/studies/PSI-69/download"
        and query.get("file") == [FLEX_FILE]
        and query.get("version") == ["1"]
    )


def flex_run_number(model_id, request):
    """Validate the selector without allowing it to replace measured conditions."""
    if not isinstance(request, dict):
        raise ValueError("Supply a FLEX run such as FLEX-002.")
    if model_id == "THM-10":
        if (set(request) != {"topic", "analysis", "scenario"}
                or request["topic"] != "droplet_combustion"
                or request["analysis"] != "estimate_droplet_regression"
                or not isinstance(request["scenario"], dict)
                or set(request["scenario"]) != {"run_id"}):
            raise ValueError("THM-10 FLEX selection needs only scenario.run_id in the droplet regression request.")
        run_id = request["scenario"]["run_id"]
    elif model_id == "THM-02":
        if set(request) - {"run_id", "temp_k", "target_species"}:
            raise ValueError("THM-02 FLEX selection accepts run_id, temp_k and optional target_species.")
        temperature = request.get("temp_k")
        if type(temperature) not in (int, float) or not math.isfinite(temperature) or temperature <= 0:
            raise ValueError("THM-02 needs a supplied positive gas temperature in kelvin. This table has no gas temperature.")
        target = request.get("target_species")
        if target is not None and (not isinstance(target, str) or target not in GAS_COLUMNS):
            raise ValueError("Select O2, N2, CO2 or He as target_species.")
        run_id = request.get("run_id")
    else:
        raise ValueError("The FLEX table supports THM-02 and THM-10.")
    if not isinstance(run_id, str) or not re.fullmatch(r"FLEX-[0-9]{3}", run_id) or run_id == "FLEX-000":
        raise ValueError("Use a FLEX test ID such as FLEX-002.")
    return int(run_id[5:])


def selected_flex_row(path, encoding, run, required_columns):
    with path.open(encoding=encoding, newline="") as handle:
        table = csv.DictReader(handle, strict=True)
        names = table.fieldnames or []
        if not required_columns.issubset(names) or len(set(names)) != len(names):
            raise ValueError("The downloaded file does not have the reviewed FLEX table headers.")
        rows = [(line, row) for line, row in enumerate(table, start=2)
                if (row.get(FLEX_TEST) or "").strip() == str(run)]
    if len(rows) != 1:
        raise ValueError(f"Expected exactly one row for FLEX-{run:03d}; found {len(rows)}.")
    line, row = rows[0]
    if None in row or any(value is None for value in row.values()):
        raise ValueError(f"FLEX-{run:03d} has an incomplete or ragged row.")
    return line, row


def measurement(row, column, *, optional=False):
    text = row[column].strip()
    if optional and not text:
        return None
    try:
        value = float(text)
    except ValueError as exc:
        raise ValueError(f"The selected FLEX run has no usable numeric value for {column!r}.") from exc
    if not math.isfinite(value):
        raise ValueError(f"The selected FLEX run has a non-finite value for {column!r}.")
    return value


def build_flex_input(model_id, request, path, file):
    """Build a model input from one actual row; source IDs resolve in the caller."""
    run = flex_run_number(model_id, request)
    run_id = f"FLEX-{run:03d}"
    columns = THM10_COLUMNS if model_id == "THM-10" else THM02_COLUMNS
    line, row = selected_flex_row(path, file.encoding or "cp1252", run, columns)
    pressure_mmhg = measurement(row, PRESSURE)
    if pressure_mmhg <= 0:
        raise ValueError(f"{run_id} does not have positive ambient pressure.")
    pressure_kpa = pressure_mmhg * 101.325 / 760
    origin = {
        "file_id": file.file_id,
        "investigation_id": "PSI-69",
        "run_id": run_id,
        "flex_identifier": row["FLEX Identifier"].strip(),
        "data_row": line - 1,
        "pressure_mmhg": pressure_mmhg,
        "source_url": FLEX_PAGE,
    }
    if model_id == "THM-02":
        composition = {name: measurement(row, column) for name, column in GAS_COLUMNS.items()}
        if any(not 0 <= x <= 1 for x in composition.values()) or not math.isclose(
            math.fsum(composition.values()), 1, rel_tol=0, abs_tol=0.001
        ):
            raise ValueError(f"{run_id} has an incomplete or inconsistent reported gas composition.")
        target = request.get("target_species")
        if target is not None and composition[target] <= 0:
            raise ValueError(f"{run_id} does not contain the requested target species.")
        return {
            "function_id": "THM-02",
            "params": {
                "mole_fracs": composition,
                "pressure_kpa": pressure_kpa,
                "temp_k": request["temp_k"],
                **({"target_species": target} if target else {}),
            },
            "investigation_context": {
                **origin,
                "temperature_source": "Request-supplied temperature; PSI-69 table does not report it.",
                "scope": "Computed transport properties of the reported inlet mixture at the specified temperature.",
            },
            "psi_citations": [FLEX_PAGE, FLEX_REPORT],
        }

    diameter = measurement(row, INITIAL_DIAMETER)
    oxygen = measurement(row, GAS_COLUMNS["O2"])
    rate = measurement(row, BURN_RATE)
    endpoint = measurement(row, END_DIAMETER)
    if row["Test end"].strip().casefold() != "extinction":
        raise ValueError(f"{run_id} did not end in reported extinction; select an extinction run.")
    if not 0 < endpoint < diameter or rate <= 0 or not 0 < oxygen <= 1:
        raise ValueError(f"{run_id} does not support a positive-rate visible extinction reconstruction.")
    fuel = row["Fuel"].strip().lower()
    if not fuel:
        raise ValueError(f"{run_id} has no fuel identity.")
    profile_id = f"psi69_{run_id.lower().replace('-', '_')}_measured_rate"
    scenario = {
        "profile_id": profile_id,
        "fuel_type": fuel,
        "process": "combustion",
        "d0_mm": diameter,
        "x_o2": oxygen,
        "pressure_kpa": pressure_kpa,
        "t_amb_k": None,
        "endpoint_diameter_mm": endpoint,
    }
    return {
        "request": {
            "topic": "droplet_combustion", "analysis": "estimate_droplet_regression",
            "scenario": scenario,
        },
        "evidence": {
            "profiles": [{
                "id": profile_id, "fuel_type": fuel, "process": "combustion",
                "method": "measured_rate", "regression_rate_mm2_s": rate,
                "validity": {key: [scenario[key], scenario[key]]
                             for key in ("d0_mm", "x_o2", "pressure_kpa")},
            }],
            "provenance": {
                **origin,
                "type": "published_run_reconstruction",
                "illustrative": False,
                "reported_burn_time_s": measurement(row, BURN_TIME, optional=True),
                "notes": [
                    "The initial diameter is taken at igniter activation; the published regression is fitted after ignition.",
                    "The modeled time to the reported visible extinction diameter and the reported burn time use different definitions.",
                    "Ambient temperature is unavailable in the selected table and unused by this measured-rate reconstruction.",
                ],
            },
            "sources": [
                {"role": "measurements", "url": FLEX_PAGE,
                 "locator": f"{FLEX_FILE}, version 1, {run_id}"},
                {"role": "units_and_method", "url": FLEX_REPORT,
                 "locator": "FLEX experimental results tables; diameter-squared regression definition and burning-rate unit (mm²/s)"},
            ],
        },
    }
