"""Actuator-like health/info payload builders (business logic only — routes live in web/app.py)."""

from __future__ import annotations

import sys

from de.ibikus.athena.core.config.loader import Config
from de.ibikus.athena.stores.vector_gateway import VectorStoreGateway


def _vector_store_component(vector_store: VectorStoreGateway | None, backend: str) -> dict:
    if vector_store is None:
        return {"status": "DOWN", "backend": backend, "error": "not configured"}
    try:
        vector_store.list_collections()
        return {"status": "UP", "backend": backend}
    except Exception as exc:  # noqa: BLE001 - health check must never raise
        return {"status": "DEGRADED", "backend": backend, "error": str(exc)}


def build_actuator_health(config: Config, vector_store: VectorStoreGateway | None) -> dict:
    vector_component = _vector_store_component(vector_store, config.vector_store.backend)
    components = {
        "web": {"status": "UP"},
        "vector_store": vector_component,
        "embedding_profile": {"status": "UP", "active": config.embedding_profiles.default_profile},
        "llm_targets": {"status": "UP", "configured": list(config.llm_targets.targets.keys())},
    }
    overall = "UP"
    if any(c["status"] != "UP" for c in components.values()):
        overall = "DEGRADED"
    return {"status": overall, "components": components}


def build_actuator_info(config: Config, version: str) -> dict:
    return {
        "app": {"name": config.app.name, "version": version, "mode": config.app.mode},
        "python": sys.version.split()[0],
        "vector_store_backend": config.vector_store.backend,
        "default_collection": (
            config.vector_store.qdrant.default_collection
            if config.vector_store.backend == "qdrant"
            else config.vector_store.chroma.default_collection
        ),
        "default_embedding_profile": config.embedding_profiles.default_profile,
        "privacy_mode": config.app.privacy_mode,
    }
