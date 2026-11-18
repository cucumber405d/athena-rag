"""Validation helpers for resolved document/chunk metadata."""

from __future__ import annotations

from de.ibikus.athena.core.models.domain import DomainsConfig

ALLOWED_ACCESS_LEVELS = {"private", "internal", "public"}


class MetadataValidationError(ValueError):
    pass


def validate_domain_id(domain_id: str, domains_config: DomainsConfig) -> None:
    if domain_id not in domains_config.ids():
        raise MetadataValidationError(
            f"Unknown domain_id '{domain_id}'. Known domains: {domains_config.ids()}"
        )


def validate_access_level(access_level: str) -> None:
    if access_level not in ALLOWED_ACCESS_LEVELS:
        raise MetadataValidationError(
            f"Unknown access_level '{access_level}'. Allowed: {sorted(ALLOWED_ACCESS_LEVELS)}"
        )


def validate_required_fields(metadata: dict, required: list[str]) -> None:
    missing = [field for field in required if not metadata.get(field)]
    if missing:
        raise MetadataValidationError(f"Missing required metadata fields: {missing}")
