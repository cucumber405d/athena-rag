# CLAUDE.md — Athena (RAG-платформа)

> MVP реализован. Подробный архитектурный снимок для людей — в `architecture-blueprint.md`
> (см. предупреждение в его начале — это не инструкция для Claude Code, актуальный источник
> истины о поведении — код + тесты).

## О проекте

Локально-ориентированная масштабируемая RAG-платформа: гибридный retrieval (BM25 + vector),
embeddings-pipeline, reranking, filter pushdown, batch ingestion CLI и три Gradio веб-морды
поверх FastAPI с production-style observability. Параллельная (не подключённая) экспериментальная
реализация на LlamaIndex — `src/de/ibikus/athena/experimental/llamaindex/`.

**Стек:** Python 3.11+ · Qdrant/ChromaDB · sentence-transformers · rank-bm25 · Gradio · FastAPI

## Предпочтения

- Язык кода: Python
- Язык общения: русский
- Комментарии в коде: английский
- Типизация: Pydantic-модели, type hints везде

## Стек

| Компонент | Технология |
|---|---|
| Векторная БД | Qdrant (production-like) / ChromaDB (local/dev) |
| Гибридный поиск | BM25 (rank-bm25) + vector, RRF/relative_score/weighted fusion |
| Re-ranking | cross-encoder (sentence-transformers), опционально |
| Веб | FastAPI + Gradio |
| Observability | structlog + contextvars (MDC) + prometheus_client |
| Экспериментально | LlamaIndex (не подключён — см. `experimental/llamaindex/`) |

## Архитектура

Пакет: `src/de/ibikus/athena/` (reverse-domain, Java-стиль имени — см.
architecture-blueprint.md, раздел 18, п. 1). Полная структура и обоснование решений — в
`architecture-blueprint.md`, разделы 3–14.

## Конвенции

- Все LLM-вызовы — через `generation/llm_router.py`, не напрямую
- Ни CLI, ни Gradio UI не обращаются к `qdrant_client`/`chromadb` напрямую — только через
  `stores/vector_gateway.py::VectorStoreGateway`
- Конфиги через `configs/*.yaml` + `core/config/loader.py`; env — через Pydantic Settings (`.env`)
- Retrieval и generation разделены на уровне модулей — не смешивать
- Delete по умолчанию — soft delete (`deleted=true`)

## Запуск

Локально (см. `RUNNING.md` для полной шпаргалки):

```bash
pip install -e .
python -m de.ibikus.athena.web.app
```

В Kubernetes (minikube) — Helm-чарт `deploy/helm/athena/` (web app + Qdrant StatefulSet +
опциональный batch-ingestion Job), сборка образа и деплой через `deploy/deploy.sh`. Детали —
в README.md / read_me.ru, раздел «Docker & Kubernetes (Helm)».

## Документация

- `README.md` (английский) и `read_me.ru` (русский) — параллельные версии одного и того же
  документа. При любом изменении `README.md` обязательно вносить то же изменение в `read_me.ru`,
  и наоборот. Код, команды, пути и имена конфигов в `read_me.ru` остаются на английском —
  переводится только описательный текст.

## Что не трогать

- `__pycache__/`, `.venv/` — артефакты среды
