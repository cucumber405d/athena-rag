"""Loader interface: reads a raw file from disk into an in-memory representation
that the matching parser (de.ibikus.athena.ingestion.parsers) knows how to turn into
ExtractedPage objects.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class Loader(Protocol):
    def load(self, path: Path) -> Any: ...


class UnsupportedFileError(NotImplementedError):
    """Raised by placeholder loaders for file types not yet implemented (audio/video/archives/...)."""
