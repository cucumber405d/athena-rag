"""Image loader — returns a PIL.Image for the parser (OCR / captioning)."""

from __future__ import annotations

from pathlib import Path


def load(path: Path):
    from PIL import Image

    return Image.open(path)
