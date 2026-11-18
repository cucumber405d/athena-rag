# Athena — сводка для актуализации описания проекта

> **Для Claude Code.** Это снимок кода Athena по состоянию на **10.11.2026**, взятый из копии
> `C:\Users\cucum\Prog\Athena`. Это не рабочий репозиторий в WSL (`~/projects/appaCl/athena`).
> Перед правкой описаний сверь каждый пункт с актуальным кодом репозитория. Источник истины —
> код и тесты, а не этот файл. Разделы «Расхождения» и «Не реализовано» нужны, чтобы не
> переносить в описание то, чего в коде нет.

## 1. Что это

Athena — подпроект модульной GenAI-платформы **Appa**: локально работающая RAG-платформа
(Retrieval-Augmented Generation). Хранит, индексирует и ищет разнородные документы, отвечает
на вопросы по ним через LLM. По умолчанию не зависит от внешних API.

Две части:
1. **Batch-ingestion**: CLI `athena`, также Kubernetes-Job.
   Pipeline: Discover → Load → Extract/OCR → Normalize → Metadata Enrichment → Chunk → Embed →
   Upsert → Verify → Report (JSON + Markdown в `data/reports/`).
2. **Online-приложение**: FastAPI + три Gradio-UI + observability в стиле Spring Actuator,
   MDC и Micrometer.

Пакет: `src/de/ibikus/athena/`. Имя в reverse-domain стиле Java выбрано осознанно. Импорты:
`from de.ibikus.athena...`.

Роль автора: единственный разработчик и архитектор (концепция, архитектура, реализация, тесты,
деплой). Код генерируется с помощью Claude Code по спецификации и правилам автора (CLAUDE.md,
architecture-blueprint.md), автор делает review.

## 2. Технологии (версии из `.venv` снимка)

| Область | Технологии |
|---|---|
| Язык / модели | Python 3.11+ (`requires-python >=3.11`; Docker `python:3.11-slim`, локальный venv 3.12), Pydantic 2.13, pydantic-settings, PyYAML |
| Vector Stores | ChromaDB 1.5.9 (default, `./data/chroma`), Qdrant (client 1.18.0; в Helm образ `qdrant/qdrant:v1.9.0`) |
| Embeddings | sentence-transformers 5.6, torch 2.13, transformers 5.13; профиль по умолчанию `bge_m3_local` = `BAAI/bge-m3`, 1024 dim, cosine, normalize |
| Retrieval | rank-bm25 0.2.2; fusion RRF / relative_score / weighted (в приложении); Cross-Encoder Reranker `BAAI/bge-reranker-v2-m3` (опционально, по умолчанию `none`) |
| Документы / OCR | pypdf 6.14, pypdfium2, python-docx, Pillow, pytesseract + tesseract-ocr, charset-normalizer, ftfy, py3langid, semantic-text-splitter 0.32 |
| LLM | httpx 0.28 → OpenAI-совместимый `/chat/completions`: LM Studio, Ollama, vLLM, llama.cpp server, OpenAI |
| Web / CLI | FastAPI 0.139, Uvicorn 0.51, Gradio 6.20, Typer 0.26, Rich, matplotlib (графики dashboard) |
| Observability | structlog 26.1 + contextvars (MDC), prometheus_client 0.25, Grafana-дашборд (`observability/grafana/`), `observability/prometheus/prometheus.yml` |
| Deployment | Docker (non-root user, порт 7860), Kubernetes/minikube, Helm-chart `deploy/helm/athena` (Deployment, Service, Qdrant StatefulSet + Service, PVC, Secret, ConfigMap, опциональный ingest-Job), `deploy/deploy.sh` |
| Тесты | pytest, pytest-mock; 36 тестов в 10 файлах |
| Экспериментально | LlamaIndex 0.14 (extra `[llamaindex]`), не подключён к рабочему пути |

## 3. Внешние API

### 3.1 HTTP (FastAPI, порт 7860, `web/app.py`)

| Endpoint | Ответ |
|---|---|
| `GET /health` | `{"status":"UP"}` (liveness) |
| `GET /actuator/health` | `status` UP/DEGRADED + `components`: `web`, `vector_store` (ping через `list_collections()`, при ошибке DEGRADED без падения приложения), `embedding_profile`, `llm_targets` |
| `GET /actuator/info` | app name/version/mode, версия Python и т. д. |
| `GET /actuator/metrics` | JSON-сводка счётчиков запросов и ошибок |
| `GET /metrics` | Prometheus exposition format |
| `/` | смонтированный Gradio (`gr.mount_gradio_app`), вкладки ниже |

HTTP-middleware пишет `athena_web_*` метрики и биндит request-context для логов.

**Важно:** REST-эндпоинтов для search/ask/ingest **нет**. Вся бизнес-функциональность
доступна только через Gradio-UI и CLI. Не описывать Athena как REST-сервис.

### 3.2 Gradio-UI (`web/pages/`, бизнес-логика в module-level функциях для тестируемости)

- **Search & Ask** (`search_page.py`, `run_search_and_ask()`): режимы *Search only*,
  *Search + Ask selected LLM* и *Compare local vs frontier* (два LLM-таргета с разным
  `privacy_level` параллельно). Полное управление параметрами retrieval: mode, top-k, fusion,
  reranker, фильтры. Можно приложить файл как дополнительный контекст. Чекбокс подтверждения
  показывается только для `privacy_level: external`.
- **Dashboard** (`dashboard_page.py`): статистика коллекций, распределения по
  domain/file_type/language (matplotlib), последние ingestion-отчёты и failed files, сэмпл
  чанков. UMAP/t-SNE пока заглушка.
- **Data Management** (`ingest_page.py`): вкладка «Add data» (upload, dry-run или реальный
  ingest через тот же `IngestionPipeline`) и вкладка «Search & edit metadata / Delete»
  (правка metadata по всем чанкам документа; soft delete по умолчанию, hard delete только
  через отдельный чекбокс).

### 3.3 CLI (Typer, entry point `athena`)

```
athena ingest --path P --domain D [--collection C] [--backend qdrant|chroma]
              [--chunking-profile X] [--embedding-profile Y] [--dry-run]
              [--tag T ...] [--document-type T] [--language L] [--access-level A]
athena search "query" [--domain D] [--collection C] [--backend B]
              [--mode vector|bm25|hybrid|hybrid_with_rerank|multi_query] [--top-k N]
              [--embedding-profile Y] [--reranker R]      # только retrieval, без LLM
athena collections [--backend B]
athena dashboard   [--backend B]                          # текстовая статистика коллекций
```

Запуск web: `python -m de.ibikus.athena.web.app`.

## 4. Внутренние API (ключевые контракты)

- **`stores/vector_gateway.py::VectorStoreGateway`** (ABC). Единственная точка доступа к
  Qdrant и Chroma. Адаптеры: `QdrantVectorStoreAdapter`, `ChromaVectorStoreAdapter`, создаются
  через `stores/factory.py::build_vector_store_gateway()`. Методы: `create_collection`,
  `upsert_chunks`, `delete_by_document_id(hard=False)`, `delete_by_filter(hard=False)`,
  `search_vector`, `search_hybrid` (по умолчанию `NotImplementedError`, нативный hybrid пока
  нигде не реализован), `update_payload`, `get_collection_stats` → `CollectionStats`,
  `get_domains`, `sample_points`, `list_collections`.
  `SearchFilters` с pushdown в нативные фильтры: domain_id, document_id, document_type,
  language, tags, access_level, deleted (default False), source_id, file_type,
  created/updated after/before, page_number.
- **`retrieval/context_builder.py::RetrievalEngine.run(RetrievalRequest) → ContextResult`**
  (`context_text`, `chunks: list[ScoredChunk]`, `diagnostics`). Режимы: `vector`, `bm25`
  (корпус строится на лету из `sample_points()`), `hybrid` и `hybrid_with_rerank`
  (vector + BM25 + fusion), `multi_query` (rule-based `QueryExpander` → hybrid по каждому
  варианту → RRF). Reranker применяется в любом режиме, если профиль не `none`. Затем
  `dedup_chunks`, `group_neighbors` и `build_context_text` с token budget
  (~4 символа на токен). Если embedding-профиль запроса не совпадает с профилем коллекции —
  `ValueError`.
- **`generation/llm_router.py::LLMRouter.generate(GenerationRequest) → GenerationResponse`**.
  Сначала `PrivacyGuard.check()`; если запрос заблокирован, возвращается `blocked=True` с
  `block_reason`. Провайдеры: только `openai_compatible`.
- **`generation/privacy_guard.py::PrivacyGuard`**. Режимы `LOCAL_ONLY` (default),
  `ALLOW_FRONTIER_WITH_CONFIRMATION`, `ALLOW_FRONTIER`. Таргеты не-`external` разрешены
  всегда. Для доменов с `frontier_allowed: false` (job, personal, media, user) нужно явное
  подтверждение при любом режиме.
- **`ingestion/pipeline.py::IngestionPipeline.run(path, domain_id, …) → IngestionReport`**.
  Loaders и parsers через registry; неподдерживаемые форматы → `UnsupportedFileError`.
- **`ingestion/embeddings.py::EmbeddingService`**: `embed_texts`, `embed_query`. Реализован
  только `HuggingFaceEmbeddingService`.
- **Хранилища рядом с vector store:** `DocStore` (`data/processed/docstore.jsonl`, метаданные
  документов), `RawFileStore` (`data/processed/raw_files/<domain>/<document_id>/`).
- **`web/services.py::AppServices`**: фасад, кэширует gateway и engine по backend. UI не
  создаёт core-объекты сам.
- **Модели** (`core/models/`): `ChunkMetadata` (payload каждого вектора: ids, domain,
  file info, checksum, language, document_type, tags, page_number, start/end_time_sec,
  chunk_index, chunking/embedding profile + model + dimension, created/updated_at, deleted,
  access_level), `Chunk`, `RetrievalRequest`, `ScoredChunk` (source: vector | bm25 | fused |
  reranked), `GenerationRequest`/`Response`, `LLMTargetConfig`, `IngestionJob`/`Report`.

## 5. Конфигурация (`configs/*.yaml` + `.env` через pydantic-settings)

- `app.yaml`: name, mode, log_level, `privacy_mode: LOCAL_ONLY`, storage dirs, флаги
  observability (json-логи, redaction, actuator `/actuator`, prometheus `/metrics`).
- `vector_stores.yaml`: `backend: chroma` (по умолчанию) | `qdrant`
  (`http://localhost:6333`, коллекция `athena_chunks_bge_m3_v1`).
- `domains.yaml`: **job, personal, tech, media, musik, books, user** (у каждого
  `default_collection`, `frontier_allowed`; media → `athena_media_vectors_v1`).
- `chunking_profiles.yaml`: `default_text` (1600 символов, overlap 200, семантические
  границы), `book_default` и др.
- `embedding_profiles.yaml`: `bge_m3_local` (default); `qwen3_embedding_06b_local` (ollama) и
  `qwen3_embedding_4b_local` (tei) помечены experimental.
- `reranker_profiles.yaml`: `none` (default), `bge_reranker_local`, `qwen3_reranker_local`
  (experimental, cuda).
- `retrieval.yaml`: `default_mode: hybrid`, vector_top_k 30, bm25_top_k 30, rerank_top_n 8,
  fusion rrf, filter_pushdown true.
- `llm_targets.yaml`: local_lmstudio (default), local_ollama (`qwen3:8b`), local_vllm
  (`Qwen/Qwen3-8B`), frontier_openai (`gpt-4.1`), frontier_anthropic.
- `.env`: `ATHENA_LOG_LEVEL`, `ATHENA_PRIVACY_MODE`, `QDRANT_URL`/`QDRANT_API_KEY`, ключи LLM
  (`LMSTUDIO_API_KEY`, `VLLM_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`).

## 6. Модули и ответственность

| Модуль | Ответственность |
|---|---|
| `core/config`, `core/models` | загрузка YAML и env; Pydantic-модели домена |
| `ingestion/loaders`, `ingestion/parsers` | TXT/MD, PDF (OCR-fallback для сканов), DOCX, изображения (OCR) |
| `ingestion/chunkers` | token-, page-aware и semantic-чанкинг по профилям |
| `ingestion/embeddings` | локальная векторизация по профилю |
| `ingestion/pipeline`, `discovery` | оркестрация batch-прогона, dry-run, verify, отчёты |
| `metadata` | sidecar `.athena.yaml` (на папку и на файл), YAML front matter, детекция языка, валидация, приоритет overrides |
| `stores` | gateway + Qdrant/Chroma-адаптеры, factory, DocStore, RawFileStore |
| `retrieval` | vector, BM25, hybrid, multi_query, fusion, reranker, context builder |
| `generation` | LLMRouter, OpenAI-compatible client, PrivacyGuard |
| `web`, `web/pages` | FastAPI + Gradio, три UI |
| `web/observability` | structlog и MDC (`request_context()`), Prometheus-метрики, health/info |
| `cli` | Typer-обёртки над теми же core-сервисами |
| `experimental/llamaindex` | параллельная реализация для сравнения, пишет в `<collection>_llamaindex` |
| `deploy/`, `observability/` | Helm, deploy-скрипт, Prometheus, Grafana |

## 7. Observability

Prometheus-метрики (низкая кардинальность, без file names, prompts и ids в labels):
- `athena_web_requests_total` / `_request_duration_seconds` / `_errors_total` (route, method, status)
- `athena_retrieval_requests_total` / `_duration_seconds` / `_chunks_returned` / `_errors_total`
- `athena_vector_search_requests_total` / `_duration_seconds` / `_errors_total` (backend, collection, operation)
- `athena_generation_requests_total` / `_duration_seconds` / `_errors_total` / `_context_tokens` / `_output_tokens` (llm_target, model, privacy_level)
- `athena_external_llm_blocked_total`, `athena_external_llm_confirmed_total` (domain, llm_target, privacy_mode)
- `athena_web_ingest_requests_total` / `_files_uploaded_total` / `_errors_total`,
  `athena_web_metadata_updates_total`, `athena_web_soft_deletes_total`, `athena_web_hard_deletes_total`

Логи: JSON через structlog. Сырые prompt, context, ключи и содержимое файлов не логируются,
пишутся только `query_length` и `prompt_hash` (sha256[:12]). Инструментирован только
web-слой, batch-CLI метрик не пишет.

## 8. Ключевые архитектурные решения

1. Retrieval и Generation разделены на уровне модулей: LLM можно менять для каждого запроса,
   «Search only» работает без LLM.
2. Весь доступ к vector store идёт через `VectorStoreGateway`: третий backend добавляется без
   правок retrieval, ingestion и UI.
3. Embedding-профиль — часть индекса: несовпадение профилей проверяется в коде.
4. Метаданные — first-class citizen: фильтры выполняются в БД (pushdown), а не после выборки.
5. Soft delete по умолчанию; hard delete только явно.
6. LlamaIndex физически изолирован через namespace коллекций.
7. Логи и метрики — независимые слои с общими смысловыми полями (`domain_id`,
   `collection_name`, `retrieval_mode`, `llm_target`), как в Java/Spring-подпроектах Appa.
8. Логика Gradio-страниц вынесена в module-level функции ради юнит-тестов.

## 9. Не реализовано (не описывать как готовое)

- REST API для search, ask и ingest; MCP-интеграция (например, через Charon).
- Нативный hybrid и sparse поиск в Qdrant: `search_hybrid` не реализован, fusion работает
  только в приложении. BM25 без персистентного индекса, корпус пересобирается на каждый
  запрос, поэтому не масштабируется на большие коллекции.
- Anthropic-провайдер: таргет сконфигурирован, при вызове будет `NotImplementedError`.
- Внешние embedding-провайдеры (ollama, tei): профили Qwen3 при использовании дадут
  `NotImplementedError`.
- Audio, video, pptx, xlsx, архивы: только интерфейсы. Визуальных (CLIP) embeddings нет.
- Evaluation (RAGAS, метрики retrieval), ссылки на источники в ответах, streaming,
  многоходовый диалог.
- PostgreSQL, MinIO/S3, multi-user auth, UMAP/t-SNE.
- Метрики для batch-ingestion CLI.

## 10. Расхождения, которые стоит поправить при актуализации

- `RUNNING.md` перечисляет домены `job | personal | tech | media | user`, а в `domains.yaml`
  есть ещё **musik** и **books**. В CLI help список уже полный.
- В Helm образ Qdrant `v1.9.0`, а `qdrant-client` 1.18: большая разница версий, стоит
  проверить совместимость или поднять образ.
- `frontier_anthropic.default_model: "claude-sonnet-5"`: значение есть в конфиге, но
  провайдер не реализован.
- В корне лежат `prompt_01.md`, `prompt_02.md` (исходные промпты генерации), а также
  `README.md` и `read_me.ru`. По конвенции «Documentation as Code» документация должна жить в
  `docs/` (`docs/architecture.md`, `docs/start.md` с командами сборки и запуска и т. д.).
  `docs/` пока содержит только `Athena_Projektbeschreibung.pdf`.
- Правило проекта: любое изменение `README.md` синхронно вносится в `read_me.ru`, и наоборот.
  В `read_me.ru` код, команды, пути и имена конфигов остаются на английском.
- `architecture-blueprint.md` прямо помечен как снимок для людей, а не инструкция. При
  расхождении прав блупринт по коду.
