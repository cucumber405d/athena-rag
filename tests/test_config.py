from __future__ import annotations


def test_config_loading(config):
    assert config.app.name == "Athena"
    assert config.embedding_profiles.default_profile == "bge_m3_local"
    assert config.embedding_profiles.get("bge_m3_local").dimension == 1024
    assert config.llm_targets.default_target in config.llm_targets.targets
    assert config.chunking_profiles.default_profile in config.chunking_profiles.profiles
    assert config.reranker_profiles.default_profile == "none"


def test_domain_config(config):
    ids = config.domains.ids()
    assert {"job", "personal", "tech", "media", "user"} <= set(ids)

    job = config.domains.get("job")
    assert job.frontier_allowed is False
    tech = config.domains.get("tech")
    assert tech.frontier_allowed is True

    assert config.domains.get("does_not_exist") is None
