"""Image parser: OCR text extraction.

TODO(v2): image captioning model, optional image embedding (see spec 24.2).
"""

from __future__ import annotations

from de.ibikus.athena.core.models.document import ExtractedPage

# Matches the platform's declared UI languages (de/en/ru, see _LANGUAGES in the web pages).
_OCR_LANGUAGES = "eng+deu+rus"


def parse(image) -> list[ExtractedPage]:
    text = ""
    try:
        import pytesseract

        text = pytesseract.image_to_string(image, lang=_OCR_LANGUAGES)
    except Exception:
        # tesseract binary / pytesseract / language packs not available in this environment.
        text = ""
    return [ExtractedPage(page_number=None, text=text)]
