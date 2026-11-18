"""Ingestion job / report models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class IngestionError(BaseModel):
    file_path: str
    error_type: str
    error_message: str


class IngestionReport(BaseModel):
    ingestion_job_id: str
    started_at: datetime
    finished_at: datetime | None = None

    domain_id: str
    target_collection: str
    embedding_profile: str
    vector_store: str
    dry_run: bool = False

    files_total: int = 0
    files_processed: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    chunks_created: int = 0

    errors: list[IngestionError] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
