"""Vector store abstraction. Backends: Qdrant (production-like), ChromaDB (local/dev).

No caller outside de.ibikus.athena.stores should import qdrant_client/chromadb directly —
retrieval, ingestion, CLI and web all go through VectorStoreGateway.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from de.ibikus.athena.core.models.chunk import Chunk
from de.ibikus.athena.core.models.retrieval import ScoredChunk


class CollectionStats(BaseModel):
    collection_name: str
    backend: str
    document_count: int
    chunk_count: int
    vector_dimension: int | None = None
    domains: dict[str, int] = {}
    file_types: dict[str, int] = {}
    languages: dict[str, int] = {}
    storage_size_bytes: int | None = None


class SearchFilters(BaseModel):
    """Pushdown-able filters shared by every backend adapter."""

    domain_id: str | None = None
    document_id: str | None = None
    document_type: str | None = None
    language: str | None = None
    tags: list[str] = []
    access_level: str | None = None
    deleted: bool | None = False
    source_id: str | None = None
    file_type: str | None = None
    created_after: str | None = None
    created_before: str | None = None
    updated_after: str | None = None
    updated_before: str | None = None
    page_number: int | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "SearchFilters":
        return cls(**{k: v for k, v in raw.items() if k in cls.model_fields})


class VectorStoreGateway(ABC):
    """Common interface implemented by QdrantVectorStoreAdapter and ChromaVectorStoreAdapter."""

    backend_name: str = "unknown"

    @abstractmethod
    def create_collection(self, collection_name: str, embedding_dimension: int, distance: str = "cosine") -> None: ...

    @abstractmethod
    def upsert_chunks(self, collection_name: str, chunks: list[Chunk]) -> None: ...

    @abstractmethod
    def delete_by_document_id(self, collection_name: str, document_id: str, hard: bool = False) -> int: ...

    @abstractmethod
    def delete_by_filter(self, collection_name: str, filters: SearchFilters, hard: bool = False) -> int: ...

    @abstractmethod
    def search_vector(
        self,
        collection_name: str,
        query_vector: list[float],
        top_k: int,
        filters: SearchFilters | None = None,
    ) -> list[ScoredChunk]: ...

    def search_hybrid(
        self,
        collection_name: str,
        query_vector: list[float],
        query_text: str,
        top_k: int,
        filters: SearchFilters | None = None,
    ) -> list[ScoredChunk]:
        """Native hybrid search. Backends without native support raise NotImplementedError;
        de.ibikus.athena.retrieval.hybrid_retriever falls back to application-level RRF fusion in that case.
        """
        raise NotImplementedError(f"{self.backend_name} has no native hybrid search")

    @abstractmethod
    def update_payload(self, collection_name: str, chunk_id: str, payload: dict[str, Any]) -> None: ...

    @abstractmethod
    def get_collection_stats(self, collection_name: str) -> CollectionStats: ...

    @abstractmethod
    def get_domains(self, collection_name: str) -> dict[str, int]: ...

    @abstractmethod
    def sample_points(
        self, collection_name: str, limit: int = 20, filters: SearchFilters | None = None
    ) -> list[ScoredChunk]:
        """Fetch chunks without vector search — used by the dashboard sample view and by
        the BM25 retriever, which builds its corpus from the vector store's payloads."""
        ...

    @abstractmethod
    def list_collections(self) -> list[str]: ...
