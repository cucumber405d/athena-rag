# Athena — локальная масштабируемая RAG-платформа (реализовано)

Этот файл — переработанная версия [`prompt_01.md`](./prompt_01.md), приведённая в соответствие с
фактически реализованной архитектурой. `prompt_01.md` сохранён без изменений как исторический
документ (исходное техзадание); этот файл — актуальная спецификация происшедшего.

Подробный человеко-читаемый архитектурный снимок — в [`architecture-blueprint.md`](./architecture-blueprint.md).
Здесь — тот же материал в формате исполняемого промпта (как если бы им можно было
регенерировать проект с нуля).

---

## Главные отличия от исходного техзадания (prompt_01.md)

1. **Пакет называется `de.ibikus.athena`, а не `athena`.** Java-стиль reverse-domain имени
   (`src/de/ibikus/athena/...`) — осознанное решение для унификации с остальными подпроектами
   репозитория, принятое отдельным запросом уже после первичной реализации MVP.
2. **LlamaIndex НЕ является основным движком.** Вопреки исходному пункту 2.13, retrieval/ingestion
   реализованы напрямую (loaders/parsers/chunkers/BM25/RRF-fusion своими силами), чтобы сохранить
   полный контроль над схемой метаданных и pluggable vector-store gateway. LlamaIndex подключён
   как **параллельная, изолированная, не задействованная в проде экспериментальная реализация**
   (`experimental/llamaindex/`) — см. раздел 14 ниже.
3. **ChromaDB — backend по умолчанию** (`vector_store.backend: chroma` в `configs/vector_stores.yaml`),
   а не Qdrant — чтобы проект запускался "из коробки" без внешнего сервера. Qdrant остаётся
   production-like backend'ом и включается сменой одной строки конфига.
4. **`read_me.ru`** — параллельный русский перевод `README.md`, синхронизируется вручную при
   каждом изменении `README.md` (правило закреплено в `CLAUDE.md`).
5. Всё, что ниже помечено как "MVP", — уже реализовано и покрыто тестами, а не только запланировано.

---

# 0. Первые действия (для дальнейшей доработки)

Перед изменением кода:

1. Прочитать `CLAUDE.md` (правила и конвенции) и `architecture-blueprint.md` (снимок архитектуры
   для людей — не инструкция к действию, может расходиться с кодом после изменений).
2. Прочитать актуальный код и тесты — они источник истины о поведении, а не этот файл.
3. Не переписывать существующие модули вслепую — расширять аккуратно, следуя уже принятым
   архитектурным решениям (раздел "Важные архитектурные решения" в blueprint).
4. Код, имена классов/файлов/переменных/конфигов — на английском. Комментарии — на английском.
   Документация (`README.md`, `CLAUDE.md`, blueprint) — как договорено для каждого файла
   (`README.md` — английский, `read_me.ru` — русский перевод, `CLAUDE.md`/blueprint — русский).

---

# 1. Цель проекта

Реализована **Athena**:

> Масштабируемая локально-ориентированная RAG-платформа для долгосрочного хранения, индексации,
> поиска и вопросно-ответной работы с разнородными данными.

Поддерживаемые типы данных (см. раздел 4 — фактический статус по каждому):
текстовые файлы, Markdown, PDF, DOCX, изображения — полностью; аудио, видео, архивы, pptx/xlsx —
интерфейсы-заглушки с явным `UnsupportedFileError`, без реального извлечения.

Athena состоит из двух частей, обе реализованы:

1. **Пакетное CLI-приложение для массовой загрузки данных** (`athena ingest`/`search`/
   `collections`/`dashboard`).
2. **Онлайн-приложение** — FastAPI-сервер с тремя Gradio веб-мордами и production-style
   observability.

---

# 2. Основные архитектурные принципы

Реализовано согласно принципам:

1. Embeddings локальны по умолчанию — `sentence-transformers`, in-process
   (`ingestion/embeddings.py::HuggingFaceEmbeddingService`).
2. Vector store конфигурируем — `VectorStoreGateway` + два адаптера.
3. **Qdrant** — production-like backend (`stores/qdrant_adapter.py`).
4. **ChromaDB** — local/dev backend и backend **по умолчанию** для zero-config старта
   (`stores/chroma_adapter.py`).
5. Метаданные — first-class citizen: `ChunkMetadata` хранится как Qdrant payload / Chroma
   metadata, не только как физическая коллекция.
6. Filter Pushdown применяется на обоих backend'ах (Chroma — частично, см. раздел 9).
7. Домен хранится как metadata field `domain_id`, не как отдельная коллекция.
8. Raw files не хранятся только в vector database — есть отдельный `RawFileStore`
   (копия файлов на диске) и `DocStore` (JSONL, document-level metadata).
9. Embedding model — часть индекса; retrieval форсирует совпадение профиля
   (`RetrievalEngine._check_embedding_profile_consistency`, бросает `ValueError` при несовпадении).
10. Generation model выбирается отдельно от retrieval и может меняться на лету
    (`generation/llm_router.py`, независим от `retrieval/context_builder.py`).
11. Gradio UI управляет параметрами retrieval и generation (`web/pages/search_page.py`).
12. **LlamaIndex используется только в параллельной, не подключённой экспериментальной ветке**
    (см. раздел 14) — основной движок написан напрямую, без LlamaIndex.
13. Pydantic — для конфигурации, metadata models, request/response models (везде).
14. Архитектура модульна: `core/`, `metadata/`, `ingestion/`, `stores/`, `retrieval/`,
    `generation/`, `web/`, `cli/`, `experimental/` — отдельные пакеты с чёткими границами
    ответственности.

---

# 3. Фактическая структура проекта

```text
athena/
  pyproject.toml            entry point `athena`, extras `dev`/`llamaindex`
  .env.example
  README.md / read_me.ru    английская и русская версии (вести параллельно)
  architecture-blueprint.md человеко-читаемый архитектурный снимок
  CLAUDE.md                 инструкции для Claude Code уровня подпроекта

  configs/
    app.yaml                имя, log level, privacy_mode, storage paths, observability
    domains.yaml            job / personal / tech / media / user, frontier_allowed
    embedding_profiles.yaml bge_m3_local (реализован) + qwen3_* (объявлены, не реализованы)
    chunking_profiles.yaml  default_text / pdf_page_aware / book_default / cv_default +
                             audio_transcript / video_scene (объявлены, чанкер не реализован)
    reranker_profiles.yaml  none (реализован) + bge_reranker_local (реализован) +
                             qwen3_reranker_local (объявлен, экспериментальный)
    vector_stores.yaml      backend: chroma (по умолчанию) | qdrant
    llm_targets.yaml        local_lmstudio/ollama/vllm, frontier_openai/anthropic
    retrieval.yaml          default_mode, top-k, fusion, filter_pushdown — отдельный файл
                             (в исходном промпте это было подсекцией app.yaml)

  data/                     raw/, processed/, chroma/, reports/ — gitignored

  observability/
    prometheus/prometheus.yml
    grafana/dashboards/athena-web-dashboard.json, README.md (PromQL-справочник)

  src/de/ibikus/athena/     # реальный путь пакета — de.ibikus.athena, не athena
    core/
      config/               loader.py (Config + lru_cache), settings.py (env, ATHENA_-префикс)
      models/               domain.py, document.py, chunk.py, ingestion_job.py,
                             retrieval.py, llm_target.py
    metadata/               sidecar.py, extractor.py, validators.py
    ingestion/
      pipeline.py           IngestionPipeline — единственная точка входа для CLI и Web UI 3
      discovery.py          обход файлов + sha256 checksum
      embeddings.py         EmbeddingService ABC: HuggingFace (реализован) / External (заглушка)
      loaders/              base.py, text_loader.py, pdf_loader.py, docx_loader.py,
                             image_loader.py, unsupported_loader.py
      parsers/              base.py, text_parser.py, pdf_parser.py, docx_parser.py,
                             image_parser.py
      chunkers/             base.py (word-based split_words), token_chunker.py,
                             page_aware_chunker.py
    stores/
      vector_gateway.py     VectorStoreGateway (ABC) + SearchFilters + CollectionStats
      qdrant_adapter.py, chroma_adapter.py
      docstore.py           JSONL DocumentMetadata store (заготовка под PostgreSQL)
      raw_file_store.py     копия исходных файлов (заготовка под MinIO/S3)
      factory.py            build_vector_store_gateway(config, backend)
    retrieval/
      vector_retriever.py, bm25_retriever.py, hybrid_retriever.py (rrf/relative_score/weighted),
      reranker.py (NoneReranker/CrossEncoderReranker), query_expander.py (rule-based)
      context_builder.py    dedup + group_neighbors + build_context_text + RetrievalEngine
    generation/
      llm_router.py, openai_compatible.py, privacy_guard.py
    web/
      app.py                FastAPI + actuator/metrics routes + mount Gradio на "/"
      services.py            AppServices — фасад над core-сервисами
      pages/                 search_page.py, dashboard_page.py, ingest_page.py, common.py
      observability/         context.py (MDC), logging.py (structlog JSON),
                             metrics.py (prometheus_client), health.py
    cli/                    main.py (Typer), ingest.py, search.py
    experimental/llamaindex/  ПАРАЛЛЕЛЬНАЯ реализация — не подключена (раздел 14)

  tests/                    conftest.py + по одному файлу на подсистему (раздел 15 blueprint)
```

---

# 4. Batch ingestion application — фактический статус по типам

```text
Полностью реализовано:
  .txt, .md, .html, .csv, .json, .xml, .log   — общий текстовый loader/parser
  .pdf                                         — pypdf, постранично; OCR для сканов — TODO
  .docx                                       — python-docx
  .jpg, .jpeg, .png, .webp, .tiff             — PIL + pytesseract (best-effort, если установлен)

Заглушки (интерфейс есть, извлечения нет — UnsupportedFileError):
  .pptx, .xlsx
  .mp3, .wav, .m4a, .ogg
  .mp4, .mkv, .mov, .avi
  .zip, .tar, .gz
```

Реестр loader/parser по `file_type` — `ingestion/pipeline.py::_REGISTRY`. Добавление нового типа —
одна запись в реестре + модуль в `loaders/`/`parsers/` (или чанкер в `chunkers/`, если нужен новый
тип разбиения).

---

# 5. Ingestion pipeline (реализовано как есть)

`IngestionPipeline.run()`:

```text
1. Discover    discovery.discover_files() — обход дерева, игнор .athena.yaml/__pycache__/.venv/.git
2. Load        loader-модуль по file_type
3. Extract     parser-модуль; markdown — отдельно отделяет front matter от тела ДО парсинга
4. Normalize   _normalize_text() — схлопывание пробелов/переносов, удаление NUL
5. Metadata    resolve_document_metadata() (auto < folder sidecar < file sidecar < front matter)
               + validate_domain_id/validate_access_level
6. Chunk       чанкер по chunking_profile.type ("token" → token_chunker, "page_aware" →
               page_aware_chunker)
7. Embed       embedding_service.embed_texts() — пропускается при dry_run=True
8. Upsert      vector_store.upsert_chunks() + docstore.upsert() + raw_file_store.store()
9. Verify      ошибка на одном файле не прерывает job — попадает в report.errors, job продолжается
10. Report     _write_report() — JSON + Markdown в data/reports/{job_id}.{json,md}
```

`document_id = f"doc_{sha256(file)[:16]}"` — детерминированный, стабилен при повторной загрузке
того же файла (передела нет — reingestion просто перезаписывает те же chunk_id).

---

# 6. Домены данных

Реализовано без изменений от исходного техзадания: `job`, `personal`, `tech`, `media`, `user` в
`configs/domains.yaml`, поле `domain_id` в metadata, `frontier_allowed` per domain (только `tech`
разрешён по умолчанию — см. раздел 19 Privacy Guard).

---

# 7. Metadata sidecar files

Реализовано полностью по спецификации: `.athena.yaml` на папку, `<file>.athena.yaml` на файл,
markdown front matter. Приоритет (выше — важнее):

```
markdown front matter  >  <file>.athena.yaml  >  .athena.yaml (папка)  >  автоопределение
```

Реализация — `metadata/sidecar.py::resolve_document_metadata()` +
`metadata/extractor.py::extract_auto_metadata()`.

---

# 8. Metadata schema

`core/models/chunk.py::ChunkMetadata` реализована практически один в один с исходной
спецификацией (раздел 8 prompt_01.md), с добавлением поля `mime_type` уже присутствовавшего в
плане, без отклонений. Хранится в Qdrant payload и Chroma metadata; PostgreSQL — не реализован
(V2, см. раздел "Roadmap" в README).

---

# 9. Filter Pushdown

Реализовано через `stores/vector_gateway.py::SearchFilters` — общая модель для обоих backend'ов,
плюс поле **`document_id`** (добавлено сверх исходного списка — понадобилось для
редактирования/удаления метаданных по документу через Web UI 3).

- **Qdrant** (`qdrant_adapter.py::_build_filter`) — полный pushdown: `FieldCondition`/
  `MatchValue`/`MatchAny` (теги)/`DatetimeRange`.
- **Chroma** (`chroma_adapter.py::_build_where`) — pushdown для всех скалярных полей; `tags`
  хранятся как `tags_csv` (join через `|`, т.к. Chroma не поддерживает списки в metadata) и
  фильтруются клиентской постобработкой поверх остального pushdown'а — задокументировано как
  частичная поддержка ("насколько backend позволяет", как и предполагал исходный промпт).

---

# 10. Vector stores

`VectorStoreGateway` (ABC) реализован с полным набором методов из исходной спецификации плюс
`list_collections()` (понадобился Web UI/CLI для выпадающих списков) и расширенный `sample_points()`
с параметром `filters` (переиспользуется BM25-ретривером для построения корпуса на лету).

## 10.1 Qdrant

Реализовано: dense vectors, payload, полный filter pushdown, collection stats (приближённая
агрегация через `scroll`, лимит 10 000 точек), soft delete через `set_payload` с `points=Filter(...)`
(без предварительного scroll). Sparse/hybrid native search — **не реализован**, явный
`NotImplementedError` с комментарием, что fusion происходит на уровне приложения (V2).

## 10.2 ChromaDB

Реализовано: persistent local storage, collections, metadata filters (кроме тегов — см. раздел 9),
vector search, stats, soft delete через `update()` metadata.

---

# 11. Collections

Реализовано без отклонений: одна коллекция на embedding-профиль
(`athena_chunks_bge_m3_v1`), домен — metadata field, не отдельная коллекция.

---

# 12. Local embedding models

Реализован только `bge_m3_local` (`BAAI/bge-m3`, HuggingFace/sentence-transformers, device по
умолчанию `cpu` в конфиге — не `cuda`, чтобы проект запускался без GPU). `qwen3_embedding_06b_local`
и `qwen3_embedding_4b_local` объявлены в `embedding_profiles.yaml`, но их provider'ы (`ollama`,
`tei`) не реализованы — при попытке использовать бросают `NotImplementedError` из
`ExternalEmbeddingService`.

Правило форсируется кодом, не только конвенцией:

```text
Embedding model = часть индекса → RetrievalEngine проверяет совпадение и бросает ValueError.
Generation model = часть ответа → передаётся в каждом GenerationRequest отдельно.
```

---

# 13. Embedding service modes

`ingestion/embeddings.py::EmbeddingService` (ABC):
- **In-process** (`HuggingFaceEmbeddingService`) — реализован, единственный рабочий путь для MVP.
- **External service** (`ExternalEmbeddingService`) — заготовка-интерфейс, `NotImplementedError`
  внутри `embed_texts()`; провайдер определяется по `embedding_profile.provider` в конфиге.

---

# 14. Экспериментальная реализация — LlamaIndex (не подключена)

Отдельный, изолированный модуль `experimental/llamaindex/`, добавленный отдельным запросом уже
после MVP — **не импортируется нигде** в активном pipeline/retrieval/CLI/web (проверено grep'ом
по кодовой базе).

- `common.py` — `llamaindex_collection_name()` (namespacing `<collection>_llamaindex`, чтобы
  никогда не пересечься с продакшн-коллекциями — метаданные LlamaIndex несовместимы с
  `ChunkMetadata`), `build_embed_model()`, `build_vector_store()`.
- `ingestion.py` — переиспользует `discovery`/`resolve_document_metadata`/
  `parse_markdown_front_matter` из основного кода, но делегирует загрузку/чанкинг/эмбеддинг/
  индексацию LlamaIndex (`SimpleDirectoryReader`, `SentenceSplitter`, `HuggingFaceEmbedding`,
  `VectorStoreIndex`).
- `retrieval.py` — `query_with_llamaindex()`: чистый dense similarity через `index.as_retriever()`,
  без fusion/rerank/filter pushdown.

Установка — отдельный extra: `pip install -e ".[llamaindex]"`. Тесты
(`tests/test_llamaindex_experimental.py`) используют `pytest.importorskip` и
`llama_index.core.embeddings.MockEmbedding`, чтобы не тянуть `torch` и не падать в окружениях без
extra.

При реализации найдены и исправлены два бага, важных как общий инвариант:
1. `tags`-список ломает запись в Chroma (нужен `tags_csv`, как в основном `chroma_adapter.py`).
2. Front matter должен отделяться от текста **до** чанкинга — иначе YAML-заголовок попадает в
   индексируемый текст.

**Решение о будущем этого модуля (промоутить в основной pipeline или оставить экспериментальным)
не принято** — пункт в Roadmap.

---

# 15. Retrieval engine

`retrieval/context_builder.py::RetrievalEngine` — все 5 режимов реализованы:

```text
vector                — VectorRetriever
bm25                   — BM25Retriever (корпус строится на лету из sample_points() тех же чанков,
                         что видны через filter pushdown; rank_bm25.BM25Okapi)
hybrid                 — HybridRetriever, fusion: rrf (по умолчанию) | relative_score | weighted
hybrid_with_rerank     — hybrid + Reranker.rerank()
multi_query            — QueryExpander (rule-based: убирает "find/search for/...", делит по
                         "and"/"or", keyword-only вариант) → hybrid по каждому варианту → RRF
```

`RetrievalRequest`/`ScoredChunk`/`RetrievalDiagnostics`/`ContextResult` реализованы без отклонений
от исходной спецификации (раздел 15.1 prompt_01.md).

---

# 16. Reranker

Реализовано: `none` (`NoneReranker`, просто обрезка до `top_n`) и `bge_reranker_local`
(`CrossEncoderReranker` на `sentence-transformers.CrossEncoder`, device `cpu` по умолчанию).
`qwen3_reranker_local` объявлен в конфиге, но отдельно не реализован — использует тот же
`CrossEncoderReranker` (provider `huggingface`), просто с другим `model_name`.

---

# 17. Context builder

Реализовано: `dedup_chunks()` (по `chunk_id`), `group_neighbors()` (схлопывает соседние
`chunk_index` одного документа, сохраняя лучший score), `build_context_text()` (token budget —
грубая оценка 4 символа/токен через `estimate_tokens()`, переиспользуется генерацией для отчёта по
токенам), `RetrievalDiagnostics` с полным списком применённых фильтров.

---

# 18. Generation / LLM routing

`generation/llm_router.py::LLMRouter` — реализован провайдер `openai_compatible`
(`openai_compatible.py`, `httpx`-клиент, покрывает LM Studio/Ollama/vLLM/llama.cpp server/OpenAI).
`anthropic` объявлен в `llm_targets.yaml`, но роутинг для него **не реализован** —
`LLMRouter.generate()` бросает `NotImplementedError` при попытке использовать не-`openai_compatible`
provider (это задокументированный TODO, а не забытая часть).

---

# 19. Privacy Guard

Реализовано **точно по исходной спецификации**, без отклонений — единственный раздел, где
реализация полностью совпала с планом с первого раза. `generation/privacy_guard.py::PrivacyGuard`:

```text
1. privacy_level != "external"                 → разрешено всегда
2. privacy_mode == LOCAL_ONLY                    → блокировка безусловно
3. domain.frontier_allowed == False              → требует external_confirmation=True,
                                                    даже если глобальный режим разрешительнее
4. иначе: ALLOW_FRONTIER_WITH_CONFIRMATION       → требует confirmation
          ALLOW_FRONTIER                          → разрешено безусловно
```

Default: `LOCAL_ONLY` (в `app.yaml` и `.env.example`). Вся матрица (режим × домен × confirmation)
покрыта тестами `tests/test_generation.py`.

---

# 20-23. Gradio web application

Реализовано три Gradio-страницы поверх FastAPI (`gr.mount_gradio_app(fastapi_app,
build_gradio_app(), path="/")`), без сокращения функциональности:

- **Search & Ask** (`search_page.py`) — все контролы из раздела 21.1 prompt_01.md реализованы;
  `run_search_and_ask()` вынесена в module-level функцию (не замыкание) специально для
  юнит-тестируемости в обход Gradio event wiring. Чекбокс внешнего API появляется только для
  targets с `privacy_level: external` (динамический `.change()` на dropdown LLM target).
- **Dashboard** (`dashboard_page.py`) — `refresh_dashboard()`: coll stats, распределения через
  `gr.BarPlot`, последние ingestion-отчёты и failed files из `data/reports/*.json`, сэмпл чанков.
  2D-проекция (UMAP/t-SNE) — явный текстовый placeholder, не реализована (V2, как и допускал
  исходный промпт).
- **Data Management** (`ingest_page.py`) — вкладки "Add data" (dry-run и реальный ingest через тот
  же `IngestionPipeline`) и "Search & edit metadata / Delete" (правка метаданных через
  `update_payload()` по всем чанкам документа; delete по умолчанию soft, hard требует отдельного
  чекбокса подтверждения).

Бизнес-логика всех трёх страниц — module-level функции, принимающие `AppServices` явным
параметром (не глобальные замыкания) — решение, принятое в процессе, когда стало ясно, что
логику внутри `build_*_page()` нельзя протестировать без полного event wiring Gradio.

---

# 24. Multimodal ingestion

Статус по факту (см. также раздел 4):

```text
PDF      → pypdf, постранично. OCR для сканов — TODO (не реализовано).
Images   → pytesseract OCR (best-effort — если бинарник tesseract недоступен, пустой текст без
            падения). Captioning и image embedding — не реализованы.
Audio    → интерфейс есть (unsupported_loader), извлечения нет.
Video    → интерфейс есть (unsupported_loader), извлечения нет.
```

---

# 25. CLI

Реализовано без отклонений: `athena ingest|search|collections|dashboard` (Typer,
`cli/main.py`), entry point прописан в `pyproject.toml` (`[project.scripts] athena =
"de.ibikus.athena.cli.main:app"`). `cli/ingest.py`/`cli/search.py` используют те же
core-сервисы (`IngestionPipeline`, `RetrievalEngine`, `build_vector_store_gateway`), что и
веб-слой — дублирования бизнес-логики нет.

---

# 26. Configuration

Реализовано с одним структурным отличием от исходного плана: `retrieval`-настройки вынесены в
отдельный файл `configs/retrieval.yaml`, а не встроены в `app.yaml` (раздел 26.4 prompt_01.md
описывал их как подсекцию, но для единообразия с остальными YAML-конфигами вынесены отдельно).
Все остальные файлы (`app.yaml`, `vector_stores.yaml`, `domains.yaml`, `embedding_profiles.yaml`,
`chunking_profiles.yaml`, `reranker_profiles.yaml`, `llm_targets.yaml`) — как в исходном плане.

---

# 27. Observability and reports (batch ingestion)

Реализовано: `IngestionReport`/`IngestionError` (Pydantic), сохранение как JSON и Markdown в
`data/reports/{job_id}.{json,md}`. Логирование внутри ingestion — стандартное (не structlog/JSON —
это намеренно ограничено веб-слоем, см. раздел observability addendum ниже).

---

# 28. Tests

Фактический набор (вместо перечисленных в исходном промпте имён — сгруппировано по подсистемам,
конкретные test-функции см. в файлах):

| Файл | Покрывает |
|---|---|
| `test_config.py` | config loading, domains, `frontier_allowed` |
| `test_metadata.py` | sidecar/front-matter приоритет, `ChunkMetadata`, валидаторы |
| `test_stores.py` | построение фильтров, интерфейс gateway, soft delete + `deleted`-фильтрация |
| `test_ingestion.py` | полный прогон pipeline на embedded ChromaDB, dry-run не пишет в vector store |
| `test_retrieval.py` | дефолты `RetrievalRequest`, все 5 режимов end-to-end, embedding-profile mismatch |
| `test_generation.py` | вся матрица `PrivacyGuard` |
| `test_web_observability.py` | MDC-контекст, инкремент метрик, actuator/health/metrics endpoints |
| `test_llamaindex_experimental.py` | namespacing, ingestion+retrieval через LlamaIndex, изоляция от прода |

Используется реальный (embedded) экземпляр ChromaDB и детерминированный `FakeEmbeddingService`
(sha256-based) вместо моков HTTP-уровня — сеть и GPU не требуются. Qdrant в тестах не участвует.

---

# 29. README

Реализовано с расширением исходного плана: помимо `README.md` (английский) ведётся параллельный
`read_me.ru` (русский перевод, код/команды не переводятся) и отдельный
`architecture-blueprint.md` (человеко-читаемый архитектурный снимок, не инструкция для Claude
Code). Правило синхронизации `README.md` ↔ `read_me.ru` закреплено в `CLAUDE.md`.

---

# 30. MVP Scope — фактически реализовано

Всё из исходного списка MVP (раздел 30 prompt_01.md) реализовано и покрыто тестами:

```text
Core: Pydantic models, config loading, domain metadata, sidecar metadata          ✅
Ingestion: txt/md/pdf/docx, chunking, local embeddings, Qdrant+Chroma adapters,
           ingestion report                                                        ✅
Retrieval: vector search, metadata filters, hybrid search, reranker (none+1)       ✅
Generation: OpenAI-compatible LLM target routing, privacy guard                    ✅
Web: Gradio Search & Ask / Dashboard / Data Management                             ✅
CLI: ingest / search / collections                                                 ✅
```

Плюс сверх исходного MVP: наблюдаемость веб-приложения (structlog/MDC/Prometheus/actuator) —
изначально была отдельным дополнением к промпту, тоже полностью реализована.

## V2 — не реализовано (осознанно, роадмап)

```text
Продвинутая обработка audio/video (ASR, keyframes)
OCR fallback для сканированных PDF; извлечение pptx/xlsx
Нативные Qdrant sparse vectors
Бенчмаркинг reranking (RAGAS)
UMAP/t-SNE 2D-проекция в dashboard
PostgreSQL metadata store, MinIO/S3 raw file storage
Prometheus/Grafana — конфиги готовы, но не задеплоены/не проверены на реальном кластере
Multi-user authentication
Anthropic LLM routing (target объявлен, роутинг не реализован)
Решение по будущему experimental/llamaindex/ (промоутить или оставить как есть)
```

---

# 31. Important implementation rules — статус соблюдения

Все правила из исходного промпта соблюдены без отклонений, дополнено новыми, добавленными по
факту реализации:

```text
1. Ingestion/retrieval/generation не смешаны в одном файле                          — соблюдено
2. Gradio UI не вызывает Qdrant/Chroma напрямую                                      — соблюдено
3. Gradio UI использует core services (через AppServices)                           — соблюдено
4. CLI использует те же core services                                               — соблюдено
5. Модели/пути/endpoint'ы не захардкожены — всё через configs/*.yaml                — соблюдено
6. Все важные параметры — в YAML/env config                                         — соблюдено
7. Personal/job context не уходит наружу без подтверждения                          — соблюдено
8. Query embedding model форсированно совпадает с embedding profile коллекции       — соблюдено,
                                                                                       код бросает ValueError
9. См. п.8                                                                           — соблюдено
10. Смена embedding model → новый index/collection                                  — соблюдено
11. Delete по умолчанию — soft delete                                                — соблюдено
12. Retrieval results показывают source references и metadata                        — соблюдено
13. Ошибки понятны пользователю (UI не показывает stack trace)                       — соблюдено
14. Код расширяем, не demo-script                                                    — соблюдено

Дополнительно (не было в исходном промпте):
15. Пакет — de.ibikus.athena (reverse-domain), не просто athena
16. experimental/llamaindex/ физически изолирован через namespacing коллекций
    (`<collection>_llamaindex`), а не просто "выключен флагом"
17. Бизнес-логика Gradio-страниц — module-level функции, не замыкания (для тестируемости)
```

---

# 32. Expected result — фактически достигнуто

Всё из исходного списка (раздел 32 prompt_01.md) реализовано и подтверждено тестами/ручной
проверкой:

1. Qdrant или ChromaDB запускаются (Chroma — без внешнего сервера, "из коробки")           ✅
2. Local embedding profile настраивается через `configs/embedding_profiles.yaml`           ✅
3. Пакетная загрузка папки — `athena ingest`                                                ✅
4. Документы разбиваются на chunks                                                          ✅
5. Локальные embeddings строятся                                                            ✅
6. Chunks + vectors + metadata сохраняются                                                  ✅
7. Поиск через CLI — `athena search`                                                        ✅
8. Gradio web app запускается — `python -m de.ibikus.athena.web.app`                        ✅
9. В Web UI выбираются vector store/collection/domain/retrieval mode/top-k/reranker/target  ✅
10. Найденные chunks видны в UI                                                              ✅
11. Context + prompt отправляются в local или frontier LLM (с Privacy Guard)                ✅
12. Dashboard состояния vector store работает                                                ✅
13. Интерактивное добавление новых данных — Web UI 3                                          ✅
14. Поиск и редактирование metadata — Web UI 3                                                ✅
15. Soft delete работает                                                                     ✅

---

# 33. Дальнейшая доработка — принципы

При продолжении работы над Athena:

```text
config → models → vector gateway → ingestion → retrieval → generation routing → Gradio UI
```

— тот же порядок зависимостей, что и при первичной реализации. После каждого крупного изменения:
1. Прогонять `pytest` (см. раздел 15 blueprint / раздел 28 выше) — весь набор должен оставаться
   зелёным.
2. Обновлять `README.md` **и** `read_me.ru` синхронно (правило в `CLAUDE.md`).
3. Не трогать `experimental/llamaindex/` неявно — если меняется общая metadata-логика
   (`metadata/sidecar.py`, `ingestion/discovery.py`), проверить, что экспериментальный модуль,
   который её переиспользует, не сломался (`pytest tests/test_llamaindex_experimental.py`, если
   extra `llamaindex` установлен).
4. Не делать декоративных доработок — расширять только то, что реально востребовано (см. Roadmap
   V2 в разделе 30 выше как список кандидатов, а не обязательный порядок).

---

# Наблюдаемость веб-приложения — фактический статус

Дополнение из исходного промпта (разделы 1-14 после основного текста prompt_01.md) реализовано
практически без отклонений — это единственный крупный раздел, где план и реализация совпали почти
дословно. Кратко:

- **Structured logging** — `structlog`, JSON, поля `timestamp/level/logger/message/event` +
  контекстные (см. ниже). Не логируются prompt/context/API-ключи/содержимое файлов — только
  `query_length`, `prompt_hash` (`short_hash()`, sha256[:12]), счётчики.
- **MDC-контекст** — `web/observability/context.py::request_context()`, обёртка над
  `structlog.contextvars`. Поддерживает вложенность (проверено тестом — вложенный контекст не
  портит внешний после выхода из `with`-блока).
- **Actuator-эндпоинты** — `/health`, `/actuator/health` (per-component UP/DEGRADED — не роняет
  всё приложение при недоступном vector store), `/actuator/info`, `/actuator/metrics` (JSON-сводка).
- **Prometheus** — `/metrics`, метрики по группам `athena_web_*`, `athena_retrieval_*`,
  `athena_vector_search_*`, `athena_generation_*`, `athena_external_llm_blocked/confirmed_total`,
  `athena_web_ingest/_metadata_updates/_soft_deletes/_hard_deletes_total`. Labels — низкой
  кардинальности намеренно (никаких raw file names/prompts/document_id/chunk_id как label).
- **Grafana** — `observability/prometheus/prometheus.yml` + dashboard JSON + PromQL-README в
  `observability/grafana/`. **Не задеплоено и не проверено на реальном Prometheus/Grafana** —
  конфиги подготовлены, но живой прогон против настоящего стека не выполнялся (см. Roadmap).

Инструментирован только веб-слой (batch ingestion CLI — нет), как и требовал исходный промпт.
