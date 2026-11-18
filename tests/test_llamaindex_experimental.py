"""Tests for the ALTERNATIVE / EXPERIMENTAL LlamaIndex pipeline
(de.ibikus.athena.experimental.llamaindex). Skipped entirely if the optional
`.[llamaindex]` extra is not installed — this path is never required by the
active Athena pipeline.
"""

from __future__ import annotations

from pathlib import Path

import pytest

llama_index = pytest.importorskip("llama_index.core")

from de.ibikus.athena.experimental.llamaindex.common import llamaindex_collection_name  # noqa: E402
from de.ibikus.athena.experimental.llamaindex.ingestion import ingest_directory_with_llamaindex  # noqa: E402
from de.ibikus.athena.experimental.llamaindex.retrieval import query_with_llamaindex  # noqa: E402


@pytest.fixture
def mock_embed_model(config):
    from llama_index.core.embeddings import MockEmbedding

    dimension = config.embedding_profiles.get("bge_m3_local").dimension
    return MockEmbedding(embed_dim=dimension)


def test_llamaindex_collection_name_is_namespaced():
    assert llamaindex_collection_name("athena_chunks_bge_m3_v1") == "athena_chunks_bge_m3_v1_llamaindex"
    # idempotent — doesn't double-suffix if already namespaced
    assert llamaindex_collection_name("athena_chunks_bge_m3_v1_llamaindex") == "athena_chunks_bge_m3_v1_llamaindex"


def test_llamaindex_ingestion_and_retrieval_end_to_end(tmp_path, config, mock_embed_model):
    raw_dir = tmp_path / "raw" / "tech"
    raw_dir.mkdir(parents=True)
    (raw_dir / ".athena.yaml").write_text("domain_id: tech\ntags:\n  - books\n", encoding="utf-8")
    (raw_dir / "note.md").write_text(
        "---\ndocument_type: article\ntags:\n  - ai\n  - rag\n---\n\n# Notes\n\nAthena supports hybrid search.\n",
        encoding="utf-8",
    )
    (raw_dir / "note.txt").write_text("Plain text about vector databases and BM25.", encoding="utf-8")
    (raw_dir / "unsupported.mp4").write_bytes(b"fake video bytes")

    summary = ingest_directory_with_llamaindex(
        config, raw_dir, domain_id="tech", backend="chroma", embed_model=mock_embed_model
    )

    assert summary["files_total"] == 3
    assert summary["files_indexed"] == 2
    assert summary["files_skipped"] == 1
    assert summary["collection_name"] == "athena_chunks_bge_m3_v1_llamaindex"

    results = query_with_llamaindex(
        config, "athena_chunks_bge_m3_v1", "chroma", "bge_m3_local", "hybrid search",
        top_k=5, embed_model=mock_embed_model,
    )
    assert len(results) == 2
    file_names = {r["metadata"]["file_name"] for r in results}
    assert file_names == {"note.md", "note.txt"}

    note_md_result = next(r for r in results if r["metadata"]["file_name"] == "note.md")
    assert "---" not in note_md_result["text"]  # front matter was stripped from the indexed text
    assert note_md_result["metadata"]["tags_csv"] == "ai,rag"  # front matter overrides folder sidecar


def test_llamaindex_collection_is_namespaced_away_from_production(tmp_path, config, mock_embed_model):
    """The experimental pipeline must never write into a collection name used
    by the production ChunkMetadata-based gateway."""
    from de.ibikus.athena.stores.chroma_adapter import ChromaVectorStoreAdapter

    raw_dir = tmp_path / "raw" / "tech"
    raw_dir.mkdir(parents=True)
    (raw_dir / "note.txt").write_text("Some content.", encoding="utf-8")

    summary = ingest_directory_with_llamaindex(
        config, raw_dir, domain_id="tech", backend="chroma", embed_model=mock_embed_model
    )

    vector_store = ChromaVectorStoreAdapter(persist_dir=config.vector_store.chroma.persist_dir)
    collections = vector_store.list_collections()
    assert "athena_chunks_bge_m3_v1" not in collections
    assert summary["collection_name"] in collections
