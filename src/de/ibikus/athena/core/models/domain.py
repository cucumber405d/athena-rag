"""Domain configuration models."""

from __future__ import annotations

from pydantic import BaseModel


class DomainConfig(BaseModel):
    """A single data domain (job, personal, tech, media, user, ...)."""

    id: str
    title: str
    description: str = ""
    default_access_level: str = "private"
    default_collection: str
    frontier_allowed: bool = False


class DomainsConfig(BaseModel):
    domains: list[DomainConfig]

    def get(self, domain_id: str) -> DomainConfig | None:
        return next((d for d in self.domains if d.id == domain_id), None)

    def ids(self) -> list[str]:
        return [d.id for d in self.domains]
