"""Shared core-service instances for the Gradio pages and the FastAPI actuator routes.

This module wires already-built core services together for the web layer; it
must never talk to Qdrant/Chroma/LLM providers directly (spec rule: no direct
backend calls from the UI layer).
"""

from __future__ import annotations

from pathlib import Path

from de.ibikus.athena.core.config.loader import Config, load_config
from de.ibikus.athena.generation.llm_router import LLMRouter
from de.ibikus.athena.generation.privacy_guard import PrivacyGuard
from de.ibikus.athena.ingestion.pipeline import IngestionPipeline
from de.ibikus.athena.retrieval.context_builder import RetrievalEngine
from de.ibikus.athena.stores.docstore import DocStore
from de.ibikus.athena.stores.factory import build_vector_store_gateway
from de.ibikus.athena.stores.raw_file_store import RawFileStore
from de.ibikus.athena.stores.vector_gateway import VectorStoreGateway


class AppServices:
    def __init__(self, config: Config | None = None):
        self.config = config or load_config()
        self._vector_stores: dict[str, VectorStoreGateway] = {}
        self._retrieval_engines: dict[str, RetrievalEngine] = {}
        self.privacy_guard = PrivacyGuard(self.config.app.privacy_mode, self.config.domains)
        self.llm_router = LLMRouter(self.config, self.privacy_guard)
        self.docstore = DocStore(Path(self.config.app.processed_dir) / "docstore.jsonl")
        self.raw_file_store = RawFileStore(Path(self.config.app.processed_dir))

    def vector_store(self, backend: str | None = None) -> VectorStoreGateway:
        backend = backend or self.config.vector_store.backend
        if backend not in self._vector_stores:
            self._vector_stores[backend] = build_vector_store_gateway(self.config, backend)
        return self._vector_stores[backend]

    def retrieval_engine(self, backend: str | None = None) -> RetrievalEngine:
        backend = backend or self.config.vector_store.backend
        if backend not in self._retrieval_engines:
            self._retrieval_engines[backend] = RetrievalEngine(self.config, self.vector_store(backend))
        return self._retrieval_engines[backend]

    def ingestion_pipeline(self, backend: str | None = None) -> IngestionPipeline:
        return IngestionPipeline(self.config, self.vector_store(backend), self.docstore, self.raw_file_store)


_services: AppServices | None = None


def get_services() -> AppServices:
    global _services
    if _services is None:
        _services = AppServices()
    return _services
