"""
LBRO — SQS Worker
Polls the incident-events queue and processes each message through the
containment pipeline. Designed to run as a long-lived ECS Fargate task.

Resilience features:
  - Exponential backoff on empty-queue polls (reduces SQS cost at idle)
  - Per-message visibility extension to prevent re-delivery during processing
  - Structured error handling: transient failures extend visibility,
    poison messages are allowed to exhaust maxReceiveCount → DLQ
  - Graceful shutdown on SIGTERM — finishes in-flight message before exiting
  - Idempotency check: skips already-contained incidents
"""
from __future__ import annotations

import asyncio
import json
import signal
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import select

from app.core.aws_clients import get_sqs
from app.config import settings
from app.core.database import AsyncSessionLocal, Base, engine
from app.core.logging import configure_logging
from app.models.incident import (
    Incident,
    IncidentStatus,
    IncidentTimelineEvent,
)
from app.worker.containment import ContainmentPipeline
from app.worker.metrics import WorkerMetrics

log = structlog.get_logger(__name__)

# ── Backoff config ─────────────────────────────────────────────────────────────
_MIN_POLL_INTERVAL = 0.1   # 100ms between polls when queue has messages
_MAX_POLL_INTERVAL = 20.0  # 20s when queue is empty (saves SQS API costs)
_BACKOFF_FACTOR    = 1.5   # Multiply interval by this on each empty poll
_VISIBILITY_EXTEND = 60    # Extend visibility by 60s mid-processing to prevent re-delivery


@dataclass
class WorkerConfig:
    queue_url: str
    max_messages: int = 10   # SQS batch size
    wait_time_seconds: int = 20  # Long-poll — reduces empty responses
    shutdown_timeout: int = 30   # Seconds to finish in-flight on SIGTERM


class Worker:
    def __init__(self, config: WorkerConfig) -> None:
        self.config = config
        self.metrics = WorkerMetrics()
        self._shutdown_event = asyncio.Event()
        self._in_flight = 0

    def _register_signals(self) -> None:
        """Register SIGTERM/SIGINT handlers for graceful shutdown."""
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._handle_shutdown_signal)

    def _handle_shutdown_signal(self) -> None:
        log.info("worker.shutdown_signal_received")
        self._shutdown_event.set()

    async def run(self) -> None:
        self._register_signals()
        poll_interval = _MIN_POLL_INTERVAL
        Path("/tmp/worker.heartbeat").touch()  # nosec B108 — intentional: container-local heartbeat file, not shared
        log.info("worker.started", queue_url=self.config.queue_url)

        while not self._shutdown_event.is_set():
            try:
                messages = await self._poll()
            except Exception as e:
                log.error("worker.poll_failed", error=str(e))
                await asyncio.sleep(5)
                continue

            if not messages:
                # Exponential backoff on empty queue
                poll_interval = min(poll_interval * _BACKOFF_FACTOR, _MAX_POLL_INTERVAL)
                await asyncio.sleep(poll_interval)
                continue

            # Reset backoff when work arrives
            poll_interval = _MIN_POLL_INTERVAL
            # Heartbeat: ECS health check verifies this file is recent
            Path("/tmp/worker.heartbeat").touch()  # nosec B108 — intentional: container-local, not shared

            # Process messages concurrently (bounded by batch size)
            tasks = [self._handle_message(msg) for msg in messages]
            await asyncio.gather(*tasks, return_exceptions=True)

        # Graceful shutdown: wait for in-flight processing to complete
        log.info("worker.draining", in_flight=self._in_flight)
        deadline = time.monotonic() + self.config.shutdown_timeout
        while self._in_flight > 0 and time.monotonic() < deadline:
            await asyncio.sleep(0.5)
        log.info("worker.stopped")

    async def _poll(self) -> list[dict[str, Any]]:
        """Long-poll SQS for up to max_messages."""
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: get_sqs().receive_message(
                QueueUrl=self.config.queue_url,
                MaxNumberOfMessages=self.config.max_messages,
                WaitTimeSeconds=self.config.wait_time_seconds,
                AttributeNames=["ApproximateReceiveCount"],
                MessageAttributeNames=["severity"],
            ),
        )
        return response.get("Messages", [])

    async def _handle_message(self, message: dict[str, Any]) -> None:
        """Process one SQS message with visibility extension and error handling."""
        receipt = message["ReceiptHandle"]
        receive_count = int(
            message.get("Attributes", {}).get("ApproximateReceiveCount", "1")
        )

        self._in_flight += 1
        started = time.monotonic()

        try:
            body = json.loads(message["Body"])
            incident_id = body["incident_id"]

            log.info(
                "worker.message_received",
                incident_id=incident_id,
                receive_count=receive_count,
            )

            # Start a background task to extend visibility while we process
            extend_task = asyncio.create_task(
                self._extend_visibility_loop(receipt, incident_id)
            )

            try:
                await self._process_incident(body)
            finally:
                extend_task.cancel()
                try:
                    await extend_task
                except asyncio.CancelledError:
                    pass

            # Delete on success
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: get_sqs().delete_message(
                    QueueUrl=self.config.queue_url,
                    ReceiptHandle=receipt,
                ),
            )

            duration = time.monotonic() - started
            self.metrics.record_success(duration)
            log.info(
                "worker.message_processed",
                incident_id=incident_id,
                duration_s=round(duration, 2),
            )

        except Exception as e:
            duration = time.monotonic() - started
            self.metrics.record_failure()
            log.error(
                "worker.message_failed",
                error=str(e),
                receive_count=receive_count,
                duration_s=round(duration, 2),
            )
            # Don't delete — let SQS retry. After maxReceiveCount it goes to DLQ.
        finally:
            self._in_flight -= 1

    async def _extend_visibility_loop(
        self, receipt: str, incident_id: str
    ) -> None:
        """Periodically extends message visibility to prevent re-delivery."""
        while True:
            await asyncio.sleep(_VISIBILITY_EXTEND // 2)
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: get_sqs().change_message_visibility(
                        QueueUrl=self.config.queue_url,
                        ReceiptHandle=receipt,
                        VisibilityTimeout=_VISIBILITY_EXTEND,
                    ),
                )
                log.debug("worker.visibility_extended", incident_id=incident_id)
            except Exception as e:
                log.warning("worker.visibility_extend_failed", error=str(e))

    async def _process_incident(self, body: dict[str, Any]) -> None:
        """Core processing pipeline for one incident message."""
        incident_id = body["incident_id"]

        async with AsyncSessionLocal() as session:
            # Idempotency: skip if already contained
            result = await session.execute(
                select(Incident).where(Incident.id == incident_id)  # type: ignore[arg-type]
            )
            incident = result.scalar_one_or_none()

            if incident is None:
                log.warning("worker.incident_not_found", incident_id=incident_id)
                return

            if incident.status in (IncidentStatus.CONTAINED, IncidentStatus.CLOSED):
                log.info(
                    "worker.incident_already_contained",
                    incident_id=incident_id,
                    status=incident.status,
                )
                return

            # Mark as containing
            incident.status = IncidentStatus.CONTAINING
            session.add(
                IncidentTimelineEvent(
                    incident_id=incident.id,
                    event_type="containment.started",
                    actor="system:worker",
                    description="Worker began containment pipeline",
                )
            )
            await session.commit()

            # Run containment pipeline
            pipeline = ContainmentPipeline(session)
            await pipeline.run(incident, body)


async def _startup() -> None:
    configure_logging()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("worker.db_ready")


def main() -> None:
    asyncio.run(_startup())

    if not settings.SQS_QUEUE_URL:
        raise RuntimeError("SQS_QUEUE_URL must be set for worker mode")

    worker = Worker(WorkerConfig(queue_url=settings.SQS_QUEUE_URL))
    asyncio.run(worker.run())


if __name__ == "__main__":
    main()
