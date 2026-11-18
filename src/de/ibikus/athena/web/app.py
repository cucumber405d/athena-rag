"""FastAPI app wrapping the Gradio web UIs with actuator-like observability endpoints.

    FastAPI app
      +-- /health
      +-- /actuator/health
      +-- /actuator/info
      +-- /actuator/metrics
      +-- /metrics
      +-- mounted Gradio app (Search & Ask / Dashboard / Data Management)
"""

from __future__ import annotations

import os
import time

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

import gradio as gr
from fastapi import FastAPI, Request
from fastapi.responses import Response

from de.ibikus.athena import __version__
from de.ibikus.athena.web.observability import metrics as m
from de.ibikus.athena.web.observability.context import request_context
from de.ibikus.athena.web.observability.health import build_actuator_health, build_actuator_info
from de.ibikus.athena.web.observability.logging import configure_logging, get_logger
from de.ibikus.athena.web.pages.dashboard_page import build_dashboard_page
from de.ibikus.athena.web.pages.ingest_page import build_ingest_page
from de.ibikus.athena.web.pages.search_page import build_search_page
from de.ibikus.athena.web.services import get_services

services = get_services()
configure_logging(services.config.app.log_level)
log = get_logger("de.ibikus.athena.web.app")

fastapi_app = FastAPI(title="Athena")


@fastapi_app.middleware("http")
async def observability_middleware(request: Request, call_next):
    route = request.url.path
    method = request.method
    started = time.perf_counter()
    with request_context(user_action="http_request"):
        try:
            response = await call_next(request)
        except Exception as exc:  # noqa: BLE001
            m.web_errors_total.labels(route=route, method=method, status="500").inc()
            m.metrics_summary.record_request(is_error=True)
            log.error("http_request_failed", error_type=type(exc).__name__, error_message=str(exc))
            raise

        duration = time.perf_counter() - started
        is_error = response.status_code >= 500
        m.web_requests_total.labels(route=route, method=method, status=str(response.status_code)).inc()
        m.web_request_duration_seconds.labels(route=route, method=method).observe(duration)
        m.metrics_summary.record_request(is_error=is_error)
        if is_error:
            m.web_errors_total.labels(route=route, method=method, status=str(response.status_code)).inc()
        return response


@fastapi_app.get("/health")
def health() -> dict:
    return {"status": "UP"}


@fastapi_app.get("/actuator/health")
def actuator_health() -> dict:
    try:
        vector_store = services.vector_store()
    except Exception:  # noqa: BLE001
        vector_store = None
    return build_actuator_health(services.config, vector_store)


@fastapi_app.get("/actuator/info")
def actuator_info() -> dict:
    return build_actuator_info(services.config, __version__)


@fastapi_app.get("/actuator/metrics")
def actuator_metrics() -> dict:
    return m.metrics_summary.as_dict()


@fastapi_app.get("/metrics")
def metrics_endpoint() -> Response:
    body, content_type = m.render_prometheus()
    return Response(content=body, media_type=content_type)


def build_gradio_app() -> gr.Blocks:
    return gr.TabbedInterface(
        [build_search_page(services), build_dashboard_page(services), build_ingest_page(services)],
        ["Search & Ask", "Dashboard", "Data Management"],
        title="Athena",
    )


gr.mount_gradio_app(fastapi_app, build_gradio_app(), path="/")


def main() -> None:
    import uvicorn

    uvicorn.run(fastapi_app, host="0.0.0.0", port=7860)


if __name__ == "__main__":
    main()
