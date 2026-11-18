"""Sidecar metadata resolution.

Priority (highest wins): markdown front matter > per-file sidecar
(``<file>.athena.yaml``) > folder sidecar (``.athena.yaml``) > auto-detected
metadata.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

FOLDER_SIDECAR_NAME = ".athena.yaml"
FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?\n)---\s*\n?(.*)$", re.DOTALL)


def _load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def load_folder_sidecar(directory: Path) -> dict[str, Any]:
    """Load ``.athena.yaml`` from ``directory`` if present."""
    return _load_yaml_file(directory / FOLDER_SIDECAR_NAME)


def load_file_sidecar(file_path: Path) -> dict[str, Any]:
    """Load ``<file>.athena.yaml`` next to ``file_path`` if present."""
    sidecar_path = file_path.with_name(file_path.name + ".athena.yaml")
    return _load_yaml_file(sidecar_path)


def parse_markdown_front_matter(text: str) -> tuple[dict[str, Any], str]:
    """Split a markdown document into (front_matter_metadata, body)."""
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return {}, text
    front_matter_raw, body = match.groups()
    metadata = yaml.safe_load(front_matter_raw) or {}
    return metadata, body


def resolve_sidecar_metadata(file_path: Path, markdown_front_matter: dict[str, Any] | None = None) -> dict[str, Any]:
    """Merge folder sidecar, file sidecar and markdown front matter for a single file.

    Later sources override earlier ones.
    """
    merged: dict[str, Any] = {}
    merged.update(load_folder_sidecar(file_path.parent))
    merged.update(load_file_sidecar(file_path))
    if markdown_front_matter:
        merged.update(markdown_front_matter)
    return merged


def resolve_document_metadata(
    file_path: Path,
    default_domain_id: str,
    markdown_front_matter: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Full metadata resolution: auto-detected < folder sidecar < file sidecar < front matter."""
    from de.ibikus.athena.metadata.extractor import extract_auto_metadata

    resolved = extract_auto_metadata(file_path)
    resolved["domain_id"] = default_domain_id
    resolved.update(resolve_sidecar_metadata(file_path, markdown_front_matter))
    return resolved
