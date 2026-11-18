from __future__ import annotations

from datetime import datetime, timezone

import pytest

from de.ibikus.athena.core.models.chunk import Chunk, ChunkMetadata
from de.ibikus.athena.stores.chroma_adapter import ChromaVectorStoreAdapter, _build_where
from de.ibikus.athena.stores.vector_gateway import SearchFilters, VectorStoreGateway


def _make_chunk(chunk_id: str, document_id: str, text: str, domain_id: str = "tech", deleted: bool = False) -> Chunk:
    now = datetime.now(timezone.utc)
    return Chunk(
        text=text,
        vector=[0.1, 0.2, 0.3],
        metadata=ChunkMetadata(
            chunk_id=chunk_id,
            document_id=document_id,
            source_id=document_id,
            domain_id=domain_id,
            collection_name="test_collection",
            file_name=f"{document_id}.txt",
            file_path=f"/tmp/{document_id}.txt",
            file_type="text",
            checksum="deadbeef",
            chunk_index=0,
            chunking_profile="default_text",
            embedding_profile="bge_m3_local",
            embedding_model="BAAI/bge-m3",
            embedding_dimension=3,
            created_at=now,
            updated_at=now,
            deleted=deleted,
        ),
    )


def test_filter_building():
    filters = SearchFilters(domain_id="job", document_type="cv", tags=["java", "ai"], deleted=False)
    where = _build_where(filters)
    assert where["$and"] == [{"domain_id": "job"}, {"document_type": "cv"}, {"deleted": False}]

    single = _build_where(SearchFilters(domain_id="job", deleted=None))
    assert single == {"domain_id": "job"}

    assert _build_where(SearchFilters(deleted=None)) is None


def test_vector_gateway_interface(tmp_path):
    adapter = ChromaVectorStoreAdapter(persist_dir=str(tmp_path / "chroma"))
    assert isinstance(adapter, VectorStoreGateway)

    adapter.create_collection("test_collection", embedding_dimension=3)
    adapter.upsert_chunks("test_collection", [_make_chunk("c1", "doc1", "hello world")])

    results = adapter.search_vector("test_collection", [0.1, 0.2, 0.3], top_k=5)
    assert len(results) == 1
    assert results[0].metadata.document_id == "doc1"

    stats = adapter.get_collection_stats("test_collection")
    assert stats.chunk_count == 1
    assert stats.domains == {"tech": 1}


def test_soft_delete_filter(tmp_path):
    adapter = ChromaVectorStoreAdapter(persist_dir=str(tmp_path / "chroma"))
    adapter.create_collection("test_collection", embedding_dimension=3)
    adapter.upsert_chunks(
        "test_collection",
        [_make_chunk("c1", "doc1", "hello world"), _make_chunk("c2", "doc2", "another chunk")],
    )

    deleted_count = adapter.delete_by_document_id("test_collection", "doc1", hard=False)
    assert deleted_count == 1

    active_only = adapter.search_vector(
        "test_collection", [0.1, 0.2, 0.3], top_k=5, filters=SearchFilters(deleted=False)
    )
    assert {c.metadata.document_id for c in active_only} == {"doc2"}

    including_deleted = adapter.sample_points("test_collection", limit=10, filters=SearchFilters(deleted=None))
    assert {c.metadata.document_id for c in including_deleted} == {"doc1", "doc2"}
    deleted_chunk = next(c for c in including_deleted if c.metadata.document_id == "doc1")
    assert deleted_chunk.metadata.deleted is True
