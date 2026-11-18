"""Document-level metadata store.

Per spec rule: raw files and document metadata must not live only inside the
vector database. For MVP this is a JSON-lines file on disk; a PostgreSQL
backend is a documented V2 upgrade with the same interface.
"""

from __future__ import annotations

import json
from pathlib import Path

from de.ibikus.athena.core.models.document import DocumentMetadata


class DocStore:
    def __init__(self, path: Path):
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.write_text("", encoding="utf-8")

    def _read_all(self) -> dict[str, DocumentMetadata]:
        records: dict[str, DocumentMetadata] = {}
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                records[data["document_id"]] = DocumentMetadata(**data)
        return records

    def _write_all(self, records: dict[str, DocumentMetadata]) -> None:
        with self._path.open("w", encoding="utf-8") as f:
            for doc in records.values():
                f.write(doc.model_dump_json() + "\n")

    def upsert(self, document: DocumentMetadata) -> None:
        records = self._read_all()
        records[document.document_id] = document
        self._write_all(records)

    def get(self, document_id: str) -> DocumentMetadata | None:
        return self._read_all().get(document_id)

    def delete(self, document_id: str, hard: bool = False) -> bool:
        records = self._read_all()
        doc = records.get(document_id)
        if doc is None:
            return False
        if hard:
            del records[document_id]
        else:
            doc.deleted = True
        self._write_all(records)
        return True

    def list_by_domain(self, domain_id: str | None = None) -> list[DocumentMetadata]:
        records = self._read_all().values()
        if domain_id is None:
            return list(records)
        return [d for d in records if d.domain_id == domain_id]

    def all(self) -> list[DocumentMetadata]:
        return list(self._read_all().values())
