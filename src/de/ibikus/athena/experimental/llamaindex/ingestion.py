"""ALTERNATIVE / EXPERIMENTAL — NOT WIRED IN.

A LlamaIndex-based stand-in for `de.ibikus.athena.ingestion.pipeline.IngestionPipeline`.
Reuses Athena's discovery/metadata-resolution logic (domains, sidecar files,
markdown front matter, chunking/embedding profile config) but delegates
loading, node parsing, embedding and indexing to LlamaIndex instead of the
hand-rolled loaders/parsers/chunkers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from de.ibikus.athena.core.config.loader import Config
from de.ibikus.athena.experimental.llamaindex.common import (
    SUPPORTED_FILE_TYPES,
    build_embed_model,
    build_vector_store,
    llamaindex_collection_name,
)
from de.ibikus.athena.ingestion import discovery
from de.ibikus.athena.metadata.extractor import detect_file_type
from de.ibikus.athena.metadata.sidecar import parse_markdown_front_matter, resolve_document_metadata
from de.ibikus.athena.metadata.validators import validate_access_level, validate_domain_id


def ingest_directory_with_llamaindex(
    config: Config,
    path: Path,
    domain_id: str,
    collection_name: str | None = None,
    backend: str = "chroma",
    chunking_profile_id: str | None = None,
    embedding_profile_id: str | None = None,
    embed_model=None,
) -> dict:
    """Discover + load + chunk + embed + index a directory via LlamaIndex.

    Returns a plain summary dict (not an IngestionReport — this path is not
    wired into the athena.web dashboard/report machinery).
    """
    from llama_index.core import Document, StorageContext, VectorStoreIndex
    from llama_index.core.node_parser import SentenceSplitter

    domain = config.domains.get(domain_id)
    if domain is None:
        raise ValueError(f"Unknown domain_id '{domain_id}'")

    base_collection_name = collection_name or domain.default_collection
    target_collection = llamaindex_collection_name(base_collection_name)
    chunking_profile = config.chunking_profiles.get(chunking_profile_id or config.chunking_profiles.default_profile)
    embedding_profile = config.embedding_profiles.get(embedding_profile_id or config.embedding_profiles.default_profile)
    embed_model = embed_model or build_embed_model(embedding_profile)

    all_files = discovery.discover_files(path)
    supported_files = [f for f in all_files if detect_file_type(f) in SUPPORTED_FILE_TYPES]
    skipped = len(all_files) - len(supported_files)

    documents: list = []
    for file_path in supported_files:
        checksum = discovery.compute_checksum(file_path)
        file_type = detect_file_type(file_path)

        front_matter: dict = {}
        if file_type == "markdown":
            raw_text = file_path.read_text(encoding="utf-8", errors="replace")
            front_matter, text = parse_markdown_front_matter(raw_text)
        elif file_type == "text":
            text = file_path.read_text(encoding="utf-8", errors="replace")
        else:
            # PDF/DOCX: delegate to LlamaIndex's own file readers.
            from llama_index.core import SimpleDirectoryReader

            loaded = SimpleDirectoryReader(input_files=[str(file_path)]).load_data()
            text = "\n\n".join(d.text for d in loaded)

        resolved = resolve_document_metadata(file_path, domain_id, markdown_front_matter=front_matter)
        resolved["domain_id"] = resolved.get("domain_id") or domain_id
        validate_domain_id(resolved["domain_id"], config.domains)
        validate_access_level(resolved.get("access_level", "private"))

        now = datetime.now(timezone.utc).isoformat()
        documents.append(
            Document(
                text=text,
                doc_id=f"doc_{checksum[:16]}",
                metadata={
                    "document_id": f"doc_{checksum[:16]}",
                    "domain_id": resolved["domain_id"],
                    "collection_name": target_collection,
                    "file_name": resolved["file_name"],
                    "file_path": str(file_path),
                    "file_type": file_type,
                    "checksum": checksum,
                    "language": resolved.get("language"),
                    "document_type": resolved.get("document_type"),
                    # Chroma/Qdrant metadata values must be scalar — see
                    # de.ibikus.athena.stores.chroma_adapter's tags_csv convention.
                    "tags_csv": ",".join(resolved.get("tags", [])),
                    "access_level": resolved.get("access_level", "private"),
                    "chunking_profile": chunking_profile.id,
                    "embedding_profile": embedding_profile.id,
                    "indexed_at": now,
                },
            )
        )

    vector_store = build_vector_store(config, backend, target_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    node_parser = SentenceSplitter(chunk_size=chunking_profile.chunk_size, chunk_overlap=chunking_profile.chunk_overlap)

    if documents:
        VectorStoreIndex.from_documents(
            documents,
            storage_context=storage_context,
            embed_model=embed_model,
            transformations=[node_parser],
        )

    return {
        "backend": backend,
        "collection_name": target_collection,
        "domain_id": domain_id,
        "embedding_profile": embedding_profile.id,
        "chunking_profile": chunking_profile.id,
        "files_total": len(all_files),
        "files_indexed": len(documents),
        "files_skipped": skipped,
    }
