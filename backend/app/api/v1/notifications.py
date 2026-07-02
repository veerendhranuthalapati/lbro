"""
LBRO — Regulatory Notifications router

Endpoints:
  GET  /api/v1/incidents/{id}/notifications                   — list + deadline status
  POST /api/v1/incidents/{id}/notifications/{nid}/dispatch    — trigger dispatch

Rate limits:
  GET  — 60/minute  dashboard polling
  POST — 10/minute  dispatch is a one-shot legal action; aggressive retries indicate a bug
"""
import json
import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.aws_clients import get_sqs
from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.core.security import RequireAPIKey
from app.models.incident import NotificationStatus, RegulatoryNotification
from app.schemas.incident import NotificationOut

log = structlog.get_logger(__name__)
router = APIRouter(dependencies=[RequireAPIKey])


@router.get(
    "/incidents/{incident_id}/notifications",
    response_model=list[NotificationOut],
    summary="List regulatory notifications for an incident",
)
@limiter.limit("60/minute")
async def list_notifications(
    request: Request,
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    result = await db.execute(
        select(RegulatoryNotification)
        .where(RegulatoryNotification.incident_id == incident_id)
        .order_by(RegulatoryNotification.deadline_at)
    )
    return result.scalars().all()


@router.post(
    "/incidents/{incident_id}/notifications/{notification_id}/dispatch",
    response_model=NotificationOut,
    status_code=status.HTTP_200_OK,
    summary="Manually trigger notification dispatch",
)
@limiter.limit("10/minute")
async def dispatch_notification(
    request: Request,
    incident_id: uuid.UUID,
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    result = await db.execute(
        select(RegulatoryNotification).where(
            RegulatoryNotification.id == notification_id,
            RegulatoryNotification.incident_id == incident_id,
        )
    )
    notif = result.scalar_one_or_none()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")

    if notif.status == NotificationStatus.DISPATCHED:
        raise HTTPException(status_code=409, detail="Notification already dispatched")

    # Enqueue to notification_dispatch SQS queue for async processing by the worker
    if settings.SQS_NOTIFICATION_QUEUE_URL:
        try:
            get_sqs().send_message(
                QueueUrl=settings.SQS_NOTIFICATION_QUEUE_URL,
                MessageBody=json.dumps({
                    "notification_id": str(notif.id),
                    "incident_id":     str(notif.incident_id),
                    "jurisdiction":    notif.jurisdiction.value,
                    "deadline_at":     notif.deadline_at.isoformat(),
                    "recipient":       notif.recipient_authority,
                    "template":        notif.template_version,
                    "triggered_by":    "manual_dispatch",
                }),
                MessageAttributes={
                    "jurisdiction": {
                        "StringValue": notif.jurisdiction.value,
                        "DataType": "String",
                    }
                },
            )
            log.info(
                "notification.enqueued",
                notification_id=str(notification_id),
                jurisdiction=notif.jurisdiction,
            )
        except Exception as e:
            log.error("notification.enqueue_failed", notification_id=str(notification_id), error=str(e))
            raise HTTPException(
                status_code=502,
                detail="Failed to enqueue notification — SQS unavailable",
            ) from e
    else:
        log.warning(
            "notification.sqs_not_configured",
            notification_id=str(notification_id),
        )

    return notif
