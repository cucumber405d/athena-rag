# Athena — локально-ориентированная масштабируемая RAG-платформа

Athena — это локально-ориентированная масштабируемая платформа Retrieval-Augmented Generation:
пакетная загрузка разнородных данных (текст, PDF, DOCX, изображения с OCR и другое), гибридный поиск
(BM25 + dense-векторы), локальные embeddings, подключаемые vector stores, опциональный reranking,
filter pushdown и три Gradio веб-интерфейса поверх FastAPI-приложения с production-style
observability.

## Статус

**MVP реализован.** Core config/models, ingestion pipeline, retrieval engine, generation routing +
Privacy Guard, CLI, три Gradio UI и web observability-слой (структурированное логирование,
actuator endpoints, Prometheus metrics) реализованы и покрыты тестами.

## Обзор архитектуры

Подробности: [architecture-blueprint.md](./architecture-blueprint.md)

```
config → models → vector gateway → ingestion → retrieval → generation routing → Gradio UI
```

```text
src/de/ibikus/athena/
  core/           загрузчик Pydantic-конфигов + модели domain/document/chunk/retrieval/llm_target
  metadata/       sidecar (.athena.yaml) + разбор markdown front matter, валидаторы
  ingestion/      discovery → load → extract → normalize → chunk → embed → upsert → report
  stores/         VectorStoreGateway + адаптеры Qdrant/Chroma, docstore, raw file store
  retrieval/      vector/BM25/hybrid retrievers, RRF fusion, reranker, context builder
  generation/     LLM router (OpenAI-compatible), Privacy Guard
  web/            FastAPI-приложение + 3 Gradio-страницы + observability (logging/metrics/health)
  cli/            CLI `athena` — использует те же core-сервисы, что и веб-приложение
```

Vector stores подключаются через абстракцию `VectorStoreGateway`: **Qdrant** — production-like
backend, **ChromaDB** — локальный/dev backend. Embedding-модель, использованная для построения
коллекции, является частью индекса этой коллекции — запросы к ней обязаны использовать тот же
`embedding_profile` (см. `RetrievalEngine._check_embedding_profile_consistency`).

Generation намеренно отделён от retrieval: `RetrievalEngine` всегда возвращает только
`ContextResult`; `LLMRouter` + `PrivacyGuard` независимо решают, отправлять ли контекст и куда.

## Установка

```bash
pip install -e .
# более тяжёлые зависимости, используемые профилями по умолчанию (torch, sentence-transformers):
pip install sentence-transformers chromadb qdrant-client gradio fastapi uvicorn
```

Скопируйте `.env.example` в `.env` и настройте API-ключи / URL по необходимости.

### OCR (опционально, для изображений и сканированных PDF)

Загрузка изображений и OCR-fallback для сканированных страниц PDF используют `pytesseract`,
которому нужен системный бинарник `tesseract-ocr` — это не pip-пакет:

```bash
sudo apt install tesseract-ocr tesseract-ocr-deu tesseract-ocr-rus  # Debian/Ubuntu
```

OCR запускается с `lang="eng+deu+rus"` — под те же языки `de/en/ru`, что заявлены в UI платформы.
Без установленного бинарника вызовы OCR молча завершаются с ошибкой (исключение проглатывается) —
изображения и сканированные страницы PDF просто дают 0 чанков вместо явной ошибки.

## Конфигурация

Все настраиваемые параметры находятся в `configs/*.yaml`:

| Файл | Назначение |
|---|---|
| `app.yaml` | имя приложения, log level, privacy mode, пути хранения, флаги observability |
| `domains.yaml` | домены (`job`, `personal`, `tech`, `media`, `musik`, `books`, `user`), флаг `frontier_allowed` |
| `embedding_profiles.yaml` | локальные embedding-модели (`bge_m3_local` — по умолчанию) |
| `chunking_profiles.yaml` | `default_text`, `pdf_page_aware`, `book_default`, ... |
| `reranker_profiles.yaml` | `none` (по умолчанию) + локальные cross-encoder профили |
| `vector_stores.yaml` | настройки подключения Qdrant/Chroma, backend по умолчанию |
| `llm_targets.yaml` | локальные (LM Studio/Ollama/vLLM) и frontier (OpenAI/Anthropic) targets |
| `retrieval.yaml` | режим retrieval по умолчанию, top-k, стратегия fusion, filter pushdown |

## Как запустить Qdrant локально

```bash
docker run -p 6333:6333 qdrant/qdrant
```

Затем укажите `vector_store.backend: qdrant` в `configs/vector_stores.yaml` (Chroma не требует
сервера — по умолчанию она сохраняет данные в `./data/chroma` и является backend'ом "из коробки").

## Как запустить пакетную загрузку

```bash
athena ingest --path ./data/raw/books --domain books --collection athena_chunks_bge_m3_v1
athena ingest --path ./data/raw/job --domain job --dry-run
athena search "Java AI Engineer CV" --domain job --top-k 10
athena collections
athena dashboard
```

`--dry-run` выполняет Discover → Load → Extract → Chunk без embedding/upsert и показывает
предполагаемое количество чанков, целевую коллекцию/embedding profile и предупреждения.

Полный справочник флагов — вызов со всеми опциональными переопределениями сразу:

```bash
athena ingest \
  --path ./data/raw/cv_docs \
  --domain job \
  --collection athena_chunks_bge_m3_v1 \
  --backend qdrant \
  --chunking-profile default \
  --embedding-profile bge_m3 \
  --tag cv --tag 2026 \
  --document-type resume \
  --language ru \
  --access-level private
```

`--domain` обязателен и должен быть одним из `job | personal | tech | media | musik | books | user` (см.
`configs/domains.yaml`); `--backend` разово переопределяет настроенный backend `qdrant`/`chroma`
для конкретного запуска.

Sidecar-метаданные поддерживаются на уровне папки (`.athena.yaml`), на уровне файла
(`<file>.athena.yaml`), а также как markdown front matter — front matter имеет приоритет над
файловым sidecar, который имеет приоритет над папочным sidecar, который имеет приоритет над
автоматически определённой метаданными.

## Как запустить Gradio веб-приложение

```bash
python -m de.ibikus.athena.web.app
```

Открывается на `http://localhost:7860` с тремя вкладками: **Search & Ask**, **Dashboard** и
**Data Management**. FastAPI-приложение также предоставляет:

```
GET /health
GET /actuator/health
GET /actuator/info
GET /actuator/metrics
GET /metrics
```

## Docker и Kubernetes (Helm)

`Dockerfile` собирает образ веб-приложения (editable install — `core/config/settings.py`
вычисляет путь к конфигам из `__file__`, поэтому образ сохраняет структуру `src/` + `configs/`,
а не обычную установку в site-packages). `deploy/helm/athena/` — Helm-чарт, разворачивающий:

- веб-приложение как `Deployment` + `Service` (NodePort)
- **Qdrant** как `StatefulSet` + headless `Service` + PVC (production-like backend)
- общий PVC (`/app/data`) для `raw/`, `processed/`, `reports/`
- `ConfigMap`, переопределяющий `configs/vector_stores.yaml`, чтобы указывать на Qdrant
  внутри кластера вместо захардкоженного в образе `localhost`
- опциональный `Job` для batch-ingestion, по умолчанию выключен

```bash
./deploy/deploy.sh
```

Собирает образ в Docker-демоне minikube и выполняет `helm upgrade --install`. Чтобы запустить
batch-ingestion после этого:

```bash
POD=$(kubectl get pod -n athena -l app.kubernetes.io/component=app -o jsonpath='{.items[0].metadata.name}')
kubectl cp ./my_docs athena/"$POD":/app/data/raw/my_docs

helm upgrade --install athena ./deploy/helm/athena -n athena --reuse-values \
  --set batchJob.enabled=true \
  --set batchJob.path=/app/data/raw/my_docs \
  --set batchJob.domain=tech

kubectl logs -n athena -l app.kubernetes.io/component=ingest-job --tail=-1 -f
```

Каждый включённый запуск создаёт новый `Job` с меткой времени (`athena-ingest-<timestamp>`),
поэтому повторные вызовы `helm upgrade` никогда не конфликтуют с предыдущим запуском.

## Как настроить локальные embeddings

Профиль по умолчанию — `bge_m3_local` (`BAAI/bge-m3`, in-process через sentence-transformers).
Добавляйте новые профили в `configs/embedding_profiles.yaml`; чанки каждой коллекции помечаются
`embedding_profile`, с помощью которого они были построены, и retrieval требует, чтобы запрос
использовал тот же профиль — смена модели означает создание новой коллекции или reindex.

## Как настроить локальный LLM target

Укажите любой OpenAI-compatible сервер (LM Studio, Ollama, vLLM, llama.cpp server) в
`configs/llm_targets.yaml` с `provider: openai_compatible` и правильным `base_url`.
Такие targets имеют `privacy_level: local` и никогда не блокируются Privacy Guard.

## Как настроить frontier LLM target

Добавьте запись с `privacy_level: external` (см. `frontier_openai` / `frontier_anthropic`).
Будет ли он реально разрешён — зависит от Privacy Guard (см. ниже) — маршрутизация anthropic
сама по себе задокументирована как TODO (MVP реализует только `openai_compatible` routing).

## Предупреждение о приватности

Athena по умолчанию использует `privacy_mode: LOCAL_ONLY` — **контекст никогда не покидает машину**,
пока вы это не измените. Правила, применяемые `de.ibikus.athena.generation.privacy_guard.PrivacyGuard`:

1. Локальные/local-or-LAN targets всегда разрешены.
2. `LOCAL_ONLY` полностью блокирует любой внешний target.
3. Домены с `frontier_allowed: false` (`job`, `personal`, `user` по умолчанию) требуют явного
   подтверждения (чекбокс "I understand...") даже если глобальный режим это разрешает.
4. В противном случае `ALLOW_FRONTIER_WITH_CONFIRMATION` требует подтверждения, а
   `ALLOW_FRONTIER` разрешает безусловно.

Заблокированные/подтверждённые запросы к внешним LLM учитываются в `athena_external_llm_blocked_total` /
`athena_external_llm_confirmed_total`.

## Observability

**Веб-приложение** (не пакетный CLI) инструментировано как production-service:

- **Структурированное JSON-логирование** (`structlog`) — см. `de.ibikus.athena.web.observability.logging`.
- **MDC-подобный контекст запроса** через `contextvars` — `request_context(...)` привязывает
  `request_id`, `domain_id`, `collection_name`, `retrieval_mode`, `llm_target` и т.д., так что
  каждая строка лога внутри запроса автоматически содержит их. Никогда не логирует полные
  prompt/context/API-ключи/содержимое файлов — только длины, хэши и счётчики.
- **Actuator-подобные endpoints**: `/health`, `/actuator/health` (статус по каждому компоненту
  UP/DEGRADED), `/actuator/info`, `/actuator/metrics` (JSON-сводка).
- **Prometheus metrics** на `/metrics` — счётчики и гистограммы web/retrieval/vector-store/
  generation/privacy/data-management, все с низкой кардинальностью labels (см.
  `de.ibikus.athena.web.observability.metrics`).
- **Grafana**: `observability/prometheus/prometheus.yml` + dashboard JSON и справочник PromQL
  в `observability/grafana/`.

### Как запустить Prometheus + подключить Grafana

См. [`observability/grafana/README.md`](./observability/grafana/README.md) для полного
руководства и примеров PromQL-запросов.

```bash
python -m de.ibikus.athena.web.app
curl http://localhost:7860/health
curl http://localhost:7860/actuator/health
curl http://localhost:7860/actuator/info
curl http://localhost:7860/metrics
```

## Тестирование

```bash
pip install -e ".[dev]"
pytest
```

Тесты используют реальный (embedded) экземпляр ChromaDB и детерминированный fake embedding-сервис —
сеть и GPU не требуются. Qdrant в тестах не используется (нет зависимости от сервера).

## Известные ограничения

- **LlamaIndex не подключён.** Исходная спецификация называла LlamaIndex предпочтительным RAG-движком;
  активный MVP вместо этого реализует loaders/chunkers/retrieval/fusion напрямую, чтобы сохранить
  полный контроль над схемой метаданных и подключаемым vector-store gateway. Параллельная,
  опциональная реализация поверх LlamaIndex существует в `de/ibikus/athena/experimental/llamaindex/`
  для сравнения — см. ниже. Она **не** импортируется активным pipeline, CLI или веб-приложением.
- У BM25 нет постоянного полнотекстового индекса — его корпус перестраивается по требованию из
  payload'ов vector store (с теми же фильтрами, что и векторный поиск), что приемлемо для MVP,
  но не масштабируется на очень большие коллекции.
- Аудио, видео, pptx/xlsx и архивы имеют интерфейсы и TODO, но без реального извлечения контента
  (бросают `UnsupportedFileError`). Изображения и сканированные страницы PDF проходят через OCR
  (`pytesseract` + `tesseract-ocr`, см. раздел «Установка») — визуальных/CLIP-эмбеддингов всё ещё
  нет, поэтому фото без читаемого текста по-прежнему даёт 0 чанков.
- Нет нативного Qdrant sparse-vector hybrid search — fusion (RRF/relative-score/weighted) всегда
  происходит на уровне приложения.
- Anthropic LLM routing настроен в конфиге, но не реализован (только `openai_compatible`).
- Нет PostgreSQL metadata store, MinIO/S3 raw file storage, multi-user auth или UMAP/t-SNE
  проекции векторов (в dashboard — заглушка).

## Экспериментально: LlamaIndex pipeline (не подключён)

`de/ibikus/athena/experimental/llamaindex/` — параллельная, опциональная реализация ingestion +
retrieval на базе LlamaIndex вместо собственного pipeline Athena. Она **нигде не импортируется**
в активном коде (ingestion, retrieval, CLI, web) — существует исключительно для того, чтобы можно
было сравнить два подхода.

```bash
pip install -e ".[llamaindex]"
```

```python
from pathlib import Path
from de.ibikus.athena.core.config.loader import load_config
from de.ibikus.athena.experimental.llamaindex.ingestion import ingest_directory_with_llamaindex
from de.ibikus.athena.experimental.llamaindex.retrieval import query_with_llamaindex

config = load_config()
ingest_directory_with_llamaindex(config, Path("./data/raw/tech"), domain_id="tech", backend="chroma")
results = query_with_llamaindex(config, "athena_chunks_bge_m3_v1", "chroma", "bge_m3_local", "your query")
```

Примечания:

- Переиспользует логику Athena по определению domain/sidecar/front-matter метаданных и
  конфигурацию chunking/embedding profile, но делегирует загрузку, разбиение на узлы, embedding
  и индексацию LlamaIndex (`SimpleDirectoryReader`, `SentenceSplitter`, `HuggingFaceEmbedding`,
  `VectorStoreIndex`).
- Пишет в `<collection_name>_llamaindex` — отдельный namespace — поэтому никогда не пересекается
  и не портит коллекции, используемые production-gateway на основе `ChunkMetadata` (эти два
  формата метаданных несовместимы).
- Поддерживает те же MVP-типы файлов, что и основной pipeline (txt/md/pdf/docx); изображения/
  аудио/видео здесь тоже пока TODO. Нет BM25/hybrid fusion, reranking или filter pushdown —
  только обычный dense vector similarity через `index.as_retriever()`.
- Тесты (`tests/test_llamaindex_experimental.py`) подставляют
  `llama_index.core.embeddings.MockEmbedding`, чтобы избежать зависимости от torch/
  sentence-transformers, и автоматически пропускаются, если extra `llamaindex` не установлен.

## Roadmap (V2)

- [ ] Решить, стоит ли переводить экспериментальный LlamaIndex pipeline в активный код
- [ ] ASR (аудио) и видео (transcript + keyframes) ingestion
- [ ] Извлечение из pptx/xlsx
- [ ] Нативные Qdrant sparse/hybrid vectors
- [ ] Бенчмаркинг cross-encoder reranking (RAGAS)
- [ ] UMAP/t-SNE 2D-проекция в dashboard
- [ ] PostgreSQL metadata store, MinIO/S3 raw file storage
- [ ] Multi-user auth
