from __future__ import annotations

from de.ibikus.athena.core.models.document import ExtractedPage
from de.ibikus.athena.ingestion.chunkers import page_aware_chunker, token_chunker

_MARKDOWN = """# Lebenslauf

## Profil

""" + ("Erfahrener Softwareentwickler. " * 40) + """

## Berufserfahrung

### Firma A

""" + ("Projektbeschreibung A. " * 40) + """

### Firma B

""" + ("Projektbeschreibung B. " * 40) + """

## Ausbildung

""" + ("Studium der Informatik. " * 20)


def test_token_chunker_markdown_splits_on_headings_not_word_count():
    pages = [ExtractedPage(page_number=None, text=_MARKDOWN)]
    pieces = token_chunker.chunk(pages, chunk_size=400, chunk_overlap=50, file_type="markdown")

    assert len(pieces) > 1
    assert all(len(p.text) <= 500 for p in pieces)  # capacity + small heading/merge slack
    # section headings should survive as their own boundary, not be split mid-word
    assert any("## Berufserfahrung" in p.text for p in pieces)


def test_token_chunker_plain_text_respects_capacity():
    long_text = "This is a sentence about Athena. " * 100
    pages = [ExtractedPage(page_number=None, text=long_text)]
    pieces = token_chunker.chunk(pages, chunk_size=500, chunk_overlap=50, file_type="text")

    assert len(pieces) > 1
    assert all(len(p.text) <= 600 for p in pieces)


def test_page_aware_chunker_preserves_page_number_and_splits_long_pages():
    pages = [
        ExtractedPage(page_number=1, text="Short first page."),
        ExtractedPage(page_number=2, text="A long second page. " * 100),
    ]
    pieces = page_aware_chunker.chunk(pages, chunk_size=500, chunk_overlap=50, file_type="pdf")

    assert pieces[0].page_number == 1
    assert all(p.page_number == 2 for p in pieces[1:])
    assert len(pieces) > 2  # the long page must have been split into more than one piece
