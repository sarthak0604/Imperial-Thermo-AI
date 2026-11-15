"""Select identifiable source resources without repeating the entire inventory.

Selection supplies candidates to extraction, never scientific associations. Full
inventory records remain in the manifest and graph. Aliases are exact after URL,
Unicode, case and whitespace normalization; broad topical similarity is not used.
"""

import html
import re
import unicodedata
from collections import defaultdict
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit

SCOPE_CAVEAT = (
    "Extraction inventory was scoped to each document's own resource, containing "
    "archives, and resources explicitly named by identifiable filename, path, "
    "title, DOI or URL in its source text. Implicit or abbreviated cross-file "
    "references may remain unresolved; all resources remain in the manifest and graph."
)

_WORD = re.compile(r"[^\W_]+(?:_[^\W_]+)*", re.UNICODE)
_DOI = re.compile(r"10\.\d{4,9}/\S+", re.IGNORECASE)
_GENERIC_STEMS = {
    "data",
    "dataset",
    "datasets",
    "document",
    "file",
    "files",
    "index",
    "metadata",
    "readme",
    "read_me",
    "read-me",
    "report",
    "results",
    "sample",
    "supplement",
    "supplementary",
    "table",
    "test",
    "untitled",
}
_GENERIC_TITLES = _GENERIC_STEMS | {
    "analyzed data",
    "raw data",
    "supporting data",
    "supporting files",
    "supplementary data",
    "supplementary material",
    "additional information",
    "experimental data",
    "data description",
    "read me",
}


def normalize(value):
    return " ".join(
        unicodedata.normalize("NFKC", html.unescape(unquote(str(value))))
        .casefold()
        .split()
    )


def _filename_alias(value):
    value = normalize(value).replace("\\", "/")
    name = PurePosixPath(value).name
    if "." not in name:
        return None
    stem, suffix = name.rsplit(".", 1)
    if not suffix.isalnum() or len(suffix) > 8 or len(re.sub(r"\W", "", stem)) < 3:
        return None
    if stem in _GENERIC_STEMS and "/" not in value:
        return None
    return value


def _aliases(resource):
    aliases = set()
    for field in ("id",):
        if value := resource.get(field):
            if len(value) >= 12 and ":" in value:
                aliases.add((normalize(value), "identifier"))
    for field in ("filename", "nasa_path"):
        if value := resource.get(field):
            if alias := _filename_alias(value):
                aliases.add((alias, "filename"))
    if title := resource.get("title"):
        normalized = normalize(title)
        if alias := _filename_alias(title):
            aliases.add((alias, "filename"))
        elif (
            normalized not in _GENERIC_TITLES
            and len(normalized) >= 20
            and len(set(_WORD.findall(normalized))) >= 3
        ):
            aliases.add((normalized, "title"))
    if doi := resource.get("doi"):
        if match := _DOI.search(normalize(doi)):
            aliases.add((match.group(0).rstrip(".,;"), "doi"))
    for field in ("source_url", "resolved_url"):
        if value := resource.get(field):
            normalized = normalize(value)
            parsed = urlsplit(normalized)
            if (
                parsed.scheme in ("http", "https")
                and parsed.netloc
                and parsed.path.strip("/")
            ):
                aliases.add((normalized, "url"))
                if match := _DOI.search(normalized):
                    aliases.add((match.group(0).rstrip(".,;"), "doi"))
    return aliases


def _contains(text, alias, kind):
    start = 0
    while (start := text.find(alias, start)) >= 0:
        end = start + len(alias)
        before = text[start - 1] if start else ""
        after = text[end] if end < len(text) else ""
        # Don't match run1.csv inside myrun1.csv or run1.csv.backup. Slashes
        # remain boundaries, allowing an explicit basename within a path.
        extra = {
            "filename": "_.-",
            "doi": "_.-/",
            "url": "_.-/?#",
        }.get(kind, "_")
        blocked_after = bool(after and (after.isalnum() or after in extra))
        if after == "." and kind in ("filename", "doi", "url"):
            following = text[end + 1] if end + 1 < len(text) else ""
            blocked_after = bool(
                following and (following.isalnum() or following == "_")
            )
        if not (before and (before.isalnum() or before in extra)) and not blocked_after:
            return True
        start += 1
    return False


class ResourceContext:
    """Reusable exact-reference index for one inventory snapshot.

    Rebuild after appending newly discovered resources. The pipeline normally
    instantiates once per document, after that document's links are discovered.
    """

    def __init__(self, resources):
        self.resources = list(resources)
        self.by_id = defaultdict(set)
        self.by_url = defaultdict(set)
        aliases = defaultdict(set)
        for index, resource in enumerate(self.resources):
            if value := resource.get("id"):
                self.by_id[value].add(index)
            for field in ("source_url", "resolved_url"):
                if value := resource.get(field):
                    self.by_url[normalize(value)].add(index)
            for alias in _aliases(resource):
                aliases[alias].add(index)
        # Index each alias by its longest word. A chunk only examines aliases
        # whose anchor occurs in the chunk, rather than every inventory record.
        self.anchors = defaultdict(list)
        for (alias, kind), indexes in aliases.items():
            words = _WORD.findall(alias)
            if words:
                anchor = max(words, key=lambda word: (len(word), word))
                self.anchors[anchor].append((alias, kind, indexes))

    def select(self, document, sections):
        selected = set()
        for field in ("id", "resource_id"):
            selected.update(self.by_id.get(document.get(field), ()))
        if source := document.get("source_url"):
            selected.update(self.by_url.get(normalize(source), ()))
        # Joining separate sections with newlines would normalize to spaces and
        # could fabricate a cross-section title; match each section separately.
        for section in sections:
            text = normalize(section.get("text", ""))
            for word in set(_WORD.findall(text)):
                for alias, kind, indexes in self.anchors.get(word, ()):
                    if _contains(text, alias, kind):
                        selected.update(indexes)
        pending = list(selected)
        while pending:
            index = pending.pop()
            parent = self.resources[index].get("parent_resource_id")
            for parent_index in self.by_id.get(parent, ()):
                if parent_index not in selected:
                    selected.add(parent_index)
                    pending.append(parent_index)
        return [self.resources[index] for index in sorted(selected)]


def select_inventory(document, sections, resources):
    return ResourceContext(resources).select(document, sections)
