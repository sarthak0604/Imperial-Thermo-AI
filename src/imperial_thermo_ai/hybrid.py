"""Rank fusion independent of embedding model; exact checks run after fusion."""

from collections import defaultdict

from .reviewed_graph import read_graph
from .vector_search import VectorGraphSearch, load_index


def reciprocal_rank_fusion(rankings, *, constant=60):
    scores = defaultdict(float)
    records = {}
    for ranking in rankings:
        seen = set()
        for rank, item in enumerate(ranking, 1):
            key = item.file_id
            if key in seen:
                continue
            seen.add(key)
            records[key] = item
            scores[key] += 1 / (constant + rank)
    return [records[key] for key in sorted(scores, key=lambda k: (-scores[k], k))]


class DenseRetriever:
    """Explicit optional service; never rebuild a stale 63k-node index during a request."""

    def __init__(self, graph_path, index_path, embedder):
        self.search = VectorGraphSearch(read_graph(graph_path), load_index(index_path))
        self.embedder = embedder

    def __call__(self, prompt, plan=None):
        from request_planner.models import SearchResults

        vector = self.embedder.encode([prompt], query=True)[0]
        return SearchResults.model_validate(
            self.search.global_search(
                vector,
                query_id="dense",
                model_id=self.embedder.model_id,
                plan=plan,
                top_k=100,
            )
        ).files
