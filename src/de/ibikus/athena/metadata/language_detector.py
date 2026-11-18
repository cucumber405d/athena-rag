"""Best-effort language detection from extracted document text.

Lowest-priority language source — sidecar/front-matter and an explicit
--language flag at ingest time both take precedence (see ingestion/pipeline.py).
"""

from __future__ import annotations

import py3langid as langid


def detect_language(text: str) -> str | None:
    if not text.strip():
        return None
    lang, _ = langid.classify(text)
    return lang
