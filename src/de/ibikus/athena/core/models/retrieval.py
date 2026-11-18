"""Retrieval request/result models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from de.ibikus.athena.core.models.chunk import ChunkMetadata


class RetrievalRequest(BaseModel):
    query: str
    domain_id: str | None = None
    collection_name: str
    vector_store: str
    retrieval_mode: str = "hybrid"

    vector_top_k: int = 30
    bm25_top_k: int = 30
    rerank_top_n: int = 8
    fusion: str = "rrf"

    use_filter_pushdown: bool = True
    filters: dict[str, Any] = Field(default_factory=dict)

    embedding_profile: str
    reranker_profile: str | None = None
    max_context_tokens: int = 4000


class ScoredChunk(BaseModel):
    chunk_id: str
    text: str
    metadata: ChunkMetadata
    score: float
    source: str = "vector"  # vector | bm25 | fused | reranked


class RetrievalDiagnostics(BaseModel):
    vector_top_k: int
    bm25_top_k: int
    fusion: str
    retrieval_mode: str
    reranker: str = "none"
    final_chunks: int
    filters_applied: dict[str, Any] = Field(default_factory=dict)


class ContextResult(BaseModel):
    """Output of the Context Builder: ready-to-send context plus diagnostics."""

    context_text: str
    chunks: list[ScoredChunk]
    diagnostics: RetrievalDiagnostics
