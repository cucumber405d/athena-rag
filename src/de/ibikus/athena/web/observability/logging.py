"""Structured JSON logging for the web application.

DO NOT log: full prompts, full retrieved context, API keys, raw chunk text,
or uploaded file contents. Safe derived values (lengths, counts, hashes) are fine.
"""

from __future__ import annotations

import hashlib
import logging
import sys

import structlog


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
            structlog.processors.EventRenamer("message"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str):
    return structlog.get_logger(name)


def short_hash(value: str, length: int = 12) -> str:
    """Safe stand-in for logging raw prompt/context text."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]
