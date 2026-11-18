"""multi_query mode: expand one query into several variants before retrieval.

Retrieval must stay independent from generation (spec section 18), so the
default expander is rule-based. A caller (e.g. the web layer) may inject an
LLM-backed `expand_fn` built on top of de.ibikus.athena.generation.llm_router if a
smarter rewrite is desired — this keeps the dependency direction one-way.
"""

from __future__ import annotations

import re
from typing import Callable

ExpandFn = Callable[[str], list[str]]

_STOPWORD_PREFIXES = ("find ", "search for ", "show me ", "look for ")


def default_expand(query: str) -> list[str]:
    variants = {query}

    stripped = query.strip()
    lowered = stripped.lower()
    for prefix in _STOPWORD_PREFIXES:
        if lowered.startswith(prefix):
            variants.add(stripped[len(prefix) :].strip())

    for connector in (" and ", " or "):
        if connector in lowered:
            for part in stripped.split(connector.strip()):
                part = part.strip(" ,")
                if part:
                    variants.add(part)

    keywords_only = re.sub(r"[^\w\s]", "", stripped)
    variants.add(keywords_only)

    return [v for v in variants if v]


class QueryExpander:
    def __init__(self, expand_fn: ExpandFn = default_expand, max_variants: int = 4):
        self._expand_fn = expand_fn
        self._max_variants = max_variants

    def expand(self, query: str) -> list[str]:
        variants = self._expand_fn(query)
        return variants[: self._max_variants] or [query]
