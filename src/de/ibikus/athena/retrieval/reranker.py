"""Reranking on top of fused vector+BM25 results."""

from __future__ import annotations

from abc import ABC, abstractmethod

from de.ibikus.athena.core.config.loader import RerankerProfile
from de.ibikus.athena.core.models.retrieval import ScoredChunk


class Reranker(ABC):
    profile_id: str

    @abstractmethod
    def rerank(self, query: str, chunks: list[ScoredChunk], top_n: int) -> list[ScoredChunk]: ...


class NoneReranker(Reranker):
    profile_id = "none"

    def rerank(self, query: str, chunks: list[ScoredChunk], top_n: int) -> list[ScoredChunk]:
        return chunks[:top_n]


class CrossEncoderReranker(Reranker):
    """Local cross-encoder reranker, e.g. bge_reranker_local / qwen3_reranker_local."""

    def __init__(self, profile: RerankerProfile):
        from sentence_transformers import CrossEncoder

        self.profile_id = profile.id
        self._model = CrossEncoder(profile.model_name, device=profile.device)

    def rerank(self, query: str, chunks: list[ScoredChunk], top_n: int) -> list[ScoredChunk]:
        if not chunks:
            return []
        pairs = [(query, c.text) for c in chunks]
        scores = self._model.predict(pairs)
        reranked = sorted(zip(chunks, scores), key=lambda pair: pair[1], reverse=True)[:top_n]
        return [
            ScoredChunk(chunk_id=c.chunk_id, text=c.text, metadata=c.metadata, score=float(s), source="reranked")
            for c, s in reranked
        ]


def build_reranker(profile: RerankerProfile) -> Reranker:
    if profile.provider == "none":
        return NoneReranker()
    if profile.provider == "huggingface":
        return CrossEncoderReranker(profile)
    raise ValueError(f"Unknown reranker provider: {profile.provider}")
