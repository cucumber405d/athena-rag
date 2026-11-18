"""Environment-backed settings (the equivalent of Spring's application.properties overrides)."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[6]
CONFIG_DIR = REPO_ROOT / "configs"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="ATHENA_", extra="ignore")

    log_level: str = "INFO"
    observability_enabled: bool = True
    prometheus_enabled: bool = True
    privacy_mode: str = "LOCAL_ONLY"

    config_dir: Path = CONFIG_DIR


def get_settings() -> Settings:
    return Settings()
