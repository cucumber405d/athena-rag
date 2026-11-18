"""Chunk and chunk-metadata models.

ChunkMetadata is the payload stored alongside every vector in Qdrant/Chroma.
It is the single source of truth for filter pushdown and dashboard stats.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ChunkMetadata(BaseModel):
    chunk_id: str
    document_id: str
    source_id: str

    domain_id: str
    collection_name: str

    file_name: str
    file_path: str
    file_type: str
    mime_type: str | None = None
    checksum: str

    language: str | None = None
    document_type: str | None = None
    tags: list[str] = Field(default_factory=list)

    page_number: int | None = None
    start_time_sec: float | None = None
    end_time_sec: float | None = None

    chunk_index: int
    chunking_profile: str
    embedding_profile: str
    embedding_model: str
    embedding_dimension: int

    created_at: datetime
    updated_at: datetime
    deleted: bool = False
    access_level: str = "private"


class Chunk(BaseModel):
    """A chunk of text ready for embedding, plus its metadata."""

    text: str
    metadata: ChunkMetadata
    vector: list[float] | None = None
