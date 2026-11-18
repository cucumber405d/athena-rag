"""Placeholder loader for file types not yet implemented: pptx, xlsx, audio, video, archives.

TODO(v2): audio -> ASR transcript (whisper), video -> transcript + keyframes,
archives -> extract and re-run discovery on contents, pptx/xlsx -> structured extraction.
"""

from __future__ import annotations

from pathlib import Path

from de.ibikus.athena.ingestion.loaders.base import UnsupportedFileError


def load(path: Path):
    raise UnsupportedFileError(f"No loader implemented yet for file type of {path.name}")
