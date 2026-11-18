"""Loads and validates the YAML files under configs/ into typed Pydantic models."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from de.ibikus.athena.core.config.settings import CONFIG_DIR
from de.ibikus.athena.core.models.domain import DomainsConfig
from de.ibikus.athena.core.models.llm_target import LLMTargetConfig


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class AppConfig(BaseModel):
    name: str = "Athena"
    mode: str = "local"
    log_level: str = "INFO"
    privacy_mode: str = "LOCAL_ONLY"
    raw_data_dir: str = "./data/raw"
    processed_dir: str = "./data/processed"
    reports_dir: str = "./data/reports"
    observability: dict[str, Any] = {}


class EmbeddingProfile(BaseModel):
    id: str
    title: str
    provider: str
    model_name: str
    dimension: int = 1024
    device: str = "cpu"
    normalize: bool = True
    supports_multilingual: bool = False
    supports_sparse: bool = False
    supports_multivector: bool = False
    experimental: bool = False
    default_for_domains: list[str] = []


class EmbeddingProfilesConfig(BaseModel):
    profiles: dict[str, EmbeddingProfile]
    default_profile: str

    def get(self, profile_id: str) -> EmbeddingProfile:
        try:
            return self.profiles[profile_id]
        except KeyError as exc:
            raise ValueError(f"Unknown embedding profile: {profile_id}") from exc


class ChunkingProfile(BaseModel):
    id: str
    type: str
    chunk_size: int = 800
    chunk_overlap: int = 120
    window_seconds: int | None = None
    overlap_seconds: int | None = None
    keyframe_interval_seconds: int | None = None


class ChunkingProfilesConfig(BaseModel):
    profiles: dict[str, ChunkingProfile]
    default_profile: str

    def get(self, profile_id: str) -> ChunkingProfile:
        try:
            return self.profiles[profile_id]
        except KeyError as exc:
            raise ValueError(f"Unknown chunking profile: {profile_id}") from exc


class RerankerProfile(BaseModel):
    id: str
    title: str
    provider: str
    model_name: str | None = None
    device: str | None = None
    experimental: bool = False


class RerankerProfilesConfig(BaseModel):
    profiles: dict[str, RerankerProfile]
    default_profile: str = "none"

    def get(self, profile_id: str) -> RerankerProfile:
        try:
            return self.profiles[profile_id]
        except KeyError as exc:
            raise ValueError(f"Unknown reranker profile: {profile_id}") from exc


class QdrantConfig(BaseModel):
    url: str
    api_key_env: str | None = None
    default_collection: str


class ChromaConfig(BaseModel):
    persist_dir: str
    default_collection: str


class VectorStoreConfig(BaseModel):
    backend: str
    qdrant: QdrantConfig
    chroma: ChromaConfig


class LLMTargetsConfig(BaseModel):
    targets: dict[str, LLMTargetConfig]
    default_target: str

    def get(self, target_id: str) -> LLMTargetConfig:
        try:
            return self.targets[target_id]
        except KeyError as exc:
            raise ValueError(f"Unknown LLM target: {target_id}") from exc


class RetrievalDefaults(BaseModel):
    default_mode: str = "hybrid"
    vector_top_k: int = 30
    bm25_top_k: int = 30
    rerank_top_n: int = 8
    fusion: str = "rrf"
    filter_pushdown: bool = True


def load_app_config(config_dir: Path = CONFIG_DIR) -> AppConfig:
    raw = _read_yaml(config_dir / "app.yaml")
    app = raw.get("app", {})
    storage = raw.get("storage", {})
    return AppConfig(
        name=app.get("name", "Athena"),
        mode=app.get("mode", "local"),
        log_level=app.get("log_level", "INFO"),
        privacy_mode=app.get("privacy_mode", "LOCAL_ONLY"),
        raw_data_dir=storage.get("raw_data_dir", "./data/raw"),
        processed_dir=storage.get("processed_dir", "./data/processed"),
        reports_dir=storage.get("reports_dir", "./data/reports"),
        observability=raw.get("observability", {}),
    )


def load_domains_config(config_dir: Path = CONFIG_DIR) -> DomainsConfig:
    raw = _read_yaml(config_dir / "domains.yaml")
    return DomainsConfig(domains=raw.get("domains", []))


def load_embedding_profiles(config_dir: Path = CONFIG_DIR) -> EmbeddingProfilesConfig:
    raw = _read_yaml(config_dir / "embedding_profiles.yaml")
    profiles_raw = raw.get("embedding_profiles", {})
    profiles = {pid: EmbeddingProfile(id=pid, **cfg) for pid, cfg in profiles_raw.items()}
    return EmbeddingProfilesConfig(profiles=profiles, default_profile=raw["default_profile"])


def load_chunking_profiles(config_dir: Path = CONFIG_DIR) -> ChunkingProfilesConfig:
    raw = _read_yaml(config_dir / "chunking_profiles.yaml")
    profiles_raw = raw.get("chunking_profiles", {})
    profiles = {pid: ChunkingProfile(id=pid, **cfg) for pid, cfg in profiles_raw.items()}
    return ChunkingProfilesConfig(profiles=profiles, default_profile=raw["default_profile"])


def load_reranker_profiles(config_dir: Path = CONFIG_DIR) -> RerankerProfilesConfig:
    raw = _read_yaml(config_dir / "reranker_profiles.yaml")
    profiles_raw = raw.get("reranker_profiles", {})
    profiles = {pid: RerankerProfile(id=pid, **cfg) for pid, cfg in profiles_raw.items()}
    return RerankerProfilesConfig(profiles=profiles, default_profile=raw.get("default_profile", "none"))


def load_vector_store_config(config_dir: Path = CONFIG_DIR) -> VectorStoreConfig:
    raw = _read_yaml(config_dir / "vector_stores.yaml")
    vs = raw["vector_store"]
    return VectorStoreConfig(
        backend=vs["backend"],
        qdrant=QdrantConfig(**vs["qdrant"]),
        chroma=ChromaConfig(**vs["chroma"]),
    )


def load_llm_targets(config_dir: Path = CONFIG_DIR) -> LLMTargetsConfig:
    raw = _read_yaml(config_dir / "llm_targets.yaml")
    targets_raw = raw.get("llm_targets", {})
    targets = {tid: LLMTargetConfig(id=tid, **cfg) for tid, cfg in targets_raw.items()}
    return LLMTargetsConfig(targets=targets, default_target=raw["default_target"])


def load_retrieval_defaults(config_dir: Path = CONFIG_DIR) -> RetrievalDefaults:
    raw = _read_yaml(config_dir / "retrieval.yaml")
    return RetrievalDefaults(**raw.get("retrieval", {}))


class Config(BaseModel):
    """Aggregates all Athena configuration in one typed object."""

    app: AppConfig
    domains: DomainsConfig
    embedding_profiles: EmbeddingProfilesConfig
    chunking_profiles: ChunkingProfilesConfig
    reranker_profiles: RerankerProfilesConfig
    vector_store: VectorStoreConfig
    llm_targets: LLMTargetsConfig
    retrieval_defaults: RetrievalDefaults


@lru_cache(maxsize=1)
def load_config(config_dir: Path = CONFIG_DIR) -> Config:
    return Config(
        app=load_app_config(config_dir),
        domains=load_domains_config(config_dir),
        embedding_profiles=load_embedding_profiles(config_dir),
        chunking_profiles=load_chunking_profiles(config_dir),
        reranker_profiles=load_reranker_profiles(config_dir),
        vector_store=load_vector_store_config(config_dir),
        llm_targets=load_llm_targets(config_dir),
        retrieval_defaults=load_retrieval_defaults(config_dir),
    )
