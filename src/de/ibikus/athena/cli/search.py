"""`athena search` — retrieval only, reusing the same RetrievalEngine as the web UI."""

from __future__ import annotations

from rich.console import Console

from de.ibikus.athena.core.config.loader import load_config
from de.ibikus.athena.core.models.retrieval import RetrievalRequest
from de.ibikus.athena.retrieval.context_builder import RetrievalEngine
from de.ibikus.athena.stores.factory import build_vector_store_gateway

console = Console()


def run_search(
    query: str,
    domain: str | None = None,
    collection: str | None = None,
    backend: str | None = None,
    mode: str = "hybrid",
    top_k: int = 10,
    embedding_profile: str | None = None,
    reranker: str | None = None,
) -> None:
    config = load_config()
    backend = backend or config.vector_store.backend
    vector_store = build_vector_store_gateway(config, backend)

    if collection is None:
        domain_cfg = config.domains.get(domain) if domain else None
        collection = domain_cfg.default_collection if domain_cfg else config.vector_store.qdrant.default_collection
    if embedding_profile is None:
        embedding_profile = config.embedding_profiles.default_profile

    request = RetrievalRequest(
        query=query,
        domain_id=domain,
        collection_name=collection,
        vector_store=backend,
        retrieval_mode=mode,
        vector_top_k=top_k,
        bm25_top_k=top_k,
        rerank_top_n=min(top_k, 8),
        embedding_profile=embedding_profile,
        reranker_profile=reranker,
    )

    engine = RetrievalEngine(config, vector_store)
    result = engine.run(request)

    console.print(f"[bold]Query:[/bold] {query}  [dim]mode={mode} collection={collection}[/dim]")
    console.print(f"[dim]diagnostics: {result.diagnostics}[/dim]\n")
    for i, chunk in enumerate(result.chunks, start=1):
        console.print(f"[bold]{i}.[/bold] {chunk.metadata.file_name} (score={chunk.score:.3f})")
        console.print(f"   {chunk.text[:200]}")
