# Athena — local-first scalable RAG platform

Athena is a local-first, scalable Retrieval-Augmented Generation platform: batch ingestion of
heterogeneous data (text, PDF, DOCX, images with OCR, and more), hybrid search (BM25 + dense vectors),
local embeddings, pluggable vector stores, optional reranking, filter pushdown, and three
Gradio web UIs on top of a FastAPI app with production-style observability.

## Status

**MVP implemented.** Core config/models, ingestion pipeline, retrieval engine, generation
routing + Privacy Guard, CLI, the three Gradio UIs, and the web observability layer
(structured logging, actuator endpoints, Prometheus metrics) are in place and covered by tests.

## Architecture overview

Full details: [architecture-blueprint.md](./architecture-blueprint.md)

```
config → models → vector gateway → ingestion → retrieval → generation routing → Gradio UI
```

```text
src/de/ibikus/athena/
  core/           Pydantic config loader + domain/document/chunk/retrieval/llm_target models
  metadata/       sidecar (.athena.yaml) + markdown front matter resolution, validators
  ingestion/      discovery → load → extract → normalize → chunk → embed → upsert → report
  stores/         VectorStoreGateway + Qdrant/Chroma adapters, docstore, raw file store
  retrieval/      vector/BM25/hybrid retrievers, RRF fusion, reranker, context builder
  generation/     LLM router (OpenAI-compatible), Privacy Guard
  web/            FastAPI app + 3 Gradio pages + observability (logging/metrics/health)
  cli/            `athena` CLI — shares the same core services as the web app
```

Vector stores are pluggable behind `VectorStoreGateway`: **Qdrant** is the production-like
backend, **ChromaDB** is the local/dev backend. The embedding model used to build a collection
is part of that collection's index — queries against it are forced to use the same
`embedding_profile` (see `RetrievalEngine._check_embedding_profile_consistency`).

Generation is intentionally decoupled from retrieval: `RetrievalEngine` only ever returns a
`ContextResult`; `LLMRouter` + `PrivacyGuard` decide, independently, whether/where to send it.

## Installation

```bash
pip install -e .
# heavier extras used by the default profiles (torch, sentence-transformers):
pip install sentence-transformers chromadb qdrant-client gradio fastapi uvicorn
```

Copy `.env.example` to `.env` and adjust API keys / URLs as needed.

### OCR (optional, for images and scanned PDFs)

Image ingestion and the scanned-PDF-page fallback both go through `pytesseract`, which needs the
`tesseract-ocr` system binary — not a pip package:

```bash
sudo apt install tesseract-ocr tesseract-ocr-deu tesseract-ocr-rus  # Debian/Ubuntu
```

OCR runs with `lang="eng+deu+rus"`, matching the platform's `de/en/ru` UI languages. Without the
binary installed, OCR calls fail silently (the exception is swallowed) — images and scanned PDF
pages just produce 0 chunks instead of erroring.

## Configuration

All tunables live under `configs/*.yaml`:

| File | Purpose |
|---|---|
| `app.yaml` | app name, log level, privacy mode, storage paths, observability toggles |
| `domains.yaml` | domains (`job`, `personal`, `tech`, `media`, `musik`, `books`, `user`), `frontier_allowed` flag |
| `embedding_profiles.yaml` | local embedding models (`bge_m3_local` is the default) |
| `chunking_profiles.yaml` | `default_text`, `pdf_page_aware`, `book_default`, ... |
| `reranker_profiles.yaml` | `none` (default) + local cross-encoder profiles |
| `vector_stores.yaml` | Qdrant/Chroma connection settings, default backend |
| `llm_targets.yaml` | local (LM Studio/Ollama/vLLM) and frontier (OpenAI/Anthropic) targets |
| `retrieval.yaml` | default retrieval mode, top-k, fusion strategy, filter pushdown |

## How to run Qdrant locally

```bash
docker run -p 6333:6333 qdrant/qdrant
```

Then set `vector_store.backend: qdrant` in `configs/vector_stores.yaml` (Chroma needs no
server — it persists to `./data/chroma` by default and is the out-of-the-box backend).

## How to run batch ingestion

```bash
athena ingest --path ./data/raw/books --domain books --collection athena_chunks_bge_m3_v1
athena ingest --path ./data/raw/job --domain job --dry-run
athena search "Java AI Engineer CV" --domain job --top-k 10
athena collections
athena dashboard
```

`--dry-run` runs Discover → Load → Extract → Chunk without embedding/upserting, and reports
the estimated chunk count, target collection/embedding profile, and any warnings.

Full flag reference, with all optional overrides in one call:

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
  --language en \
  --access-level private
```

`--domain` is required and must be one of `job | personal | tech | media | musik | books | user` (see
`configs/domains.yaml`); `--backend` overrides the configured `qdrant`/`chroma` backend
for a single run.

Sidecar metadata is supported at the folder level (`.athena.yaml`), file level
(`<file>.athena.yaml`), and as markdown front matter — front matter overrides the file
sidecar, which overrides the folder sidecar, which overrides auto-detected metadata.

## How to run the Gradio web app

```bash
source .venv/bin/activate
python -m de.ibikus.athena.web.app
```

Opens on `http://localhost:7860` with three tabs: **Search & Ask**, **Dashboard**, and
**Data Management**. The FastAPI app also exposes:

```
GET /health
GET /actuator/health
GET /actuator/info
GET /actuator/metrics
GET /metrics
```

## Docker & Kubernetes (Helm)

A `Dockerfile` builds the web app image (editable install — `core/config/settings.py`
derives its config path from `__file__`, so the image keeps the `src/` + `configs/` layout
instead of a normal site-packages install). `deploy/helm/athena/` is a Helm chart deploying:

- the web app as a `Deployment` + `Service` (NodePort)
- **Qdrant** as a `StatefulSet` + headless `Service` + PVC (the production-like backend)
- a shared PVC (`/app/data`) for `raw/`, `processed/`, `reports/`
- a `ConfigMap` overriding `configs/vector_stores.yaml` to point at the in-cluster Qdrant
  service instead of the image's baked-in `localhost` default
- an opt-in batch-ingestion `Job`, disabled by default

```bash
./deploy/deploy.sh
```

Builds the image into minikube's Docker daemon and runs `helm upgrade --install`. To run
batch ingestion afterwards:

```bash
POD=$(kubectl get pod -n athena -l app.kubernetes.io/component=app -o jsonpath='{.items[0].metadata.name}')
kubectl cp ./my_docs athena/"$POD":/app/data/raw/my_docs

helm upgrade --install athena ./deploy/helm/athena -n athena --reuse-values \
  --set batchJob.enabled=true \
  --set batchJob.path=/app/data/raw/my_docs \
  --set batchJob.domain=tech

kubectl logs -n athena -l app.kubernetes.io/component=ingest-job --tail=-1 -f
```

Each enabled run creates a new, timestamped `Job` (`athena-ingest-<timestamp>`) so repeated
`helm upgrade` calls never collide with a previous run.

## How to configure local embeddings

Default profile is `bge_m3_local` (`BAAI/bge-m3`, in-process via sentence-transformers).
Add more profiles to `configs/embedding_profiles.yaml`; each collection's chunks are tagged
with the `embedding_profile` used to build them, and retrieval enforces that the query uses
the same profile — switching models means creating a new collection or reindexing.

## How to configure a local LLM target

Point any OpenAI-compatible server (LM Studio, Ollama, vLLM, llama.cpp server) at
`configs/llm_targets.yaml` with `provider: openai_compatible` and the right `base_url`.
These have `privacy_level: local` and are never blocked by the Privacy Guard.

## How to configure a frontier LLM target

Add an entry with `privacy_level: external` (see `frontier_openai` / `frontier_anthropic`).
Whether it's actually allowed depends on the Privacy Guard (see below) — anthropic routing
itself is a documented TODO (MVP implements `openai_compatible` routing only).

## Privacy warning

Athena defaults to `privacy_mode: LOCAL_ONLY` — **no context ever leaves the machine** unless
you change this. Rules enforced by `de.ibikus.athena.generation.privacy_guard.PrivacyGuard`:

1. Local/local-or-LAN targets are always allowed.
2. `LOCAL_ONLY` blocks every external target outright.
3. Domains with `frontier_allowed: false` (`job`, `personal`, `user` by default) require
   explicit confirmation (the "I understand..." checkbox) even if the global mode allows it.
4. Otherwise `ALLOW_FRONTIER_WITH_CONFIRMATION` requires confirmation and `ALLOW_FRONTIER`
   allows it unconditionally.

Blocked/confirmed external requests are counted in `athena_external_llm_blocked_total` /
`athena_external_llm_confirmed_total`.

## Observability

The **web application** (not the batch CLI) is instrumented like a production service:

- **Structured JSON logging** (`structlog`) — see `de.ibikus.athena.web.observability.logging`.
- **MDC-like request context** via `contextvars` — `request_context(...)` binds
  `request_id`, `domain_id`, `collection_name`, `retrieval_mode`, `llm_target`, etc. so every
  log line inside a request carries them automatically. Never logs raw prompts/context/API
  keys/file contents — only lengths, hashes, and counts.
- **Actuator-like endpoints**: `/health`, `/actuator/health` (per-component UP/DEGRADED),
  `/actuator/info`, `/actuator/metrics` (JSON summary).
- **Prometheus metrics** at `/metrics` — web/retrieval/vector-store/generation/privacy/
  data-management counters and histograms, all with low-cardinality labels (see
  `de.ibikus.athena.web.observability.metrics`).
- **Grafana**: `observability/prometheus/prometheus.yml` + a dashboard JSON and PromQL
  reference at `observability/grafana/`.

### How to run Prometheus + connect Grafana

See [`observability/grafana/README.md`](./observability/grafana/README.md) for the full
walkthrough and example PromQL queries.

```bash
python -m de.ibikus.athena.web.app
curl http://localhost:7860/health
curl http://localhost:7860/actuator/health
curl http://localhost:7860/actuator/info
curl http://localhost:7860/metrics
```

## Testing

```bash
pip install -e ".[dev]"
pytest
```

Tests use a real (embedded) ChromaDB instance and a deterministic fake embedding service —
no network access or GPU required. Qdrant is not exercised in tests (no server dependency).

## Known limitations

- **LlamaIndex is not wired in.** The spec lists LlamaIndex as the preferred RAG engine;
  the active MVP implements loaders/chunkers/retrieval/fusion directly instead, to keep
  full control over the metadata schema and the pluggable vector-store gateway. A parallel,
  optional implementation on top of LlamaIndex exists at
  `de/ibikus/athena/experimental/llamaindex/` for comparison — see below. It is **not**
  imported by the active pipeline, the CLI, or the web app.
- BM25 has no persistent full-text index — its corpus is rebuilt on demand from the vector
  store's payloads (filtered the same way as vector search), which is fine at MVP scale but
  won't scale to very large collections.
- Audio, video, pptx/xlsx and archives have interfaces + TODOs but no real extraction yet (they
  raise `UnsupportedFileError`). Images and scanned PDF pages go through OCR (`pytesseract` +
  `tesseract-ocr`, see Installation) — there's still no visual/CLIP embedding, so a photo with
  no readable text yields 0 chunks.
- No native Qdrant sparse-vector hybrid search — fusion (RRF/relative-score/weighted) always
  happens at the application level.
- Anthropic LLM routing is configured but not implemented (`openai_compatible` only).
- No PostgreSQL metadata store, MinIO/S3 raw file storage, multi-user auth, or UMAP/t-SNE
  vector projection (dashboard has a placeholder).

## Experimental: LlamaIndex pipeline (not wired in)

`de/ibikus/athena/experimental/llamaindex/` is a parallel, optional implementation of
ingestion + retrieval built on LlamaIndex instead of Athena's hand-rolled pipeline. It is
**not imported anywhere** in the active code path (ingestion, retrieval, CLI, web) — it
exists purely so the two approaches can be evaluated side by side.

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

Notes:

- Reuses Athena's domain/sidecar/front-matter metadata resolution and chunking/embedding
  profile config, but delegates loading, node parsing, embedding and indexing to LlamaIndex
  (`SimpleDirectoryReader`, `SentenceSplitter`, `HuggingFaceEmbedding`, `VectorStoreIndex`).
- Writes to `<collection_name>_llamaindex` — a separate namespace — so it can never collide
  with or corrupt collections used by the production `ChunkMetadata`-based gateway (the two
  metadata layouts aren't compatible).
- Supports the same MVP file types as the main pipeline (txt/md/pdf/docx); images/audio/video
  are TODOs here too. No BM25/hybrid fusion, reranking, or filter pushdown — plain dense
  vector similarity via `index.as_retriever()`.
- Tests (`tests/test_llamaindex_experimental.py`) inject `llama_index.core.embeddings.MockEmbedding`
  to avoid a torch/sentence-transformers dependency and are skipped automatically if the
  `llamaindex` extra isn't installed.

## Roadmap (V2)

- [ ] Decide whether to promote the experimental LlamaIndex pipeline to the active path
- [ ] ASR (audio) and video (transcript + keyframes) ingestion
- [ ] pptx/xlsx extraction
- [ ] Native Qdrant sparse/hybrid vectors
- [ ] Cross-encoder reranking benchmarking (RAGAS)
- [ ] UMAP/t-SNE 2D projection in the dashboard
- [ ] PostgreSQL metadata store, MinIO/S3 raw file storage
- [ ] Multi-user auth
