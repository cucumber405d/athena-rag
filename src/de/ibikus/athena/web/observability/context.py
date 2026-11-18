"""MDC-like request context, built on structlog.contextvars.

Every log call inside a request automatically carries whatever is bound here
(see de.ibikus.athena.web.observability.logging, which adds `merge_contextvars` to the
processor chain) — the Python equivalent of Java's MDC.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from typing import Iterator

import structlog

CONTEXT_FIELDS = (
    "request_id",
    "trace_id",
    "session_id",
    "user_action",
    "domain_id",
    "collection_name",
    "vector_store",
    "retrieval_mode",
    "llm_target",
    "model",
    "retrieval_request_id",
    "generation_request_id",
)


def new_id() -> str:
    return uuid.uuid4().hex


@contextmanager
def request_context(**fields: str | None) -> Iterator[dict[str, str]]:
    """Bind MDC fields for the duration of the block, restoring the previous state after."""
    fields.setdefault("request_id", new_id())
    clean = {k: v for k, v in fields.items() if v is not None}
    tokens = structlog.contextvars.bind_contextvars(**clean)
    try:
        yield clean
    finally:
        structlog.contextvars.reset_contextvars(**tokens)


def bind(**fields: str | None) -> None:
    clean = {k: v for k, v in fields.items() if v is not None}
    structlog.contextvars.bind_contextvars(**clean)


def current_context() -> dict[str, str]:
    return dict(structlog.contextvars.get_contextvars())
