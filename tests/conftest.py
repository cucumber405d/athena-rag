from __future__ import annotations

import hashlib

import pytest

from de.ibikus.athena.core.config.loader import load_config
from de.ibikus.athena.ingestion.embeddings import EmbeddingService


@pytest.fixture
def config(tmp_path):
    load_config.cache_clear()
    cfg = load_config()
    cfg.vector_store.chroma.persist_dir = str(tmp_path / "chroma")
    cfg.app.processed_dir = str(tmp_path / "processed")
    cfg.app.reports_dir = str(tmp_path / "reports")
    yield cfg
    load_config.cache_clear()


class FakeEmbeddingService(EmbeddingService):
    """Deterministic, dependency-free stand-in for sentence-transformers."""

    def __init__(self, profile):
        self.profile_id = profile.id
        self.dimension = profile.dimension

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            digest = hashlib.sha256(text.encode()).digest()
            vectors.append([digest[i % len(digest)] / 255.0 for i in range(self.dimension)])
        return vectors


@pytest.fixture
def fake_embedding_builder():
    return lambda profile: FakeEmbeddingService(profile)
