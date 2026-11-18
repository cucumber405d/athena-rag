"""Dense vector retrieval."""

from __future__ import annotations

from de.ibikus.athena.core.models.retrieval import ScoredChunk
from de.ibikus.athena.ingestion.embeddings import EmbeddingService
from de.ibikus.athena.stores.vector_gateway import SearchFilters, VectorStoreGateway


class VectorRetriever:
    def __init__(self, vector_store: VectorStoreGateway, embedding_service: EmbeddingService):
        self._vector_store = vector_store
        self._embedding_service = embedding_service

    def retrieve(
        self, query: str, collection_name: str, top_k: int, filters: SearchFilters | None = None
    ) -> list[ScoredChunk]:
        query_vector = self._embedding_service.embed_query(query)
        return self._vector_store.search_vector(collection_name, query_vector, top_k, filters)
