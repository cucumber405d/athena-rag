from __future__ import annotations

from pathlib import Path

from de.ibikus.athena.ingestion.pipeline import IngestionPipeline, _normalize_text
from de.ibikus.athena.stores.chroma_adapter import ChromaVectorStoreAdapter
from de.ibikus.athena.stores.docstore import DocStore
from de.ibikus.athena.stores.raw_file_store import RawFileStore


def test_normalize_text_dehyphenates_line_wrapped_words():
    assert _normalize_text("This is infor-\nmation split across lines.") == "This is information split across lines."


def test_normalize_text_fixes_mojibake_and_nul_bytes():
    assert _normalize_text("CafÃ©\x00 latte") == "Café latte"


def _make_pipeline(config, tmp_path, fake_embedding_builder):
    vector_store = ChromaVectorStoreAdapter(persist_dir=config.vector_store.chroma.persist_dir)
    docstore = DocStore(tmp_path / "docstore.jsonl")
    raw_file_store = RawFileStore(tmp_path / "processed")
    return IngestionPipeline(config, vector_store, docstore, raw_file_store, embedding_service_builder=fake_embedding_builder)


def test_ingestion_pipeline_end_to_end(tmp_path, config, fake_embedding_builder):
    raw_dir = tmp_path / "raw" / "tech"
    raw_dir.mkdir(parents=True)
    (raw_dir / ".athena.yaml").write_text("domain_id: tech\ntags:\n  - books\n", encoding="utf-8")
    (raw_dir / "note.md").write_text(
        "---\ndocument_type: article\ntags:\n  - ai\n---\n\n# Notes\n\nAthena is a RAG platform.\n",
        encoding="utf-8",
    )
    (raw_dir / "note.txt").write_text("Plain text about vector databases and hybrid search.", encoding="utf-8")
    (raw_dir / "unsupported.mp4").write_bytes(b"fake video bytes")

    pipeline = _make_pipeline(config, tmp_path, fake_embedding_builder)
    report = pipeline.run(raw_dir, domain_id="tech")

    assert report.files_total == 3
    assert report.files_processed == 2
    assert report.files_skipped == 1
    assert report.files_failed == 0
    assert report.chunks_created >= 2
    assert report.target_collection == "athena_chunks_bge_m3_v1"

    reports_dir = Path(config.app.reports_dir)
    assert (reports_dir / f"{report.ingestion_job_id}.json").exists()
    assert (reports_dir / f"{report.ingestion_job_id}.md").exists()


def test_ingestion_dry_run_does_not_upsert(tmp_path, config, fake_embedding_builder):
    raw_dir = tmp_path / "raw" / "tech"
    raw_dir.mkdir(parents=True)
    (raw_dir / "note.txt").write_text("A short note.", encoding="utf-8")

    pipeline = _make_pipeline(config, tmp_path, fake_embedding_builder)
    report = pipeline.run(raw_dir, domain_id="tech", dry_run=True)

    assert report.dry_run is True
    assert report.files_processed == 1
    assert report.chunks_created >= 1

    # dry run must not create the collection or write any vectors
    assert report.target_collection not in pipeline._vector_store.list_collections()
