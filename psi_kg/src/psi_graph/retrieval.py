"""Transparent lexical concept search followed by typed graph traversal."""

import math
import re
from collections import Counter, defaultdict

STOP = {
    "a",
    "an",
    "the",
    "of",
    "in",
    "on",
    "for",
    "to",
    "and",
    "or",
    "what",
    "which",
    "how",
    "does",
    "do",
    "is",
    "are",
    "with",
    "find",
    "data",
    "about",
    "show",
    "me",
}


def tokens(text):
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [
        word[:-1] if word.endswith("s") and len(word) > 4 else word
        for word in words
        if word not in STOP
    ]


def search(graph, query, limit=5):
    nodes = {n["id"]: n for n in graph["nodes"]}
    concepts = [n for n in graph["nodes"] if n["type"] == "Concept"]
    docs = [
        tokens(
            " ".join(
                [
                    n["properties"]["name"],
                    *n["properties"]["synonyms"],
                    n["properties"]["description"] or "",
                ]
            )
        )
        for n in concepts
    ]
    frequency = Counter(word for doc in docs for word in set(doc))
    mean_length = sum(map(len, docs)) / max(1, len(docs))
    query_tokens = set(tokens(query))
    matches = []
    for concept, doc in zip(concepts, docs):
        counts = Counter(doc)
        score = 0.0
        matched = sorted(query_tokens & counts.keys())
        for term in matched:
            idf = math.log(
                1 + (len(docs) - frequency[term] + 0.5) / (frequency[term] + 0.5)
            )
            score += (
                idf
                * counts[term]
                * 2.2
                / (counts[term] + 1.2 * (0.25 + 0.75 * len(doc) / max(1, mean_length)))
            )
        for name in [concept["properties"]["name"], *concept["properties"]["synonyms"]]:
            if set(tokens(name)) and set(tokens(name)) <= query_tokens:
                score += 3
        if score:
            matches.append(
                dict(node=concept, score=round(score, 4), matched_terms=matched)
            )
    matches.sort(key=lambda x: (-x["score"], x["node"]["id"]))
    matches = matches[:limit]
    outgoing = defaultdict(list)
    experiments = {}
    for edge in graph["edges"]:
        outgoing[edge["source"]].append(edge)
    for match in matches:
        for edge in graph["edges"]:
            if edge["type"] != "STUDIES" or edge["target"] != match["node"]["id"]:
                continue
            experiment = nodes[edge["source"]]
            result = experiments.setdefault(
                experiment["id"],
                dict(
                    node=experiment, score=0.0, reasons=[], variables=[], resources=[]
                ),
            )
            result["score"] += match["score"]
            result["reasons"].append(
                dict(
                    concept=match["node"]["properties"]["name"],
                    matched_terms=match["matched_terms"],
                    explanation="Query matches the concept; a source-supported STUDIES edge connects it to this experiment.",
                    evidence=edge["properties"]["evidence"],
                )
            )
    for exp_id, result in experiments.items():
        for edge in outgoing[exp_id]:
            target = nodes[edge["target"]]
            if edge["type"] == "MEASURES":
                result["variables"].append(target)
            elif edge["type"] == "HAS_RESOURCE":
                result["resources"].append(
                    dict(
                        node=target,
                        explanation="Associated by a validated HAS_RESOURCE edge.",
                        evidence=edge["properties"]["evidence"],
                        source_url=target["properties"]["source_url"],
                        storage_uri=target["properties"]["storage_uri"],
                        access_status=target["properties"]["access_status"],
                    )
                )
    ranked = sorted(experiments.values(), key=lambda x: (-x["score"], x["node"]["id"]))[
        :limit
    ]
    return dict(query=query, concepts=matches, experiments=ranked)


def run_cases(graph, cases):
    results = []
    for case in cases:
        result = search(graph, case["query"], limit=10)
        experiment_ids = {r["node"]["id"] for r in result["experiments"]}
        resource_ids = {
            r["node"]["id"] for exp in result["experiments"] for r in exp["resources"]
        }
        passed = bool(result["concepts"] and experiment_ids and resource_ids)
        passed = (
            passed and set(case.get("expected_experiment_ids", [])) <= experiment_ids
        )
        passed = passed and set(case.get("expected_resource_ids", [])) <= resource_ids
        concept_ids = {c["node"]["id"] for c in result["concepts"]}
        passed = passed and set(case.get("expected_concept_ids", [])) <= concept_ids
        if case.get("max_expected_rank"):
            top = {
                r["node"]["id"]
                for r in result["experiments"][: case["max_expected_rank"]]
            }
            passed = passed and set(case.get("expected_experiment_ids", [])) <= top
        results.append(
            dict(
                query=case["query"],
                passed=passed,
                concept_count=len(result["concepts"]),
                experiment_count=len(experiment_ids),
                resource_count=len(resource_ids),
                result=result,
            )
        )
    unrelated = search(graph, "photosynthesis chlorophyll ocean plankton")
    results.append(
        dict(
            query="photosynthesis chlorophyll ocean plankton",
            passed=not unrelated["experiments"],
            negative_control=True,
            result=unrelated,
        )
    )
    return results
