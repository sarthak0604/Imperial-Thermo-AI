"""Portable passage index, built offline from retained extracted source sections."""

import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

from request_planner.backend_models import EvidenceItem

from .graph_search import tokens


class EvidenceIndex:
    def __init__(self, items):
        self.items = [EvidenceItem.model_validate(i) for i in items]
        self.postings = defaultdict(set)
        for i, item in enumerate(self.items):
            for term in tokens(item.text + " " + item.title):
                self.postings[term].add(i)

    @classmethod
    def read(cls, path):
        p = Path(path)
        return cls(json.loads(p.read_text())["items"]) if p.is_file() else cls([])

    def search(self, question, investigations=(), excluded=(), limit=8, file_ids=None):
        words = tokens(question)
        scores = defaultdict(float)
        for term in words:
            hits = self.postings.get(term, ())
            for i in hits:
                scores[i] += math.log1p(len(self.items) / max(1, len(hits)))
        # Titles should matter more than repeated bibliographic name mentions.
        for i in scores:
            title_terms = tokens(self.items[i].title.replace("_", " "))
            scores[i] += 3 * len(words & title_terms)
            if self.items[i].review_status == "reviewed_selected_sections":
                scores[i] *= 1.5
        ranked = sorted(scores, key=lambda i: (-scores[i], self.items[i].id))
        result, counts = [], defaultdict(int)
        for i in ranked:
            item = self.items[i]
            if (
                investigations
                and item.investigation_id not in investigations
                or item.investigation_id in excluded
            ):
                continue
            if file_ids is not None and item.file_id not in file_ids:
                continue
            if counts[item.file_id] >= 2:
                continue
            counts[item.file_id] += 1
            result.append(item)
            if len(result) == limit:
                break
        return result


def build(sources, output):
    items = []
    for path in sorted(Path(sources).glob("*/extracted/*.json")):
        record = json.loads(path.read_text())
        # Numerical table rows belong in typed data retrieval, not prose search.
        if Path(record.get("filename", "")).suffix.lower() not in {
            ".pdf",
            ".doc",
            ".docx",
            ".ppt",
            ".pptx",
            ".txt",
            ".md",
        }:
            continue
        digest = record.get("sha256")
        if not digest or not record.get("source_url"):
            continue
        reviewed = set(record.get("reviewed_locators", []))
        chars = 0
        for section in record.get("sections", []):
            if chars >= 200000:
                break
            text, locator = section.get("text", "").strip(), section.get("locator", "")
            if len(text) < 40 or not locator:
                continue
            text = text[: 200000 - chars]
            chars += len(text)
            # Split long source sections with overlap and a source-local offset.
            for offset in range(0, len(text), 5000):
                passage = text[max(0, offset - 300) : offset + 5000]
                eid = hashlib.sha256(
                    f"{record['id']}:{digest}:{locator}:{offset}".encode()
                ).hexdigest()[:24]
                items.append(
                    EvidenceItem(
                        id=eid,
                        file_id=record["id"],
                        investigation_id=record["study"],
                        title=record["filename"],
                        text=passage,
                        locator=f"{locator}; chars {max(0, offset - 300)}–{min(len(text), offset + 5000)}",
                        source_url=record["source_url"],
                        sha256=digest,
                        review_status="reviewed_selected_sections"
                        if locator in reviewed
                        else "text_extracted_unreviewed",
                    ).model_dump()
                )
    Path(output).write_text(
        json.dumps({"schema_version": "2.0", "items": items}, ensure_ascii=False)
    )
    return len(items)


if __name__ == "__main__":
    import argparse

    cli = argparse.ArgumentParser()
    cli.add_argument("--sources", required=True)
    cli.add_argument("--output", required=True)
    args = cli.parse_args()
    print(build(args.sources, args.output))
