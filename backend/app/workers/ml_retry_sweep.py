"""Retry SQS enqueue for incidents stuck in ml_classification_status=pending."""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.incident import Incident
from app.services.sqs_service import sqs_service

logger = logging.getLogger(__name__)


async def sweep_pending_ml_classifications() -> int:
    """
    Re-enqueue classify jobs for pending incidents with exponential backoff.

    Bounded attempts prevent infinite loops when SQS is permanently unavailable.
    """
    now = datetime.now(UTC)
    max_attempts = settings.ML_PENDING_MAX_ATTEMPTS
    retried = 0

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Incident)
            .where(Incident.ml_classification_status == "pending")
            .where(Incident.ml_classification_attempts < max_attempts)
            .where(
                (Incident.ml_classification_next_retry_at.is_(None))
                | (Incident.ml_classification_next_retry_at <= now)
            )
            .limit(25)
        )
        incidents = result.scalars().all()
        for incident in incidents:
            try:
                sqs_service.enqueue_incident(str(incident.id), "classify")
                incident.ml_classification_next_retry_at = now + timedelta(
                    seconds=min(
                        3600,
                        settings.ML_PENDING_RETRY_BASE_SECONDS
                        * (2 ** incident.ml_classification_attempts),
                    )
                )
                incident.ml_classification_attempts += 1
                retried += 1
                logger.info(
                    "ML retry enqueue incident=%s attempt=%s",
                    incident.id,
                    incident.ml_classification_attempts,
                )
            except Exception as exc:
                incident.ml_classification_attempts += 1
                incident.ml_classification_next_retry_at = now + timedelta(
                    seconds=settings.ML_PENDING_RETRY_BASE_SECONDS
                    * (2 ** incident.ml_classification_attempts)
                )
                logger.error(
                    "ML retry enqueue failed incident=%s: %s",
                    incident.id,
                    exc,
                )
        if incidents:
            await db.commit()
    return retried
