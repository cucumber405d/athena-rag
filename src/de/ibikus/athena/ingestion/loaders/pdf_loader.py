"""PDF loader — returns the file path; the parser opens it with pypdf for text
extraction and, for pages with no text layer, with pypdfium2 to render an
image for OCR fallback.
"""

from __future__ import annotations

from pathlib import Path


def load(path: Path) -> Path:
    return path
