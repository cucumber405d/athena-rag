"""Hybrid retrieval: vector + BM25 fused, with optional reranking on top.

Native Qdrant sparse-vector hybrid search is a documented V2 upgrade
(VectorStoreGateway.search_hybrid); for now fusion always happens at the
application level.
"""

from __future__ import annotations

from de.ibikus.athena.core.models.retrieval import ScoredChunk
from de.ibikus.athena.retrieval.bm25_retriever import BM25Retriever
from de.ibikus.athena.retrieval.vector_retriever import VectorRetriever
from de.ibikus.athena.stores.vector_gateway import SearchFilters

_RRF_K = 60


def rrf_fuse(rankings: list[list[ScoredChunk]], k: int = _RRF_K) -> list[ScoredChunk]:
    """Reciprocal Rank Fusion across one or more ranked chunk lists."""
    scores: dict[str, float] = {}
    best_chunk: dict[str, ScoredChunk] = {}
    for ranking in rankings:
        for rank, chunk in enumerate(ranking):
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1.0 / (k + rank + 1)
            best_chunk.setdefault(chunk.chunk_id, chunk)

    fused = [
        ScoredChunk(
            chunk_id=chunk_id,
            text=best_chunk[chunk_id].text,
            metadata=best_chunk[chunk_id].metadata,
            score=score,
            source="fused",
        )
        for chunk_id, score in scores.items()
    ]
    fused.sort(key=lambda c: c.score, reverse=True)
    return fused


def relative_score_fuse(rankings: list[list[ScoredChunk]]) -> list[ScoredChunk]:
    """Normalize each ranking's scores to [0, 1] and sum them."""
    scores: dict[str, float] = {}
    best_chunk: dict[str, ScoredChunk] = {}
    for ranking in rankings:
        if not ranking:
            continue
        max_score = max(c.score for c in ranking) or 1.0
        for chunk in ranking:
            normalized = chunk.score / max_score
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + normalized
            best_chunk.setdefault(chunk.chunk_id, chunk)

    fused = [
        ScoredChunk(chunk_id=cid, text=best_chunk[cid].text, metadata=best_chunk[cid].metadata, score=s, source="fused")
        for cid, s in scores.items()
    ]
    fused.sort(key=lambda c: c.score, reverse=True)
    return fused


def weighted_fuse(rankings: list[list[ScoredChunk]], weights: list[float] | None = None) -> list[ScoredChunk]:
    weights = weights or [1.0] * len(rankings)
    scores: dict[str, float] = {}
    best_chunk: dict[str, ScoredChunk] = {}
    for ranking, weight in zip(rankings, weights):
        for chunk in ranking:
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + weight * chunk.score
            best_chunk.setdefault(chunk.chunk_id, chunk)

    fused = [
        ScoredChunk(chunk_id=cid, text=best_chunk[cid].text, metadata=best_chunk[cid].metadata, score=s, source="fused")
        for cid, s in scores.items()
    ]
    fused.sort(key=lambda c: c.score, reverse=True)
    return fused


_FUSION_STRATEGIES = {
    "rrf": rrf_fuse,
    "relative_score": relative_score_fuse,
    "weighted": weighted_fuse,
}


class HybridRetriever:
    def __init__(self, vector_retriever: VectorRetriever, bm25_retriever: BM25Retriever):
        self._vector_retriever = vector_retriever
        self._bm25_retriever = bm25_retriever

    def retrieve(
        self,
        query: str,
        collection_name: str,
        vector_top_k: int,
        bm25_top_k: int,
        fusion: str = "rrf",
        filters: SearchFilters | None = None,
    ) -> list[ScoredChunk]:
        vector_results = self._vector_retriever.retrieve(query, collection_name, vector_top_k, filters)
        bm25_results = self._bm25_retriever.retrieve(query, collection_name, bm25_top_k, filters)
        fuse = _FUSION_STRATEGIES.get(fusion, rrf_fuse)
        return fuse([vector_results, bm25_results])
