"""Split extraction requests without discarding text or inventory records."""

import json

from .local_model import LocalModelError


def extraction_requests(client, payload, schema):
    fits = getattr(client, "fits", lambda *args: True)
    pending = [payload]
    while pending:
        request = pending.pop()
        if fits("extract", request, schema):
            yield request
            continue
        parts = split_request(request)
        if parts is None:
            raise LocalModelError(
                "Extraction metadata, schema, or a single resource record exceeds "
                "LLM_INPUT_TOKENS. No source text or inventory record was dropped. "
                "Inspect the saved resource metadata before raising the working budget."
            )
        pending.extend(reversed(parts))


def split_request(request, *, prefer_sections=False):
    sections = request["sections"]
    inventory = request["resource_inventory"]
    # Split the larger dimension first; every source span is paired with every
    # resource batch so matching an explicitly referenced file remains possible.
    inventory_size = len(json.dumps(inventory, ensure_ascii=False))
    section_size = len(json.dumps(sections, ensure_ascii=False))
    can_split_sections = len(sections) > 1 or (
        len(sections) == 1 and len(sections[0]["text"]) > 1
    )
    if len(inventory) > 1 and (
        (not prefer_sections and inventory_size >= section_size)
        or not can_split_sections
    ):
        middle = len(inventory) // 2
        parts = [
            dict(request, resource_inventory=part)
            for part in (inventory[:middle], inventory[middle:])
        ]
    elif can_split_sections:
        if len(sections) > 1:
            middle = len(sections) // 2
            halves = (sections[:middle], sections[middle:])
        else:
            section = sections[0]
            text = section["text"]
            middle = len(text) // 2
            # Prefer a nearby paragraph, sentence or word boundary. Extremely
            # long unbroken strings still need an exact character split.
            for separator in ("\n", ". ", " "):
                boundary = text.rfind(separator, middle // 2, middle)
                if boundary >= 0:
                    middle = boundary + len(separator)
                    break
            halves = (
                [dict(section, text=section["text"][:middle])],
                [dict(section, text=section["text"][middle:])],
            )
        parts = [dict(request, sections=part) for part in halves]
    else:
        return None
    return parts
