"""
LBRO — Worker metrics
Emits CloudWatch custom metrics for worker processing.
"""
from __future__ import annotations

import time
from typing import Any

import structlog

from app.config import settings

log = structlog.get_logger(__name__)


class WorkerMetrics:
    """Batches and emits worker processing metrics to CloudWatch."""

    def __init__(self) -> None:
        self._success_count = 0
        self._failure_count = 0
        self._total_duration = 0.0
        self._last_flush = time.monotonic()
        self._flush_interval = 60.0  # Flush every 60 seconds

    def record_success(self, duration_s: float) -> None:
        self._success_count += 1
        self._total_duration += duration_s
        self._maybe_flush()

    def record_failure(self) -> None:
        self._failure_count += 1
        self._maybe_flush()

    def _maybe_flush(self) -> None:
        if time.monotonic() - self._last_flush >= self._flush_interval:
            self._flush()

    def _flush(self) -> None:
        if settings.APP_ENV == "dev":
            return

        try:
            from app.core.aws_clients import get_cloudwatch
            metrics: list[dict[str, Any]] = [
                {
                    "MetricName": "WorkerMessagesProcessed",
                    "Value": self._success_count,
                    "Unit": "Count",
                },
                {
                    "MetricName": "WorkerMessagesFailed",
                    "Value": self._failure_count,
                    "Unit": "Count",
                },
            ]
            if self._success_count > 0:
                metrics.append({
                    "MetricName": "WorkerAvgProcessingTimeMs",
                    "Value": (self._total_duration / self._success_count) * 1000,
                    "Unit": "Milliseconds",
                })
            get_cloudwatch().put_metric_data(Namespace="LBRO", MetricData=metrics)
        except Exception as e:
            log.warning("worker.metrics_flush_failed", error=str(e))

        self._success_count = 0
        self._failure_count = 0
        self._total_duration = 0.0
        self._last_flush = time.monotonic()
