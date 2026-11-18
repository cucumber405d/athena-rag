"""Chunker interface and the transient chunk-piece produced before metadata attachment."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ChunkPiece:
    text: str
    chunk_index: int
    page_number: int | None = None
    start_time_sec: float | None = None
    end_time_sec: float | None = None
