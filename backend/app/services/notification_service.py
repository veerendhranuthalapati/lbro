"""Regulatory notification state machine and delivery service."""
from __future__ import annotations

import asyncio
import smtplib
import uuid
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from string import Template
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.exceptions import NotFoundError, ConflictError
from app.models.notification import Notification
from app.models.incident import Incident
from app.models.user import User
from app.services.sqs_service import sqs_service


# ── Notification templates ────────────────────────────────────────────────────
# Use string.Template ($var syntax) instead of str.format() so that curly
# braces inside user-controlled fields (incident titles, descriptions) cannot
# cause KeyError or format-string injection.
NOTIFICATION_TEMPLATES = {
    "GDPR": {
        "subject": "[GDPR Article 33] Personal Data Breach Notification - $incident_title",
        "body": Template("""Dear Data Protection Authority,

We are writing to notify you of a personal data breach as required under Article 33 of the General Data Protection Regulation (GDPR).

INCIDENT DETAILS:
- Incident ID: $incident_id
- Title: $incident_title
- Detection Date: $detected_at
- Severity: $severity
- Attack Category: $attack_category

NATURE OF BREACH:
$description

CATEGORIES OF DATA SUBJECTS:
Affected individuals whose personal data may have been compromised.

APPROXIMATE NUMBER OF DATA SUBJECTS:
Under investigation.

LIKELY CONSEQUENCES:
The breach may result in unauthorized access to personal data.

MEASURES TAKEN:
$containment_actions

We are continuing our investigation and will provide further updates as they become available.

Contact: $contact_email
Data Controller: LBRO Security Operations

This notification is submitted within the 72-hour requirement of GDPR Article 33.
"""),
    },
    "HIPAA": {
        "subject": "[HIPAA Breach Notification] - $incident_title",
        "body": Template("""Dear HHS Office for Civil Rights,

This notification is submitted pursuant to the HIPAA Breach Notification Rule (45 CFR SS 164.400-414).

BREACH DETAILS:
- Incident ID: $incident_id
- Discovery Date: $detected_at
- Breach Title: $incident_title
- Severity: $severity

DESCRIPTION OF BREACH:
$description

TYPES OF INFORMATION INVOLVED:
Protected Health Information (PHI)

STEPS TAKEN:
$containment_actions

We are conducting a full risk assessment and will notify affected individuals as required.

Contact Information: $contact_email
"""),
    },
    "DPDPA": {
        "subject": "[DPDPA] Personal Data Breach Intimation - $incident_title",
        "body": Template("""To the Data Protection Board of India,

We hereby intimate you of a personal data breach as required under the Digital Personal Data Protection Act, 2023.

BREACH INTIMATION:
- Incident Reference: $incident_id
- Date of Breach Detection: $detected_at
- Nature of Breach: $attack_category
- Severity: $severity

DESCRIPTION:
$description

REMEDIAL ACTIONS:
$containment_actions

We shall provide a detailed report within the prescribed timeline.

Data Fiduciary Contact: $contact_email
"""),
    },
}


class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_for_incident(self, incident: Incident) -> list[Notification]:
        notifications = []
        now = datetime.now(timezone.utc)
        jurisdictions = incident.affected_jurisdictions or []

        rules = {
            "GDPR": {"hours": settings.GDPR_NOTIFICATION_HOURS, "jurisdictions": ["EU", "EEA", "UK"]},
            "HIPAA": {"hours": settings.HIPAA_NOTIFICATION_HOURS, "jurisdictions": ["US"]},
            "DPDPA": {"hours": settings.DPDPA_NOTIFICATION_HOURS, "jurisdictions": ["IN"]},
        }

        for regulation, rule in rules.items():
            should_notify = any(j in rule["jurisdictions"] for j in jurisdictions)
            if regulation == "HIPAA" and incident.health_data_involved:
                should_notify = True
            if regulation in ("GDPR", "DPDPA") and incident.personal_data_involved:
                should_notify = True
            if not should_notify:
                continue

            template = NOTIFICATION_TEMPLATES[regulation]
            containment = ", ".join(incident.containment_actions or ["Containment in progress"])
            vars = dict(
                incident_id=str(incident.id),
                incident_title=incident.title,
                detected_at=incident.detected_at.strftime("%Y-%m-%d %H:%M UTC"),
                severity=incident.severity,
                attack_category=incident.attack_category or "Under investigation",
                description=incident.description or "Details under investigation.",
                containment_actions=containment,
                contact_email=settings.SMTP_FROM,
            )
            # Template.safe_substitute leaves unknown $placeholders intact rather than raising
            subject = Template(template["subject"]).safe_substitute(vars)
            body = template["body"].safe_substitute(vars)

            notification = Notification(
                incident_id=incident.id,
                regulation=regulation,
                jurisdiction=",".join(rule["jurisdictions"]),
                authority=f"{regulation} Supervisory Authority",
                status="pending",
                subject=subject,
                body=body,
                deadline=now + timedelta(hours=rule["hours"]),
            )
            self.db.add(notification)
            notifications.append(notification)

        await self.db.flush()
        return notifications

    async def get(self, notification_id: uuid.UUID) -> Notification:
        result = await self.db.execute(
            select(Notification)
            .where(Notification.id == notification_id)
            .options(selectinload(Notification.recipients))
        )
        n = result.scalar_one_or_none()
        if not n:
            raise NotFoundError("Notification")
        return n

    async def approve(self, notification_id: uuid.UUID, approver: User) -> Notification:
        n = await self.get(notification_id)
        if n.status != "pending":
            raise ConflictError(f"Notification status is '{n.status}', expected 'pending'")
        n.status = "approved"
        n.approved_by = approver.id
        n.approved_at = datetime.now(timezone.utc)
        await self.db.flush()
        # Queue for sending
        try:
            sqs_service.enqueue_notification(str(notification_id))
        except Exception:
            pass
        return n

    async def send(self, notification_id: uuid.UUID) -> Notification:
        n = await self.get(notification_id)
        if n.status not in ("approved", "failed"):
            raise ConflictError(f"Cannot send notification in status '{n.status}'")

        try:
            await self._send_email(n)
            n.status = "sent"
            n.sent_at = datetime.now(timezone.utc)
            n.last_error = None
        except Exception as exc:
            n.status = "failed"
            n.retry_count += 1
            n.last_error = str(exc)

        await self.db.flush()
        return n

    async def _send_email(self, notification: Notification) -> None:
        import logging
        log = logging.getLogger(__name__)

        if not settings.SMTP_HOST:
            # Log instead of sending in dev/test
            log.info("[DEV] Would send %s notification to %s", notification.regulation, notification.authority_email)
            return

        msg = MIMEMultipart("alternative")
        msg["Subject"] = notification.subject
        msg["From"] = settings.SMTP_FROM
        msg["To"] = notification.authority_email or "dpa@example.com"
        msg.attach(MIMEText(notification.body, "plain"))

        # smtplib is synchronous; run in a thread pool to avoid blocking the event loop.
        def _smtp_send() -> None:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _smtp_send)

    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        regulation: Optional[str] = None,
        incident_id: Optional[uuid.UUID] = None,
    ) -> tuple[list[Notification], int]:
        query = select(Notification).options(selectinload(Notification.recipients))
        count_query = select(func.count(Notification.id))

        if status:
            query = query.where(Notification.status == status)
            count_query = count_query.where(Notification.status == status)
        if regulation:
            query = query.where(Notification.regulation == regulation)
            count_query = count_query.where(Notification.regulation == regulation)
        if incident_id:
            query = query.where(Notification.incident_id == incident_id)
            count_query = count_query.where(Notification.incident_id == incident_id)

        total = (await self.db.execute(count_query)).scalar_one()
        result = await self.db.execute(
            query.order_by(Notification.deadline.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return result.scalars().all(), total
