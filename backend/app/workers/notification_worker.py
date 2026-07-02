"""Notification worker — sends approved regulatory notifications with retry logic."""
from __future__ import annotations

import logging
import uuid

from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


async def process_notification_message(body: dict) -> None:
    notification_id = body.get("notification_id")
    if not notification_id:
        logger.error("Missing notification_id in message: %s", body)
        return
    await send_notification(uuid.UUID(notification_id))


async def send_notification(notification_id: uuid.UUID) -> None:
    from sqlalchemy import select
    from app.models.notification import Notification
    from app.services.notification_service import NotificationService

    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(Notification).where(Notification.id == notification_id)
            )
            notification = result.scalar_one_or_none()
            if not notification:
                logger.warning("Notification %s not found", notification_id)
                return

            if notification.status not in ("approved", "failed"):
                logger.info(
                    "Notification %s in status '%s', skipping send",
                    notification_id, notification.status
                )
                return

            if notification.retry_count >= MAX_RETRIES:
                logger.error(
                    "Notification %s exceeded max retries (%d), giving up",
                    notification_id, MAX_RETRIES
                )
                return

            svc = NotificationService(db)
            await svc.send(notification_id)
            await db.commit()

            if notification.status == "sent":
                logger.info("Notification %s sent successfully", notification_id)
            else:
                logger.warning(
                    "Notification %s failed (attempt %d): %s",
                    notification_id, notification.retry_count, notification.last_error
                )
        except Exception as exc:
            await db.rollback()
            logger.error("Error processing notification %s: %s", notification_id, exc)
            raise
