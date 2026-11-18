"""Loader for plain-text-like formats: txt, md, html, csv, json, xml, log.

Encoding is auto-detected (UTF-8, cp1251, cp866, koi8-r, ...) since source files
come from mixed tools/locales and are not guaranteed to be UTF-8. Format-aware
extraction (HTML tag stripping, CSV column awareness, ...) is a TODO for later
parser refinement.
"""

from __future__ import annotations

from pathlib import Path

from charset_normalizer import from_path


def load(path: Path) -> str:
    match = from_path(path).best()
    if match is None:
        return path.read_text(encoding="utf-8", errors="replace")
    return str(match)
