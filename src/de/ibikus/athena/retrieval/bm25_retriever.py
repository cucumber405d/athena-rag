"""BM25 retrieval.

Athena has no separate full-text index in the MVP: the BM25 corpus is built
on demand from the vector store's payloads (filtered by the same
domain/access filters as the vector search), then scored with rank_bm25.
This keeps the vector store as the single source of truth for chunks+metadata.
"""

from __future__ import annotations

from rank_bm25 import BM25Okapi

from de.ibikus.athena.core.models.retrieval import ScoredChunk
from de.ibikus.athena.stores.vector_gateway import SearchFilters, VectorStoreGateway

_CORPUS_SAMPLE_LIMIT = 5_000


def _tokenize(text: str) -> list[str]:
    return text.lower().split()


class BM25Retriever:
    def __init__(self, vector_store: VectorStoreGateway):
        self._vector_store = vector_store

    def retrieve(
        self, query: str, collection_name: str, top_k: int, filters: SearchFilters | None = None
    ) -> list[ScoredChunk]:
        corpus_chunks = self._vector_store.sample_points(
            collection_name, limit=_CORPUS_SAMPLE_LIMIT, filters=filters
        )
        if not corpus_chunks:
            return []

        tokenized_corpus = [_tokenize(c.text) for c in corpus_chunks]
        bm25 = BM25Okapi(tokenized_corpus)
        scores = bm25.get_scores(_tokenize(query))

        ranked = sorted(zip(corpus_chunks, scores), key=lambda pair: pair[1], reverse=True)[:top_k]
        return [
            ScoredChunk(chunk_id=c.chunk_id, text=c.text, metadata=c.metadata, score=float(score), source="bm25")
            for c, score in ranked
            if score > 0
        ]
