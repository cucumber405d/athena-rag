# Athena — Prometheus + Grafana

This directory contains everything needed to observe Athena's **web application**
(Search & Ask, Dashboard, Data Management). Batch ingestion is not instrumented.

## 1. Run Prometheus

```bash
docker run -d --name athena-prometheus \
  -p 9090:9090 \
  -v "$(pwd)/observability/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml" \
  prom/prometheus
```

`prometheus.yml` scrapes `localhost:7860/metrics` (the default port of
`python -m athena.web.app`). If you run the web app on a different host/port,
edit the `targets` list.

## 2. Run Grafana

```bash
docker run -d --name athena-grafana -p 3000:3000 grafana/grafana
```

Add Prometheus (`http://host.docker.internal:9090` or your Prometheus URL) as
a datasource, then import `dashboards/athena-web-dashboard.json`
(Dashboards → New → Import). Grafana will ask you to map the `DS_PROMETHEUS`
input to your Prometheus datasource.

## 3. Panels

| Panel | PromQL |
|---|---|
| Web requests total | `rate(athena_web_requests_total[5m])` |
| Web request latency p95 | `histogram_quantile(0.95, rate(athena_web_request_duration_seconds_bucket[5m]))` |
| Retrieval requests by mode | `rate(athena_retrieval_requests_total[5m])` |
| Retrieval latency p95 | `histogram_quantile(0.95, rate(athena_retrieval_duration_seconds_bucket[5m]))` |
| Chunks returned per request | `histogram_quantile(0.50, rate(athena_retrieval_chunks_returned_bucket[5m]))` |
| Vector store search latency | `histogram_quantile(0.95, rate(athena_vector_search_duration_seconds_bucket[5m]))` |
| Generation requests by LLM target | `rate(athena_generation_requests_total[5m])` |
| Generation latency p95 | `histogram_quantile(0.95, rate(athena_generation_duration_seconds_bucket[5m]))` |
| External LLM blocked/confirmed | `rate(athena_external_llm_blocked_total[5m])` / `rate(athena_external_llm_confirmed_total[5m])` |
| Errors by component | `rate(athena_web_errors_total[5m])`, `rate(athena_retrieval_errors_total[5m])`, `rate(athena_generation_errors_total[5m])`, `rate(athena_vector_search_errors_total[5m])` |

## 4. Sanity checks

```bash
curl http://localhost:7860/health
curl http://localhost:7860/actuator/health
curl http://localhost:7860/actuator/info
curl http://localhost:7860/actuator/metrics
curl http://localhost:7860/metrics
```

If the dashboard JSON fails to import for any reason (Grafana version
differences), use the PromQL table above to build panels manually — it is
the source of truth.
