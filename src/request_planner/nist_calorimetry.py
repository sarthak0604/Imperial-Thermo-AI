"""SI-assisted direct analysis of the sourced NIST excerpt bundled with THM-04."""

import json
import re
import tempfile

from .execution import ExecutionSession, present_result
from .function_registry import function_root, model_spec
from .models import ExecutionLimits


def nist_window(prompt):
    if not re.search(r"\bNGQC[_ -]?3m[_ -]?2kgs\b", prompt, re.I):
        return None
    if not re.search(r"\b(?:heat|hrr|power|energy|calorimetry)\b", prompt, re.I):
        return None
    if re.search(r"\b(?:compare|versus|another run|instead|excluding|without|whole|entire)\b", prompt, re.I):
        return None
    matches = list(re.finditer(
        r"\b(?:between|from)?\s*(\d+(?:\.\d+)?)\s*(?:s(?:ec(?:onds?)?)?\s*)?"
        r"(?:and|to|[-–])\s*(\d+(?:\.\d+)?)\s*(?:s|secs?|seconds?)\b",
        prompt, re.I,
    ))
    if len(matches) != 1:
        return None
    match = matches[0]
    other = prompt[:match.start()] + prompt[match.end():]
    other = re.sub(r"\b(?:THM-04|NGQC[_ -]?3m[_ -]?2kgs)\b", "", other, flags=re.I)
    if re.search(r"\d", other):
        return None
    return tuple(float(value) for value in match.groups())


def run_nist_window(window):
    payload = json.loads(function_root().joinpath(model_spec("THM-04")["example"]).read_text())
    run = payload["evidence"]["runs"][0]
    samples = run["samples"]
    if not samples[0]["time_s"] <= window[0] < window[1] <= samples[-1]["time_s"]:
        return None
    payload["request"]["scenario"]["time_window_s"] = list(window)
    with tempfile.TemporaryDirectory(prefix="thermo-nist-") as directory:
        result = ExecutionSession(directory, ExecutionLimits()).calculate("THM-04", payload)
    source_id = "nist-ngqc-3m-2kgs"
    blocks = [b for b in present_result("THM-04", result, include_input=True)
              if b["type"] == "calculation" or b["series"][0]["label"] == "hrr_W"]
    for block in blocks:
        block["source_file_ids"] = [source_id]
        if block["type"] == "chart":
            block["title"] = "THM-04 heat release rate over time"
            block["x"]["label"], block["x"]["unit"] = "Elapsed time", "s"
            block["series"][0]["label"], block["series"][0]["unit"] = "Heat release rate", "W"
    return result, blocks, {
        "file_id": source_id, "title": "NIST burner measurements · NGQC_3m_2kgs",
        "source_page_url": run["source_url"],
    }, payload["evidence"]["provenance"]["notes"]
