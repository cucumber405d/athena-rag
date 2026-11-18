from __future__ import annotations
from datetime import datetime, timezone

import de.ibikus.athena.retrieval.context_builder as context_builder_module
from de.ibikus.athena.core.models.chunk import ChunkMetadata
from de.ibikus.athena.core.models.retrieval import RetrievalRequest, ScoredChunk
from de.ibikus.athena.ingestion.pipeline import IngestionPipeline
from de.ibikus.athena.retrieval.context_builder import RetrievalEngine, build_context_text
from de.ibikus.athena.stores.chroma_adapter import ChromaVectorStoreAdapter
from de.ibikus.athena.stores.docstore import DocStore
from de.ibikus.athena.stores.raw_file_store import RawFileStore


def _chunk(chunk_id: str, text: str) -> ScoredChunk:
    now = datetime.now(timezone.utc)
    metadata = ChunkMetadata(
        chunk_id=chunk_id, document_id="doc1", source_id="doc1", domain_id="tech",
        collection_name="test_collection", file_name="note.txt", file_path="/tmp/note.txt",
        file_type="text", checksum="deadbeef", chunk_index=0, chunking_profile="default_text",
        embedding_profile="bge_m3_local", embedding_model="BAAI/bge-m3", embedding_dimension=3,
        created_at=now, updated_at=now,
    )
    return ScoredChunk(chunk_id=chunk_id, text=text, metadata=metadata, score=1.0)


def test_build_context_text_truncates_oversized_first_chunk():
    huge = _chunk("c1", "word " * 5000)  # ~6250 estimated tokens, well over the 4000 budget
    context_text, selected = build_context_text([huge], max_context_tokens=4000)
    assert len(selected) == 1
    # allow small overhead from the "[i] source=..." block header, which isn't counted in the budget
    assert context_builder_module.estimate_tokens(context_text) <= 4010


def test_build_context_text_respects_budget_across_chunks():
    chunks = [_chunk(f"c{i}", "word " * 1000) for i in range(5)]  # ~1250 tokens each
    context_text, selected = build_context_text(chunks, max_context_tokens=4000)
    assert len(selected) < len(chunks)
    assert context_builder_module.estimate_tokens(context_text) <= 4040


def test_retrieval_request_model_defaults():
    request = RetrievalRequest(
        query="test query", collection_name="athena_chunks_bge_m3_v1", vector_store="chroma", embedding_profile="bge_m3_local"
    )
    assert request.retrieval_mode == "hybrid"
    assert request.vector_top_k == 30
    assert request.bm25_top_k == 30
    assert request.rerank_top_n == 8
    assert request.use_filter_pushdown is True
    assert request.filters == {}


def test_retrieval_modes_end_to_end(tmp_path, config, fake_embedding_builder, monkeypatch):
    monkeypatch.setattr(context_builder_module, "build_embedding_service", lambda profile: fake_embedding_builder(profile))

    raw_dir = tmp_path / "raw" / "tech"
    raw_dir.mkdir(parents=True)
    (raw_dir / "note.txt").write_text("Athena supports hybrid search combining BM25 and vector retrieval.", encoding="utf-8")

    vector_store = ChromaVectorStoreAdapter(persist_dir=config.vector_store.chroma.persist_dir)
    docstore = DocStore(tmp_path / "docstore.jsonl")
    raw_file_store = RawFileStore(tmp_path / "processed")
    pipeline = IngestionPipeline(config, vector_store, docstore, raw_file_store, embedding_service_builder=fake_embedding_builder)
    report = pipeline.run(raw_dir, domain_id="tech")

    engine = RetrievalEngine(config, vector_store)
    for mode in ["vector", "bm25", "hybrid", "hybrid_with_rerank", "multi_query"]:
        request = RetrievalRequest(
            query="hybrid search vector retrieval",
            collection_name=report.target_collection,
            vector_store="chroma",
            retrieval_mode=mode,
            embedding_profile="bge_m3_local",
            reranker_profile="none",
        )
        result = engine.run(request)
        assert result.diagnostics.retrieval_mode == mode


def test_embedding_profile_mismatch_is_rejected(tmp_path, config, fake_embedding_builder, monkeypatch):
    monkeypatch.setattr(context_builder_module, "build_embedding_service", lambda profile: fake_embedding_builder(profile))

    raw_dir = tmp_path / "raw" / "tech"
    raw_dir.mkdir(parents=True)
    (raw_dir / "note.txt").write_text("Some content.", encoding="utf-8")

    vector_store = ChromaVectorStoreAdapter(persist_dir=config.vector_store.chroma.persist_dir)
    docstore = DocStore(tmp_path / "docstore.jsonl")
    raw_file_store = RawFileStore(tmp_path / "processed")
    pipeline = IngestionPipeline(config, vector_store, docstore, raw_file_store, embedding_service_builder=fake_embedding_builder)
    report = pipeline.run(raw_dir, domain_id="tech")

    engine = RetrievalEngine(config, vector_store)
    request = RetrievalRequest(
        query="test",
        collection_name=report.target_collection,
        vector_store="chroma",
        embedding_profile="qwen3_embedding_06b_local",  # different from the index's bge_m3_local
    )
    try:
        engine.run(request)
        assert False, "expected ValueError for embedding profile mismatch"
    except ValueError as exc:
        assert "bge_m3_local" in str(exc)
