from __future__ import annotations

from de.ibikus.athena.core.models.document import ExtractedPage


def parse(document) -> list[ExtractedPage]:
    text = "\n".join(p.text for p in document.paragraphs if p.text.strip())
    return [ExtractedPage(page_number=None, text=text)]
