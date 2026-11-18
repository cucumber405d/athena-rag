"""Context Builder + the RetrievalEngine that ties vector/bm25/hybrid/rerank/
multi_query modes together and produces the final ContextResult for generation.
"""

from __future__ import annotations

from de.ibikus.athena.core.config.loader import Config
from de.ibikus.athena.core.models.retrieval import ContextResult, RetrievalDiagnostics, RetrievalRequest, ScoredChunk
from de.ibikus.athena.ingestion.embeddings import EmbeddingService, build_embedding_service
from de.ibikus.athena.retrieval.bm25_retriever import BM25Retriever
from de.ibikus.athena.retrieval.hybrid_retriever import HybridRetriever, rrf_fuse
from de.ibikus.athena.retrieval.query_expander import QueryExpander
from de.ibikus.athena.retrieval.reranker import Reranker, build_reranker
from de.ibikus.athena.retrieval.vector_retriever import VectorRetriever
from de.ibikus.athena.stores.vector_gateway import SearchFilters, VectorStoreGateway

_CHARS_PER_TOKEN = 4


def dedup_chunks(chunks: list[ScoredChunk]) -> list[ScoredChunk]:
    seen: set[str] = set()
    result = []
    for chunk in chunks:
        if chunk.chunk_id in seen:
            continue
        seen.add(chunk.chunk_id)
        result.append(chunk)
    return result


def group_neighbors(chunks: list[ScoredChunk]) -> list[ScoredChunk]:
    """Merge chunks that are adjacent (same document, consecutive chunk_index),
    keeping the group's best score and the original relative ordering."""
    by_document: dict[str, list[ScoredChunk]] = {}
    order: list[str] = []
    for chunk in chunks:
        doc_id = chunk.metadata.document_id
        by_document.setdefault(doc_id, []).append(chunk)
        if doc_id not in order:
            order.append(doc_id)

    grouped: list[ScoredChunk] = []
    for doc_id in order:
        doc_chunks = sorted(by_document[doc_id], key=lambda c: c.metadata.chunk_index)
        current_group: list[ScoredChunk] = []
        for chunk in doc_chunks:
            if current_group and chunk.metadata.chunk_index == current_group[-1].metadata.chunk_index + 1:
                current_group.append(chunk)
            else:
                if current_group:
                    grouped.append(_merge_group(current_group))
                current_group = [chunk]
        if current_group:
            grouped.append(_merge_group(current_group))

    grouped.sort(key=lambda c: c.score, reverse=True)
    return grouped


def _merge_group(group: list[ScoredChunk]) -> ScoredChunk:
    if len(group) == 1:
        return group[0]
    merged_text = "\n".join(c.text for c in group)
    best = max(group, key=lambda c: c.score)
    return ScoredChunk(chunk_id=best.chunk_id, text=merged_text, metadata=best.metadata, score=best.score, source=best.source)


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // _CHARS_PER_TOKEN)


def build_context_text(chunks: list[ScoredChunk], max_context_tokens: int) -> tuple[str, list[ScoredChunk]]:
    selected: list[ScoredChunk] = []
    used_tokens = 0
    blocks: list[str] = []
    for i, chunk in enumerate(chunks, start=1):
        remaining = max_context_tokens - used_tokens
        if remaining <= 0:
            break
        text = chunk.text
        piece_tokens = estimate_tokens(text)
        if piece_tokens > remaining:
            text = text[: remaining * _CHARS_PER_TOKEN]
            piece_tokens = estimate_tokens(text)
        location = f" page={chunk.metadata.page_number}" if chunk.metadata.page_number else ""
        blocks.append(f"[{i}] source={chunk.metadata.file_name}{location} score={chunk.score:.2f}\n{text}")
        selected.append(chunk)
        used_tokens += piece_tokens
    return "\n\n".join(blocks), selected


class RetrievalEngine:
    """Runs a RetrievalRequest end to end: retrieve -> fuse -> rerank -> build context."""

    def __init__(self, config: Config, vector_store: VectorStoreGateway):
        self._config = config
        self._vector_store = vector_store
        self._embedding_services: dict[str, EmbeddingService] = {}
        self._rerankers: dict[str, Reranker] = {}
        self._query_expander = QueryExpander()

    def _embedding_service(self, profile_id: str) -> EmbeddingService:
        if profile_id not in self._embedding_services:
            profile = self._config.embedding_profiles.get(profile_id)
            self._embedding_services[profile_id] = build_embedding_service(profile)
        return self._embedding_services[profile_id]

    def _reranker(self, profile_id: str) -> Reranker:
        if profile_id not in self._rerankers:
            profile = self._config.reranker_profiles.get(profile_id)
            self._rerankers[profile_id] = build_reranker(profile)
        return self._rerankers[profile_id]

    def _check_embedding_profile_consistency(self, request: RetrievalRequest) -> None:
        """Rule: query embedding model must match the collection's index embedding profile."""
        sample = self._vector_store.sample_points(request.collection_name, limit=1)
        if not sample:
            return
        indexed_profile = sample[0].metadata.embedding_profile
        if indexed_profile != request.embedding_profile:
            raise ValueError(
                f"Collection '{request.collection_name}' was indexed with embedding profile "
                f"'{indexed_profile}', but the request specified '{request.embedding_profile}'. "
                "Create a new collection or reindex to use a different embedding model."
            )

    def _build_filters(self, request: RetrievalRequest) -> SearchFilters | None:
        if not request.use_filter_pushdown:
            return None
        filters = SearchFilters.from_dict(request.filters)
        if request.domain_id and not filters.domain_id:
            filters.domain_id = request.domain_id
        return filters

    def run(self, request: RetrievalRequest) -> ContextResult:
        self._check_embedding_profile_consistency(request)
        filters = self._build_filters(request)

        embedding_service = self._embedding_service(request.embedding_profile)
        vector_retriever = VectorRetriever(self._vector_store, embedding_service)
        bm25_retriever = BM25Retriever(self._vector_store)
        hybrid_retriever = HybridRetriever(vector_retriever, bm25_retriever)

        reranker_profile_id = request.reranker_profile or self._config.reranker_profiles.default_profile

        if request.retrieval_mode == "vector":
            chunks = vector_retriever.retrieve(request.query, request.collection_name, request.vector_top_k, filters)
        elif request.retrieval_mode == "bm25":
            chunks = bm25_retriever.retrieve(request.query, request.collection_name, request.bm25_top_k, filters)
        elif request.retrieval_mode in ("hybrid", "hybrid_with_rerank"):
            chunks = hybrid_retriever.retrieve(
                request.query, request.collection_name, request.vector_top_k, request.bm25_top_k, request.fusion, filters
            )
        elif request.retrieval_mode == "multi_query":
            variants = self._query_expander.expand(request.query)
            rankings = [
                hybrid_retriever.retrieve(
                    variant, request.collection_name, request.vector_top_k, request.bm25_top_k, request.fusion, filters
                )
                for variant in variants
            ]
            chunks = rrf_fuse(rankings)
        else:
            raise ValueError(f"Unknown retrieval_mode: {request.retrieval_mode}")

        if reranker_profile_id != "none":
            chunks = self._reranker(reranker_profile_id).rerank(request.query, chunks, request.rerank_top_n)

        chunks = dedup_chunks(chunks)
        chunks = group_neighbors(chunks)

        used_reranker = reranker_profile_id if reranker_profile_id != "none" else "none"
        context_text, final_chunks = build_context_text(chunks, max_context_tokens=request.max_context_tokens)

        diagnostics = RetrievalDiagnostics(
            vector_top_k=request.vector_top_k,
            bm25_top_k=request.bm25_top_k,
            fusion=request.fusion,
            retrieval_mode=request.retrieval_mode,
            reranker=used_reranker,
            final_chunks=len(final_chunks),
            filters_applied=filters.model_dump(exclude_defaults=True) if filters else {},
        )
        return ContextResult(context_text=context_text, chunks=final_chunks, diagnostics=diagnostics)
