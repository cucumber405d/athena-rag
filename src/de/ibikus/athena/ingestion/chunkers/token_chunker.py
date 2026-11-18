"""default_text / book_default / cv_default chunking profiles: splits on semantic
boundaries (markdown structure for .md files, paragraphs/sentences otherwise)
instead of a blind word-count window, via semantic_text_splitter.
"""

from __future__ import annotations

from de.ibikus.athena.core.models.document import ExtractedPage
from de.ibikus.athena.ingestion.chunkers.base import ChunkPiece
from de.ibikus.athena.ingestion.chunkers.semantic_splitters import build_splitter


def chunk(
    pages: list[ExtractedPage], chunk_size: int, chunk_overlap: int, file_type: str | None = None
) -> list[ChunkPiece]:
    full_text = "\n\n".join(p.text for p in pages)
    splitter = build_splitter(file_type, chunk_size, chunk_overlap)
    pieces = splitter.chunks(full_text)
    return [ChunkPiece(text=text, chunk_index=i) for i, text in enumerate(pieces)]
