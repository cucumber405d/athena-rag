> ⚠️ **Этот документ предназначен только для отчётности и передачи людям** (портфолио, ревью,
> онбординг нового разработчика и т. п.). Он **не является инструкцией для Claude Code** и не
> должен интерпретироваться как руководство к действию при работе над проектом — для этого
> используется [`CLAUDE.md`](./CLAUDE.md). Данный файл — снимок архитектуры на момент написания;
> он может расходиться с кодом после последующих изменений и не поддерживается автоматически.

# Architecture Blueprint — Athena (локально-ориентированная RAG-платформа)

Подробное описание архитектуры проекта: что это, из чего состоит, как устроено внутри и почему
именно так. Написано так, чтобы по этому документу можно было воссоздать проект с нуля или
объяснить его архитектуру человеку, не знакомому с кодовой базой.

---

## 1. Обзор проекта

**Назначение:** локально-ориентированная масштабируемая RAG-платформа (Retrieval-Augmented
Generation) для долгосрочного хранения, индексации, гибридного поиска и вопросно-ответной работы
с большим количеством разнородных данных — текстовые файлы, Markdown, PDF (включая сканы через
OCR-fallback), DOCX, изображения (через OCR; аудио/видео — заложены как расширяемые интерфейсы).

Состоит из двух частей:
1. **Пакетное приложение ingestion** — CLI + core-сервисы для массовой загрузки файлов
   (Discover → Load → Extract → Normalize → Metadata Enrichment → Chunk → Embed → Upsert →
   Verify → Report).
2. **Онлайн-приложение** — FastAPI-сервер с тремя Gradio веб-мордами (Search & Ask, Dashboard,
   Data Management) и production-style observability (структурные логи, actuator endpoints,
   Prometheus metrics).

**Ключевые особенности:**
- Embeddings — локальные по умолчанию (`sentence-transformers`, профиль `bge_m3_local` /
  `BAAI/bge-m3`), без обязательной зависимости от внешних API
- Vector store — подключаемый backend: **Qdrant** (production-like) и **ChromaDB**
  (локальный/dev), за единой абстракцией `VectorStoreGateway`
- Метаданные — first-class citizen: домен, тип документа, язык, теги, access_level хранятся как
  payload/metadata в векторной БД, а не только через физическую коллекцию
- Filter Pushdown — фильтры транслируются в нативные `Filter`/`where` конструкции backend'а, а не
  применяются постфактум в приложении
- Sidecar-метаданные — `.athena.yaml` на папку и на файл, а также YAML front matter в Markdown,
  с чётким приоритетом переопределения
- Retrieval и Generation разделены сознательно: `RetrievalEngine` только ищет и строит контекст,
  `LLMRouter` + `PrivacyGuard` решают, отправлять ли этот контекст и куда
- Privacy Guard — по умолчанию `LOCAL_ONLY`; для доменов `job`/`personal`/`user` отправка во
  внешние LLM требует явного подтверждения даже при более разрешительном глобальном режиме
- Наблюдаемость веб-приложения — Python-эквиваленты Spring Actuator/MDC/Micrometer:
  `structlog` + `contextvars` + `prometheus_client` + FastAPI actuator-эндпоинты
- Параллельная (не подключённая) экспериментальная реализация ingestion/retrieval на базе
  **LlamaIndex** — для сравнения подходов, без риска для рабочего пути

---

## 2. Технологический стек и внешние пакеты

| Компонент | Технология | Версия (pyproject) |
|-----------|-----------|---------------------|
| Язык | Python | 3.11+ |
| Валидация / конфигурация | `pydantic`, `pydantic-settings` | >=2.7 / >=2.3 |
| Загрузка YAML-конфигов | `pyyaml` | >=6.0 |
| CLI-фреймворк | `typer` (+ `rich` для вывода) | >=0.12 / >=13.7 |
| Полнотекстовый поиск | `rank-bm25` | >=0.2.2 |
| Локальные embeddings / reranker | `sentence-transformers` | >=3.0 |
| Vector DB (production) | `qdrant-client` | >=1.9 |
| Vector DB (local/dev) | `chromadb` | >=0.5 |
| Разбор PDF (текстовый слой) | `pypdf` | >=4.2 |
| Рендер страниц PDF под OCR | `pypdfium2` (чистый wheel, без системного poppler) | >=5.0 |
| Разбор DOCX | `python-docx` | >=1.1 |
| Работа с изображениями / OCR | `pillow`, `pytesseract` (+ системный бинарник `tesseract-ocr`) | >=10.3 / >=0.3.10 |
| Веб-интерфейс | `gradio` | >=4.36 |
| Веб-сервер / REST-обёртка | `fastapi`, `uvicorn[standard]` | >=0.111 / >=0.30 |
| Структурное логирование | `structlog` | >=24.1 |
| Метрики Prometheus | `prometheus-client` | >=0.20 |
| HTTP-клиент (OpenAI-compatible LLM) | `httpx` | >=0.27 |
| `.env`-файлы | `python-dotenv` | >=1.0 |
| Восстановление кодировки текста | `charset-normalizer` | >=3.3 |
| Починка mojibake / Unicode-нормализация | `ftfy` | >=6.2 |
| Определение языка текста (fallback) | `py3langid` | >=0.3 |
| Рендер графиков дашборда | `matplotlib` | >=3.8 |
| Семантическое разбиение на чанки | `semantic-text-splitter` | >=0.32 |
| Тесты | `pytest`, `pytest-mock` (extra `dev`) | >=8.2 / >=3.14 |

**Опциональная группа `llamaindex`** (extra, не входит в основную установку) — используется
только экспериментальным параллельным pipeline (см. раздел 14):

| Пакет | Назначение |
|---|---|
| `llama-index-core` | движок индексации/retrieval (`VectorStoreIndex`, `SentenceSplitter`, `SimpleDirectoryReader`) |
| `llama-index-vector-stores-chroma` | адаптер LlamaIndex → ChromaDB |
| `llama-index-vector-stores-qdrant` | адаптер LlamaIndex → Qdrant |
| `llama-index-embeddings-huggingface` | обёртка над `sentence-transformers`-моделями для LlamaIndex |
| `llama-index-readers-file` | чтение PDF/DOCX внутри LlamaIndex-пайплайна |

Для юнит-тестов экспериментального пайплайна используется `llama_index.core.embeddings.MockEmbedding`
вместо реальной модели — тесты не тянут `torch`.

Внешние процессы (не Python-зависимости, опциональны в зависимости от backend'а):
- **Qdrant** — `docker run -p 6333:6333 qdrant/qdrant` (нужен только если `vector_store.backend: qdrant`)
- **Prometheus** / **Grafana** — для сбора и визуализации метрик веб-приложения (см. раздел 12)
- **LM Studio / Ollama / vLLM / llama.cpp server** — любой локальный OpenAI-compatible LLM-сервер

---

## 3. Структура пакетов

```text
athena/
  pyproject.toml            зависимости, entry point `athena`, extras (`dev`, `llamaindex`)
  .env.example
  configs/                  app.yaml, domains.yaml, embedding_profiles.yaml,
                             chunking_profiles.yaml, reranker_profiles.yaml,
                             vector_stores.yaml, llm_targets.yaml, retrieval.yaml
  data/                     raw/, processed/, chroma/, reports/ (gitignored)
  observability/
    prometheus/prometheus.yml
    grafana/dashboards/athena-web-dashboard.json, README.md
  src/de/ibikus/athena/     — Java-стиль reverse-domain пакет (см. раздел 18, п. 1)
    core/
      config/               loader.py (типизированный YAML-загрузчик + lru_cache), settings.py (env)
      models/                domain.py, document.py, chunk.py, ingestion_job.py,
                             retrieval.py, llm_target.py — все Pydantic-модели
    metadata/                sidecar.py, extractor.py, validators.py, language_detector.py
                             (best-effort определение языка через py3langid, низший приоритет
                             после sidecar/front matter/явного --language)
    ingestion/
      pipeline.py            оркестратор всех стадий ingestion
      discovery.py            обход файлов + checksum (sha256)
      embeddings.py           EmbeddingService (in-process / external, заготовка)
      loaders/, parsers/       по одному модулю на тип файла (txt/md/pdf/docx/image/unsupported)
      chunkers/                token_chunker.py, page_aware_chunker.py
    stores/
      vector_gateway.py        абстрактный VectorStoreGateway + SearchFilters + CollectionStats
      qdrant_adapter.py, chroma_adapter.py
      docstore.py              JSONL-хранилище DocumentMetadata (заготовка под PostgreSQL)
      raw_file_store.py        копия исходных файлов на диске (заготовка под MinIO/S3)
      factory.py                build_vector_store_gateway(config, backend)
    retrieval/
      vector_retriever.py, bm25_retriever.py, hybrid_retriever.py (RRF/relative_score/weighted)
      reranker.py, query_expander.py
      context_builder.py        dedup + группировка соседних чанков + token budget + RetrievalEngine
    generation/
      llm_router.py, openai_compatible.py, privacy_guard.py
    web/
      app.py                    FastAPI-обёртка + actuator/metrics routes + mount Gradio
      services.py                AppServices — фасад над core-сервисами для web-слоя
      pages/                     search_page.py, dashboard_page.py, ingest_page.py, common.py
      observability/              context.py, logging.py, metrics.py, health.py
    cli/                        main.py (Typer app), ingest.py, search.py
    experimental/llamaindex/    ПАРАЛЛЕЛЬНАЯ реализация — не подключена (раздел 14)
  tests/                       по одному файлу на подсистему + conftest.py
```

---

## 4. Конфигурация

Всё настраиваемое живёт в `configs/*.yaml` и загружается через
`de.ibikus.athena.core.config.loader.load_config()` (обёрнуто в `functools.lru_cache`) в один
типизированный объект `Config`, агрегирующий:

| Атрибут `Config` | YAML-файл | Модель |
|---|---|---|
| `app` | `app.yaml` | `AppConfig` — имя, log level, privacy_mode, пути хранения, observability-флаги |
| `domains` | `domains.yaml` | `DomainsConfig` / `DomainConfig` — id, default_collection, `frontier_allowed` |
| `embedding_profiles` | `embedding_profiles.yaml` | `EmbeddingProfilesConfig` / `EmbeddingProfile` |
| `chunking_profiles` | `chunking_profiles.yaml` | `ChunkingProfilesConfig` / `ChunkingProfile` |
| `reranker_profiles` | `reranker_profiles.yaml` | `RerankerProfilesConfig` / `RerankerProfile` |
| `vector_store` | `vector_stores.yaml` | `VectorStoreConfig` (backend + `QdrantConfig`/`ChromaConfig`) |
| `llm_targets` | `llm_targets.yaml` | `LLMTargetsConfig` / `LLMTargetConfig` |
| `retrieval_defaults` | `retrieval.yaml` | `RetrievalDefaults` |

Переменные окружения (`.env`, префикс `ATHENA_`) читаются отдельно через `pydantic-settings`
(`core/config/settings.py`) — log level, флаги observability/prometheus, privacy mode по умолчанию.

Домены по умолчанию: `job`, `personal`, `tech`, `media`, `musik`, `books`, `user`. `tech`, `musik`
и `books` имеют `frontier_allowed: true` — остальные по умолчанию требуют подтверждения на отправку
во внешний LLM (см. раздел 10).

---

## 5. Core-модели

Все модели — Pydantic `BaseModel`, без исключений для сценариев, которые не могут произойти.

- **`ChunkMetadata`** (`core/models/chunk.py`) — единственный источник истины для payload
  векторной БД: `chunk_id`, `document_id`, `source_id`, `domain_id`, `collection_name`,
  файловые атрибуты, `language`/`document_type`/`tags`/`access_level`, `page_number` /
  `start_time_sec` / `end_time_sec` (для будущих аудио/видео), `chunking_profile` +
  `embedding_profile` + `embedding_model` + `embedding_dimension`, `deleted` (soft delete).
- **`DocumentMetadata`** / **`ExtractedDocument`** / **`ExtractedPage`** (`document.py`) —
  документ до чанкинга: результат стадий Load + Extract.
- **`IngestionReport`** / **`IngestionError`** (`ingestion_job.py`) — счётчики
  files_total/processed/skipped/failed, chunks_created, список ошибок/предупреждений;
  сохраняется как JSON и Markdown в `data/reports/`.
- **`RetrievalRequest`** / **`ScoredChunk`** / **`RetrievalDiagnostics`** / **`ContextResult`**
  (`retrieval.py`) — вход/выход retrieval-слоя.
- **`LLMTargetConfig`** / **`GenerationRequest`** / **`GenerationResponse`** (`llm_target.py`).

---

## 6. Metadata и sidecar-файлы

`metadata/sidecar.py` реализует приоритет источников метаданных (выше — важнее):

```
markdown front matter  >  <file>.athena.yaml  >  .athena.yaml (папка)  >  автоопределение
```

- `extract_auto_metadata()` (`extractor.py`) — угадывает `file_type`/`mime_type`/`document_type`
  (по ключевым словам вроде `cv`, `lebenslauf`, `vacancy`) чисто по имени файла.
- `parse_markdown_front_matter()` — регулярка на блок `---\n...\n---`, отделяет YAML-заголовок от
  тела текста (важно: тело без front matter уходит в chunking, иначе YAML-заголовок попадает в
  индексируемый текст — это реальный баг, найденный и исправленный при построении параллельного
  LlamaIndex-пайплайна, см. раздел 14).
- `validators.py` — `validate_domain_id`, `validate_access_level` (`private`/`internal`/`public`),
  бросают `MetadataValidationError` с понятным сообщением.

---

## 7. Ingestion pipeline

`ingestion/pipeline.py::IngestionPipeline.run()` — единственная точка входа, общая для CLI и
Web UI 3 (`Не смешивай ingestion, retrieval и generation в одном большом файле` — соблюдено:
файл отвечает только за оркестрацию стадий).

Реестр loader/parser по `file_type` (`_REGISTRY`):

| file_type | Loader | Parser | Статус |
|---|---|---|---|
| text/markdown/html/csv/json/xml/log | `text_loader` | `text_parser` | реализовано (общий текстовый путь; кодировка исходного файла автоопределяется через `charset-normalizer` — UTF-8/cp1251/cp866/koi8-r/..., не предполагается UTF-8) |
| pdf | `pdf_loader` (отдаёт путь; открывается парсером) | `pdf_parser` (по страницам, `pypdf`; для страниц без текстового слоя — OCR-fallback через `pypdfium2`-рендер + `pytesseract`) | реализовано, включая OCR-fallback |
| docx | `docx_loader` (`python-docx`) | `docx_parser` | реализовано |
| image (jpg/png/webp/tiff) | `image_loader` (`PIL.Image`) | `image_parser` (`pytesseract`, требует системный `tesseract-ocr`) | реализовано |
| pptx, xlsx, audio, video, archive | `unsupported_loader` | — | заглушка, `UnsupportedFileError` |

Чанкеры (`ingestion/chunkers/`): оба построены на `semantic_text_splitter` вместо word-count
окна — режут по смысловым границам, а не по счётчику слов. `token_chunker` (для
`default_text`/`book_default`/`cv_default`) использует `MarkdownSplitter` для `.md`-файлов
(границы заголовков/списков/код-блоков) и `TextSplitter` (абзацы/предложения) для остального
текста; `page_aware_chunker` (для `pdf_page_aware`) делает то же самое внутри каждой страницы,
сохраняя `page_number`. `chunk_size`/`chunk_overlap` в `chunking_profiles.yaml` — в символах
(единица `semantic_text_splitter`), не в словах.

Стадии `run()`:
1. `discovery.discover_files()` — обход дерева, игнор `.athena.yaml`/`__pycache__`/`.venv`/`.git`
2. Для каждого файла: `discovery.compute_checksum()` (sha256) → `document_id = f"doc_{checksum[:16]}"`
   (детерминированный id, стабильный при повторной загрузке того же файла)
3. `_extract_pages()` — загрузка + (для markdown) отделение front matter
4. `_normalize_text()` — удаление NUL-байтов, `ftfy.fix_text()` (починка mojibake + Unicode NFC),
   de-hyphenation переносов слов на конце строки (артефакт PDF/OCR), схлопывание пробелов/переносов
5. `resolve_document_metadata()` + `validate_domain_id`/`validate_access_level`; если язык не задан
   ни sidecar/front matter, ни явным `--language` — авто-определение через
   `language_detector.detect_language()` (py3langid, best-effort, низший приоритет)
6. Чанкинг по выбранному профилю
7. `embedding_service.embed_texts()` (пропускается в `dry_run`)
8. `vector_store.upsert_chunks()` + `docstore.upsert()` + `raw_file_store.store()`
9. Ошибка на одном файле не прерывает job — попадает в `report.errors`, обработка продолжается
10. `_write_report()` — JSON + Markdown в `data/reports/{job_id}.{json,md}`

`dry_run=True` выполняет всё до эмбеддинга включительно и возвращает оценочное число чанков, не
трогая vector store (проверено тестом `test_ingestion_dry_run_does_not_upsert`).

`embeddings.py` — `EmbeddingService` ABC: `HuggingFaceEmbeddingService` (in-process,
`sentence-transformers`, единственная полностью реализованная для MVP) и заготовка
`ExternalEmbeddingService` для будущего HTTP-сервиса эмбеддингов (TEI/Ollama/кастомный endpoint).

---

## 8. Vector store gateway

`stores/vector_gateway.py::VectorStoreGateway` — абстрактный класс с методами
`create_collection`, `upsert_chunks`, `delete_by_document_id`, `delete_by_filter`,
`search_vector`, `search_hybrid` (по умолчанию `NotImplementedError` — fallback на fusion уровня
приложения), `update_payload`, `get_collection_stats`, `get_domains`, `sample_points`,
`list_collections`. Ни CLI, ни Gradio UI не обращаются к `qdrant_client`/`chromadb` напрямую —
только через эту абстракцию (`factory.py::build_vector_store_gateway`).

**`SearchFilters`** — общая Pydantic-модель фильтров (`domain_id`, `document_id`, `document_type`,
`language`, `tags`, `access_level`, `deleted`, `source_id`, `file_type`, диапазоны
`created_*`/`updated_*`, `page_number`), транслируемая в нативные конструкции каждого backend'а.

- **`QdrantVectorStoreAdapter`** — `_build_filter()` строит `qdrant_client.http.models.Filter` с
  `FieldCondition`/`MatchValue`/`MatchAny` (для тегов) /`DatetimeRange`. Soft delete — `set_payload`
  с `points=Filter(...)` (без предварительного scroll). `chunk_id` (строка) мапится в UUID
  Qdrant-точки через `uuid.uuid5` с фиксированным namespace. Статистика по доменам/типам/языкам —
  приближённая агрегация через `scroll` (лимит по умолчанию 10 000 точек — компромисс для MVP).
- **`ChromaVectorStoreAdapter`** — Chroma не поддерживает списки в metadata, поэтому `tags`
  сериализуются в `tags_csv` (join по `|`), а фильтрация по тегам делается клиентской
  постобработкой поверх `where`-пушдауна остальных полей (задокументировано как частичный
  pushdown — "настолько, насколько поддерживает backend").

`docstore.py` — JSONL-файл с `DocumentMetadata` (документ-уровень метаданных, отдельно от
векторной БД, как того требует правило "raw files нельзя хранить только в vector database").
`raw_file_store.py` — копия исходных файлов по пути `processed/raw_files/{domain}/{document_id}/`.
Оба — явные заготовки под будущий PostgreSQL/MinIO (see Roadmap).

---

## 9. Retrieval engine

`retrieval/context_builder.py::RetrievalEngine` — единая точка входа для CLI/веб, реализует все
пять режимов `RetrievalRequest.retrieval_mode`:

| Режим | Реализация |
|---|---|
| `vector` | `VectorRetriever` — embed запроса + `search_vector` |
| `bm25` | `BM25Retriever` — корпус строится на лету из `sample_points()` (payload'ов vector store, с теми же фильтрами), скоринг через `rank_bm25.BM25Okapi` |
| `hybrid` / `hybrid_with_rerank` | `HybridRetriever` — vector + BM25, слияние через `rrf_fuse`/`relative_score_fuse`/`weighted_fuse` (оба режима идентичны по retrieval-части) |
| `multi_query` | `QueryExpander` (rule-based: убирает "find/search for/...", разбивает по "and"/"or", keyword-only вариант) → hybrid по каждому варианту → RRF по всем спискам |

Reranking (`Reranker.rerank()` — `NoneReranker` или `CrossEncoderReranker` на `sentence-transformers.CrossEncoder`)
применяется **независимо от `retrieval_mode`**: если `request.reranker_profile != "none"`, он прогоняется
поверх чанков, полученных любым из режимов выше, перед `dedup_chunks()`/`group_neighbors()`.

**Жёсткое правило #8/#9 из исходной спецификации** — embedding-модель запроса обязана совпадать
с embedding-моделью, которой построена коллекция. `RetrievalEngine._check_embedding_profile_consistency()`
берёт один сэмпл через `sample_points(limit=1)` и сверяет `metadata.embedding_profile` с
`request.embedding_profile`; при несовпадении — `ValueError` с понятным сообщением
(проверено тестом `test_embedding_profile_mismatch_is_rejected`).

`context_builder.py` также содержит: `dedup_chunks()` (по `chunk_id`), `group_neighbors()`
(схлопывает соседние `chunk_index` одного документа, сохраняя лучший score), `build_context_text()`
(token budget — грубая оценка 4 символа/токен, `estimate_tokens()` переиспользуется и генерацией
для отчёта по токенам).

---

## 10. Generation и Privacy Guard

`generation/llm_router.py::LLMRouter` — единственный провайдер для MVP: `openai_compatible`
(`openai_compatible.py`, `httpx`-клиент к `/chat/completions`, покрывает LM Studio/Ollama/vLLM/
llama.cpp server/OpenAI). Anthropic сконфигурирован в `llm_targets.yaml`, но роутинг для него —
задокументированный TODO.

`generation/privacy_guard.py::PrivacyGuard` — порядок проверки:
1. `llm_target.privacy_level != "external"` → разрешено всегда.
2. Глобальный `privacy_mode == LOCAL_ONLY` → блокировка безусловно.
3. `domain.frontier_allowed == False` (job/personal/user по умолчанию) → требуется явное
   подтверждение (`external_confirmation=True`), даже если глобальный режим разрешительнее.
4. Иначе: `ALLOW_FRONTIER_WITH_CONFIRMATION` требует подтверждения, `ALLOW_FRONTIER` разрешает
   безусловно.

Вся матрица (5 комбинаций режим × домен × confirmation) покрыта тестами
(`tests/test_generation.py`).

---

## 11. Web-приложение (FastAPI + Gradio)

`web/app.py` — FastAPI-приложение, оборачивающее Gradio (`gr.mount_gradio_app(fastapi_app,
build_gradio_app(), path="/")`). Explicit-роуты (`/health`, `/actuator/*`, `/metrics`)
регистрируются раньше монтирования Gradio на `/`, поэтому не перекрываются им (проверено:
Starlette matches роуты в порядке регистрации).

`web/services.py::AppServices` — фасад, кэширующий `VectorStoreGateway`/`RetrievalEngine` по
backend'у, инициализирующий `PrivacyGuard`, `LLMRouter`, `DocStore`, `RawFileStore`. Ни одна
Gradio-страница не создаёт эти объекты напрямую.

Три страницы (`web/pages/`), каждая — `gr.Blocks`, бизнес-логика вынесена в module-level функции
(не замыкания) специально для юнит-тестируемости в обход Gradio event wiring:

- **`search_page.py`** — `run_search_and_ask()`: полный контроль над retrieval + generation
  request'ами, поддержка вложенного файла-attachment (быстрое извлечение текста через реестр
  ingestion), режим "Compare local vs frontier" (два LLM-таргета параллельно), чекбокс
  подтверждения внешнего API появляется только для `privacy_level: external`.
- **`dashboard_page.py`** — `refresh_dashboard()`: статистика коллекций, распределения по
  domain/file_type/language (рендер server-side через `matplotlib` в `gr.Plot` — `gr.BarPlot`/
  Vega-Lite не рисует столбцы для номинальной оси в используемой версии Gradio), последние
  ingestion-отчёты и failed files (парсятся из `data/reports/*.json`), сэмпл чанков. 2D-проекция
  векторов (UMAP/t-SNE) — явный placeholder на V2.
- **`ingest_page.py`** — вкладка "Add data" (`run_web_ingest()`, dry-run/real через тот же
  `IngestionPipeline`) и вкладка "Search & edit metadata / Delete"
  (`search_documents()`/`load_document_for_edit()`/`save_document_metadata()`/`delete_document()`
  — метаданные правятся через `update_payload()` по всем чанкам документа, delete по умолчанию
  soft, hard delete требует отдельного чекбокса подтверждения).

---

## 12. Observability

Инструментирован **только веб-слой** (batch ingestion CLI — нет), Java-аналогии явно
прописаны в коде:

| Java/Spring | Python/Athena |
|---|---|
| Spring Boot Actuator | `/health`, `/actuator/health`, `/actuator/info`, `/actuator/metrics` (FastAPI-роуты в `web/app.py`) |
| Java MDC | `web/observability/context.py::request_context()` — обёртка над `structlog.contextvars` |
| Micrometer/Prometheus | `web/observability/metrics.py` — `prometheus_client` Counter/Histogram, экспорт на `/metrics` |
| Grafana dashboards | `observability/grafana/dashboards/athena-web-dashboard.json` + PromQL-README |

`context.py` — `request_context(**fields)` — контекстный менеджер, `bind_contextvars()` +
`reset_contextvars()`, поддерживает вложенность (проверено тестом — вложенный контекст не портит
внешний после выхода). Логи никогда не содержат сырых prompt/context/API-ключей/содержимого
файлов — только `query_length`, `prompt_hash` (`short_hash()` — sha256[:12]), счётчики.

`metrics.py` — метрики по группам: `athena_web_*` (requests/duration/errors по route+method+status),
`athena_retrieval_*` (+ `chunks_returned`), `athena_vector_search_*` (по backend+collection+operation),
`athena_generation_*` (+ context/output tokens), `athena_external_llm_blocked_total` /
`_confirmed_total`, `athena_web_ingest_*` / `_metadata_updates_total` / `_soft_deletes_total` /
`_hard_deletes_total`. Labels низкокардинальны намеренно — никаких raw file names/prompts/
document_id/chunk_id в качестве label-значений.

`health.py` — `/actuator/health` пингует `vector_store.list_collections()`; при ошибке компонент
получает статус `DEGRADED` (не роняет всё приложение), UI остаётся доступным.

---

## 13. CLI

`cli/main.py` — Typer-приложение, entry point `athena` (см. `pyproject.toml`
`[project.scripts]`). Команды `ingest`/`search`/`collections`/`dashboard` — тонкие обёртки над
`cli/ingest.py::run_ingest()` и `cli/search.py::run_search()`, которые используют те же
core-сервисы (`IngestionPipeline`, `RetrievalEngine`, `build_vector_store_gateway`), что и веб-слой
— никакой продублированной бизнес-логики.

---

## 14. Экспериментальная реализация — LlamaIndex (не подключена)

`experimental/llamaindex/` — параллельная реализация ingestion + retrieval на LlamaIndex,
**нигде не импортируется** активным пайплайном/CLI/веб-приложением (проверено grep'ом по
кодовой базе). Существует для сравнения с hand-rolled реализацией, потому что исходная
спецификация проекта называла LlamaIndex предпочтительным RAG-движком, а активный MVP пошёл
другим путём ради полного контроля над схемой метаданных и pluggable vector-store gateway.

- `common.py` — `llamaindex_collection_name()` (namespacing `<collection>_llamaindex`, чтобы
  никогда не пересечься с продакшн-коллекциями — метаданные LlamaIndex несовместимы с
  `ChunkMetadata`), `build_embed_model()`, `build_vector_store()` (адаптеры на Chroma/Qdrant).
- `ingestion.py` — переиспользует `discovery`/`resolve_document_metadata`/`parse_markdown_front_matter`
  из основного кода, но делегирует загрузку/чанкинг/эмбеддинг/индексацию LlamaIndex
  (`SimpleDirectoryReader`, `SentenceSplitter`, `HuggingFaceEmbedding`, `VectorStoreIndex`).
- `retrieval.py` — `query_with_llamaindex()`: чистый dense similarity через `index.as_retriever()`,
  без fusion/rerank/filter pushdown.

При построении этого модуля найдены и исправлены два бага, релевантные и для основного пайплайна
как напоминание о инвариантах:
1. `tags` как Python-список ломает запись в Chroma (metadata должна быть скалярной) — тот же
   `tags_csv`-паттерн, что и в `chroma_adapter.py`.
2. Markdown front matter должен отделяться от тела текста *до* чанкинга — иначе YAML-заголовок
   попадает в индексируемый/возвращаемый текст.

Тесты (`tests/test_llamaindex_experimental.py`) используют `pytest.importorskip("llama_index.core")`
и `llama_index.core.embeddings.MockEmbedding` — весь набор пропускается автоматически, если extra
`llamaindex` не установлен, и не тянет `torch`/`sentence-transformers` для проверки логики.

---

## 15. Тестирование

`tests/conftest.py` — фикстура `config` (свежий `Config` на каждый тест, пути `chroma`/
`processed`/`reports` подменены на `tmp_path`, `load_config.cache_clear()` до и после) и
`fake_embedding_builder` (`FakeEmbeddingService` — детерминированный вектор из sha256 текста,
без зависимости от `torch`).

| Файл | Что проверяет |
|---|---|
| `test_config.py` | загрузка конфигов, домены, `frontier_allowed` |
| `test_metadata.py` | приоритет sidecar/front matter, `ChunkMetadata`, валидаторы |
| `test_stores.py` | построение `where`-фильтров, интерфейс gateway, soft delete + фильтрация `deleted` |
| `test_ingestion.py` | полный прогон pipeline (реальная embedded ChromaDB), dry-run не пишет в vector store |
| `test_retrieval.py` | дефолты `RetrievalRequest`, все 5 режимов retrieval end-to-end, embedding-profile mismatch |
| `test_generation.py` | вся матрица `PrivacyGuard` |
| `test_web_observability.py` | MDC-контекст в логах, инкремент метрик, `/health`/`/actuator/*`/`/metrics` через `TestClient` |
| `test_llamaindex_experimental.py` | namespacing коллекций, ingestion+retrieval через LlamaIndex, изоляция от продакшн-коллекций |

Все тесты используют реальный (embedded, no-server) экземпляр ChromaDB — не моки уровня HTTP;
Qdrant в тестах не участвует (нет зависимости от поднятого сервера). Сеть и GPU не требуются.

---

## 16. Запуск

```bash
pip install -e .

# батчевая загрузка данных
athena ingest --path ./data/raw/tech --domain tech --collection athena_chunks_bge_m3_v1
athena ingest --path ./data/raw/job --domain job --dry-run
athena search "Java AI Engineer CV" --domain job --top-k 10
athena collections
athena dashboard

# веб-приложение (Search & Ask / Dashboard / Data Management + observability)
python -m de.ibikus.athena.web.app
curl http://localhost:7860/health
curl http://localhost:7860/actuator/health
curl http://localhost:7860/metrics
```

```bash
# тесты
pip install -e ".[dev]"
pytest

# экспериментальный LlamaIndex-пайплайн (опционально)
pip install -e ".[llamaindex]"
pytest tests/test_llamaindex_experimental.py
```

```bash
# опционально: Qdrant как backend вместо ChromaDB
docker run -p 6333:6333 qdrant/qdrant
# затем vector_store.backend: qdrant в configs/vector_stores.yaml
```

---

## 17. Известные ограничения и Roadmap

См. подробный список в [`README.md`](./README.md#known-limitations) / [`read_me.ru`](./read_me.ru#известные-ограничения).
Кратко: LlamaIndex не подключён к активному пайплайну (раздел 14); BM25 без персистентного
индекса (корпус строится на лету); сканированные PDF/audio/video/pptx/xlsx/архивы — интерфейсы
без реального извлечения; нет нативного Qdrant sparse/hybrid search; Anthropic routing не
реализован; нет PostgreSQL/MinIO/S3/multi-user auth/UMAP-проекции.

---

## 18. Важные архитектурные решения

1. **Пакет назван `de.ibikus.athena` (reverse-domain, Java-стиль)**, а не просто `athena`.
   Это осознанный выбор соглашения об именовании для унификации с остальными подпроектами
   репозитория, а не типичная Python-конвенция — учитывать при поиске импортов
   (`from de.ibikus.athena.xxx import ...`, а не `from athena.xxx import ...`).

2. **Retrieval и Generation разделены на уровне модулей**, не только классов.
   `RetrievalEngine` ничего не знает о LLM-таргетах; `LLMRouter`/`PrivacyGuard` ничего не знают о
   векторном поиске. Это позволяет менять generation-модель "на лету" на каждый запрос, не
   трогая retrieval, и наоборот — использовать retrieval без генерации ("Search only" в UI).

3. **Embedding-профиль — часть индекса, а не параметр запроса.** Смена embedding-модели требует
   новой коллекции или reindex — правило форсируется кодом (`_check_embedding_profile_consistency`),
   а не только описано в документации.

4. **VectorStoreGateway — единственная точка входа к Qdrant/Chroma.** Ни CLI, ни Gradio UI не
   импортируют `qdrant_client`/`chromadb` напрямую — это позволяет добавить третий backend, не
   трогая retrieval/ingestion/web-код.

5. **Экспериментальный LlamaIndex-пайплайн физически изолирован через namespacing коллекций**
   (`<collection>_llamaindex`), а не просто "выключен флагом" — так даже случайный вызов из
   экспериментального кода не может испортить данные в продакшн-коллекции.

6. **Все delete-операции по умолчанию — soft delete** (`deleted=true` в metadata/payload).
   Hard delete — отдельный, явно запрашиваемый путь с чекбоксом подтверждения в Web UI 3.

7. **MDC-контекст, структурные логи и Prometheus-метрики — независимые, но согласованные слои**,
   как и в Java/Spring-подпроектах этого репозитория (см. `boreas/architecture-blueprint.md`,
   раздел 13): `request_context()` не знает о метриках, метрики не знают о логах — но оба
   используют одни и те же смысловые поля (`domain_id`, `collection_name`, `retrieval_mode`,
   `llm_target`), что делает логи и метрики сопоставимыми при разборе инцидентов.

8. **Бизнес-логика Gradio-страниц вынесена в module-level функции**, а не замыкания внутри
   `build_*_page()`. Иначе её нельзя было бы протестировать без полного event-wiring Gradio —
   решение принято уже в процессе реализации, когда стало ясно, что закрытые внутри `build_*`
   функции недоступны тестам напрямую.
