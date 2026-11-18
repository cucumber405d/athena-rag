"""Embedding service abstraction.

Two modes per spec section 13:
  - in-process (MVP default): sentence-transformers model loaded in this process.
  - external service (TODO v2): HTTP call to a TEI/Ollama/custom embedding endpoint,
    so athena-ingest/athena-web/athena-eval can share one embedding backend.

The embedding_profile used to build a collection is part of that collection's
index — see de.ibikus.athena.retrieval for the enforcement of "query profile == collection profile".
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from de.ibikus.athena.core.config.loader import EmbeddingProfile


class EmbeddingService(ABC):
    profile_id: str
    dimension: int

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]


class HuggingFaceEmbeddingService(EmbeddingService):
    """In-process embedding via sentence-transformers. Default profile: bge_m3_local."""

    def __init__(self, profile: EmbeddingProfile):
        from sentence_transformers import SentenceTransformer

        self.profile_id = profile.id
        self.dimension = profile.dimension
        self._normalize = profile.normalize
        self._model = SentenceTransformer(profile.model_name, device=profile.device)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, normalize_embeddings=self._normalize)
        return [v.tolist() for v in vectors]


class ExternalEmbeddingService(EmbeddingService):
    """Calls an external OpenAI-compatible/TEI/Ollama embedding endpoint.

    TODO(v2): implement HTTP client. Placeholder so the embedding_profile
    provider field (ollama/tei) has a defined extension point.
    """

    def __init__(self, profile: EmbeddingProfile):
        self.profile_id = profile.id
        self.dimension = profile.dimension
        self._profile = profile

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError(
            f"External embedding provider '{self._profile.provider}' is not implemented yet (v2)"
        )


def build_embedding_service(profile: EmbeddingProfile) -> EmbeddingService:
    if profile.provider == "huggingface":
        return HuggingFaceEmbeddingService(profile)
    return ExternalEmbeddingService(profile)
