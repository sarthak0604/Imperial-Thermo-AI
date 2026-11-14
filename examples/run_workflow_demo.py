"""Offline synthetic demo: saved LLM plan → temporary data → THM-04 → frontend JSON.

SI-assisted example. No external network, LLM request, or NASA measurements.
"""

import json
from pathlib import Path

import httpx

from request_planner.__main__ import ReplayPlanner
from request_planner.models import SearchResults
from request_planner.planner import build_request
from request_planner.service import execute_request


def main():
    root = Path(__file__).resolve().parent
    results = SearchResults.model_validate_json((root / "thermo_search_results.json").read_text())
    request = build_request("Calculate heat release and show the test video and PDF", results,
                            ReplayPlanner(root / "thermo_plan.json"))
    fixture_bytes = {
        "/measurements.csv": (root / "thermo_measurements.csv").read_bytes(),
        "/evidence.json": (root / "thermo_input_template.json").read_bytes(),
    }

    def fixture_transport(request):
        if request.url.host != "example.org":
            raise ValueError("Offline demo accepts only its synthetic fixture URLs")
        return httpx.Response(200, stream=httpx.ByteStream(fixture_bytes[request.url.path]))

    # This injected transport cannot make network connections. Production execution
    # uses public_url validation and real streaming HTTP by default.
    with httpx.Client(transport=httpx.MockTransport(fixture_transport)) as client:
        response = execute_request(request, results, client=client, url_validator=lambda url: None)
    print(response.model_dump_json(indent=2))
    return 0 if response.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
