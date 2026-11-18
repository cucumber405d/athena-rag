# Athena — способы запуска

Шпаргалка с готовыми командами. Подробности по архитектуре — в `architecture-blueprint.md`.

## 1. Установка

```bash
cd athena
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

Опционально:

```bash
pip install -e ".[dev]"          # pytest
pip install -e ".[llamaindex]"   # экспериментальный пайплайн, в основной путь не входит
```

Файл окружения:

```bash
cp .env.example .env
```

## 2. Векторное хранилище

По умолчанию — Chroma, ничего дополнительно ставить не нужно (персистится в `./data/chroma`).

Для Qdrant:

```bash
docker run -p 6333:6333 qdrant/qdrant
```

и переключить `vector_store.backend: qdrant` в `configs/vector_stores.yaml`.

## 3. Batch-ingestion (CLI)

Прогон без записи (проверить, что всё распарсится):

```bash
athena ingest --path ./data/raw/my_docs --domain tech --dry-run
```

Реальный ingestion:

```bash
athena ingest --path ./data/raw/my_docs --domain tech
```

С доп. параметрами:

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

`--domain` — один из: `job | personal | tech | media | user` (см. `configs/domains.yaml`).

## 4. Проверка результата (CLI)

```bash
athena collections            # список коллекций в текущем backend
athena dashboard               # чанки/документы/домены/языки по каждой коллекции
```

## 5. Поиск без генерации (CLI)

```bash
athena search "запрос" --domain tech --mode hybrid --top-k 10
```

## 6. Веб-приложение (Gradio + FastAPI)

```bash
source .venv/bin/activate
python -m de.ibikus.athena.web.app
```

http://localhost:7860


## 7. Docker / Kubernetes (Helm, minikube)

```bash
./deploy/deploy.sh
```

Собирает образ в Docker-демоне minikube и разворачивает Helm-релиз (web app + Qdrant
StatefulSet + PVC). Batch ingestion в кластере — через опциональный Job:

```bash
POD=$(kubectl get pod -n athena -l app.kubernetes.io/component=app -o jsonpath='{.items[0].metadata.name}')
kubectl cp ./my_docs athena/"$POD":/app/data/raw/my_docs

helm upgrade --install athena ./deploy/helm/athena -n athena --reuse-values \
  --set batchJob.enabled=true \
  --set batchJob.path=/app/data/raw/my_docs \
  --set batchJob.domain=tech

kubectl logs -n athena -l app.kubernetes.io/component=ingest-job --tail=-1 -f
```

Подробности — в README.md / read_me.ru, раздел «Docker & Kubernetes (Helm)».
