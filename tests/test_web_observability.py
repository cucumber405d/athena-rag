from __future__ import annotations

import structlog

from de.ibikus.athena.generation.privacy_guard import LOCAL_ONLY, PrivacyGuard
from de.ibikus.athena.web.observability import metrics as m
from de.ibikus.athena.web.observability.context import request_context
from de.ibikus.athena.web.observability.logging import configure_logging


def test_request_context_is_added_to_logs():
    configure_logging("INFO")
    captured: list[dict] = []

    def _capture_processor(logger, method_name, event_dict):
        captured.append(dict(event_dict))
        raise structlog.DropEvent

    structlog.configure(
        processors=[structlog.contextvars.merge_contextvars, _capture_processor],
        wrapper_class=structlog.make_filtering_bound_logger(20),
        logger_factory=structlog.PrintLoggerFactory(),
    )
    log = structlog.get_logger("test")

    with request_context(user_action="search_and_ask", domain_id="job"):
        log.info("something_happened")

    assert captured
    event = captured[-1]
    assert event["user_action"] == "search_and_ask"
    assert event["domain_id"] == "job"
    assert "request_id" in event

    # context must not leak outside the `with` block
    captured.clear()
    log.info("after_context")
    assert "user_action" not in captured[-1]

    configure_logging("INFO")  # restore default config for subsequent tests


def test_retrieval_metrics_increment():
    before = m.retrieval_requests_total.labels(
        vector_store="chroma", collection="c", domain="tech", retrieval_mode="hybrid", reranker="none"
    )._value.get()

    m.retrieval_requests_total.labels(
        vector_store="chroma", collection="c", domain="tech", retrieval_mode="hybrid", reranker="none"
    ).inc()
    after = m.retrieval_requests_total.labels(
        vector_store="chroma", collection="c", domain="tech", retrieval_mode="hybrid", reranker="none"
    )._value.get()
    assert after == before + 1


def test_generation_metrics_increment():
    before = m.generation_requests_total.labels(
        llm_target="local_lmstudio", model="qwen3:8b", privacy_level="local"
    )._value.get()
    m.generation_requests_total.labels(llm_target="local_lmstudio", model="qwen3:8b", privacy_level="local").inc()
    after = m.generation_requests_total.labels(
        llm_target="local_lmstudio", model="qwen3:8b", privacy_level="local"
    )._value.get()
    assert after == before + 1


def test_privacy_block_counter(config):
    guard = PrivacyGuard(LOCAL_ONLY, config.domains)
    external_target = config.llm_targets.get("frontier_openai")
    decision = guard.check("job", external_target, external_confirmation=False)
    assert not decision.allowed

    before = m.external_llm_blocked_total.labels(
        domain="job", llm_target="frontier_openai", privacy_mode=LOCAL_ONLY
    )._value.get()
    m.external_llm_blocked_total.labels(domain="job", llm_target="frontier_openai", privacy_mode=LOCAL_ONLY).inc()
    after = m.external_llm_blocked_total.labels(
        domain="job", llm_target="frontier_openai", privacy_mode=LOCAL_ONLY
    )._value.get()
    assert after == before + 1


def test_health_actuator_and_metrics_endpoints():
    from fastapi.testclient import TestClient

    from de.ibikus.athena.web.app import fastapi_app

    client = TestClient(fastapi_app)

    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "UP"}

    r = client.get("/actuator/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("UP", "DEGRADED")
    assert "vector_store" in body["components"]

    r = client.get("/actuator/info")
    assert r.status_code == 200
    assert r.json()["app"]["name"] == "Athena"

    r = client.get("/actuator/metrics")
    assert r.status_code == 200
    assert "requests_total" in r.json()

    r = client.get("/metrics")
    assert r.status_code == 200
    assert "athena_web_requests_total" in r.text
