"""Raw file storage: keeps a copy of every ingested source file on local disk,
organized by domain/document_id. A MinIO/S3 backend is a documented V2 upgrade.
"""

from __future__ import annotations

import shutil
from pathlib import Path


class RawFileStore:
    def __init__(self, processed_dir: Path):
        self._root = processed_dir / "raw_files"

    def store(self, src_path: Path, domain_id: str, document_id: str) -> Path:
        target_dir = self._root / domain_id / document_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / src_path.name
        shutil.copy2(src_path, target_path)
        return target_path

    def get_path(self, domain_id: str, document_id: str, file_name: str) -> Path | None:
        candidate = self._root / domain_id / document_id / file_name
        return candidate if candidate.exists() else None

    def delete(self, domain_id: str, document_id: str) -> bool:
        target_dir = self._root / domain_id / document_id
        if not target_dir.exists():
            return False
        shutil.rmtree(target_dir)
        return True
