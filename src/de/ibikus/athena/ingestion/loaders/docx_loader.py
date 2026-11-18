"""DOCX loader — returns a python-docx Document for the parser to walk."""

from __future__ import annotations

from pathlib import Path


def load(path: Path):
    import docx

    return docx.Document(str(path))
