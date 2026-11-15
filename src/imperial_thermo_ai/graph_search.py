"""Execute validated PSI search plans without executing model-generated code.

SI assistance: OpenAI Codex. Matches describe graph metadata, not established
engineering conclusions. Unknown metadata remains unknown under negation.
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any


NODE_TYPES = {"Investigation", "Experiment", "Concept", "Variable", "Resource"}
ENDPOINTS = {
    "CONTAINS": ("Investigation", "Experiment"),
    "STUDIES": ("Experiment", "Concept"),
    "MEASURES": ("Experiment", "Variable"),
    "HAS_RESOURCE": ("Experiment", "Resource"),
}
OPERATORS = {"eq", "ne", "lt", "lte", "gt", "gte", "contains", "in", "exists"}
TEXT_FIELDS = ("name", "title", "summary", "description", "keywords", "synonyms", "methods", "variables")
STOPWORDS = set("a an and are as at be been by can data dataset datasets do does evidence experiment experiments file files find for from has have how i in into is it me my of on or paper papers please relevant research resource resources show studies study test tests that the their these this to under using was were what which with would you".split())


def normalize(value: Any) -> str:
    """Unicode-aware matching; retain letters, numbers, and chemical symbols."""
    text = unicodedata.normalize("NFKC", str(value).replace("_", " ")).casefold()
    return " ".join(re.sub(r"[^\w%]+", " ", text, flags=re.UNICODE).split())


def tokens(text: str) -> set[str]:
    return {word[:-1] if len(word) > 5 and word.endswith("s") else word
            for word in normalize(text).split() if word not in STOPWORDS}


def stringify(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(stringify(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(stringify(item) for item in value)
    return "" if value is None else str(value)


@dataclass
class Evaluation:
    state: bool | None
    details: list[dict] = field(default_factory=list)
    edges: list[dict] = field(default_factory=list)


class GraphIndex:
    def __init__(self, graph: dict):
        if not isinstance(graph, dict) or not isinstance(graph.get("nodes"), list) or not isinstance(graph.get("edges"), list):
            raise ValueError("Graph must contain nodes and edges arrays.")
        self.graph = graph
        self.nodes: dict[str, dict] = {}
        self.outgoing: dict[str, list[dict]] = {}
        self.incoming: dict[str, list[dict]] = {}
        for node in graph["nodes"]:
            if not isinstance(node, dict) or not isinstance(node.get("id"), str) or not node["id"]:
                raise ValueError("Each graph node needs a nonempty string id.")
            if node["id"] in self.nodes:
                raise ValueError(f"Duplicate node id: {node['id']}")
            if node.get("type") not in NODE_TYPES or not isinstance(node.get("properties"), dict):
                raise ValueError(f"Invalid type/properties for node {node['id']}")
            self.nodes[node["id"]] = node
            self.outgoing[node["id"]] = []
            self.incoming[node["id"]] = []
        edge_ids = set()
        for edge in graph["edges"]:
            if not isinstance(edge, dict) or not isinstance(edge.get("id"), str) or not edge["id"]:
                raise ValueError("Each graph edge needs a nonempty string id.")
            if edge["id"] in edge_ids:
                raise ValueError(f"Duplicate edge id: {edge['id']}")
            edge_ids.add(edge["id"])
            source, target, kind = edge.get("source"), edge.get("target"), edge.get("type")
            if source not in self.nodes or target not in self.nodes:
                raise ValueError(f"Dangling graph edge: {edge['id']}")
            if kind not in ENDPOINTS or (self.nodes[source]["type"], self.nodes[target]["type"]) != ENDPOINTS[kind]:
                raise ValueError(f"Wrong edge type or endpoint types: {edge['id']}")
            if not isinstance(edge.get("properties", {}), dict):
                raise ValueError(f"Invalid edge properties: {edge['id']}")
            self.outgoing[source].append(edge)
            self.incoming[target].append(edge)

    def complete(self, node_id: str, edge: str, direction: str) -> bool:
        """Absence is known only with an explicit export completeness declaration."""
        declaration = self.graph.get("relation_completeness")
        if declaration is True:
            return True
        if not isinstance(declaration, dict):
            return False
        value = declaration.get(node_id, [])
        key = edge if direction == "out" else "in:" + edge
        return value is True or isinstance(value, list) and key in value

    def context(self, node_id: str, max_hops: int = 2) -> list[dict]:
        seen = {node_id}
        frontier = [node_id]
        for _ in range(max_hops):
            new = []
            for current in frontier:
                for edge in self.outgoing[current] + self.incoming[current]:
                    other = edge["target"] if edge["source"] == current else edge["source"]
                    if other not in seen:
                        seen.add(other)
                        new.append(other)
            frontier = new
        return [self.nodes[key] for key in sorted(seen)]


def read_field(node: dict, path: str) -> Any:
    if path == "id":
        return node["id"]
    if path == "text":
        return " ".join(stringify(node["properties"].get(key)) for key in TEXT_FIELDS)
    value = node["properties"]
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _known(value: Any) -> bool:
    return value is not None and value != "" and value != [] and value != {}


def _number(value: Any) -> bool:
    return type(value) is int or type(value) is float and math.isfinite(value)


def evaluate_filter(node: dict, predicate: dict) -> Evaluation:
    path, operator, expected = predicate.get("field"), predicate.get("operator"), predicate.get("value")
    if not isinstance(path, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)*", path):
        raise ValueError("Invalid graph property path.")
    if operator not in OPERATORS:
        raise ValueError("Unsupported graph filter operator.")
    raw = read_field(node, path)
    observed = raw.get("value") if isinstance(raw, dict) and "value" in raw else raw
    state: bool | None = None
    reason = "Requested property is absent or null in this graph."

    if operator == "exists":
        if expected is not None and type(expected) is not bool:
            raise ValueError("exists requires a boolean or null value.")
        state = _known(observed) == (expected is not False)
        reason = "Property presence checked in this graph export."
    elif _known(observed):
        missing_metadata = []
        incompatible_metadata = []
        for key in ("unit", "basis", "stage", "scope"):
            requested = predicate.get(key)
            if requested is None:
                continue
            actual = raw.get(key) if isinstance(raw, dict) else None
            if actual is None:
                missing_metadata.append(key)
            elif normalize(actual) != normalize(requested):
                incompatible_metadata.append(key)
        if missing_metadata or incompatible_metadata:
            # A value in another unit/stage does not establish this requested value.
            reason = "Cannot compare: " + "; ".join(
                (["missing " + ", ".join(missing_metadata)] if missing_metadata else []) +
                (["different " + ", ".join(incompatible_metadata)] if incompatible_metadata else [])
            ) + ". No automatic unit, scope, or stage substitution was made."
        elif operator in {"lt", "lte", "gt", "gte"}:
            if _number(observed) and _number(expected):
                state = {"lt": observed < expected, "lte": observed <= expected,
                         "gt": observed > expected, "gte": observed >= expected}[operator]
                reason = "Compared recorded numerical values."
            else:
                reason = "A numeric comparison needs finite numeric values on both sides."
        elif expected is None:
            reason = "No definite requested value was supplied."
        elif isinstance(observed, dict) or (_number(observed) and isinstance(expected, str)) or (isinstance(observed, str) and _number(expected)):
            reason = "The requested and recorded value types cannot be compared without interpretation; qualitative terms do not establish numerical thresholds."
        else:
            values = observed if isinstance(observed, list) else [observed]
            if path == "name" and node["type"] in {"Concept", "Variable"}:
                aliases = node["properties"].get("synonyms", [])
                if isinstance(aliases, list):
                    values = values + aliases
            def equals(item: Any, wanted: Any) -> bool:
                if isinstance(item, str) and isinstance(wanted, str):
                    return normalize(item) == normalize(wanted)
                return type(item) is type(wanted) and item == wanted or _number(item) and _number(wanted) and item == wanted

            if operator in {"eq", "ne"}:
                state = any(equals(item, expected) for item in values)
                if operator == "ne":
                    state = not state
            elif operator == "in":
                if not isinstance(expected, list):
                    raise ValueError("in requires an array of values.")
                state = any(equals(item, wanted) for item in values for wanted in expected)
            elif operator == "contains":
                state = any(normalize(expected) in normalize(item) for item in values)
                if path in {'title', 'filename'} and isinstance(expected, str):
                    # Natural-language document descriptions reorder title words;
                    # exact filename identity still uses eq or the stable file ID.
                    state = any(tokens(expected).issubset(tokens(str(item))) for item in values)
            reason = "Matched graph property or declared synonym." if state else "Recorded property conflicts with the requested condition."
            # Fuzzy matches are discovery candidates, never asserted identities.
            if path == "name" and operator == "eq" and state is False and isinstance(expected, str):
                ratio = max((SequenceMatcher(None, normalize(item), normalize(expected)).ratio()
                             for item in values if isinstance(item, str)), default=0)
                if ratio >= 0.86:
                    state = None
                    reason = "Similar spelling found; identity requires confirmation."
    detail = {
        "node_id": node["id"], "field": path, "operator": operator,
        "requested": expected, "observed": raw,
        "source_text": predicate.get("source_text", ""),
        "requested_metadata": {key: predicate[key] for key in ("unit", "basis", "stage", "scope") if predicate.get(key) is not None},
        "status": "satisfied" if state is True else "conflicting" if state is False else "unverified",
        "reason": reason,
    }
    return Evaluation(state, [detail])


def evaluate(index: GraphIndex, node_id: str, expression: dict, depth: int = 0) -> Evaluation:
    if depth > 24 or not isinstance(expression, dict):
        raise ValueError("Invalid or overly nested graph expression.")
    kind = expression.get("kind")
    if kind == "filter":
        return evaluate_filter(index.nodes[node_id], expression)
    if kind in {"all", "any"}:
        items = expression.get("items")
        if not isinstance(items, list) or len(items) > 100:
            raise ValueError("A boolean expression requires a bounded items array.")
        children = [evaluate(index, node_id, item, depth + 1) for item in items]
        if kind == "all":
            state = False if any(c.state is False for c in children) else None if any(c.state is None for c in children) else True
        else:
            state = True if any(c.state is True for c in children) else None if any(c.state is None for c in children) else False
            children = [c for c in children if c.state is state] or children
        return Evaluation(state, [d for c in children for d in c.details], [e for c in children for e in c.edges])
    if kind == "not":
        child = evaluate(index, node_id, expression.get("item"), depth + 1)
        state = None if child.state is None else not child.state
        # Keep the inner expression for inspection but do not mislabel its sign.
        detail = {"node_id": node_id, "field": None, "operator": "not",
                  "requested": expression.get("item"), "observed": None,
                  "status": "satisfied" if state is True else "conflicting" if state is False else "unverified",
                  "reason": "Negated condition evaluated without treating unknown as false.",
                  "inner_details": child.details}
        return Evaluation(state, [detail], child.edges)
    if kind == "relation":
        edge_type, direction = expression.get("edge"), expression.get("direction")
        if edge_type not in ENDPOINTS or direction not in {"in", "out"}:
            raise ValueError("Invalid graph traversal.")
        required_type = ENDPOINTS[edge_type][0 if direction == "out" else 1]
        if index.nodes[node_id]["type"] != required_type:
            raise ValueError(f"{direction} {edge_type} cannot start at {index.nodes[node_id]['type']}.")
        adjacency = index.outgoing if direction == "out" else index.incoming
        related = [edge for edge in adjacency[node_id] if edge["type"] == edge_type]
        children = []
        for edge in related:
            other = edge["target"] if direction == "out" else edge["source"]
            child = evaluate(index, other, expression.get("where"), depth + 1)
            children.append(Evaluation(child.state, child.details, [edge] + child.edges))
        complete = index.complete(node_id, edge_type, direction)
        state = True if any(c.state is True for c in children) else None if any(c.state is None for c in children) or not complete else False
        selected = [c for c in children if c.state is state]
        if not selected:
            selected = children
        details = [d for c in selected for d in c.details]
        if state is None and not any(c.state is None for c in children):
            details.append({"node_id": node_id, "field": None, "operator": "relation",
                            "requested": {"edge": edge_type, "direction": direction}, "observed": None,
                            "status": "unverified", "reason": "No qualifying edge in this export; completeness of this relationship is not declared."})
        elif state is False and not children:
            details.append({"node_id": node_id, "field": None, "operator": "relation",
                            "requested": {"edge": edge_type, "direction": direction}, "observed": [],
                            "status": "conflicting", "reason": "No qualifying edge in a relationship explicitly declared complete."})
        return Evaluation(state, details, [e for c in selected for e in c.edges])
    raise ValueError("Unknown graph expression kind.")


def _requested_values(index: GraphIndex, node_id: str, requests: list[dict]) -> list[dict]:
    output = []
    context = index.context(node_id)
    for request in requests:
        matching_nodes = [node for node in context if node["type"] == request.get("node_type")]
        if not matching_nodes:
            output.append({"node_id": None, **request, "value": None, "status": "unavailable"})
        for node in matching_nodes:
            value = read_field(node, request["field"])
            stage = request.get("stage")
            if stage is not None and (not isinstance(value, dict) or normalize(value.get("stage")) != normalize(stage)):
                value = None
            output.append({"node_id": node["id"], **request, "value": value,
                           "status": "available" if _known(value) else "unavailable"})
    return output


def _hit(index: GraphIndex, node: dict, evaluation: Evaluation, score: float, requests: list[dict], kind: str) -> dict:
    paths = list({edge["id"]: edge for edge in evaluation.edges}.values())
    return {
        "id": node["id"], "node": node, "match_kind": kind,
        "score": round(score, 4), "score_type": "lexical_relevance_not_probability",
        "satisfied": [d for d in evaluation.details if d["status"] == "satisfied"],
        "unverified": [d for d in evaluation.details if d["status"] == "unverified"],
        "conflicting": [d for d in evaluation.details if d["status"] == "conflicting"],
        "paths": paths,
        "requested_fields": _requested_values(index, node["id"], requests),
        "evidence_status": "metadata_only",
        "provenance": {"graph_id": index.graph.get("graph_id"), "graph_source_url": index.graph.get("source_url"),
                       "node_source_url": node["properties"].get("source_url"),
                       "edge_properties": [{"id": edge["id"], "properties": edge.get("properties", {})} for edge in paths]},
    }


def search_graph(graph: dict, plan: dict, limit: int = 20) -> dict:
    """Return exact metadata matches, incomplete candidates, and related leads.

    Numeric values may be scalar when no unit/basis/stage/scope is requested.
    Otherwise use a property object such as {value: 20, unit: '%', basis:
    'volume', stage: 'initial', scope: 'chamber'}. This executor deliberately
    does not invent units or convert atmospheric basis/stage. Explicit
    relation_completeness=true declares this exported graph closed-world;
    a mapping {node_id: ['HAS_RESOURCE', 'in:CONTAINS']} declares selected paths.
    Without it, absence of a relationship cannot establish a negative claim.
    """
    if not isinstance(plan, dict) or not isinstance(plan.get("queries"), list):
        raise ValueError("Expected a version 2 query plan with queries array.")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000.")
    index = graph if isinstance(graph, GraphIndex) else GraphIndex(graph)
    graph = index.graph
    query_tokens = tokens(plan.get("search_text", ""))
    output = []
    for query in plan["queries"]:
        return_type = query.get("return_type")
        if return_type not in NODE_TYPES:
            raise ValueError("Unknown query return type.")
        buckets: dict[str, list] = {"matches": [], "candidates": [], "related_candidates": []}
        for node in index.nodes.values():
            if node["type"] != return_type:
                continue
            evaluation = evaluate(index, node["id"], query.get("where"))
            # Rank on bounded direct ownership context. Shared concept fanout
            # must not turn a resource lookup into an unbounded two-hop scan.
            nearby = [node]
            for edge in (index.incoming[node['id']] + index.outgoing[node['id']])[:32]:
                other = edge['source'] if edge['target'] == node['id'] else edge['target']
                nearby.append(index.nodes[other])
            context_text = " ".join(stringify(n["properties"].get(key)) for n in nearby for key in TEXT_FIELDS)
            words = tokens(context_text)
            score = len(words & query_tokens) / max(1, len(query_tokens))
            meaningful_match = any(d["status"] == "satisfied" and d.get("field") in {"name", "id", "title", "material"} for d in evaluation.details)
            if evaluation.state is True:
                bucket, kind = "matches", "metadata_match"
            elif score > 0 or meaningful_match:
                bucket, kind = ("candidates", "unverified") if evaluation.state is None else ("related_candidates", "related_only")
            else:
                continue
            buckets[bucket].append(_hit(index, node, evaluation, score, plan.get("requested_fields", []), kind))
        item = {"label": query.get("label", ""), "return_type": return_type}
        for key, rows in buckets.items():
            rows.sort(key=lambda row: (-row["score"], row["id"]))
            item["total_" + key] = len(rows)
            item[key] = rows[:limit]
        output.append(item)
    return {
        "queries": output,
        "coverage": {
            "graph_id": graph.get("graph_id"), "nodes": len(index.nodes), "edges": len(graph["edges"]),
            "relationship_completeness_declared": graph.get("relation_completeness", False),
            "retrieval": "deterministic_graph_filters_and_lexical_ranking",
            "limitations": ["Matches establish graph metadata only, not a material safety prediction.",
                            "Candidates have unverified conditions; related candidates may conflict with requested conditions.",
                            "Missing quantities, units, stages, bases, and scopes remain unknown.",
                            "Scores are lexical relevance, not calibrated confidence or scientific evidence strength."],
        },
    }
