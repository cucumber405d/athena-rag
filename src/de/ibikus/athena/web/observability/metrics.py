"""Prometheus metrics for the Athena web application.

Labels are kept low-cardinality on purpose: never raw file names, prompts,
document IDs or chunk IDs — only route/backend/collection/domain/mode/model-class values.
"""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram, generate_latest

REGISTRY = CollectorRegistry(auto_describe=True)

web_requests_total = Counter(
    "athena_web_requests_total", "Web requests", ["route", "method", "status"], registry=REGISTRY
)
web_request_duration_seconds = Histogram(
    "athena_web_request_duration_seconds", "Web request duration", ["route", "method"], registry=REGISTRY
)
web_errors_total = Counter(
    "athena_web_errors_total", "Web errors", ["route", "method", "status"], registry=REGISTRY
)

retrieval_requests_total = Counter(
    "athena_retrieval_requests_total",
    "Retrieval requests",
    ["vector_store", "collection", "domain", "retrieval_mode", "reranker"],
    registry=REGISTRY,
)
retrieval_duration_seconds = Histogram(
    "athena_retrieval_duration_seconds",
    "Retrieval duration",
    ["vector_store", "collection", "domain", "retrieval_mode", "reranker"],
    registry=REGISTRY,
)
retrieval_chunks_returned = Histogram(
    "athena_retrieval_chunks_returned",
    "Chunks returned per retrieval request",
    ["vector_store", "collection", "domain", "retrieval_mode"],
    registry=REGISTRY,
)
retrieval_errors_total = Counter(
    "athena_retrieval_errors_total",
    "Retrieval errors",
    ["vector_store", "collection", "domain", "retrieval_mode"],
    registry=REGISTRY,
)

vector_search_requests_total = Counter(
    "athena_vector_search_requests_total", "Vector store operations", ["backend", "collection", "operation"], registry=REGISTRY
)
vector_search_duration_seconds = Histogram(
    "athena_vector_search_duration_seconds", "Vector store operation duration", ["backend", "collection", "operation"], registry=REGISTRY
)
vector_search_errors_total = Counter(
    "athena_vector_search_errors_total", "Vector store operation errors", ["backend", "collection", "operation"], registry=REGISTRY
)

generation_requests_total = Counter(
    "athena_generation_requests_total", "Generation requests", ["llm_target", "model", "privacy_level"], registry=REGISTRY
)
generation_duration_seconds = Histogram(
    "athena_generation_duration_seconds", "Generation duration", ["llm_target", "model", "privacy_level"], registry=REGISTRY
)
generation_errors_total = Counter(
    "athena_generation_errors_total", "Generation errors", ["llm_target", "model", "privacy_level"], registry=REGISTRY
)
generation_context_tokens = Histogram(
    "athena_generation_context_tokens", "Context tokens sent to the LLM", ["llm_target", "model"], registry=REGISTRY
)
generation_output_tokens = Histogram(
    "athena_generation_output_tokens", "Output tokens returned by the LLM", ["llm_target", "model"], registry=REGISTRY
)

external_llm_blocked_total = Counter(
    "athena_external_llm_blocked_total", "External LLM requests blocked by the Privacy Guard", ["domain", "llm_target", "privacy_mode"], registry=REGISTRY
)
external_llm_confirmed_total = Counter(
    "athena_external_llm_confirmed_total", "External LLM requests explicitly confirmed by the user", ["domain", "llm_target", "privacy_mode"], registry=REGISTRY
)

web_ingest_requests_total = Counter(
    "athena_web_ingest_requests_total", "Ingestion requests from Web UI 3", ["domain", "collection"], registry=REGISTRY
)
web_ingest_files_uploaded_total = Counter(
    "athena_web_ingest_files_uploaded_total", "Files uploaded via Web UI 3", ["domain", "file_type"], registry=REGISTRY
)
web_ingest_errors_total = Counter(
    "athena_web_ingest_errors_total", "Ingestion errors from Web UI 3", ["domain", "collection"], registry=REGISTRY
)
web_metadata_updates_total = Counter(
    "athena_web_metadata_updates_total", "Metadata edits from Web UI 3", ["domain", "collection"], registry=REGISTRY
)
web_soft_deletes_total = Counter(
    "athena_web_soft_deletes_total", "Soft deletes from Web UI 3", ["domain", "collection"], registry=REGISTRY
)
web_hard_deletes_total = Counter(
    "athena_web_hard_deletes_total", "Hard deletes from Web UI 3", ["domain", "collection"], registry=REGISTRY
)


def render_prometheus() -> tuple[bytes, str]:
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST


class RequestMetricsSummary:
    """Backing counters for the /actuator/metrics JSON summary (section 5.4)."""

    def __init__(self) -> None:
        self.requests_total = 0
        self.retrieval_requests_total = 0
        self.generation_requests_total = 0
        self.errors_total = 0
        self._retrieval_latency_sum = 0.0
        self._retrieval_latency_count = 0
        self._generation_latency_sum = 0.0
        self._generation_latency_count = 0

    def record_request(self, is_error: bool = False) -> None:
        self.requests_total += 1
        if is_error:
            self.errors_total += 1

    def record_retrieval(self, duration_seconds: float) -> None:
        self.retrieval_requests_total += 1
        self._retrieval_latency_sum += duration_seconds
        self._retrieval_latency_count += 1

    def record_generation(self, duration_seconds: float) -> None:
        self.generation_requests_total += 1
        self._generation_latency_sum += duration_seconds
        self._generation_latency_count += 1

    def as_dict(self) -> dict[str, float | int]:
        avg_retrieval_ms = (
            (self._retrieval_latency_sum / self._retrieval_latency_count) * 1000
            if self._retrieval_latency_count
            else 0.0
        )
        avg_generation_ms = (
            (self._generation_latency_sum / self._generation_latency_count) * 1000
            if self._generation_latency_count
            else 0.0
        )
        return {
            "requests_total": self.requests_total,
            "retrieval_requests_total": self.retrieval_requests_total,
            "generation_requests_total": self.generation_requests_total,
            "errors_total": self.errors_total,
            "avg_retrieval_latency_ms": round(avg_retrieval_ms, 2),
            "avg_generation_latency_ms": round(avg_generation_ms, 2),
        }


metrics_summary = RequestMetricsSummary()
