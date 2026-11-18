"""Automatic metadata detection from file path / extension.

This is the lowest-priority metadata source — sidecar files and markdown
front matter always override it (see de.ibikus.athena.metadata.sidecar).
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any

_DOCUMENT_TYPE_HINTS: dict[str, str] = {
    "cv": "cv",
    "lebenslauf": "cv",
    "resume": "cv",
    "vacancy": "vacancy",
    "stellenanzeige": "vacancy",
    "job_ad": "vacancy",
    "anschreiben": "cover_letter",
    "cover_letter": "cover_letter",
}

_FILE_TYPE_BY_SUFFIX: dict[str, str] = {
    ".txt": "text",
    ".md": "markdown",
    ".html": "html",
    ".csv": "csv",
    ".json": "json",
    ".xml": "xml",
    ".log": "log",
    ".pdf": "pdf",
    ".docx": "docx",
    ".pptx": "pptx",
    ".xlsx": "xlsx",
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
    ".webp": "image",
    ".tiff": "image",
    ".mp3": "audio",
    ".wav": "audio",
    ".m4a": "audio",
    ".ogg": "audio",
    ".mp4": "video",
    ".mkv": "video",
    ".mov": "video",
    ".avi": "video",
    ".zip": "archive",
    ".tar": "archive",
    ".gz": "archive",
}


def detect_file_type(file_path: Path) -> str:
    return _FILE_TYPE_BY_SUFFIX.get(file_path.suffix.lower(), "unknown")


def detect_mime_type(file_path: Path) -> str | None:
    mime_type, _ = mimetypes.guess_type(file_path.name)
    return mime_type


def guess_document_type(file_path: Path) -> str | None:
    stem = file_path.stem.lower()
    for hint, document_type in _DOCUMENT_TYPE_HINTS.items():
        if hint in stem:
            return document_type
    return None


def extract_auto_metadata(file_path: Path) -> dict[str, Any]:
    """Best-effort metadata guessed purely from the file name/extension."""
    return {
        "file_name": file_path.name,
        "file_type": detect_file_type(file_path),
        "mime_type": detect_mime_type(file_path),
        "document_type": guess_document_type(file_path),
        "language": None,
        "tags": [],
        "access_level": "private",
    }
