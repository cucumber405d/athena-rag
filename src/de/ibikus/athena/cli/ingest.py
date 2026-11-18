"""`athena ingest` — batch ingestion, reusing the same IngestionPipeline as the web UI."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from de.ibikus.athena.core.config.loader import load_config
from de.ibikus.athena.ingestion.pipeline import IngestionPipeline
from de.ibikus.athena.stores.docstore import DocStore
from de.ibikus.athena.stores.factory import build_vector_store_gateway
from de.ibikus.athena.stores.raw_file_store import RawFileStore

console = Console()


def run_ingest(
    path: Path,
    domain: str,
    collection: str | None = None,
    backend: str | None = None,
    chunking_profile: str | None = None,
    embedding_profile: str | None = None,
    dry_run: bool = False,
    tags: list[str] | None = None,
    document_type: str | None = None,
    language: str | None = None,
    access_level: str | None = None,
) -> None:
    config = load_config()
    vector_store = build_vector_store_gateway(config, backend)
    docstore = DocStore(Path(config.app.processed_dir) / "docstore.jsonl")
    raw_file_store = RawFileStore(Path(config.app.processed_dir))

    pipeline = IngestionPipeline(config, vector_store, docstore, raw_file_store)
    report = pipeline.run(
        path=path,
        domain_id=domain,
        collection_name=collection,
        chunking_profile_id=chunking_profile,
        embedding_profile_id=embedding_profile,
        dry_run=dry_run,
        tags=tags,
        document_type=document_type,
        language=language,
        access_level=access_level,
    )

    console.print(f"[bold]Ingestion job {report.ingestion_job_id}[/bold] ({'dry-run' if dry_run else 'live'})")
    console.print(f"  collection:      {report.target_collection}")
    console.print(f"  embedding:       {report.embedding_profile}")
    console.print(f"  files total:     {report.files_total}")
    console.print(f"  files processed: {report.files_processed}")
    console.print(f"  files skipped:   {report.files_skipped}")
    console.print(f"  files failed:    {report.files_failed}")
    console.print(f"  chunks created:  {report.chunks_created}")
    for warning in report.warnings:
        console.print(f"  [yellow]warning:[/yellow] {warning}")
    for error in report.errors:
        console.print(f"  [red]error:[/red] {error.file_path}: {error.error_type}: {error.error_message}")
