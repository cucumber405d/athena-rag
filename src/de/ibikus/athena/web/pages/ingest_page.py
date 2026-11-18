"""Web UI 3 — Data Management / Interactive Ingestion."""

from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path

import gradio as gr
import pandas as pd

from de.ibikus.athena.metadata.validators import ALLOWED_ACCESS_LEVELS
from de.ibikus.athena.stores.vector_gateway import SearchFilters
from de.ibikus.athena.web.observability import metrics as m
from de.ibikus.athena.web.observability.context import request_context
from de.ibikus.athena.web.observability.logging import get_logger
from de.ibikus.athena.web.pages.common import collection_dropdown_update
from de.ibikus.athena.web.services import AppServices

log = get_logger("de.ibikus.athena.web.ingest")

_LANGUAGES = ["", "de", "en", "ru", "mixed"]


def _stage_uploaded_files(files: list, domain: str) -> Path:
    staging_dir = Path(tempfile.mkdtemp(prefix=f"athena_upload_{domain}_"))
    for f in files:
        src = Path(f.name if hasattr(f, "name") else f)
        shutil.copy2(src, staging_dir / src.name)
    return staging_dir


def run_web_ingest(
    services: AppServices,
    files, domain, document_type, language, tags, access_level, chunking_profile, embedding_profile,
    backend, collection, dry_run,
):
    """Core logic behind Web UI 3's 'Add data' Run button — module-level for unit testing."""
    if not files:
        return "No files selected."
    with request_context(user_action="web_ingest", domain_id=domain, vector_store=backend, collection_name=collection or None):
        staging_dir = _stage_uploaded_files(files, domain)
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
        m.web_ingest_requests_total.labels(domain=domain, collection=collection or "default").inc()

        started = time.perf_counter()
        try:
            pipeline = services.ingestion_pipeline(backend)
            report = pipeline.run(
                path=staging_dir,
                domain_id=domain,
                collection_name=collection or None,
                chunking_profile_id=chunking_profile,
                embedding_profile_id=None if embedding_profile == "(auto)" else embedding_profile,
                dry_run=dry_run,
                tags=tag_list,
                document_type=document_type or None,
                language=language or None,
                access_level=access_level or None,
            )
            for f in files:
                from de.ibikus.athena.metadata.extractor import detect_file_type

                file_type = detect_file_type(Path(f.name if hasattr(f, "name") else f))
                m.web_ingest_files_uploaded_total.labels(domain=domain, file_type=file_type).inc()
        except Exception as exc:  # noqa: BLE001
            m.web_ingest_errors_total.labels(domain=domain, collection=collection or "default").inc()
            log.error("web_ingest_failed", error_type=type(exc).__name__, error_message=str(exc))
            return f"Ingestion failed: {exc}"
        finally:
            shutil.rmtree(staging_dir, ignore_errors=True)

        duration = time.perf_counter() - started
        log.info(
            "web_ingest_completed", dry_run=dry_run, files_total=report.files_total,
            chunks_created=report.chunks_created, duration_ms=round(duration * 1000, 1),
        )

        lines = [
            f"**{'Dry run preview' if dry_run else 'Ingestion complete'}** (job `{report.ingestion_job_id}`)",
            f"- Files found: {report.files_total}",
            f"- Supported / processed: {report.files_processed}",
            f"- Unsupported / skipped: {report.files_skipped}",
            f"- Failed: {report.files_failed}",
            f"- Estimated/created chunks: {report.chunks_created}",
            f"- Target vector store: {report.vector_store}",
            f"- Target collection: {report.target_collection}",
            f"- Domain: {report.domain_id}",
            f"- Embedding profile: {report.embedding_profile}",
        ]
        if report.warnings:
            lines.append("\n**Warnings:**")
            lines += [f"- {w}" for w in report.warnings]
        if report.errors:
            lines.append("\n**Errors:**")
            lines += [f"- {e.file_path}: {e.error_type}: {e.error_message}" for e in report.errors]
        return "\n".join(lines)


def _add_data_tab(services: AppServices):
    config = services.config
    domain_choices = config.domains.ids()
    chunking_choices = list(config.chunking_profiles.profiles.keys())
    embedding_choices = ["(auto)"] + list(config.embedding_profiles.profiles.keys())

    def _run(*args):
        return run_web_ingest(services, *args)

    def _on_backend_change(backend_value: str):
        return collection_dropdown_update(services, backend_value, select_first=False)

    with gr.Tab("Add data"):
        files = gr.File(file_count="multiple", label="Upload files")
        with gr.Row():
            domain = gr.Dropdown(domain_choices, value=domain_choices[0], label="Domain")
            document_type = gr.Textbox(label="Document type")
            language = gr.Dropdown(_LANGUAGES, value="", label="Language")
        with gr.Row():
            tags = gr.Textbox(label="Tags (comma-separated)")
            access_level = gr.Dropdown(sorted(ALLOWED_ACCESS_LEVELS), value="private", label="Access level")
        with gr.Row():
            chunking_profile = gr.Dropdown(chunking_choices, value=config.chunking_profiles.default_profile, label="Chunking profile")
            embedding_profile = gr.Dropdown(embedding_choices, value="(auto)", label="Embedding profile")
        with gr.Row():
            backend = gr.Dropdown(["qdrant", "chroma"], value=config.vector_store.backend, label="Vector store")
            collection = gr.Dropdown(
                [], value=None, allow_custom_value=True,
                label="Collection (optional — pick an existing one or type a new name)",
            )
        dry_run = gr.Checkbox(value=True, label="Dry run")
        run_button = gr.Button("Run", variant="primary")
        output = gr.Markdown()

        backend.change(_on_backend_change, inputs=backend, outputs=collection)

        run_button.click(
            _run,
            inputs=[files, domain, document_type, language, tags, access_level, chunking_profile, embedding_profile, backend, collection, dry_run],
            outputs=output,
        )

    return backend, collection


def search_documents(services: AppServices, domain: str, text: str) -> pd.DataFrame:
    docs = services.docstore.list_by_domain(None if domain == "all" else domain)
    if text:
        docs = [d for d in docs if text.lower() in d.file_name.lower()]
    rows = [
        [d.document_id, d.file_name, d.domain_id, d.document_type, d.language, ",".join(d.tags), d.access_level, d.deleted]
        for d in docs
    ]
    return pd.DataFrame(
        rows, columns=["document_id", "file_name", "domain", "document_type", "language", "tags", "access_level", "deleted"]
    )


def load_document_for_edit(services: AppServices, document_id: str):
    doc = services.docstore.get(document_id) if document_id else None
    if doc is None:
        return "all", "", "", "", "", False, "Document not found."
    return (
        doc.domain_id, doc.document_type or "", doc.language or "", ",".join(doc.tags), doc.access_level,
        doc.deleted, f"Loaded '{doc.file_name}' ({document_id}).",
    )


def save_document_metadata(
    services: AppServices, document_id: str, backend: str, collection: str, domain_id: str,
    document_type: str, language: str, tags: str, access_level: str, deleted: bool,
) -> str:
    if not document_id:
        return "No document selected."
    doc = services.docstore.get(document_id)
    if doc is None:
        return f"Document '{document_id}' not found."

    with request_context(user_action="web_metadata_update", domain_id=domain_id, collection_name=collection or None):
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        doc.domain_id, doc.document_type, doc.language = domain_id, document_type or None, language or None
        doc.tags, doc.access_level, doc.deleted = tag_list, access_level, deleted
        services.docstore.upsert(doc)

        vector_store = services.vector_store(backend)
        target_collection = collection or doc.collection_name
        chunks = vector_store.sample_points(
            target_collection, limit=10_000, filters=SearchFilters(document_id=document_id, deleted=None)
        )
        payload = {
            "domain_id": domain_id, "document_type": document_type or None, "language": language or None,
            "tags": tag_list, "access_level": access_level, "deleted": deleted,
        }
        for chunk in chunks:
            vector_store.update_payload(target_collection, chunk.chunk_id, payload)

        m.web_metadata_updates_total.labels(domain=domain_id, collection=target_collection).inc()
        log.info("metadata_updated", document_id=document_id, chunks_updated=len(chunks))
        return f"Updated metadata for {len(chunks)} chunk(s) of document '{document_id}'."


def delete_document(services: AppServices, document_id: str, backend: str, collection: str, hard: bool, confirm: bool) -> str:
    if not document_id:
        return "No document selected."
    doc = services.docstore.get(document_id)
    if doc is None:
        return f"Document '{document_id}' not found."
    if hard and not confirm:
        return "Hard delete requires the confirmation checkbox."

    with request_context(user_action="web_delete", domain_id=doc.domain_id, collection_name=collection or doc.collection_name):
        target_collection = collection or doc.collection_name
        vector_store = services.vector_store(backend)
        count = vector_store.delete_by_document_id(target_collection, document_id, hard=hard)
        services.docstore.delete(document_id, hard=hard)
        if hard:
            services.raw_file_store.delete(doc.domain_id, document_id)
            m.web_hard_deletes_total.labels(domain=doc.domain_id, collection=target_collection).inc()
        else:
            m.web_soft_deletes_total.labels(domain=doc.domain_id, collection=target_collection).inc()
        log.info("document_deleted", document_id=document_id, hard=hard, chunks_affected=count)
        return f"{'Hard' if hard else 'Soft'} deleted {count} chunk(s) of document '{document_id}'."


def _edit_and_delete_tab(services: AppServices):
    config = services.config
    domain_choices = ["all"] + config.domains.ids()

    def _search(domain, text):
        return search_documents(services, domain, text)

    def _load_for_edit(document_id):
        return load_document_for_edit(services, document_id)

    def _save_metadata(document_id, backend, collection, domain_id, document_type, language, tags, access_level, deleted):
        return save_document_metadata(
            services, document_id, backend, collection, domain_id, document_type, language, tags, access_level, deleted
        )

    def _delete(document_id, backend, collection, hard, confirm):
        return delete_document(services, document_id, backend, collection, hard, confirm)

    with gr.Tab("Search & edit metadata / Delete"):
        with gr.Row():
            search_domain = gr.Dropdown(domain_choices, value="all", label="Domain")
            search_text = gr.Textbox(label="File name contains")
            search_button = gr.Button("Search")
        results_table = gr.Dataframe(interactive=False)

        gr.Markdown("### Selected document")
        document_id = gr.Textbox(label="document_id (copy from the table above)")
        load_button = gr.Button("Load")

        with gr.Row():
            edit_domain = gr.Dropdown(config.domains.ids(), label="Domain")
            edit_document_type = gr.Textbox(label="Document type")
            edit_language = gr.Textbox(label="Language")
        with gr.Row():
            edit_tags = gr.Textbox(label="Tags (comma-separated)")
            edit_access_level = gr.Dropdown(sorted(ALLOWED_ACCESS_LEVELS), label="Access level")
            edit_deleted = gr.Checkbox(label="Deleted")
        with gr.Row():
            edit_backend = gr.Dropdown(["qdrant", "chroma"], value=config.vector_store.backend, label="Vector store")
            edit_collection = gr.Textbox(label="Collection (optional override)")
        save_button = gr.Button("Save metadata", variant="primary")
        status = gr.Markdown()

        gr.Markdown("### Delete")
        with gr.Row():
            hard_delete = gr.Checkbox(label="Hard delete (irreversible)")
            confirm_hard = gr.Checkbox(label="I understand hard delete permanently removes vectors/metadata")
            delete_button = gr.Button("Delete", variant="stop")
        delete_status = gr.Markdown()

        search_button.click(_search, inputs=[search_domain, search_text], outputs=results_table)
        load_button.click(
            _load_for_edit, inputs=document_id,
            outputs=[edit_domain, edit_document_type, edit_language, edit_tags, edit_access_level, edit_deleted, status],
        )
        save_button.click(
            _save_metadata,
            inputs=[document_id, edit_backend, edit_collection, edit_domain, edit_document_type, edit_language, edit_tags, edit_access_level, edit_deleted],
            outputs=status,
        )
        delete_button.click(
            _delete, inputs=[document_id, edit_backend, edit_collection, hard_delete, confirm_hard], outputs=delete_status
        )


def build_ingest_page(services: AppServices) -> gr.Blocks:
    with gr.Blocks(title="Athena — Data Management") as page:
        gr.Markdown("## Data Management / Interactive Ingestion")
        add_backend, add_collection = _add_data_tab(services)
        _edit_and_delete_tab(services)
        page.load(
            lambda backend_value: collection_dropdown_update(services, backend_value, select_first=False),
            inputs=add_backend,
            outputs=add_collection,
        )
    return page
