"""Web UI 1 — Search & Ask."""

from __future__ import annotations

import time
from pathlib import Path

import gradio as gr

from de.ibikus.athena.core.models.llm_target import GenerationRequest
from de.ibikus.athena.core.models.retrieval import RetrievalRequest
from de.ibikus.athena.metadata.extractor import detect_file_type
from de.ibikus.athena.web.observability import metrics as m
from de.ibikus.athena.web.observability.context import request_context
from de.ibikus.athena.web.observability.logging import get_logger, short_hash
from de.ibikus.athena.web.pages.common import collection_dropdown_update
from de.ibikus.athena.web.services import AppServices

log = get_logger("de.ibikus.athena.web.search")

_LANGUAGES = ["auto", "de", "en", "ru", "mixed"]
_SEARCH_MODES = ["vector", "bm25", "hybrid", "hybrid_with_rerank", "multi_query"]
_FUSIONS = ["rrf", "relative_score", "weighted"]
_ACTIONS = ["Search only", "Search + Ask selected LLM", "Compare local vs frontier"]


def _extract_upload_context(file_path: str | None, max_chars: int = 2000) -> str:
    if not file_path:
        return ""
    path = Path(file_path)
    file_type = detect_file_type(path)
    try:
        from de.ibikus.athena.ingestion.pipeline import _REGISTRY, _extract_pages

        if file_type not in _REGISTRY or _REGISTRY[file_type][1] is None:
            return f"[Attachment '{path.name}': file type not supported for extraction yet]"
        pages, _ = _extract_pages(path, file_type)
        text = "\n".join(p.text for p in pages)
        return text[:max_chars]
    except Exception as exc:  # noqa: BLE001
        return f"[Attachment '{path.name}': extraction failed ({type(exc).__name__})]"


def _embedding_profile_for_collection(services: AppServices, backend: str, collection: str) -> str:
    try:
        sample = services.vector_store(backend).sample_points(collection, limit=1)
        if sample:
            return sample[0].metadata.embedding_profile
    except Exception:  # noqa: BLE001
        pass
    return services.config.embedding_profiles.default_profile


def run_search_and_ask(
    services: AppServices,
    prompt: str,
    upload,
    vector_store_backend: str,
    collection_name: str,
    domain: str,
    document_type: str,
    language: str,
    search_mode: str,
    vector_top_k: int,
    bm25_top_k: int,
    fusion: str,
    reranker: str,
    rerank_top_n: int,
    use_filter_pushdown: bool,
    action: str,
    llm_target_id: str,
    model: str,
    temperature: float,
    max_context_tokens: int,
    external_confirmation: bool,
):
    """Core logic behind the 'Run' button — a module-level function so it can be
    unit-tested without going through Gradio's event wiring."""
    config = services.config
    llm_target_choices = list(config.llm_targets.targets.keys())
    warnings: list[str] = []

    if not prompt or not prompt.strip():
        return "", [], {}, "", "Please enter a query."
    if not collection_name:
        return "", [], {}, "", "Please select a collection."

    domain_id = None if domain == "all" else domain
    attachment_context = _extract_upload_context(upload.name if upload else None)

    filters: dict = {}
    if domain_id:
        filters["domain_id"] = domain_id
    if document_type:
        filters["document_type"] = document_type
    if language and language != "auto":
        filters["language"] = language

    embedding_profile = _embedding_profile_for_collection(services, vector_store_backend, collection_name)

    with request_context(
        user_action="search_and_ask",
        domain_id=domain_id,
        collection_name=collection_name,
        vector_store=vector_store_backend,
        retrieval_mode=search_mode,
        llm_target=llm_target_id,
    ):
        request = RetrievalRequest(
            query=prompt,
            domain_id=domain_id,
            collection_name=collection_name,
            vector_store=vector_store_backend,
            retrieval_mode=search_mode,
            vector_top_k=int(vector_top_k),
            bm25_top_k=int(bm25_top_k),
            rerank_top_n=int(rerank_top_n),
            fusion=fusion,
            use_filter_pushdown=use_filter_pushdown,
            filters=filters,
            embedding_profile=embedding_profile,
            reranker_profile=reranker,
            max_context_tokens=int(max_context_tokens),
        )

        log.info("search_started", query_length=len(prompt), prompt_hash=short_hash(prompt))
        started = time.perf_counter()
        try:
            result = services.retrieval_engine(vector_store_backend).run(request)
        except Exception as exc:  # noqa: BLE001
            m.retrieval_errors_total.labels(
                vector_store=vector_store_backend, collection=collection_name, domain=domain_id or "all",
                retrieval_mode=search_mode,
            ).inc()
            log.error("search_failed", error_type=type(exc).__name__, error_message=str(exc))
            return "", [], {}, "", f"Search failed: {exc}"
        duration = time.perf_counter() - started

        m.retrieval_requests_total.labels(
            vector_store=vector_store_backend, collection=collection_name, domain=domain_id or "all",
            retrieval_mode=search_mode, reranker=result.diagnostics.reranker,
        ).inc()
        m.retrieval_duration_seconds.labels(
            vector_store=vector_store_backend, collection=collection_name, domain=domain_id or "all",
            retrieval_mode=search_mode, reranker=result.diagnostics.reranker,
        ).observe(duration)
        m.retrieval_chunks_returned.labels(
            vector_store=vector_store_backend, collection=collection_name, domain=domain_id or "all",
            retrieval_mode=search_mode,
        ).observe(len(result.chunks))
        m.metrics_summary.record_retrieval(duration)
        log.info("search_completed", chunks_returned=len(result.chunks), duration_ms=round(duration * 1000, 1))

        chunks_table = [
            [c.metadata.file_name, c.metadata.document_type, c.metadata.page_number, round(c.score, 3), c.text[:300]]
            for c in result.chunks
        ]
        context_text = result.context_text
        if attachment_context:
            context_text = f"[Attached file context]\n{attachment_context}\n\n{context_text}"

        if action == "Search only":
            return "", chunks_table, result.diagnostics.model_dump(), context_text, "\n".join(warnings)

        targets = [llm_target_id]
        if action == "Compare local vs frontier":
            other = next(
                (
                    t for t in llm_target_choices
                    if config.llm_targets.targets[t].privacy_level != config.llm_targets.targets[llm_target_id].privacy_level
                ),
                None,
            )
            if other:
                targets.append(other)

        answers = []
        for target_id in targets:
            target_cfg = config.llm_targets.get(target_id)
            gen_request = GenerationRequest(
                prompt=prompt,
                context_text=context_text,
                llm_target=target_id,
                model=model or None,
                temperature=temperature,
                external_confirmation=external_confirmation,
                domain_id=domain_id,
            )
            gen_started = time.perf_counter()
            response = services.llm_router.generate(gen_request)
            gen_duration = time.perf_counter() - gen_started

            if response.blocked:
                m.external_llm_blocked_total.labels(
                    domain=domain_id or "all", llm_target=target_id, privacy_mode=config.app.privacy_mode
                ).inc()
                log.info("generation_blocked", reason=response.block_reason)
                answers.append(f"**[{target_id}] BLOCKED:** {response.block_reason}")
                continue

            if target_cfg.privacy_level == "external" and external_confirmation:
                m.external_llm_confirmed_total.labels(
                    domain=domain_id or "all", llm_target=target_id, privacy_mode=config.app.privacy_mode
                ).inc()

            m.generation_requests_total.labels(
                llm_target=target_id, model=response.model, privacy_level=target_cfg.privacy_level
            ).inc()
            m.generation_duration_seconds.labels(
                llm_target=target_id, model=response.model, privacy_level=target_cfg.privacy_level
            ).observe(gen_duration)
            m.generation_context_tokens.labels(llm_target=target_id, model=response.model).observe(
                response.context_tokens_estimate
            )
            m.generation_output_tokens.labels(llm_target=target_id, model=response.model).observe(
                response.output_tokens_estimate
            )
            m.metrics_summary.record_generation(gen_duration)
            log.info(
                "generation_completed", llm_target=target_id, model=response.model,
                duration_ms=round(gen_duration * 1000, 1),
            )
            answers.append(f"**[{target_id} / {response.model}]**\n\n{response.answer}")

        return (
            "\n\n---\n\n".join(answers),
            chunks_table,
            result.diagnostics.model_dump(),
            context_text,
            "\n".join(warnings),
        )


def build_search_page(services: AppServices) -> gr.Blocks:
    config = services.config
    domain_choices = ["all"] + config.domains.ids()
    reranker_choices = list(config.reranker_profiles.profiles.keys())
    llm_target_choices = list(config.llm_targets.targets.keys())

    def _on_backend_change(backend: str):
        return collection_dropdown_update(services, backend)

    def _on_collection_change(backend: str, collection: str):
        if not collection:
            return ""
        return _embedding_profile_for_collection(services, backend, collection)

    def _on_llm_target_change(llm_target_id: str):
        target = config.llm_targets.targets.get(llm_target_id)
        visible = bool(target and target.privacy_level == "external")
        return gr.update(visible=visible)

    def _run(*args):
        return run_search_and_ask(services, *args)

    with gr.Blocks(title="Athena — Search & Ask") as page:
        gr.Markdown("## Search & Ask")
        with gr.Row():
            with gr.Column(scale=2):
                prompt = gr.Textbox(label="Prompt", lines=3)
                upload = gr.File(label="Optional attachment (image / audio / video / document)")
                with gr.Row():
                    vector_store_backend = gr.Dropdown(["qdrant", "chroma"], value=config.vector_store.backend, label="Vector Store")
                    collection_name = gr.Dropdown([], label="Collection")
                    embedding_profile_display = gr.Textbox(label="Embedding Profile", interactive=False)
                with gr.Row():
                    domain = gr.Dropdown(domain_choices, value="all", label="Domain")
                    document_type = gr.Textbox(label="Document Type (optional)")
                    language = gr.Dropdown(_LANGUAGES, value="auto", label="Language")
                with gr.Row():
                    search_mode = gr.Dropdown(_SEARCH_MODES, value=config.retrieval_defaults.default_mode, label="Search Mode")
                    fusion = gr.Dropdown(_FUSIONS, value=config.retrieval_defaults.fusion, label="Fusion")
                with gr.Row():
                    vector_top_k = gr.Slider(1, 100, value=config.retrieval_defaults.vector_top_k, step=1, label="Vector Top-K")
                    bm25_top_k = gr.Slider(1, 100, value=config.retrieval_defaults.bm25_top_k, step=1, label="BM25 Top-K")
                with gr.Row():
                    reranker = gr.Dropdown(reranker_choices, value=config.reranker_profiles.default_profile, label="Reranker")
                    rerank_top_n = gr.Slider(1, 30, value=config.retrieval_defaults.rerank_top_n, step=1, label="Rerank Top-N")
                use_filter_pushdown = gr.Checkbox(value=config.retrieval_defaults.filter_pushdown, label="Use Filter Pushdown")
                action = gr.Radio(_ACTIONS, value=_ACTIONS[1], label="Action")
                with gr.Row():
                    llm_target_id = gr.Dropdown(llm_target_choices, value=config.llm_targets.default_target, label="LLM Target")
                    model = gr.Textbox(label="Model (optional override)")
                with gr.Row():
                    temperature = gr.Slider(0.0, 2.0, value=0.2, step=0.1, label="Temperature")
                    max_context_tokens = gr.Number(value=4000, label="Max Context Tokens")
                external_confirmation = gr.Checkbox(
                    label="I understand that retrieved context will be sent to an external API", visible=False
                )

            with gr.Column(scale=3):
                run_button = gr.Button("Run", variant="primary")
                answer = gr.Markdown(label="Answer")
                chunks = gr.Dataframe(
                    headers=["file_name", "document_type", "page", "score", "text"], label="Retrieved chunks"
                )
                diagnostics = gr.JSON(label="Retrieval diagnostics")
                context_sent = gr.Textbox(label="Context sent to LLM", lines=8)
                errors = gr.Markdown(label="Errors/warnings")

        vector_store_backend.change(_on_backend_change, inputs=vector_store_backend, outputs=collection_name)
        collection_name.change(
            _on_collection_change, inputs=[vector_store_backend, collection_name], outputs=embedding_profile_display
        )
        llm_target_id.change(_on_llm_target_change, inputs=llm_target_id, outputs=external_confirmation)
        page.load(_on_backend_change, inputs=vector_store_backend, outputs=collection_name)

        run_button.click(
            _run,
            inputs=[
                prompt, upload, vector_store_backend, collection_name, domain, document_type, language,
                search_mode, vector_top_k, bm25_top_k, fusion, reranker, rerank_top_n, use_filter_pushdown,
                action, llm_target_id, model, temperature, max_context_tokens, external_confirmation,
            ],
            outputs=[answer, chunks, diagnostics, context_sent, errors],
        )

    return page
