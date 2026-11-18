"""Parser interface: turns a loaded object into ExtractedPage objects."""

from __future__ import annotations

from typing import Any, Protocol

from de.ibikus.athena.core.models.document import ExtractedPage


class Parser(Protocol):
    def parse(self, loaded: Any) -> list[ExtractedPage]: ...
