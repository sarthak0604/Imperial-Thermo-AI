"""Resolve public NASA PSI study titles, acronyms, accessions and URLs."""

import re
from urllib.parse import urlencode

from . import nasa_access as nasa

PAGE_URL = "https://psi.nasa.gov/physci/repo/data/investigations/"


def catalogue():
    """Read every page of the same public search API used by the PSI website."""
    studies = {}
    offset = 0
    while True:
        query = urlencode({"type": "investigation", "size": 100, "from": offset})
        data = nasa.read_json(f"{nasa.BASE_URL}/repo/search?{query}")
        try:
            hits = data["hits"]["hits"]
            total = data["hits"]["total"]
            if isinstance(total, dict):
                if total.get("relation", "eq") != "eq":
                    raise ValueError("Inexact catalogue count")
                total = total["value"]
            if not isinstance(hits, list) or type(total) is not int or total < 0:
                raise ValueError("Invalid catalogue page")
            if data.get("timed_out") or data.get("_shards", {}).get("failed", 0):
                raise ValueError("Incomplete catalogue response")
            before = len(studies)
            for hit in hits:
                source = hit["_source"]
                accession = nasa.investigation_id(source["Accession"])
                title = source["Title"]
                if not isinstance(title, str) or not title.strip():
                    raise ValueError("Missing study title")
                studies[accession] = {
                    "id": accession,
                    "title": title,
                    "acronym": source.get("Acronym") or "",
                }
            offset += len(hits)
            if offset >= total:
                break
            if not hits or len(studies) == before:
                raise ValueError("Catalogue pagination stopped early")
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeError(
                "NASA's study catalogue is incomplete or has changed. "
                "Use PSI IDs or investigation URLs instead."
            ) from error
    return sorted(studies.values(), key=lambda study: study["id"])


def normalized(value):
    return " ".join(re.findall(r"\w+", value.casefold()))


def resolve_studies(values, *, interactive=False):
    """Resolve each selection once; never silently choose an ambiguous title."""
    selections = [
        part.strip() for value in values for part in value.split(";") if part.strip()
    ]
    if not selections:
        raise ValueError("Enter at least one study name, PSI ID or URL.")
    available = None
    resolved = []
    for value in selections:
        try:
            accession = nasa.investigation_id(value)
        except ValueError:
            if "://" in value or value.upper().startswith("PSI-"):
                raise ValueError(f"Invalid NASA PSI ID or URL: {value}") from None
            if available is None:
                available = catalogue()
            term = normalized(value)
            if not term:
                raise ValueError(f"Invalid study name: {value!r}")
            exact = [
                s
                for s in available
                if term in (normalized(s["title"]), normalized(s["acronym"]))
            ]
            matches = exact or [
                s
                for s in available
                if term in normalized(s["title"]) or term in normalized(s["acronym"])
            ]
            if not matches:
                raise ValueError(
                    f"No NASA PSI study matches {value!r}. Use its full title or PSI ID."
                )
            if len(matches) > 1:
                options = "\n".join(
                    f"{i}: {s['id']} — {s['title']}" for i, s in enumerate(matches, 1)
                )
                if not interactive:
                    raise ValueError(
                        f"Multiple studies match {value!r}; use a PSI ID:\n{options}"
                    )
                print(f"Multiple studies match {value!r}:\n{options}")
                while True:
                    answer = input("Choose a study number (or q to cancel): ").strip()
                    if answer.casefold() == "q":
                        raise ValueError("Study selection cancelled.")
                    if answer.isdigit() and 1 <= int(answer) <= len(matches):
                        matches = [matches[int(answer) - 1]]
                        break
                    print("Enter one of the listed numbers.")
            accession = matches[0]["id"]
            print(f"Selected {accession}: {matches[0]['title']}", flush=True)
        url = PAGE_URL + accession
        if url not in resolved:
            resolved.append(url)
    return resolved


def select_studies(values):
    interactive = not values
    if interactive:
        values = [
            input("NASA PSI study names, IDs or URLs (separate studies with ;): ")
        ]
    return resolve_studies(values, interactive=interactive)
