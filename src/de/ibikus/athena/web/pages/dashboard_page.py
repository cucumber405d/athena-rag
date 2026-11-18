"""Web UI 2 — Vector Store Dashboard."""

from __future__ import annotations

import json
import time
from pathlib import Path

import gradio as gr
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure

from de.ibikus.athena.core.models.ingestion_job import IngestionReport
from de.ibikus.athena.web.observability import metrics as m
from de.ibikus.athena.web.observability.context import request_context
from de.ibikus.athena.web.observability.logging import get_logger
from de.ibikus.athena.web.pages.common import collection_dropdown_update
from de.ibikus.athena.web.services import AppServices

log = get_logger("de.ibikus.athena.web.dashboard")

_SAMPLE_LIMIT = 30
_SAMPLE_FETCH_CAP = 2000


def _load_recent_reports(reports_dir: Path, limit: int = 20) -> list[IngestionReport]:
    if not reports_dir.exists():
        return []
    reports = []
    for path in reports_dir.glob("*.json"):
        try:
            reports.append(IngestionReport(**json.loads(path.read_text(encoding="utf-8"))))
        except Exception:  # noqa: BLE001
            continue
    reports.sort(key=lambda r: r.started_at, reverse=True)
    return reports[:limit]


def _dir_size_bytes(path: Path) -> int | None:
    if not path.exists():
        return None
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


# Fixed categorical order (blue, green, red, violet, orange), validated with
# scripts/validate_palette.js against the white chart surface: CVD-safe adjacent
# spacing (worst ΔE 13.3) and >=3:1 contrast on every slot. Cycled by bar
# position, not randomized per render, so a category keeps its color on refresh.
_BAR_COLORS = ["#2a78d6", "#008300", "#e34948", "#4a3aa7", "#eb6834"]


def _dist_figure(dist: dict[str, int], label_col: str) -> Figure:
    # Rendered server-side with matplotlib instead of gr.BarPlot (Vega-Lite): the native
    # Gradio bar plot silently fails to draw the bar mark for nominal x-axes in this
    # gradio version (axes/legend render, the bar itself doesn't) — a known upstream issue.
    fig, ax = plt.subplots(figsize=(4, 3))
    if dist:
        colors = [_BAR_COLORS[i % len(_BAR_COLORS)] for i in range(len(dist))]
        ax.bar(list(dist.keys()), list(dist.values()), color=colors)
    ax.set_xlabel(label_col)
    ax.set_ylabel("count")
    fig.tight_layout()
    plt.close(fig)
    return fig


def refresh_dashboard(services: AppServices, backend: str, collection: str):
    """Core logic behind the dashboard refresh — a module-level function so it can be
    unit-tested without going through Gradio's event wiring."""
    config = services.config
    with request_context(user_action="dashboard_load", vector_store=backend, collection_name=collection):
        started = time.perf_counter()
        try:
            vector_store = services.vector_store(backend)
            collection_names = vector_store.list_collections()
            collections_rows = []
            for name in collection_names:
                stats = vector_store.get_collection_stats(name)
                collections_rows.append(
                    [stats.collection_name, stats.backend, stats.document_count, stats.chunk_count, stats.vector_dimension]
                )
            collections_df = pd.DataFrame(
                collections_rows, columns=["collection", "backend", "documents", "chunks", "dimension"]
            )

            if not collection:
                empty_fig = _dist_figure({}, "")
                return (
                    backend, collections_df, "0", "0",
                    empty_fig, empty_fig, empty_fig,
                    pd.DataFrame(), pd.DataFrame(), "n/a", pd.DataFrame(),
                )

            stats = vector_store.get_collection_stats(collection)
            storage_size = None
            if backend == "chroma":
                storage_size = _dir_size_bytes(Path(config.vector_store.chroma.persist_dir))

            reports = _load_recent_reports(Path(config.app.reports_dir))
            reports_df = pd.DataFrame(
                [
                    [r.ingestion_job_id, r.started_at, r.domain_id, r.target_collection, r.files_processed, r.files_failed, r.chunks_created]
                    for r in reports
                ],
                columns=["job_id", "started_at", "domain", "collection", "files_ok", "files_failed", "chunks_created"],
            )
            failed_rows = [
                [r.ingestion_job_id, e.file_path, e.error_type, e.error_message]
                for r in reports
                for e in r.errors
            ]
            failed_df = pd.DataFrame(failed_rows, columns=["job_id", "file_path", "error_type", "error_message"])

            # Neither backend's scroll/get exposes a native "most recent" order, so pull a
            # bounded pool and sort client-side by created_at instead of showing insertion order.
            fetch_limit = min(stats.chunk_count, _SAMPLE_FETCH_CAP)
            samples = vector_store.sample_points(collection, limit=fetch_limit) if fetch_limit else []
            samples = sorted(samples, key=lambda s: s.metadata.created_at, reverse=True)[:_SAMPLE_LIMIT]
            samples_df = pd.DataFrame(
                [
                    [s.metadata.created_at, s.metadata.file_name, s.metadata.domain_id, s.metadata.document_type, s.text[:200]]
                    for s in samples
                ],
                columns=["created_at", "file_name", "domain", "document_type", "text"],
            )

            duration = time.perf_counter() - started
            log.info("dashboard_loaded", collection_name=collection, duration_ms=round(duration * 1000, 1))

            return (
                backend,
                collections_df,
                str(stats.document_count),
                str(stats.chunk_count),
                _dist_figure(stats.domains, "domain"),
                _dist_figure(stats.file_types, "file_type"),
                _dist_figure(stats.languages, "language"),
                reports_df,
                failed_df,
                f"{storage_size} bytes" if storage_size is not None else "n/a (Qdrant storage size not exposed)",
                samples_df,
            )
        except Exception as exc:  # noqa: BLE001
            log.error("dashboard_load_failed", error_type=type(exc).__name__, error_message=str(exc))
            m.web_errors_total.labels(route="/dashboard", method="LOAD", status="error").inc()
            empty = pd.DataFrame()
            empty_fig = _dist_figure({}, "")
            return backend, empty, "0", "0", empty_fig, empty_fig, empty_fig, empty, empty, "error", empty


def build_dashboard_page(services: AppServices) -> gr.Blocks:
    config = services.config

    def _list_collections(backend: str):
        return collection_dropdown_update(services, backend)

    def _refresh(backend: str, collection: str):
        return refresh_dashboard(services, backend, collection)

    with gr.Blocks(title="Athena — Dashboard") as page:
        gr.Markdown("## Vector Store Dashboard")
        with gr.Row():
            backend = gr.Dropdown(["qdrant", "chroma"], value=config.vector_store.backend, label="Active backend")
            collection = gr.Dropdown([], label="Collection")
            refresh = gr.Button("Refresh", variant="primary")

        collections_table = gr.Dataframe(label="Collections")
        with gr.Row():
            document_count = gr.Textbox(label="Number of documents", interactive=False)
            chunk_count = gr.Textbox(label="Number of chunks", interactive=False)
            storage_size = gr.Textbox(label="Storage size", interactive=False)

        with gr.Row():
            domains_chart = gr.Plot(label="Chunks by domain")
            file_types_chart = gr.Plot(label="Documents by file type")
            languages_chart = gr.Plot(label="Language distribution")

        gr.Markdown("### Latest ingestion jobs")
        reports_table = gr.Dataframe()
        gr.Markdown("### Failed files")
        failed_table = gr.Dataframe()
        gr.Markdown("### Sample chunks")
        samples_table = gr.Dataframe(max_height=400)
        gr.Markdown("_2D vector projection (UMAP/t-SNE): not implemented in this MVP — planned for V2._")

        backend.change(_list_collections, inputs=backend, outputs=collection)
        outputs = [
            backend, collections_table, document_count, chunk_count,
            domains_chart, file_types_chart, languages_chart,
            reports_table, failed_table, storage_size, samples_table,
        ]
        refresh.click(_list_collections, inputs=backend, outputs=collection).then(
            _refresh, inputs=[backend, collection], outputs=outputs
        )
        collection.change(_refresh, inputs=[backend, collection], outputs=outputs)
        page.load(_list_collections, inputs=backend, outputs=collection)

    return page
