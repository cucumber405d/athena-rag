# Athena — локальная масштабируемая RAG-платформа
#\\wsl.localhost\Ubuntu\home\cucum\projects\appaCl\athena

Ты — Claude Code. Работай как senior Python architect и implementation agent.

Твоя задача — спроектировать и реализовать проект **Athena**: локально-ориентированную масштабируемую RAG-платформу с пакетной загрузкой данных, Hybrid Search, локальными embedding-моделями, configurable vector stores, reranking, Filter Pushdown, multimodal ingestion и несколькими Gradio-веб-интерфейсами.

---

# 0. Первые действия

Перед написанием кода:

1. Полностью изучи репозиторий.
2. Найди и прочитай `CLAUDE.md`, если он существует.
3. Изучи текущую архитектуру, структуру пакетов, зависимости, конфигурации, тесты и стиль проекта.
4. Не переписывай весь проект вслепую.
5. Если проект уже существует — расширяй его аккуратно.
6. Если проект пустой или неподходящий — создай чистую Python-структуру с нуля.
7. После анализа коротко опиши план реализации и только потом переходи к изменениям.

Код, имена классов, файлов, переменных и конфигураций пиши на английском.
Комментарии и документацию можно писать на английском или русском, но предпочтительно на английском для технических частей.

---

# 1. Цель проекта

Создать **Athena**:

> Масштабируемую RAG-платформу для долгосрочного хранения, индексации, поиска и вопросно-ответной работы с большим количеством разнородных данных.

Система должна уметь работать с:

* текстовыми файлами;
* Markdown;
* PDF;
* DOCX;
* изображениями;
* аудиофайлами;
* видеофайлами;
* архивами;
* технической документацией;
* книгами;
* CV;
* вакансиями;
* личными данными;
* пользовательскими доменами.

Athena должна состоять из двух основных частей:

1. **Пакетное приложение для массовой загрузки данных**
2. **Онлайн-приложение с несколькими Gradio-вебмордами**

---

# 2. Основные архитектурные принципы

Реализуй систему согласно следующим принципам:

1. Embeddings должны быть локальными по умолчанию.
2. Vector store должен быть конфигурируемым.
3. Основные vector stores: **Qdrant** и **ChromaDB**.
4. Qdrant считать основным production-like backend.
5. ChromaDB использовать как локальный/dev/test backend.
6. Метаданные должны быть first-class citizen.
7. Filter Pushdown должен применяться везде, где это поддерживает backend.
8. Домен данных должен храниться как metadata/payload, а не только как физическая коллекция.
9. Raw files нельзя хранить только в vector database.
10. Embedding model является частью индекса.
11. Generation model выбирается отдельно и может меняться при каждом запросе.
12. Gradio UI должен позволять управлять параметрами retrieval и generation.
13. Использовать **LlamaIndex** как основной RAG-движок, где это уместно.
14. Использовать **Pydantic** для конфигурации, metadata models и request/response models.
15. Архитектура должна быть модульной и расширяемой.

---

# 3. Рекомендуемая структура проекта

Создай или адаптируй структуру примерно такого вида:

```text
athena/
  pyproject.toml
  README.md
  .env.example

  configs/
    app.yaml
    domains.yaml
    embedding_profiles.yaml
    vector_stores.yaml
    llm_targets.yaml
    chunking_profiles.yaml
    reranker_profiles.yaml

  data/
    raw/
    processed/
    chroma/
    reports/

  src/
    athena/
      __init__.py

      core/
        config/
          settings.py
          loader.py

        models/
          document.py
          chunk.py
          domain.py
          ingestion_job.py
          retrieval.py
          llm_target.py

        metadata/
          sidecar.py
          extractor.py
          validators.py

        ingestion/
          pipeline.py
          discovery.py
          loaders/
          parsers/
          chunkers/
          embeddings.py

        stores/
          vector_gateway.py
          qdrant_adapter.py
          chroma_adapter.py
          docstore.py
          raw_file_store.py

        retrieval/
          vector_retriever.py
          bm25_retriever.py
          hybrid_retriever.py
          reranker.py
          query_expander.py
          context_builder.py

        generation/
          llm_router.py
          openai_compatible.py
          privacy_guard.py

        web/
          app.py
          pages/
            search_page.py
            dashboard_page.py
            ingest_page.py

        cli/
          main.py
          ingest.py
          search.py

  tests/
    test_config.py
    test_metadata.py
    test_ingestion.py
    test_retrieval.py
```

Не обязательно делать всё сразу идеально, но заложи такую архитектурную логику.

---

# 4. Batch ingestion application

Первая часть проекта — пакетное приложение.

Оно должно уметь в пакетном режиме загружать большое количество файлов, извлекать из них данные, делить данные на чанки, строить embeddings и сохранять результат в vector store.

## 4.1 Поддерживаемые входные данные

Реализуй архитектуру loaders/parsers для следующих типов:

```text
Text:
  .txt, .md, .html, .csv, .json, .xml, .log

Documents:
  .pdf, .docx, .pptx, .xlsx

Images:
  .jpg, .jpeg, .png, .webp, .tiff

Audio:
  .mp3, .wav, .m4a, .ogg

Video:
  .mp4, .mkv, .mov, .avi

Archives:
  .zip, .tar, .gz
```

Для MVP можно реализовать полноценно:

* `.txt`
* `.md`
* `.pdf`
* `.docx`
* `.jpg`
* `.png`

Для остальных типов оставить расширяемые интерфейсы и понятные TODO.

---

# 5. Ingestion pipeline

Реализуй pipeline примерно такого вида:

```text
1. Discover
   Найти файлы, вычислить checksum/hash, определить file type.

2. Load
   Загрузить файл через соответствующий loader.

3. Extract
   Извлечь текст, страницы, OCR, transcript, metadata.

4. Normalize
   Очистить текст, нормализовать кодировки, удалить технический мусор.

5. Metadata Enrichment
   Добавить domain_id, source_id, file_path, language, document_type,
   tags, checksum, created_at, access_level.

6. Chunk
   Разделить документ на чанки.

7. Embed
   Построить локальные embeddings.

8. Upsert
   Сохранить chunks, vectors и metadata в Qdrant или ChromaDB.

9. Verify
   Проверить количество документов, чанков, ошибок.

10. Report
   Сформировать JSON/Markdown-отчёт по ingestion job.
```

---

# 6. Домены данных

Athena должна поддерживать домены данных.

Примеры доменов:

```text
job        # работа, вакансии, CV, Anschreiben, интервью, рекрутеры
personal   # личные документы, заметки, сканы, фото
tech       # техническая документация, книги, статьи, курсы
media      # фото, аудио, видео
user       # пользовательская область
```

Домен должен храниться как metadata field:

```text
domain_id
```

Не делай домен только через физическую коллекцию.

---

# 7. Metadata sidecar files

Для batch-загрузки реализуй поддержку sidecar metadata-файлов.

## 7.1 Metadata для папки

Пример:

```yaml
# /data/books/.athena.yaml

domain_id: tech
language: mixed
tags:
  - books
  - ai
  - programming
access_level: private
chunking_profile: book_default
embedding_profile: bge_m3_local
```

## 7.2 Metadata для отдельного файла

Пример:

```yaml
# my_cv.pdf.athena.yaml

domain_id: job
document_type: cv
language: de
tags:
  - lebenslauf
  - java
  - ai
source: manual_upload
access_level: private
```

## 7.3 Markdown front matter

Также поддержи Markdown с YAML front matter:

```markdown
---
domain_id: job
document_type: vacancy
language: de
tags:
  - java
  - spring
  - ai
---

# Vacancy notes

This vacancy is interesting because of Java + AI + remote work.
```

Sidecar metadata должны иметь приоритет над автоматическим определением metadata.

---

# 8. Metadata schema

Создай Pydantic-модели для документов, чанков и retrieval-запросов.

Минимальная модель chunk metadata:

```python
class ChunkMetadata(BaseModel):
    chunk_id: str
    document_id: str
    source_id: str

    domain_id: str
    collection_name: str

    file_name: str
    file_path: str
    file_type: str
    mime_type: str | None = None
    checksum: str

    language: str | None = None
    document_type: str | None = None
    tags: list[str] = []

    page_number: int | None = None
    start_time_sec: float | None = None
    end_time_sec: float | None = None

    chunk_index: int
    chunking_profile: str
    embedding_profile: str
    embedding_model: str
    embedding_dimension: int

    created_at: datetime
    updated_at: datetime
    deleted: bool = False
    access_level: str = "private"
```

Эта metadata должна сохраняться:

* в Qdrant payload;
* в ChromaDB metadata;
* опционально в локальный PostgreSQL.

---

# 9. Filter Pushdown

Filter Pushdown обязателен.

Фильтры должны применяться на уровне vector store, а не только после получения результатов.

Поддерживаемые фильтры:

```text
domain_id
document_type
language
tags
access_level
deleted
source_id
file_type
created_at
updated_at
page_number
```

Пример логики:

```text
User query:
  "найди мои немецкие CV под AI Engineer"

Filters:
  domain_id = "job"
  document_type = "cv"
  language = "de"
  deleted = false
  access_level <= current_user_access
```

Qdrant adapter должен преобразовывать эти фильтры в Qdrant payload filters.

Chroma adapter должен преобразовывать эти фильтры в Chroma `where` filters, насколько это возможно.

---

# 10. Vector stores

Реализуй слой абстракции:

```python
class VectorStoreGateway:
    def create_collection(...)
    def upsert_chunks(...)
    def delete_by_document_id(...)
    def delete_by_filter(...)
    def search_vector(...)
    def search_hybrid(...)
    def update_payload(...)
    def get_collection_stats(...)
    def get_domains(...)
    def sample_points(...)
```

Реализуй два backend adapter:

```text
QdrantVectorStoreAdapter
ChromaVectorStoreAdapter
```

## 10.1 Qdrant

Qdrant — основной backend.

Должен поддерживать:

* dense vectors;
* metadata payload;
* payload filters;
* collection stats;
* soft delete через payload;
* optional sparse/hybrid search;
* named vectors, если это удобно.

## 10.2 ChromaDB

ChromaDB — локальный/dev backend.

Должен поддерживать:

* persistent local storage;
* collections;
* metadata filters;
* vector search;
* basic stats;
* soft delete через metadata.

---

# 11. Collections

Не создавай отдельную коллекцию на каждый домен по умолчанию.

Рекомендуемая схема:

```text
athena_chunks_bge_m3_v1
athena_chunks_qwen3_06b_v1
athena_media_vectors_v1
athena_experiments_v1
```

Домен должен быть metadata field:

```json
{
  "domain_id": "job",
  "document_type": "cv",
  "language": "de",
  "tags": ["java", "ai"],
  "source_id": "file_123",
  "chunk_id": "chunk_456"
}
```

---

# 12. Local embedding models

Embeddings должны быть локальными по умолчанию.

Создай понятие:

```text
embedding_profile
```

Embedding profile является частью индекса.
Если коллекция создана через одну embedding model, запросы к ней должны использовать ту же embedding model.

Правило:

```text
Embedding model = часть индекса.
Смена embedding model требует нового индекса или reindex.

Generation model = часть ответа.
Её можно менять на лету.
```

## 12.1 Default embedding model

Основной рекомендуемый профиль:

```yaml
bge_m3_local:
  title: "BGE-M3 Local"
  provider: "huggingface"
  model_name: "BAAI/bge-m3"
  dimension: 1024
  device: "cuda"
  normalize: true
  supports_multilingual: true
  supports_sparse: true
  supports_multivector: true
  default_for_domains:
    - job
    - personal
    - tech
```

## 12.2 Experimental embedding models

Добавь конфигурационные профили для экспериментов:

```yaml
qwen3_embedding_06b_local:
  title: "Qwen3 Embedding 0.6B Local"
  provider: "ollama"
  model_name: "qwen3-embedding:0.6b"
  device: "local"
  experimental: true

qwen3_embedding_4b_local:
  title: "Qwen3 Embedding 4B Local"
  provider: "tei"
  model_name: "Qwen/Qwen3-Embedding-4B"
  device: "cuda"
  experimental: true
```

Для MVP можно реализовать только `bge_m3_local`, но архитектура должна позволять добавлять другие профили.

---

# 13. Embedding service modes

Поддержи несколько режимов работы embeddings.

## 13.1 In-process mode

Простой MVP-режим:

```text
Athena напрямую загружает локальную HuggingFace embedding model.
```

## 13.2 External embedding service

Более production-like режим:

```text
athena-ingest  ┐
athena-web     ├──► athena-embedding-service
athena-eval    ┘
```

Embedding service может быть реализован позже через:

* Text Embeddings Inference;
* custom FastAPI service;
* Ollama embeddings;
* другой OpenAI-compatible/local endpoint.

Для MVP достаточно сделать интерфейс и один рабочий локальный implementation.

---

# 14. Chunking profiles

Добавь configurable chunking profiles.

Пример:

```yaml
default_text:
  type: token
  chunk_size: 800
  chunk_overlap: 120

book_default:
  type: semantic_or_token
  chunk_size: 1200
  chunk_overlap: 150
  preserve_headings: true

cv_default:
  type: section_aware
  chunk_size: 500
  chunk_overlap: 80
  preserve_sections: true

pdf_page_aware:
  type: page_aware
  chunk_size: 800
  chunk_overlap: 100
  preserve_page_number: true

audio_transcript:
  type: time_window
  window_seconds: 60
  overlap_seconds: 10

video_scene:
  type: scene_or_time_window
  keyframe_interval_seconds: 30
```

Для MVP реализуй:

* `default_text`
* `pdf_page_aware`
* `book_default`

---

# 15. Retrieval engine

Реализуй retrieval engine, который поддерживает разные режимы поиска.

Минимальные режимы:

```text
vector
bm25
hybrid
hybrid_with_rerank
multi_query
```

## 15.1 Retrieval settings

Создай Pydantic-модель:

```python
class RetrievalRequest(BaseModel):
    query: str
    domain_id: str | None = None
    collection_name: str
    vector_store: str
    retrieval_mode: str

    vector_top_k: int = 30
    bm25_top_k: int = 30
    rerank_top_n: int = 8

    use_filter_pushdown: bool = True
    filters: dict[str, Any] = {}

    embedding_profile: str
    reranker_profile: str | None = None
```

## 15.2 Hybrid Search

Для Qdrant реализуй native hybrid/sparse search, если это удобно.

Если native hybrid search слишком сложен для первого этапа, реализуй fusion на уровне приложения:

```text
vector results + BM25 results → RRF fusion → optional reranking
```

Поддержи fusion modes:

```text
rrf
relative_score
weighted
```

Для MVP достаточно `rrf`.

---

# 16. Reranker

Добавь понятие:

```text
reranker_profile
```

Пример конфигурации:

```yaml
reranker_profiles:
  none:
    title: "No reranker"
    provider: "none"

  bge_reranker_local:
    title: "BGE Reranker Local"
    provider: "huggingface"
    model_name: "BAAI/bge-reranker-v2-m3"
    device: "cuda"

  qwen3_reranker_local:
    title: "Qwen3 Reranker Local"
    provider: "huggingface"
    model_name: "Qwen/Qwen3-Reranker-0.6B"
    device: "cuda"
    experimental: true
```

Для MVP можно реализовать:

* `none`
* один local reranker, если это быстро и стабильно

Если reranker не реализован, UI всё равно должен иметь настройку `No reranker`.

---

# 17. Context builder

После retrieval и reranking реализуй Context Builder.

Он должен:

1. Убирать дубликаты.
2. Сохранять source references.
3. Группировать соседние чанки одного документа.
4. Учитывать token budget.
5. Возвращать context block для LLM.
6. Возвращать диагностическую информацию.

Пример результата:

```text
Context:
  [1] source=my_cv.pdf page=2 score=0.87
      ...

  [2] source=vacancy_java_ai.md score=0.83
      ...

Diagnostics:
  vector_top_k=50
  bm25_top_k=50
  fusion=rrf
  reranker=bge_reranker_local
  final_chunks=8
```

---

# 18. Generation / LLM routing

Нужно явно отделить retrieval от generation.

Retrieval отвечает за поиск.
Generation отвечает за отправку prompt + найденный context в выбранную модель.

Добавь понятие:

```text
llm_target
```

Пользователь должен иметь возможность выбрать в вебморде, куда отправить найденный контекст:

* локальная LLM;
* LM Studio;
* Ollama;
* vLLM;
* llama.cpp server;
* OpenAI-compatible endpoint;
* frontier model;
* OpenAI;
* Anthropic;
* другой endpoint.

## 18.1 LLM targets config

Пример:

```yaml
llm_targets:
  local_lmstudio:
    title: "Local LM Studio"
    provider: "openai_compatible"
    base_url: "http://localhost:1234/v1"
    api_key_env: "LMSTUDIO_API_KEY"
    default_model: "local-model"
    privacy_level: "local"

  local_ollama:
    title: "Local Ollama"
    provider: "openai_compatible"
    base_url: "http://localhost:11434/v1"
    api_key: "ollama"
    default_model: "qwen3:8b"
    privacy_level: "local"

  local_vllm:
    title: "Local vLLM"
    provider: "openai_compatible"
    base_url: "http://localhost:8000/v1"
    api_key_env: "VLLM_API_KEY"
    default_model: "Qwen/Qwen3-8B"
    privacy_level: "local_or_lan"

  frontier_openai:
    title: "OpenAI Frontier"
    provider: "openai"
    base_url: "https://api.openai.com/v1"
    api_key_env: "OPENAI_API_KEY"
    default_model: "gpt-4.1"
    privacy_level: "external"

  frontier_anthropic:
    title: "Anthropic Frontier"
    provider: "anthropic"
    api_key_env: "ANTHROPIC_API_KEY"
    default_model: "claude-opus-4"
    privacy_level: "external"
```

Для MVP реализуй OpenAI-compatible routing.
Это позволит использовать LM Studio, Ollama, vLLM и другие OpenAI-compatible endpoints через один интерфейс.

---

# 19. Privacy Guard

Если пользователь выбирает внешний LLM target, Athena должна явно предупреждать, что найденный context будет отправлен наружу.

Добавь privacy modes:

```text
LOCAL_ONLY
ALLOW_FRONTIER_WITH_CONFIRMATION
ALLOW_FRONTIER
```

Default:

```text
LOCAL_ONLY
```

Для доменов `personal` и `job` по умолчанию запрещай отправку во внешние модели без явного подтверждения.

Для домена `tech` можно разрешить отправку наружу, но только если это указано в конфиге.

В Gradio UI добавь checkbox:

```text
[ ] I understand that retrieved context will be sent to an external API
```

Если target имеет `privacy_level: external`, а checkbox не включён — не отправлять запрос.

---

# 20. Gradio web application

Вторая часть проекта — онлайн-приложение на Python + Gradio.

Оно должно содержать несколько веб-морд.

---

# 21. Web UI 1 — Search & Ask

Первая веб-морда позволяет:

1. Ввести prompt/query в текстовое поле.
2. Опционально загрузить картинку, видео, аудио или документ.
3. Найти релевантные chunks через RAG.
4. Управлять retrieval-параметрами.
5. Смотреть найденные chunks.
6. Отправлять context + prompt в выбранную LLM.
7. Выбирать local или frontier LLM target.
8. Смотреть diagnostics.

## 21.1 UI controls

Добавь controls:

```text
Prompt:
  textarea

Upload:
  file/image/audio/video upload

Vector Store:
  dropdown: qdrant, chroma

Collection:
  dropdown from available collections

Embedding Profile:
  read-only field from selected collection

Domain:
  dropdown: all, job, personal, tech, media, user

Document Type:
  dropdown / optional text

Language:
  dropdown: auto, de, en, ru, mixed

Search Mode:
  vector, bm25, hybrid, hybrid_with_rerank, multi_query

Vector Top-K:
  slider / number input

BM25 Top-K:
  slider / number input

Fusion:
  dropdown: rrf, relative_score, weighted

Reranker:
  dropdown: none, bge_reranker_local, qwen3_reranker_local

Rerank Top-N:
  slider / number input

Use Filter Pushdown:
  checkbox

Action:
  Search only
  Search + Ask selected LLM
  Compare local vs frontier

LLM Target:
  dropdown from llm_targets

Model:
  dropdown or text input

Temperature:
  slider

Max Context Tokens:
  number input

External API confirmation:
  checkbox, visible only for external targets
```

## 21.2 Output sections

Покажи:

```text
Answer
Retrieved chunks
Chunk metadata
Scores
Source references
Context sent to LLM
Retrieval diagnostics
Errors/warnings
```

---

# 22. Web UI 2 — Vector Store Dashboard

Вторая веб-морда показывает состояние vector store.

Цель — красиво и понятно показать, что находится внутри Athena.

Показывать:

```text
Active backend
Collections
Number of documents
Number of chunks
Vector dimensions
Embedding profiles
Domains distribution
File types distribution
Languages distribution
Last ingestion jobs
Failed files
Storage size, if available
Sample chunks
```

## 22.1 Visualizations

Реализуй базовые визуализации:

```text
Bar chart: chunks by domain
Bar chart: documents by file type
Pie/bar chart: language distribution
Table: collections and stats
Table: latest ingestion jobs
Table: sample chunks
Optional: 2D projection of vector sample
```

Для 2D-визуализации можно использовать:

```text
UMAP or t-SNE
```

Если UMAP/t-SNE пока сложно — оставь placeholder и clean interface.

---

# 23. Web UI 3 — Data Management / Interactive Ingestion

Третья веб-морда позволяет интерактивно добавлять, искать, редактировать и удалять данные.

## 23.1 Add data

Поля:

```text
Upload files
Domain
Document type
Language
Tags
Access level
Chunking profile
Embedding profile
Vector store
Collection
Dry run
Ingest
```

## 23.2 Dry run

Перед реальной загрузкой показывать:

```text
Files found
Supported files
Unsupported files
Estimated chunks
Target vector store
Target collection
Domain
Chunking profile
Embedding profile
Warnings
```

## 23.3 Edit metadata

Реализуй поиск документов/chunks и возможность редактировать metadata:

```text
domain_id
tags
document_type
language
access_level
title
description
deleted
```

Если меняется только metadata — делай update payload/metadata.

Если меняется content — нужен re-ingestion.

## 23.4 Delete

Поддержи:

```text
Soft delete:
  deleted = true

Hard delete:
  remove vectors/chunks/document metadata
```

Default delete mode: soft delete.

---

# 24. Multimodal ingestion

Заложи архитектуру для multimodal data.

## 24.1 PDF

```text
PDF → pages → text blocks → page-aware chunks
Scanned PDF → OCR → page-aware chunks
Tables → markdown-like text
```

## 24.2 Images

```text
Image → OCR text
Image → generated caption
Image → optional image embedding
```

## 24.3 Audio

```text
Audio → ASR transcript
Transcript → time-window chunks
Metadata: start_time_sec, end_time_sec
```

## 24.4 Video

```text
Video → audio transcript
Video → keyframes
Video → scene/time chunks
Metadata: timestamp, frame_path, transcript segment
```

Для MVP реализуй текст/PDF/DOCX/images.
Для audio/video создай interfaces и placeholders.

---

# 25. CLI

Добавь CLI-команды.

Пример:

```bash
athena ingest --path ./data/raw/books --domain tech --collection athena_chunks_bge_m3_v1
athena ingest --path ./data/raw/job --domain job --dry-run
athena search "Java AI Engineer CV" --domain job --top-k 10
athena collections
athena dashboard
```

CLI должен использовать тот же core-код, что и Gradio UI.

---

# 26. Configuration

Создай конфигурации.

## 26.1 app.yaml

```yaml
app:
  name: Athena
  mode: local
  log_level: INFO
  privacy_mode: LOCAL_ONLY

storage:
  raw_data_dir: ./data/raw
  processed_dir: ./data/processed
  reports_dir: ./data/reports
```

## 26.2 vector_stores.yaml

```yaml
vector_store:
  backend: qdrant

  qdrant:
    url: http://localhost:6333
    api_key_env: QDRANT_API_KEY
    default_collection: athena_chunks_bge_m3_v1

  chroma:
    persist_dir: ./data/chroma
    default_collection: athena_dev_chunks_v1
```

## 26.3 domains.yaml

```yaml
domains:
  - id: job
    title: Job Search
    description: CV, vacancies, recruiter emails, interview notes
    default_access_level: private
    default_collection: athena_chunks_bge_m3_v1
    frontier_allowed: false

  - id: personal
    title: Personal Knowledge
    description: Personal notes, documents, scans
    default_access_level: private
    default_collection: athena_chunks_bge_m3_v1
    frontier_allowed: false

  - id: tech
    title: Technical Library
    description: Books, documentation, courses
    default_access_level: private
    default_collection: athena_chunks_bge_m3_v1
    frontier_allowed: true

  - id: user
    title: User Domain
    description: Custom user data
    default_access_level: private
    default_collection: athena_chunks_bge_m3_v1
    frontier_allowed: false
```

## 26.4 retrieval defaults

```yaml
retrieval:
  default_mode: hybrid
  vector_top_k: 30
  bm25_top_k: 30
  rerank_top_n: 8
  fusion: rrf
  filter_pushdown: true
```

---

# 27. Observability and reports

Добавь простое логирование и ingestion reports.

Минимально:

```text
logs:
  ingestion started
  file discovered
  file skipped
  file parsed
  chunks created
  embeddings created
  upsert done
  errors

reports:
  ingestion_job_id
  started_at
  finished_at
  files_total
  files_processed
  files_failed
  chunks_created
  target_collection
  embedding_profile
  errors
```

Report сохранять как JSON и Markdown.

---

# 28. Tests

Добавь тесты для ключевых частей.

Минимум:

```text
test_config_loading
test_domain_config
test_sidecar_metadata_loading
test_chunk_metadata_model
test_filter_building
test_vector_gateway_interface
test_soft_delete_filter
test_retrieval_request_model
```

Если Qdrant/Chroma недоступны, используй mocks/fakes.

---

# 29. README

Обнови README.

README должен содержать:

```text
What is Athena
Architecture overview
Installation
Configuration
How to run Qdrant locally
How to run batch ingestion
How to run Gradio web app
How to configure local embeddings
How to configure local LLM target
How to configure frontier LLM target
Privacy warning
Examples
Known limitations
Roadmap
```

---

# 30. MVP Scope

Не пытайся реализовать всё идеально сразу.

## MVP должен включать:

```text
Core:
  Pydantic models
  config loading
  domain metadata
  sidecar metadata

Ingestion:
  txt/md/pdf/docx basic ingestion
  chunking
  local embeddings
  Qdrant adapter
  Chroma adapter if not too expensive
  ingestion report

Retrieval:
  vector search
  metadata filters
  basic hybrid search or placeholder
  optional reranker or No reranker

Generation:
  OpenAI-compatible LLM target routing
  privacy guard

Web:
  Gradio Search & Ask page
  Gradio Dashboard page
  Gradio Data Management page

CLI:
  ingest
  search
  collections
```

## Можно оставить на V2:

```text
Advanced audio/video processing
Full multimodal vector search
Native Qdrant sparse vectors
Advanced reranking
UMAP/t-SNE visualization
Kubernetes deployment
PostgreSQL metadata store
MinIO/S3 raw file storage
Prometheus/Grafana
Multi-user authentication
```

---

# 31. Important implementation rules

Следуй этим правилам:

1. Не смешивай ingestion, retrieval и generation в одном большом файле.
2. Не делай прямой вызов Qdrant/Chroma из Gradio UI.
3. Gradio UI должен использовать core services.
4. CLI должен использовать те же core services.
5. Не хардкодь модели, пути и endpoint'ы в коде.
6. Все важные параметры должны быть в YAML/env config.
7. Не отправляй personal/job context во внешний API без подтверждения.
8. Не разрешай query embedding model, отличающуюся от embedding profile коллекции.
9. Если выбранная collection использует `bge_m3_local`, query embedding тоже должен быть `bge_m3_local`.
10. Если пользователь хочет другую embedding model — создай новый index/collection или reindex flow.
11. Все delete operations по умолчанию должны быть soft delete.
12. Все retrieval results должны показывать source references и metadata.
13. Ошибки должны быть понятными пользователю.
14. Код должен быть расширяемым, а не одноразовым demo-script.

---

# 32. Expected result

После выполнения задачи проект должен позволять:

1. Запустить Qdrant или ChromaDB.
2. Настроить local embedding profile.
3. Пакетно загрузить папку с файлами.
4. Разбить документы на chunks.
5. Построить локальные embeddings.
6. Сохранить chunks + vectors + metadata.
7. Выполнить поиск через CLI.
8. Запустить Gradio web app.
9. В Web UI выбрать:

   * vector store;
   * collection;
   * domain;
   * retrieval mode;
   * top-k;
   * reranker;
   * LLM target.
10. Посмотреть найденные chunks.
11. Отправить context + prompt в выбранную local или frontier LLM.
12. Посмотреть dashboard состояния vector store.
13. Интерактивно добавить новые данные.
14. Найти и отредактировать metadata.
15. Выполнить soft delete.

---

# 33. Final instruction

Реализуй Athena итеративно.

Сначала создай устойчивый фундамент:

```text
config → models → vector gateway → ingestion → retrieval → generation routing → Gradio UI
```

После каждого крупного этапа проверяй, что проект запускается, тесты проходят, а README отражает текущее состояние.

Не делай декоративную демку.
Делай расширяемую RAG-платформу, которую можно развивать дальше.

# Дополнение к Athena: Observability для Web-приложения

Добавь observability-слой **только для web-приложения Athena**.

Это дополнение касается Gradio/FastAPI web-части проекта:

```text
src/athena/web/
src/athena/generation/
src/athena/retrieval/
src/athena/stores/
```

Не меняй batch ingestion CLI без необходимости.
Не добавляй тяжёлую observability-инфраструктуру в ingestion pipeline, если это не требуется для web-запросов.

---

# 1. Цель

Нужно добавить в web-приложение Athena:

1. Структурированный JSON-логгинг.
2. MDC-like context через `contextvars`.
3. Actuator-like endpoints.
4. Prometheus metrics endpoint.
5. Пользовательские метрики для RAG/web-запросов.
6. Подготовку к Grafana dashboards.
7. Корреляцию логов, метрик и пользовательских действий.

Важно: Athena написана на Python + Gradio, поэтому Spring Boot Actuator и Java MDC напрямую не используются.
Нужно реализовать Python/FastAPI-эквиваленты:

```text
Spring Actuator equivalent → FastAPI health/info/metrics endpoints
Java MDC equivalent        → Python contextvars + structured logging
Micrometer/Prometheus      → prometheus_client / OpenMetrics endpoint
Grafana                    → dashboard JSON / documentation / Prometheus datasource
```

---

# 2. Архитектурное требование

Если текущее Gradio-приложение запускается напрямую, оберни его в FastAPI app или используй FastAPI mount:

```text
FastAPI app
  ├── /health
  ├── /actuator/health
  ├── /actuator/info
  ├── /actuator/metrics
  ├── /metrics
  └── mounted Gradio app
```

Gradio UI должен продолжать работать как раньше.

---

# 3. Structured Logging

Добавь структурированный JSON-логгинг для web-приложения.

Используй один из вариантов:

```text
preferred:
  structlog

acceptable:
  standard logging + JSON formatter
```

Логи должны быть JSON-совместимыми и содержать поля:

```text
timestamp
level
logger
message
event
request_id
trace_id
session_id
user_action
domain_id
collection_name
vector_store
retrieval_mode
llm_target
model
duration_ms
status
error_type
error_message
```

Не логируй чувствительные данные:

```text
DO NOT log:
  full prompt
  full retrieved context
  API keys
  personal documents
  raw chunk text
  uploaded file contents
```

Можно логировать безопасные укороченные значения:

```text
query_length
context_token_count
chunks_returned
prompt_hash
file_count
file_types
```

---

# 4. MDC-like Context

Реализуй аналог Java MDC через Python `contextvars`.

Создай модуль, например:

```text
src/athena/web/observability/context.py
```

Он должен управлять request context:

```text
request_id
trace_id
session_id
user_action
domain_id
collection_name
vector_store
retrieval_mode
llm_target
model
```

Каждый web-запрос должен получать `request_id`.

Если frontend/user action создаёт retrieval-запрос, добавляй:

```text
retrieval_request_id
generation_request_id
```

Логи внутри retrieval/generation/vector store должны автоматически включать этот context.

Пример желаемого поведения:

```text
User clicks "Search + Ask LLM"
  request_id=...
  session_id=...
  user_action=search_and_ask
  domain_id=job
  collection_name=athena_chunks_bge_m3_v1
  retrieval_mode=hybrid_with_rerank
  llm_target=local_lmstudio
```

Все последующие logs внутри этого запроса должны содержать те же context fields.

---

# 5. Actuator-like Endpoints

Добавь endpoints:

```text
GET /health
GET /actuator/health
GET /actuator/info
GET /actuator/metrics
GET /metrics
```

## 5.1 `/health`

Должен возвращать простой статус:

```json
{
  "status": "UP"
}
```

## 5.2 `/actuator/health`

Должен возвращать подробный статус компонентов:

```json
{
  "status": "UP",
  "components": {
    "web": {
      "status": "UP"
    },
    "vector_store": {
      "status": "UP",
      "backend": "qdrant"
    },
    "embedding_profile": {
      "status": "UP",
      "active": "bge_m3_local"
    },
    "llm_targets": {
      "status": "UP",
      "configured": ["local_lmstudio", "local_ollama", "frontier_openai"]
    }
  }
}
```

Если Qdrant/Chroma недоступен, статус должен быть `DEGRADED`, а не обязательно падать полностью.

## 5.3 `/actuator/info`

Должен возвращать:

```json
{
  "app": {
    "name": "Athena",
    "version": "...",
    "mode": "local"
  },
  "python": "...",
  "vector_store_backend": "...",
  "default_collection": "...",
  "default_embedding_profile": "...",
  "privacy_mode": "LOCAL_ONLY"
}
```

## 5.4 `/actuator/metrics`

Можно вернуть краткий JSON summary пользовательских метрик:

```json
{
  "requests_total": 123,
  "retrieval_requests_total": 45,
  "generation_requests_total": 30,
  "errors_total": 2,
  "avg_retrieval_latency_ms": 120.5,
  "avg_generation_latency_ms": 3500.0
}
```

## 5.5 `/metrics`

Должен отдавать Prometheus/OpenMetrics формат.

---

# 6. Prometheus Metrics

Добавь Prometheus metrics через `prometheus_client`.

Создай модуль:

```text
src/athena/web/observability/metrics.py
```

Добавь как минимум следующие метрики.

## 6.1 Web request metrics

```text
athena_web_requests_total
athena_web_request_duration_seconds
athena_web_errors_total
```

Labels:

```text
route
method
status
```

## 6.2 Retrieval metrics

```text
athena_retrieval_requests_total
athena_retrieval_duration_seconds
athena_retrieval_chunks_returned
athena_retrieval_errors_total
```

Labels:

```text
vector_store
collection
domain
retrieval_mode
reranker
```

## 6.3 Vector store metrics

```text
athena_vector_search_requests_total
athena_vector_search_duration_seconds
athena_vector_search_errors_total
```

Labels:

```text
backend
collection
operation
```

Operations:

```text
search_vector
search_hybrid
upsert
delete
update_payload
stats
```

## 6.4 LLM generation metrics

```text
athena_generation_requests_total
athena_generation_duration_seconds
athena_generation_errors_total
athena_generation_context_tokens
athena_generation_output_tokens
```

Labels:

```text
llm_target
model
privacy_level
```

## 6.5 Privacy metrics

```text
athena_external_llm_blocked_total
athena_external_llm_confirmed_total
```

Labels:

```text
domain
llm_target
privacy_mode
```

## 6.6 Data management metrics

For Web UI 3:

```text
athena_web_ingest_requests_total
athena_web_ingest_files_uploaded_total
athena_web_ingest_errors_total
athena_web_metadata_updates_total
athena_web_soft_deletes_total
athena_web_hard_deletes_total
```

Labels:

```text
domain
collection
file_type
```

Be careful with label cardinality.

Do not use raw file names, user prompts, document IDs or chunk IDs as Prometheus labels.

---

# 7. Grafana

Добавь базовую подготовку для Grafana.

Создай директорию:

```text
observability/
  prometheus/
    prometheus.yml
  grafana/
    dashboards/
      athena-web-dashboard.json
    README.md
```

## 7.1 Prometheus config

Добавь пример `prometheus.yml`:

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: "athena-web"
    metrics_path: "/metrics"
    static_configs:
      - targets: ["localhost:7860"]
```

Если FastAPI/Gradio работает на другом порту, укажи это в README.

## 7.2 Grafana dashboard

Создай простой Grafana dashboard JSON или README с описанием панелей.

Панели:

```text
Web requests total
Web request latency p50/p95/p99
Retrieval requests by mode
Retrieval latency
Chunks returned per request
Vector store search latency
Generation requests by LLM target
Generation latency
External LLM blocked/confirmed
Errors by component
```

Если полноценный dashboard JSON сложно сгенерировать корректно, создай README с готовыми PromQL-запросами.

Примеры PromQL:

```promql
rate(athena_web_requests_total[5m])
histogram_quantile(0.95, rate(athena_web_request_duration_seconds_bucket[5m]))
rate(athena_retrieval_requests_total[5m])
histogram_quantile(0.95, rate(athena_retrieval_duration_seconds_bucket[5m]))
rate(athena_generation_requests_total[5m])
histogram_quantile(0.95, rate(athena_generation_duration_seconds_bucket[5m]))
rate(athena_web_errors_total[5m])
```

---

# 8. Where to instrument

Instrument только web-path.

Обязательно добавить logging + metrics вокруг:

```text
Search & Ask action
Retrieval execution
Hybrid search
Reranking
Context building
LLM routing
Privacy guard blocking/allowing
Data upload from Web UI 3
Metadata update
Soft delete
Hard delete
Dashboard stats loading
```

Не надо добавлять метрики внутрь каждой мелкой функции.

---

# 9. Error Handling

Все ошибки web-приложения должны:

1. Логироваться структурированно.
2. Увеличивать соответствующий Prometheus counter.
3. Возвращать понятное сообщение в Gradio UI.
4. Не раскрывать секреты и внутренние stack traces пользователю.

Для логов можно сохранять:

```text
error_type
error_message
component
request_id
trace_id
```

Stack trace допустим только в server logs, не в UI.

---

# 10. Configuration

Добавь observability-конфиг:

```yaml
observability:
  enabled: true

  logging:
    format: json
    level: INFO
    include_context: true
    redact_sensitive_data: true

  actuator:
    enabled: true
    base_path: /actuator

  prometheus:
    enabled: true
    metrics_path: /metrics

  grafana:
    enabled: true
```

Добавь `.env.example`:

```env
ATHENA_LOG_LEVEL=INFO
ATHENA_OBSERVABILITY_ENABLED=true
ATHENA_PROMETHEUS_ENABLED=true
```

---

# 11. README update

Обнови README разделом:

```text
Observability
  - Structured JSON logging
  - MDC-like context
  - Actuator-like endpoints
  - Prometheus metrics
  - Grafana dashboard
  - How to run Prometheus
  - How to connect Grafana
  - Example queries
```

Добавь примеры запуска:

```bash
python -m athena.web.app
```

И проверки:

```bash
curl http://localhost:7860/health
curl http://localhost:7860/actuator/health
curl http://localhost:7860/actuator/info
curl http://localhost:7860/metrics
```

---

# 12. Tests

Добавь тесты:

```text
test_health_endpoint
test_actuator_info_endpoint
test_metrics_endpoint
test_request_context_is_added_to_logs
test_privacy_block_counter
test_retrieval_metrics_increment
test_generation_metrics_increment
```

Если полноценный web integration test сложен, добавь unit tests для context, metrics wrapper и health service.

---

# 13. Important constraints

1. Это дополнение касается только web-приложения.
2. Не ломай existing Gradio UI.
3. Не загрязняй Prometheus labels высококардинальными значениями.
4. Не логируй prompt, raw context, API keys и contents of uploaded files.
5. Actuator-like endpoints должны работать независимо от Gradio pages.
6. Metrics endpoint должен быть совместим с Prometheus.
7. Все web-запросы должны иметь request_id.
8. Все retrieval/generation logs должны быть связаны через MDC-like context.
9. Если Qdrant/Chroma/LLM target недоступны, health должен показывать `DEGRADED`, а UI должен оставаться доступным.
10. Реализуй это итеративно и не переписывай ядро Athena без необходимости.

---

# 14. Expected result

После реализации web-приложение Athena должно иметь:

```text
Structured JSON logs
MDC-like request context
/health
/actuator/health
/actuator/info
/actuator/metrics
/metrics
Prometheus-compatible metrics
Grafana/Prometheus example configs
Custom RAG metrics
Privacy metrics
README documentation
Basic tests
```

Цель — сделать web-приложение наблюдаемым как нормальный production-like сервис, даже если оно запускается локально.
