"""Shared semantic_text_splitter setup: splits on paragraph/sentence boundaries
(or markdown structure for .md files) instead of blind word-count windows.
"""

from __future__ import annotations

from typing import Protocol

from semantic_text_splitter import MarkdownSplitter, TextSplitter


class Splitter(Protocol):
    def chunks(self, text: str) -> list[str]: ...


def build_splitter(file_type: str | None, capacity: int, overlap: int) -> Splitter:
    if file_type == "markdown":
        return MarkdownSplitter(capacity, overlap)
    return TextSplitter(capacity, overlap)
