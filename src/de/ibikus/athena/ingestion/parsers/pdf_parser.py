"""PDF parser: page-by-page text extraction, with an OCR fallback (pypdfium2
render + pytesseract) for pages that have no extractable text layer, i.e.
scanned PDFs. Text and scanned pages can be mixed within the same document.
"""

from __future__ import annotations

from pathlib import Path

from de.ibikus.athena.core.models.document import ExtractedPage

# Matches the platform's declared UI languages (de/en/ru, see _LANGUAGES in the web pages).
_OCR_LANGUAGES = "eng+deu+rus"
_OCR_RENDER_SCALE = 2.0  # ~144 DPI: enough for OCR accuracy without huge render times


def _ocr_render_pages(path: Path, page_indices: set[int]) -> dict[int, str]:
    if not page_indices:
        return {}
    try:
        import pypdfium2 as pdfium
        import pytesseract
    except Exception:
        # pypdfium2 / pytesseract / tesseract binary not available in this environment.
        return {}

    texts: dict[int, str] = {}
    try:
        pdf = pdfium.PdfDocument(str(path))
        try:
            for i in page_indices:
                try:
                    image = pdf[i].render(scale=_OCR_RENDER_SCALE).to_pil()
                    texts[i] = pytesseract.image_to_string(image, lang=_OCR_LANGUAGES)
                except Exception:
                    texts[i] = ""
        finally:
            pdf.close()
    except Exception:
        return {}
    return texts


def parse(path: Path) -> list[ExtractedPage]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    raw_texts = [page.extract_text() or "" for page in reader.pages]
    empty_indices = {i for i, text in enumerate(raw_texts) if not text.strip()}
    ocr_texts = _ocr_render_pages(path, empty_indices)

    return [ExtractedPage(page_number=i + 1, text=ocr_texts.get(i, text)) for i, text in enumerate(raw_texts)]
