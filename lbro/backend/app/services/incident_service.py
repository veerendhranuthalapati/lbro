"""
LBRO — IncidentService
Orchestrates: creation → jurisdiction detection → SQS dispatch → timeline events
"""
import json
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.incident import (
    Incident,
    IncidentStatus,
    IncidentTimelineEvent,
    Jurisdiction,
    RegulatoryNotification,
)
from app.schemas.incident import IncidentCreate, IncidentUpdate

log = structlog.get_logger(__name__)

DEADLINES: dict[Jurisdiction, timedelta] = {
    Jurisdiction.GDPR:  timedelta(hours=settings.GDPR_NOTIFICATION_HOURS),
    Jurisdiction.HIPAA: timedelta(days=settings.HIPAA_NOTIFICATION_DAYS),
    Jurisdiction.DPDPA: timedelta(hours=settings.DPDPA_NOTIFICATION_HOURS),
}

AUTHORITIES: dict[Jurisdiction, str] = {
    Jurisdiction.GDPR:  "Lead Supervisory Authority (per GDPR Art. 55)",
    Jurisdiction.HIPAA: "HHS Office for Civil Rights",
    Jurisdiction.DPDPA: "Data Protection Board of India",
}


class IncidentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_and_dispatch(self, payload: IncidentCreate) -> Incident:
        """
        Full ingestion pipeline:
        1. Detect applicable jurisdictions
        2. Persist incident
        3. Create regulatory notification records with deadlines
        4. Enqueue to SQS for worker containment
        5. Write initial timeline event
        """
        jurisdictions = self._detect_jurisdictions(payload)

        incident = Incident(
            title=payload.title,
            description=payload.description,
            severity=payload.severity,
            source_system=payload.source_system,
            source_ip=payload.source_ip,
            affected_systems=payload.affected_systems,
            affected_records_count=payload.affected_records_count,
            external_id=payload.external_id,
            contains_pii=payload.contains_pii,
            contains_phi=payload.contains_phi,
            raw_payload=payload.raw_payload,
            jurisdictions=[j.value for j in jurisdictions],
            status=IncidentStatus.DETECTED,
        )
        self.db.add(incident)
        await self.db.flush()  # Get ID without committing

        for jx in jurisdictions:
            notif = RegulatoryNotification(
                incident_id=incident.id,
                jurisdiction=jx,
                deadline_at=datetime.now(timezone.utc) + DEADLINES[jx],
                template_version="v1",
                recipient_authority=AUTHORITIES[jx],
            )
            self.db.add(notif)

        self.db.add(IncidentTimelineEvent(
            incident_id=incident.id,
            event_type="incident.created",
            actor="system:api",
            description=f"Incident ingested from {incident.source_system}",
            event_metadata={"jurisdictions": [j.value for j in jurisdictions]},
        ))

        await self.db.flush()

        msg_id = await self._enqueue_incident(incident)
        if msg_id:
            incident.sqs_message_id = msg_id
            incident.status = IncidentStatus.TRIAGING

        await self.db.commit()
        await self.db.refresh(incident)
        return incident

    async def update_status(self, incident: Incident, payload: IncidentUpdate) -> Incident:
        now = datetime.now(timezone.utc)

        if payload.status:
            old_status = incident.status
            incident.status = payload.status

            if payload.status == IncidentStatus.CONTAINED:
                incident.contained_at = now
            elif payload.status == IncidentStatus.CLOSED:
                incident.closed_at = now

            self.db.add(IncidentTimelineEvent(
                incident_id=incident.id,
                event_type="incident.status_changed",
                actor="system:api",
                description=f"Status changed: {old_status} → {payload.status}",
            ))

        if payload.contains_pii is not None:
            incident.contains_pii = payload.contains_pii
        if payload.contains_phi is not None:
            incident.contains_phi = payload.contains_phi
        if payload.affected_records_count is not None:
            incident.affected_records_count = payload.affected_records_count

        await self.db.commit()
        await self.db.refresh(incident)
        return incident

    def _detect_jurisdictions(self, payload: IncidentCreate) -> list[Jurisdiction]:
        """
        Heuristic jurisdiction detector.
        PII → GDPR + DPDPA, PHI → HIPAA, any affected records → conservative GDPR default.
        """
        jx: set[Jurisdiction] = set()

        if payload.contains_pii:
            jx.add(Jurisdiction.GDPR)
            jx.add(Jurisdiction.DPDPA)

        if payload.contains_phi:
            jx.add(Jurisdiction.HIPAA)

        # Conservative fallback: records exposed but classification unknown → GDPR
        if payload.affected_records_count and payload.affected_records_count > 0 and not jx:
            jx.add(Jurisdiction.GDPR)

        return list(jx)

    async def _enqueue_incident(self, incident: Incident) -> str | None:
        """Send incident to SQS for worker processing. Returns message ID or None on failure."""
        if not settings.SQS_QUEUE_URL:
            log.warning("sqs.not_configured", incident_id=str(incident.id))
            return None

        try:
            from app.core.aws_clients import get_sqs
            client = get_sqs()
            message = {
                "incident_id": str(incident.id),
                "severity": incident.severity.value,
                "source_system": incident.source_system,
                "source_ip": incident.source_ip,
                "affected_systems": incident.affected_systems or [],
                "contains_pii": incident.contains_pii,
                "contains_phi": incident.contains_phi,
                "jurisdictions": incident.jurisdictions or [],
                "detected_at": incident.detected_at.isoformat(),
            }
            resp = client.send_message(
                QueueUrl=settings.SQS_QUEUE_URL,
                MessageBody=json.dumps(message),
                MessageAttributes={
                    "severity": {"StringValue": incident.severity.value, "DataType": "String"},
                },
            )
            log.info("sqs.enqueued", incident_id=str(incident.id), message_id=resp["MessageId"])
            return resp["MessageId"]
        except Exception as e:
            log.error("sqs.enqueue_failed", incident_id=str(incident.id), error=str(e))
            return None
