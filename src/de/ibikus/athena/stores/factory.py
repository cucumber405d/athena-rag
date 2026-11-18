"""Builds the configured VectorStoreGateway implementation."""

from __future__ import annotations

import os

from de.ibikus.athena.core.config.loader import Config
from de.ibikus.athena.stores.vector_gateway import VectorStoreGateway


def build_vector_store_gateway(config: Config, backend: str | None = None) -> VectorStoreGateway:
    backend = backend or config.vector_store.backend
    if backend == "qdrant":
        from de.ibikus.athena.stores.qdrant_adapter import QdrantVectorStoreAdapter

        qdrant_cfg = config.vector_store.qdrant
        api_key = os.environ.get(qdrant_cfg.api_key_env or "", None)
        return QdrantVectorStoreAdapter(url=qdrant_cfg.url, api_key=api_key)
    if backend == "chroma":
        from de.ibikus.athena.stores.chroma_adapter import ChromaVectorStoreAdapter

        return ChromaVectorStoreAdapter(persist_dir=config.vector_store.chroma.persist_dir)
    raise ValueError(f"Unknown vector store backend: {backend}")
