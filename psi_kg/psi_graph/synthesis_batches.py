"""Bounded synthesis with deterministic, evidence-preserving batch merging."""

from copy import deepcopy

from .common import slug
from .local_model import LocalModelError


def unique(values):
    result = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def joined(left, right):
    if left is None and right is None:
        return None
    return "\n\n".join(unique(value for value in (left, right) if value))


def merge_records(records, key, merge):
    merged = {}
    for record in records:
        identity = key(record)
        if identity in merged:
            merge(merged[identity], record)
        else:
            merged[identity] = deepcopy(record)
    return list(merged.values())


def merge_fields(left, right, strings=(), lists=()):
    for field in strings:
        left[field] = joined(left[field], right[field])
    for field in lists:
        left[field] = unique(left[field] + right[field])


def merge_study(left, right):
    merge_fields(
        left,
        right,
        strings=("summary",),
        lists=("keywords", "methods", "findings", "evidence"),
    )
    # Graph export uses a dictionary keyed by condition.name: retain conflicting
    # values together rather than silently allowing the last batch to win.
    left["conditions"] = merge_records(
        left["conditions"] + right["conditions"],
        lambda x: x["name"],
        lambda a, b: merge_fields(a, b, strings=("value",)),
    )
    left["concepts"] = merge_records(
        left["concepts"] + right["concepts"],
        lambda x: slug(x["name"]),
        lambda a, b: merge_fields(
            a, b, strings=("description",), lists=("synonyms", "evidence")
        ),
    )
    left["variables"] = merge_records(
        left["variables"] + right["variables"],
        lambda x: (slug(x["name"]), x["unit"], x["role"]),
        lambda a, b: merge_fields(a, b, strings=("symbol",), lists=("evidence",)),
    )
    left["resources"] = merge_records(
        left["resources"] + right["resources"],
        lambda x: x["resource_id"],
        lambda a, b: merge_fields(a, b, lists=("evidence",)),
    )


def merge_syntheses(results):
    from .science import Synthesis

    records = [r.model_dump() for r in results]
    merged = dict(
        investigation_summary="\n\n".join(
            unique(r["investigation_summary"] for r in records)
        ),
        investigation_keywords=unique(
            v for r in records for v in r["investigation_keywords"]
        ),
        investigation_evidence=unique(
            v for r in records for v in r["investigation_evidence"]
        ),
        studies=merge_records(
            [v for r in records for v in r["studies"]],
            lambda x: slug(x["key"]),
            merge_study,
        ),
        resources=merge_records(
            [v for r in records for v in r["resources"]],
            lambda x: x["resource_id"],
            lambda a, b: merge_fields(
                a, b, strings=("summary",), lists=("keywords", "variables", "evidence")
            ),
        ),
        caveats=unique(v for r in records for v in r["caveats"]),
    )
    if len(records) > 1:
        merged["caveats"].append(
            "Synthesis used bounded batches. Identical study keys and resource IDs were merged "
            "without dropping evidence or findings; differently named study identities across "
            "batches may remain duplicated. Conflicting condition values are retained together."
        )
    return Synthesis.model_validate(merged)


def referenced_ids(value):
    if isinstance(value, dict):
        for name, item in value.items():
            if name in ("resource_id", "document_id") and isinstance(item, str):
                yield item
            else:
                yield from referenced_ids(item)
    elif isinstance(value, list):
        for item in value:
            yield from referenced_ids(item)


def extraction_atoms(records):
    """Split record lists without truncating any scientific object or quote."""
    for record in records:
        extraction = record["extraction"]
        yielded = False
        for field in ("studies", "resources", "caveats"):
            for item in extraction[field]:
                atom = {
                    key: value for key, value in record.items() if key != "extraction"
                }
                atom["extraction"] = {"studies": [], "resources": [], "caveats": []}
                atom["extraction"][field] = [item]
                yielded = True
                yield atom
        if not yielded:
            yield record


def bounded_batches(client, stage, values, payload, schema, max_items=None):
    """Never submit an oversized atomic record, even when no split is possible."""
    fits = getattr(client, "fits", lambda *args: True)
    batch = []
    for value in values:
        if max_items is not None and len(batch) >= max_items:
            yield batch
            batch = []
        if fits(stage, payload(batch + [value]), schema):
            batch.append(value)
            continue
        if batch:
            yield batch
            batch = []
        if not fits(stage, payload([value]), schema):
            raise LocalModelError(
                f"A single {stage} record exceeds the complete request budget; "
                "no evidence was truncated and no oversized request was sent. "
                "Reduce the source extraction size or inspect the saved intermediate record."
            )
        batch = [value]
    if batch:
        yield batch


def excerpt_context(context, quote, radius=600):
    """Preserve the full quote with nearby source text, never an arbitrary prefix."""
    from .common import normalized

    if not context:
        return ""
    start = context.find(quote)
    if start < 0:
        context, quote = normalized(context), normalized(quote)
        start = context.find(quote)
    if start < 0 or not quote:
        # No valid location means there is no safe quote-centered excerpt.
        raise LocalModelError(
            "Cannot locate audit evidence in its saved source context"
        )
    return context[max(0, start - radius) : start + len(quote) + radius]


def fit_review_items(client, items, payload, schema, scope):
    fits = getattr(client, "fits", lambda *args: True)
    for item in items:
        if fits("scientific_review", payload([item]), schema):
            yield item
            continue
        bounded = deepcopy(item)
        bounded["source_context"] = [
            excerpt_context(context, ref["text"])
            for context, ref in zip(
                item["source_context"], item["evidence"], strict=True
            )
        ]
        bounded["context_scope"] = (
            "Quote-centered excerpts only. Full source sections are saved separately; "
            "do not claim that the complete source context was reviewed."
        )
        if not fits("scientific_review", payload([bounded]), schema):
            scope["complete"] = False
            scope["blocked_item_id"] = item["id"]
            raise LocalModelError(
                f"Scientific audit item {item['id']} exceeds the complete request budget "
                "even with quote-centered context. No evidence was truncated or oversized "
                "request sent; the final graph was not published."
            )
        scope["excerpt_context_ids"].append(item["id"])
        yield bounded
