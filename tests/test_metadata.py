from __future__ import annotations

from datetime import datetime, timezone

import pytest

from de.ibikus.athena.core.models.chunk import ChunkMetadata
from de.ibikus.athena.metadata.sidecar import parse_markdown_front_matter, resolve_document_metadata
from de.ibikus.athena.metadata.validators import MetadataValidationError, validate_access_level, validate_domain_id


def test_sidecar_metadata_loading(tmp_path, config):
    folder = tmp_path / "books"
    folder.mkdir()
    (folder / ".athena.yaml").write_text(
        "domain_id: tech\nlanguage: en\ntags:\n  - books\naccess_level: private\n", encoding="utf-8"
    )
    (folder / "my_cv.pdf.athena.yaml").write_text(
        "domain_id: job\ndocument_type: cv\ntags:\n  - java\n", encoding="utf-8"
    )
    file_path = folder / "my_cv.pdf"
    file_path.write_bytes(b"%PDF-1.4 fake")

    resolved = resolve_document_metadata(file_path, default_domain_id="tech")

    # file-level sidecar overrides folder-level sidecar
    assert resolved["domain_id"] == "job"
    assert resolved["document_type"] == "cv"
    assert resolved["tags"] == ["java"]


def test_markdown_front_matter_priority(tmp_path):
    folder = tmp_path / "vacancies"
    folder.mkdir()
    (folder / ".athena.yaml").write_text("domain_id: tech\n", encoding="utf-8")
    md_text = (
        "---\ndomain_id: job\ndocument_type: vacancy\ntags:\n  - java\n  - spring\n---\n\n# Vacancy notes\n"
    )
    file_path = folder / "vacancy.md"
    file_path.write_text(md_text, encoding="utf-8")

    front_matter, body = parse_markdown_front_matter(md_text)
    assert front_matter["domain_id"] == "job"
    assert "Vacancy notes" in body

    resolved = resolve_document_metadata(file_path, default_domain_id="tech", markdown_front_matter=front_matter)
    assert resolved["domain_id"] == "job"
    assert resolved["document_type"] == "vacancy"


def test_chunk_metadata_model():
    now = datetime.now(timezone.utc)
    chunk = ChunkMetadata(
        chunk_id="doc1_0",
        document_id="doc1",
        source_id="doc1",
        domain_id="tech",
        collection_name="athena_chunks_bge_m3_v1",
        file_name="note.txt",
        file_path="/tmp/note.txt",
        file_type="text",
        checksum="abc123",
        chunk_index=0,
        chunking_profile="default_text",
        embedding_profile="bge_m3_local",
        embedding_model="BAAI/bge-m3",
        embedding_dimension=1024,
        created_at=now,
        updated_at=now,
    )
    assert chunk.tags == []
    assert chunk.deleted is False
    assert chunk.access_level == "private"


def test_validators(config):
    validate_domain_id("job", config.domains)
    with pytest.raises(MetadataValidationError):
        validate_domain_id("not_a_domain", config.domains)

    validate_access_level("private")
    with pytest.raises(MetadataValidationError):
        validate_access_level("super_secret")
