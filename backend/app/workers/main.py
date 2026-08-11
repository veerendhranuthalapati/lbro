"""Worker entry point — polls SQS queues and dispatches jobs."""
from __future__ import annotations

import asyncio
import json
import logging
import signal
from pathlib import Path

from app.config import settings
from app.workers.incident_worker import process_incident_message
from app.workers.notification_worker import process_notification_message

logger = logging.getLogger(__name__)
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")

_shutdown = False
HEARTBEAT_PATH = Path("/tmp/lbro-worker-heartbeat")
HEARTBEAT_INTERVAL_SECONDS = 15


def _touch_heartbeat() -> None:
    """Update mtime for Docker/process health monitoring (no HTTP server)."""
    HEARTBEAT_PATH.parent.mkdir(parents=True, exist_ok=True)
    HEARTBEAT_PATH.touch()


async def _heartbeat_loop() -> None:
    while not _shutdown:
        _touch_heartbeat()
        await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)


def _handle_signal(sig, frame):
    global _shutdown
    logger.info("Received signal %s, shutting down gracefully...", sig)
    _shutdown = True


async def poll_queue(queue_url: str, handler) -> None:
    """Long-poll a SQS queue and dispatch messages to handler."""
    from app.services.sqs_service import sqs_service
    logger.info("Starting poll loop for %s", queue_url)
    while not _shutdown:
        try:
            messages = sqs_service.receive_messages(
                queue_url,
                max_messages=settings.SQS_MAX_MESSAGES,
                wait_time=settings.SQS_WAIT_TIME_SECONDS,
            )
            for msg in messages:
                try:
                    body = json.loads(msg["Body"])
                    await handler(body)
                    sqs_service.delete_message(queue_url, msg["ReceiptHandle"])
                    logger.info("Processed message %s", msg.get("MessageId"))
                except Exception as exc:
                    logger.error("Failed to process message %s: %s", msg.get("MessageId"), exc)
        except Exception as exc:
            logger.error("Queue poll error: %s", exc)
            await asyncio.sleep(5)


async def main() -> None:
    global _shutdown
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    _touch_heartbeat()
    heartbeat_task = asyncio.create_task(_heartbeat_loop())

    tasks = []
    if settings.SQS_INCIDENT_QUEUE_URL:
        tasks.append(poll_queue(settings.SQS_INCIDENT_QUEUE_URL, process_incident_message))
    if settings.SQS_NOTIFICATION_QUEUE_URL:
        tasks.append(poll_queue(settings.SQS_NOTIFICATION_QUEUE_URL, process_notification_message))

    try:
        if not tasks:
            logger.warning("No SQS queues configured — worker idle (waiting for shutdown signal)")
            while not _shutdown:
                await asyncio.sleep(30)
            return

        await asyncio.gather(*tasks)
    finally:
        _shutdown = True
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    asyncio.run(main())
