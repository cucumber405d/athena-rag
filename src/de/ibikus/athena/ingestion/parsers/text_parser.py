from __future__ import annotations

from de.ibikus.athena.core.models.document import ExtractedPage


def parse(loaded: str) -> list[ExtractedPage]:
    return [ExtractedPage(page_number=None, text=loaded)]
