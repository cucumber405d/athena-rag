"""pdf_page_aware chunking profile: splits within each page on paragraph/sentence
boundaries (semantic_text_splitter), preserving page_number.
"""

from __future__ import annotations

from de.ibikus.athena.core.models.document import ExtractedPage
from de.ibikus.athena.ingestion.chunkers.base import ChunkPiece
from de.ibikus.athena.ingestion.chunkers.semantic_splitters import build_splitter


def chunk(
    pages: list[ExtractedPage], chunk_size: int, chunk_overlap: int, file_type: str | None = None
) -> list[ChunkPiece]:
    splitter = build_splitter(file_type, chunk_size, chunk_overlap)
    pieces: list[ChunkPiece] = []
    index = 0
    for page in pages:
        for text in splitter.chunks(page.text):
            pieces.append(ChunkPiece(text=text, chunk_index=index, page_number=page.page_number))
            index += 1
    return pieces
