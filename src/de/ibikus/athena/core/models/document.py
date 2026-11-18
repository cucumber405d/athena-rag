"""Document-level models produced by the discovery/load/extract stages."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    """Metadata resolved for a single source document, before chunking.

    Populated from: automatic detection, sidecar files, and markdown
    front matter, in that order of increasing priority.
    """

    document_id: str
    source_id: str

    domain_id: str
    file_name: str
    file_path: str
    file_type: str
    mime_type: str | None = None
    checksum: str

    language: str | None = None
    document_type: str | None = None
    tags: list[str] = Field(default_factory=list)
    access_level: str = "private"

    chunking_profile: str | None = None
    embedding_profile: str | None = None
    collection_name: str | None = None

    title: str | None = None
    description: str | None = None

    created_at: datetime
    updated_at: datetime
    deleted: bool = False


class ExtractedPage(BaseModel):
    """A single page/segment of extracted text (used for page-aware chunking)."""

    page_number: int | None = None
    text: str
    start_time_sec: float | None = None
    end_time_sec: float | None = None


class ExtractedDocument(BaseModel):
    """Result of the Load+Extract stages: raw text ready for normalization."""

    metadata: DocumentMetadata
    pages: list[ExtractedPage]

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages)
