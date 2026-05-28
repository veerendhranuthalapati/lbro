"""
LBRO — Middleware
  RequestTracingMiddleware  assigns X-Request-ID, binds to structlog context
  MetricsMiddleware         emits CloudWatch custom metrics per endpoint
"""
import time
import uuid

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.config import settings

log = structlog.get_logger(__name__)


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """Assigns a unique request_id to every request and binds it to all log lines."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class MetricsMiddleware(BaseHTTPMiddleware):
    """Emits latency and status-code metrics to CloudWatch. Skips health endpoints."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        path = request.url.path
        status_code = response.status_code

        log.info(
            "http.request",
            path=path,
            method=request.method,
            status=status_code,
            duration_ms=round(duration_ms, 2),
        )

        if settings.APP_ENV != "dev" and not path.startswith("/health"):
            _emit_metrics(path, status_code, duration_ms)

        return response


def _emit_metrics(path: str, status_code: int, duration_ms: float) -> None:
    """Best-effort CloudWatch metric emission — never raises."""
    try:
        from app.core.aws_clients import get_cloudwatch
        get_cloudwatch().put_metric_data(
            Namespace="LBRO",
            MetricData=[
                {
                    "MetricName": "APILatencyMs",
                    "Value": duration_ms,
                    "Unit": "Milliseconds",
                    "Dimensions": [{"Name": "Path", "Value": path}],
                },
                {
                    "MetricName": "APIRequestCount",
                    "Value": 1,
                    "Unit": "Count",
                    "Dimensions": [
                        {"Name": "Path", "Value": path},
                        {"Name": "StatusCode", "Value": str(status_code)},
                    ],
                },
            ],
        )
    except Exception as e:
        log.warning("metrics.put_failed", error=str(e))
