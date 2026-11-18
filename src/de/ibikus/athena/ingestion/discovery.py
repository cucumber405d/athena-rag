"""Discover stage: find candidate files under a root path and compute their checksum."""

from __future__ import annotations

import hashlib
from pathlib import Path

_IGNORED_DIR_NAMES = {"__pycache__", ".venv", ".git"}
_SIDECAR_SUFFIX = ".athena.yaml"


def discover_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]

    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in _IGNORED_DIR_NAMES for part in path.parts):
            continue
        if path.name.endswith(_SIDECAR_SUFFIX) or path.name == ".athena.yaml":
            continue
        files.append(path)
    return files


def compute_checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
