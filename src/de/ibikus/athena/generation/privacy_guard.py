"""Privacy Guard: decides whether a generation request may leave the machine.

Precedence:
  1. Non-external targets (local / local_or_lan) are always allowed.
  2. Global privacy_mode == LOCAL_ONLY blocks every external target outright.
  3. A domain with frontier_allowed=False (job, personal, user by default)
     additionally requires explicit user confirmation, regardless of the
     global mode.
  4. Otherwise, ALLOW_FRONTIER_WITH_CONFIRMATION requires confirmation and
     ALLOW_FRONTIER allows unconditionally.
"""

from __future__ import annotations

from pydantic import BaseModel

from de.ibikus.athena.core.models.domain import DomainsConfig
from de.ibikus.athena.core.models.llm_target import LLMTargetConfig

LOCAL_ONLY = "LOCAL_ONLY"
ALLOW_FRONTIER_WITH_CONFIRMATION = "ALLOW_FRONTIER_WITH_CONFIRMATION"
ALLOW_FRONTIER = "ALLOW_FRONTIER"


class PrivacyDecision(BaseModel):
    allowed: bool
    reason: str | None = None
    requires_confirmation: bool = False


class PrivacyGuard:
    def __init__(self, privacy_mode: str, domains_config: DomainsConfig):
        self._privacy_mode = privacy_mode
        self._domains_config = domains_config

    def check(
        self, domain_id: str | None, llm_target: LLMTargetConfig, external_confirmation: bool
    ) -> PrivacyDecision:
        if llm_target.privacy_level != "external":
            return PrivacyDecision(allowed=True)

        if self._privacy_mode == LOCAL_ONLY:
            return PrivacyDecision(
                allowed=False, reason="Privacy mode is LOCAL_ONLY: external LLM targets are disabled."
            )

        domain = self._domains_config.get(domain_id) if domain_id else None
        domain_requires_confirmation = domain is not None and not domain.frontier_allowed

        if domain_requires_confirmation or self._privacy_mode == ALLOW_FRONTIER_WITH_CONFIRMATION:
            if not external_confirmation:
                reason = (
                    f"Domain '{domain_id}' does not allow frontier LLMs by default; explicit confirmation required."
                    if domain_requires_confirmation
                    else "This LLM target is external; explicit confirmation required."
                )
                return PrivacyDecision(allowed=False, reason=reason, requires_confirmation=True)
            return PrivacyDecision(allowed=True, requires_confirmation=True)

        return PrivacyDecision(allowed=True)
