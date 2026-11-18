from __future__ import annotations

import de.ibikus.athena.ingestion.parsers.pdf_parser as pdf_parser_module


class _FakePage:
    def __init__(self, text: str):
        self._text = text

    def extract_text(self):
        return self._text


class _FakeReader:
    def __init__(self, _path):
        self.pages = [_FakePage("Real text on page 1"), _FakePage("   "), _FakePage("")]


def test_pdf_parser_ocr_fallback_only_for_pages_without_text(monkeypatch, tmp_path):
    monkeypatch.setattr("pypdf.PdfReader", _FakeReader)
    monkeypatch.setattr(
        pdf_parser_module, "_ocr_render_pages", lambda path, indices: {i: f"ocr-text-{i}" for i in indices}
    )

    pages = pdf_parser_module.parse(tmp_path / "fake.pdf")

    assert [p.page_number for p in pages] == [1, 2, 3]
    assert pages[0].text == "Real text on page 1"  # untouched, had a text layer
    assert pages[1].text == "ocr-text-1"  # whitespace-only counts as "no text"
    assert pages[2].text == "ocr-text-2"


def test_pdf_parser_falls_back_to_empty_text_when_ocr_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr("pypdf.PdfReader", _FakeReader)
    monkeypatch.setattr(pdf_parser_module, "_ocr_render_pages", lambda path, indices: {})

    pages = pdf_parser_module.parse(tmp_path / "fake.pdf")

    assert pages[0].text == "Real text on page 1"
    assert pages[1].text == "   "  # falls back to whatever pypdf originally extracted
    assert pages[2].text == ""
