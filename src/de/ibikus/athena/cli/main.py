"""Athena CLI. Shares core services with the Gradio web app — no logic lives here."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from de.ibikus.athena.cli.ingest import run_ingest
from de.ibikus.athena.cli.search import run_search
from de.ibikus.athena.core.config.loader import load_config
from de.ibikus.athena.stores.factory import build_vector_store_gateway

app = typer.Typer(help="Athena — local-first scalable RAG platform")
console = Console()


@app.command()
def ingest(
    path: Path = typer.Option(..., "--path", help="File or directory to ingest"),
    domain: str = typer.Option(..., "--domain", help="Domain id (job, personal, tech, media, musik, books, user)"),
    collection: str | None = typer.Option(None, "--collection"),
    backend: str | None = typer.Option(None, "--backend", help="qdrant or chroma"),
    chunking_profile: str | None = typer.Option(None, "--chunking-profile"),
    embedding_profile: str | None = typer.Option(None, "--embedding-profile"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    tags: list[str] = typer.Option([], "--tag"),
    document_type: str | None = typer.Option(None, "--document-type"),
    language: str | None = typer.Option(None, "--language"),
    access_level: str | None = typer.Option(None, "--access-level"),
) -> None:
    """Batch-ingest a file or directory into a vector store collection."""
    run_ingest(
        path=path,
        domain=domain,
        collection=collection,
        backend=backend,
        chunking_profile=chunking_profile,
        embedding_profile=embedding_profile,
        dry_run=dry_run,
        tags=tags or None,
        document_type=document_type,
        language=language,
        access_level=access_level,
    )


@app.command()
def search(
    query: str = typer.Argument(...),
    domain: str | None = typer.Option(None, "--domain"),
    collection: str | None = typer.Option(None, "--collection"),
    backend: str | None = typer.Option(None, "--backend"),
    mode: str = typer.Option("hybrid", "--mode"),
    top_k: int = typer.Option(10, "--top-k"),
    embedding_profile: str | None = typer.Option(None, "--embedding-profile"),
    reranker: str | None = typer.Option(None, "--reranker"),
) -> None:
    """Run retrieval only (no generation) and print the resulting chunks."""
    run_search(
        query=query,
        domain=domain,
        collection=collection,
        backend=backend,
        mode=mode,
        top_k=top_k,
        embedding_profile=embedding_profile,
        reranker=reranker,
    )


@app.command()
def collections(backend: str | None = typer.Option(None, "--backend")) -> None:
    """List collections available in the configured (or given) vector store backend."""
    config = load_config()
    vector_store = build_vector_store_gateway(config, backend)
    table = Table(title=f"Collections ({vector_store.backend_name})")
    table.add_column("Name")
    for name in vector_store.list_collections():
        table.add_row(name)
    console.print(table)


@app.command()
def dashboard(backend: str | None = typer.Option(None, "--backend")) -> None:
    """Print a quick textual snapshot of every collection. For the full visual
    dashboard, run the Gradio web app instead (`python -m de.ibikus.athena.web.app`)."""
    config = load_config()
    vector_store = build_vector_store_gateway(config, backend)
    for name in vector_store.list_collections():
        stats = vector_store.get_collection_stats(name)
        console.print(f"\n[bold]{name}[/bold] ({stats.backend})")
        console.print(f"  documents: {stats.document_count}  chunks: {stats.chunk_count}  dim: {stats.vector_dimension}")
        console.print(f"  domains: {stats.domains}")
        console.print(f"  file_types: {stats.file_types}")
        console.print(f"  languages: {stats.languages}")


if __name__ == "__main__":
    app()
