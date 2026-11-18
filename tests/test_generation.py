from __future__ import annotations

from de.ibikus.athena.generation.privacy_guard import (
    ALLOW_FRONTIER,
    ALLOW_FRONTIER_WITH_CONFIRMATION,
    LOCAL_ONLY,
    PrivacyGuard,
)


def test_local_target_always_allowed(config):
    guard = PrivacyGuard(LOCAL_ONLY, config.domains)
    local_target = config.llm_targets.get("local_lmstudio")
    decision = guard.check("job", local_target, external_confirmation=False)
    assert decision.allowed is True


def test_local_only_blocks_external(config):
    guard = PrivacyGuard(LOCAL_ONLY, config.domains)
    external_target = config.llm_targets.get("frontier_openai")
    decision = guard.check("job", external_target, external_confirmation=True)
    assert decision.allowed is False
    assert "LOCAL_ONLY" in decision.reason


def test_domain_without_frontier_requires_confirmation(config):
    guard = PrivacyGuard(ALLOW_FRONTIER, config.domains)
    external_target = config.llm_targets.get("frontier_openai")

    blocked = guard.check("job", external_target, external_confirmation=False)
    assert blocked.allowed is False

    allowed = guard.check("job", external_target, external_confirmation=True)
    assert allowed.allowed is True


def test_domain_with_frontier_allowed(config):
    guard = PrivacyGuard(ALLOW_FRONTIER, config.domains)
    external_target = config.llm_targets.get("frontier_openai")
    decision = guard.check("tech", external_target, external_confirmation=False)
    assert decision.allowed is True


def test_with_confirmation_mode_requires_checkbox(config):
    guard = PrivacyGuard(ALLOW_FRONTIER_WITH_CONFIRMATION, config.domains)
    external_target = config.llm_targets.get("frontier_openai")

    assert guard.check("tech", external_target, external_confirmation=False).allowed is False
    assert guard.check("tech", external_target, external_confirmation=True).allowed is True
