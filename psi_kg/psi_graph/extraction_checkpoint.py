"""Completed scientific document contributions, independent of GPU batch size."""

import json

from .common import digest, read_json, write_json


def identity(client, payloads, system, schema, document=None):
    # Payloads contain scientific identity fields, never mutable transfer status.
    # Input/context budgets affect execution, not the meaning of validated output.
    return digest(
        json.dumps(
            dict(
                version="scoped-extraction-1",
                source={
                    key: (document or {}).get(key)
                    for key in ("id", "source_url", "sha256", "parser_version")
                },
                provider=getattr(client, "provider", type(client).__name__),
                model=getattr(client, "model", None),
                base_url=getattr(client, "base_url", None),
                system=system,
                schema=schema.model_json_schema(),
                payloads=payloads,
            ),
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def load(path, fingerprint, document_id, schema):
    if not path.exists():
        return None
    try:
        cached = read_json(path)
        if (
            cached.get("fingerprint") != fingerprint
            or cached.get("complete") is not True
        ):
            return None
        results = cached["results"]
        if not isinstance(results, list) or not results:
            return None
        for item in results:
            if item["document_id"] != document_id:
                return None
            schema.model_validate(item["extraction"])
        failures = cached["failures"]
        if not isinstance(failures, list):
            return None
        return results, failures
    except (ValueError, KeyError, TypeError):
        # An interrupted or outdated cache is recomputed; no unvalidated graph is used.
        return None


def save(path, fingerprint, results, failures):
    write_json(
        path,
        dict(
            fingerprint=fingerprint, complete=True, results=results, failures=failures
        ),
    )
