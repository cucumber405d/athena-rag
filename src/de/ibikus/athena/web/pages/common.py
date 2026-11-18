"""Small helpers shared by the three Gradio pages."""

from __future__ import annotations

import gradio as gr

from de.ibikus.athena.web.services import AppServices


def collection_dropdown_update(services: AppServices, backend: str, select_first: bool = True):
    try:
        names = services.vector_store(backend).list_collections()
    except Exception:  # noqa: BLE001
        names = []
    value = (names[0] if names else None) if select_first else None
    return gr.update(choices=names, value=value)
