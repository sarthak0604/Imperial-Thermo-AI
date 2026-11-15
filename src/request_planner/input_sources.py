"""Read traceable values from table cells, JSON pointers and document text."""

import csv
import json
from math import isfinite
import re
import unicodedata

from pypdf import PdfReader
from pypdf.errors import PdfReadError


SUPPORTED_MEDIA = {"text/csv", "application/json", "application/pdf", "text/plain", "text/markdown"}
TEXT_MEDIA = SUPPORTED_MEDIA - {"text/csv", "application/json"}
NUMBER = r"[+\-−]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+\-−]?\d+)?"


class MappingError(ValueError):
    """A source value is missing, ambiguous, or incompatible with a model field."""


def pointer_parts(pointer):
    if not isinstance(pointer, str) or not pointer.startswith("/") or pointer == "/":
        raise MappingError("Use a JSON Pointer beginning with '/'.")
    return tuple(part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/"))


def quote_text(text):
    return " ".join(unicodedata.normalize("NFKC", text).split()).replace("−", "-")


def normalized_unit(text):
    if not isinstance(text, str) or not text.strip():
        raise MappingError("A numeric source needs a unit.")
    text = quote_text(text).replace("^", "").replace("·", " ").replace("°", "deg")
    text = re.sub(r"\s+", " ", text).strip()
    aliases = {
        "fraction": "1", "dimensionless": "1",
        "mole fraction": "mf", "volume fraction": "mf", "vol frac": "mf",
        "mass fraction": "yf", "% by vol": "m%", "vol %": "m%", "vol%": "m%",
        "mole %": "m%", "mol%": "m%", "% by mass": "y%", "wt%": "y%",
        "percent": "%", "second": "s", "seconds": "s", "sec": "s", "secs": "s", "degrees": "deg",
        "hr": "h", "micron": "μm", "microns": "μm",
        "Pa*s": "Pa s", "mPa*s": "mPa s",
        "W/m/K": "W/(m K)", "W/m K": "W/(m K)", "J/kg/K": "J/(kg K)",
        "kJ/kg/K": "kJ/(kg K)", "J/mol/K": "J/(mol K)", "W/m2/K": "W/(m2 K)",
        "deg C": "degC", "deg c": "degC", "celsius": "degC", "deg F": "degF",
    }
    return aliases.get(text, aliases.get(text.casefold(), text))


# Scale and offset to an SI reference within each quantity family.
UNITS = {}
for family, entries in {
    "length": {"m": 1, "cm": .01, "mm": .001, "μm": 1e-6},
    "area": {"m2": 1, "cm2": .0001, "mm2": 1e-6},
    "volume": {"m3": 1, "cm3": 1e-6, "L": .001},
    "time": {"s": 1, "ms": .001, "min": 60, "h": 3600},
    "pressure": {"Pa": 1, "kPa": 1000, "MPa": 1e6, "bar": 1e5,
                 "atm": 101325, "mmHg": 101325 / 760, "Torr": 101325 / 760, "psi": 6894.757293168},
    "mass": {"kg": 1, "g": .001, "mg": 1e-6},
    "mass flow": {"kg/s": 1, "g/s": .001, "mg/s": 1e-6},
    "density": {"kg/m3": 1, "g/cm3": 1000},
    "areal mass": {"kg/m2": 1, "g/m2": .001},
    "speed": {"m/s": 1, "cm/s": .01, "mm/s": .001},
    "diffusivity": {"m2/s": 1, "cm2/s": .0001, "mm2/s": 1e-6},
    "power": {"W": 1, "kW": 1000}, "flux": {"W/m2": 1, "kW/m2": 1000},
    "molar energy": {"J/mol": 1, "kJ/mol": 1000},
    "specific energy": {"J/kg": 1, "kJ/kg": 1000, "MJ/kg": 1e6},
    "molar mass": {"kg/mol": 1, "g/mol": .001},
    "molar heat capacity": {"J/(mol K)": 1, "kJ/(mol K)": 1000},
    "mass heat capacity": {"J/(kg K)": 1, "kJ/(kg K)": 1000},
    "viscosity": {"Pa s": 1, "mPa s": .001, "cP": .001},
    "gravity": {"g": 9.80665, "m/s2": 1, "cm/s2": .01},
    "angle": {"deg": 1, "rad": 57.29577951308232},
    "flow": {"sccm": 1, "slpm": 1000},
}.items():
    UNITS.update({name: (family, scale, 0) for name, scale in entries.items()})
UNITS.update({"K": ("temperature", 1, 0), "degC": ("temperature", 1, 273.15),
              "degF": ("temperature", 5 / 9, 255.3722222222222),
              "dK": ("temperature difference", 1, 0), "dC": ("temperature difference", 1, 0)})


def convert(value, source_unit, destination):
    if type(value) not in (float, int) or not isfinite(value):
        raise MappingError("Numeric inputs must be finite.")
    source = normalized_unit(source_unit)
    target = normalized_unit(destination)
    if source == target or target == "D":
        return value
    fractions = {"1": (None, 1), "%": (None, .01), "mf": ("mole", 1),
                 "m%": ("mole", .01), "yf": ("mass", 1), "y%": ("mass", .01)}
    if source in fractions and target in fractions:
        a, scale = fractions[source]
        b, dest_scale = fractions[target]
        if not a or not b or a == b:
            return value * scale / dest_scale
    if target == "dK" and source in {"K", "degC"}:
        return value
    if target == "dK" and source in {"degF", "dF"}:
        return value * 5 / 9
    left, right = UNITS.get(source), UNITS.get(target)
    # The source label g can mean grams or standard gravity.
    if source == "g" and right and right[0] == "mass":
        left = ("mass", .001, 0)
    if target == "g" and left and left[0] == "mass":
        right = ("mass", .001, 0)
    if left and right and left[0] == right[0]:
        return (value * left[1] + left[2] - right[2]) / right[1]
    raise MappingError(f"Cannot convert {source_unit} to {destination}.")


def parse_number(token):
    if isinstance(token, str) and re.fullmatch(NUMBER, token.strip()):
        return float(token.strip().replace("−", "-"))
    if type(token) in (float, int):
        return token
    raise MappingError(f"Expected a numeric source value, received {str(token)[:65]!r}.")


def verified_quote(text, source, *, numeric):
    quote, token = source.get("quote"), source.get("token")
    if not isinstance(quote, str) or not quote.strip() or len(quote) > 800:
        raise MappingError("Supply a short, nonempty source quote for the field.")
    if not isinstance(token, str) or not token.strip():
        raise MappingError("Supply the exact value token in the quote.")
    normalized_quote, normalized_token = quote_text(quote), quote_text(token)
    normalized_text = quote_text(text)
    if normalized_quote not in normalized_text:
        raise MappingError("The cited quote was not found.")
    barrier = r"[\w.+\-]" if numeric else r"[\w]"
    if not re.search(rf"(?<!{barrier}){re.escape(normalized_token)}(?!{barrier})", normalized_quote):
        raise MappingError("The supplied value token is not in the cited quote.")
    if numeric:
        header = source.get("unit_quote", quote)
        if not isinstance(header, str) or quote_text(header) not in normalized_text:
            raise MappingError("The cited unit header was not found.")
        stated_unit = source.get("unit")
        if not isinstance(stated_unit, str) or not stated_unit.strip():
            raise MappingError("A numeric quote needs its printed unit.")
        # The token is literal source wording. Unit aliases are applied at conversion.
        unit_token = quote_text(stated_unit)
        if not re.search(rf"(?<![A-Za-z]){re.escape(unit_token)}(?![A-Za-z0-9/])", quote_text(header)):
            raise MappingError("The printed unit was not found in the cited quote or header.")
        return parse_number(normalized_token), stated_unit
    return normalized_token, None


class Sources:
    """Use the execution session's existing downloads and cache parsed files."""

    def __init__(self, files, fetch, remaining):
        self.files = files
        self.fetch = fetch
        self.remaining = remaining
        self.tables = {}
        self.json = {}
        self.text = {}
        self.pdf = {}
        self.pages = {}

    def table(self, file_id):
        if file_id not in self.tables:
            file = self.files[file_id]
            with self.fetch(file).open(encoding=file.encoding or "utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream, strict=True)
                header = reader.fieldnames or []
                if not header or not all(header) or len(header) != len(set(header)):
                    raise MappingError("CSV requires unique, nonempty headers.")
                rows = []
                for row in reader:
                    if len(rows) % 1000 == 0:
                        self.remaining()
                    rows.append(row)
                self.tables[file_id] = (header, rows)
        return self.tables[file_id]

    def json_source(self, file_id, pointer, *, whole_column):
        file = self.files[file_id]
        if file_id not in self.json:
            self.json[file_id] = json.loads(self.fetch(file).read_text(encoding=file.encoding or "utf-8-sig"))
        path = pointer_parts(pointer)
        units = {item.name: item.unit for item in file.variables or []}
        unit = units.get(pointer, units.get(path[-1]))

        def read(value, parts):
            try:
                for key in parts:
                    if isinstance(value, list):
                        if not key.isdecimal():
                            raise KeyError(key)
                        value = value[int(key)]
                    elif isinstance(value, dict):
                        value = value[key]
                    else:
                        raise KeyError(key)
            except (KeyError, IndexError) as exc:
                raise MappingError(f"No JSON source value at {pointer}.") from exc
            return value

        def unbox(value):
            if isinstance(value, dict) and {"value", "unit"} <= set(value):
                return value["value"], value["unit"]
            return value, unit

        root = self.json[file_id]
        if "#" not in path or not whole_column:
            return unbox(read(root, path))
        if path.count("#") != 1:
            raise MappingError("A bulk source pointer takes one # index.")
        index = path.index("#")
        records = read(root, path[:index])
        if not isinstance(records, list) or not records:
            raise MappingError(f"The # in {pointer} must select a nonempty array.")
        values = []
        first_unit = None
        for row, record in enumerate(records):
            if row % 1000 == 0:
                self.remaining()
            value, row_unit = unbox(read(record, path[index + 1:]))
            if row == 0:
                first_unit = row_unit
            elif row_unit != first_unit and (row_unit is None or first_unit is None
                    or normalized_unit(row_unit) != normalized_unit(first_unit)):
                raise MappingError(f"The JSON array at {pointer} mixes different source units.")
            values.append(value)
        return values, first_unit

    def pdf_reader(self, file_id):
        if file_id not in self.pdf:
            try:
                reader = PdfReader(self.fetch(self.files[file_id]), strict=False)
                if reader.is_encrypted:
                    raise MappingError("Supply accessible text for the encrypted PDF.")
                self.pdf[file_id] = reader
            except PdfReadError as exc:
                raise MappingError("The source is not a readable PDF.") from exc
        return self.pdf[file_id]

    def document(self, file_id, page=None):
        file = self.files[file_id]
        if file.media_type == "application/pdf":
            pages = self.pdf_reader(file_id).pages
            if type(page) is not int or not 1 <= page <= len(pages):
                raise MappingError("Cite a valid one-based PDF page number.")
            if (file_id, page) not in self.pages:
                self.remaining()
                try:
                    self.pages[file_id, page] = pages[page - 1].extract_text() or ""
                except (PdfReadError, ValueError, NotImplementedError) as exc:
                    raise MappingError(f"Could not extract text from PDF page {page}.") from exc
            return self.pages[file_id, page]
        if page is not None:
            raise MappingError("Page numbers are only used for PDFs.")
        if file_id not in self.text:
            self.text[file_id] = self.fetch(file).read_text(encoding=file.encoding or "utf-8-sig")
        return self.text[file_id]

    def preview_document(self, file_id, prompt):
        file = self.files[file_id]
        if file.media_type != "application/pdf":
            return [{"text": self.document(file_id)[:14000]}]
        count = len(self.pdf_reader(file_id).pages)
        # Search bounded pages and always honor explicit page numbers or file metadata.
        hinted = [int(number) for number in re.findall(r"\bpage\s+(\d{1,4})", prompt, re.I)]
        page_hint = file.conditions.get("page")
        if type(page_hint) in (float, int) and isfinite(page_hint) and 1 <= page_hint <= count and page_hint == int(page_hint):
            hinted.append(int(page_hint))
        if file.source_page_url:
            hinted.extend(int(number) for number in re.findall(r"#page=(\d{1,5})$", str(file.source_page_url)))
        requested = {number for number in hinted if 1 <= number <= count}
        terms = set(re.findall(r"[\w-]{4,}", prompt.lower())) - {"using", "from", "what", "data", "model", "calculate"}
        candidates = []
        for page in sorted(set(range(1, min(64, count) + 1)) | requested):
            raw = self.document(file_id, page)
            if raw.strip():
                lines = raw.splitlines()
                top = max(range(len(lines)), key=lambda index: sum(
                    word in lines[index].lower() for word in terms
                ), default=0)
                start = max(0, top - 9)
                excerpt = "\n".join(lines[start:])[:3600]
                rank = sum(word in raw.lower() for word in terms)
                candidates.append((page in requested, rank, page, excerpt))
        selected = sorted(candidates, key=lambda part: (-part[0], -part[1], part[2]))[:4]
        return [{"page": page, "text": excerpt} for _, _, page, excerpt in selected]
