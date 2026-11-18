"""The batch ingestion pipeline: Discover -> Load -> Extract -> Normalize ->
Metadata Enrichment -> Chunk -> Embed -> Upsert -> Verify -> Report.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import ftfy

from de.ibikus.athena.core.config.loader import Config
from de.ibikus.athena.core.models.chunk import Chunk, ChunkMetadata
from de.ibikus.athena.core.models.document import DocumentMetadata, ExtractedPage
from de.ibikus.athena.core.models.ingestion_job import IngestionError, IngestionReport
from de.ibikus.athena.ingestion import discovery
from de.ibikus.athena.ingestion.chunkers import page_aware_chunker, token_chunker
from de.ibikus.athena.ingestion.embeddings import EmbeddingService, build_embedding_service
from de.ibikus.athena.ingestion.loaders import docx_loader, image_loader, pdf_loader, text_loader, unsupported_loader
from de.ibikus.athena.ingestion.parsers import docx_parser, image_parser, pdf_parser, text_parser
from de.ibikus.athena.metadata.extractor import detect_file_type
from de.ibikus.athena.metadata.language_detector import detect_language
from de.ibikus.athena.metadata.sidecar import parse_markdown_front_matter, resolve_document_metadata
from de.ibikus.athena.metadata.validators import validate_access_level, validate_domain_id
from de.ibikus.athena.stores.docstore import DocStore
from de.ibikus.athena.stores.raw_file_store import RawFileStore
from de.ibikus.athena.stores.vector_gateway import VectorStoreGateway

# file_type -> (loader module, parser module | None). None means "not implemented yet".
_REGISTRY: dict[str, tuple[object, object | None]] = {
    "text": (text_loader, text_parser),
    "markdown": (text_loader, text_parser),
    "html": (text_loader, text_parser),
    "csv": (text_loader, text_parser),
    "json": (text_loader, text_parser),
    "xml": (text_loader, text_parser),
    "log": (text_loader, text_parser),
    "pdf": (pdf_loader, pdf_parser),
    "docx": (docx_loader, docx_parser),
    "image": (image_loader, image_parser),
    "pptx": (unsupported_loader, None),
    "xlsx": (unsupported_loader, None),
    "audio": (unsupported_loader, None),
    "video": (unsupported_loader, None),
    "archive": (unsupported_loader, None),
    "unknown": (unsupported_loader, None),
}

_CHUNKERS = {
    "token": token_chunker,
    "page_aware": page_aware_chunker,
}


def _is_supported(file_type: str) -> bool:
    _, parser = _REGISTRY.get(file_type, (unsupported_loader, None))
    return parser is not None


def _normalize_text(text: str) -> str:
    text = text.replace("\x00", "")
    text = ftfy.fix_text(text)  # mojibake repair + Unicode NFC normalization
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # de-hyphenate line-wrapped words (PDF/OCR artifact)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_pages(path: Path, file_type: str) -> tuple[list[ExtractedPage], dict]:
    loader, parser = _REGISTRY[file_type]
    loaded = loader.load(path)
    front_matter: dict = {}
    if file_type == "markdown":
        front_matter, body = parse_markdown_front_matter(loaded)
        loaded = body
    pages = parser.parse(loaded)
    normalized = [ExtractedPage(**{**p.model_dump(), "text": _normalize_text(p.text)}) for p in pages]
    return normalized, front_matter


def _pick_embedding_profile_id(config: Config, domain_id: str, override: str | None) -> str:
    if override:
        return override
    for profile in config.embedding_profiles.profiles.values():
        if domain_id in profile.default_for_domains:
            return profile.id
    return config.embedding_profiles.default_profile


def _write_report(report: IngestionReport, reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    json_path = reports_dir / f"{report.ingestion_job_id}.json"
    md_path = reports_dir / f"{report.ingestion_job_id}.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")

    lines = [
        f"# Ingestion report {report.ingestion_job_id}",
        "",
        f"- started_at: {report.started_at}",
        f"- finished_at: {report.finished_at}",
        f"- domain_id: {report.domain_id}",
        f"- target_collection: {report.target_collection}",
        f"- embedding_profile: {report.embedding_profile}",
        f"- vector_store: {report.vector_store}",
        f"- dry_run: {report.dry_run}",
        f"- files_total: {report.files_total}",
        f"- files_processed: {report.files_processed}",
        f"- files_skipped: {report.files_skipped}",
        f"- files_failed: {report.files_failed}",
        f"- chunks_created: {report.chunks_created}",
    ]
    if report.warnings:
        lines += ["", "## Warnings", *[f"- {w}" for w in report.warnings]]
    if report.errors:
        lines += ["", "## Errors", *[f"- {e.file_path}: {e.error_type}: {e.error_message}" for e in report.errors]]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class IngestionPipeline:
    def __init__(
        self,
        config: Config,
        vector_store: VectorStoreGateway,
        docstore: DocStore,
        raw_file_store: RawFileStore,
        embedding_service_builder=build_embedding_service,
    ):
        self._config = config
        self._vector_store = vector_store
        self._docstore = docstore
        self._raw_file_store = raw_file_store
        self._embedding_service_builder = embedding_service_builder
        self._embedding_services: dict[str, EmbeddingService] = {}

    def _embedding_service(self, profile_id: str) -> EmbeddingService:
        if profile_id not in self._embedding_services:
            profile = self._config.embedding_profiles.get(profile_id)
            self._embedding_services[profile_id] = self._embedding_service_builder(profile)
        return self._embedding_services[profile_id]

    def run(
        self,
        path: Path,
        domain_id: str,
        collection_name: str | None = None,
        chunking_profile_id: str | None = None,
        embedding_profile_id: str | None = None,
        dry_run: bool = False,
        access_level: str | None = None,
        tags: list[str] | None = None,
        document_type: str | None = None,
        language: str | None = None,
    ) -> IngestionReport:
        domain = self._config.domains.get(domain_id)
        if domain is None:
            raise ValueError(f"Unknown domain_id '{domain_id}'")

        collection_name = collection_name or domain.default_collection
        chunking_profile_id = chunking_profile_id or self._config.chunking_profiles.default_profile
        embedding_profile_id = _pick_embedding_profile_id(self._config, domain_id, embedding_profile_id)
        chunking_profile = self._config.chunking_profiles.get(chunking_profile_id)
        embedding_profile = self._config.embedding_profiles.get(embedding_profile_id)
        chunker = _CHUNKERS.get(chunking_profile.type)
        if chunker is None:
            raise ValueError(f"No chunker implemented for chunking type '{chunking_profile.type}'")

        started_at = datetime.now(timezone.utc)
        report = IngestionReport(
            ingestion_job_id=str(uuid.uuid4()),
            started_at=started_at,
            domain_id=domain_id,
            target_collection=collection_name,
            embedding_profile=embedding_profile_id,
            vector_store=self._vector_store.backend_name,
            dry_run=dry_run,
        )

        files = discovery.discover_files(path)
        report.files_total = len(files)

        if not dry_run:
            self._vector_store.create_collection(collection_name, embedding_profile.dimension)
        embedding_service = None if dry_run else self._embedding_service(embedding_profile_id)

        for file_path in files:
            file_type = detect_file_type(file_path)
            if not _is_supported(file_type):
                report.files_skipped += 1
                report.warnings.append(f"Unsupported file type '{file_type}': {file_path}")
                continue

            try:
                checksum = discovery.compute_checksum(file_path)
                document_id = f"doc_{checksum[:16]}"
                source_id = str(file_path)

                pages, front_matter = _extract_pages(file_path, file_type)

                resolved = resolve_document_metadata(file_path, domain_id, front_matter)
                resolved["domain_id"] = resolved.get("domain_id") or domain_id
                if document_type:
                    resolved["document_type"] = document_type
                if language:
                    resolved["language"] = language
                if tags:
                    resolved["tags"] = list({*resolved.get("tags", []), *tags})
                if access_level:
                    resolved["access_level"] = access_level
                if not resolved.get("language"):
                    resolved["language"] = detect_language("\n".join(p.text for p in pages)[:5000])

                validate_domain_id(resolved["domain_id"], self._config.domains)
                validate_access_level(resolved.get("access_level", "private"))

                now = datetime.now(timezone.utc)
                document_metadata = DocumentMetadata(
                    document_id=document_id,
                    source_id=source_id,
                    domain_id=resolved["domain_id"],
                    file_name=resolved["file_name"],
                    file_path=str(file_path),
                    file_type=resolved["file_type"],
                    mime_type=resolved.get("mime_type"),
                    checksum=checksum,
                    language=resolved.get("language"),
                    document_type=resolved.get("document_type"),
                    tags=resolved.get("tags", []),
                    access_level=resolved.get("access_level", "private"),
                    chunking_profile=chunking_profile_id,
                    embedding_profile=embedding_profile_id,
                    collection_name=collection_name,
                    created_at=now,
                    updated_at=now,
                )

                pieces = chunker.chunk(pages, chunking_profile.chunk_size, chunking_profile.chunk_overlap, file_type)

                if dry_run:
                    report.chunks_created += len(pieces)
                    report.files_processed += 1
                    continue

                texts = [p.text for p in pieces]
                vectors = embedding_service.embed_texts(texts) if texts else []

                chunks = [
                    Chunk(
                        text=piece.text,
                        vector=vector,
                        metadata=ChunkMetadata(
                            chunk_id=f"{document_id}_{piece.chunk_index}",
                            document_id=document_id,
                            source_id=source_id,
                            domain_id=document_metadata.domain_id,
                            collection_name=collection_name,
                            file_name=document_metadata.file_name,
                            file_path=document_metadata.file_path,
                            file_type=document_metadata.file_type,
                            mime_type=document_metadata.mime_type,
                            checksum=checksum,
                            language=document_metadata.language,
                            document_type=document_metadata.document_type,
                            tags=document_metadata.tags,
                            page_number=piece.page_number,
                            start_time_sec=piece.start_time_sec,
                            end_time_sec=piece.end_time_sec,
                            chunk_index=piece.chunk_index,
                            chunking_profile=chunking_profile_id,
                            embedding_profile=embedding_profile_id,
                            embedding_model=embedding_profile.model_name,
                            embedding_dimension=embedding_profile.dimension,
                            created_at=now,
                            updated_at=now,
                            access_level=document_metadata.access_level,
                        ),
                    )
                    for piece, vector in zip(pieces, vectors)
                ]

                if chunks:
                    self._vector_store.upsert_chunks(collection_name, chunks)
                self._docstore.upsert(document_metadata)
                self._raw_file_store.store(file_path, domain_id, document_id)

                report.files_processed += 1
                report.chunks_created += len(chunks)
            except Exception as exc:  # noqa: BLE001 - collect and continue, per-file isolation
                report.files_failed += 1
                report.errors.append(
                    IngestionError(file_path=str(file_path), error_type=type(exc).__name__, error_message=str(exc))
                )

        report.finished_at = datetime.now(timezone.utc)
        _write_report(report, Path(self._config.app.reports_dir))
        return report
