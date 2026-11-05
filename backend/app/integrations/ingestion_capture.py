"""Persist ingestion artifacts — evidence vault + incident enrichment."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.integrations.event_context import (
    build_http_log_excerpt,
    compliance_from_payload,
    extract_endpoint_context,
    extract_integration_context,
)
from app.models.evidence import ChainOfCustody, Evidence
from app.models.incident import Incident, IncidentAction
from app.models.security_event import SecurityEvent
from app.services.s3_service import compute_sha256


def _json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, indent=2, default=str).encode("utf-8")


async def enrich_incident_from_payload(
    incident: Incident,
    data: Any,
    event: SecurityEvent,
) -> None:
    """Copy network topology and flow features from the event payload onto the incident."""
    ctx = extract_endpoint_context(data.payload or {})
    if ctx.get("destination_ip"):
        incident.destination_ip = ctx["destination_ip"]
    if ctx.get("source_port") is not None:
        incident.source_port = ctx["source_port"]
    if ctx.get("destination_port") is not None:
        incident.destination_port = ctx["destination_port"]
    if ctx.get("protocol"):
        incident.protocol = ctx["protocol"]
    if ctx.get("network_features"):
        incident.network_features = ctx["network_features"]

    integration = extract_integration_context(
        data.payload or {},
        event_type=getattr(data, "event_type", ""),
        source_ip=getattr(data, "source_ip", None),
        source_application=getattr(data, "source_application", None),
        source_host=getattr(data, "source_host", None),
    )
    integration["security_event_id"] = str(event.id)
    incident.integration_context = integration

    for field, value in compliance_from_payload(data.payload).items():
        setattr(incident, field, value)

    if incident.network_features and event.ml_source == "model":
        incident.ml_classification_status = "completed"
    elif incident.network_features:
        incident.ml_classification_status = "pending"


async def record_ingestion_ml_action(
    db: AsyncSession,
    incident: Incident,
    event: SecurityEvent,
) -> None:
    """Audit trail for ML outcome tied to the ingested event."""
    if not event.ml_attack_category:
        return

    action = IncidentAction(
        incident_id=incident.id,
        action_type="ml_classification",
        description=(
            f"Ingestion ML: '{event.ml_attack_category}' "
            f"source={event.ml_source} confidence={event.ml_confidence or 0:.1%} "
            f"coverage={event.ml_feature_coverage or 0:.0%}"
        ),
        automated=True,
        result=f"severity={incident.severity}, review_needed={incident.needs_analyst_review}",
        action_metadata={
            "security_event_id": str(event.id),
            "ml_source": event.ml_source,
            "ml_confidence": event.ml_confidence,
            "ml_feature_coverage": event.ml_feature_coverage,
            "ml_needs_review": event.ml_needs_review,
        },
    )
    db.add(action)


async def capture_ingestion_evidence(
    db: AsyncSession,
    incident_id: uuid.UUID,
    event: SecurityEvent,
    data: Any,
) -> int:
    """
    Store structured capture files in the evidence vault (PostgreSQL file_data).

    Returns number of evidence rows created.
    """
    if not settings.EVENT_INGESTION_CAPTURE_EVIDENCE:
        return 0

    created = 0
    ts = datetime.now(timezone.utc).isoformat()

    snapshot = {
        "captured_at": ts,
        "security_event_id": str(event.id),
        "incident_id": str(incident_id),
        "ingestion": {
            "event_type": data.event_type,
            "severity": data.severity,
            "source_ip": data.source_ip,
            "source_host": data.source_host,
            "source_application": data.source_application,
            "message": data.message,
            "event_timestamp": data.event_timestamp.isoformat() if data.event_timestamp else None,
        },
        "ml": {
            "attack_category": event.ml_attack_category,
            "confidence": event.ml_confidence,
            "source": event.ml_source,
            "feature_coverage": event.ml_feature_coverage,
            "needs_review": event.ml_needs_review,
            "model_version": event.ml_model_version,
        },
        "payload": data.payload or {},
    }
    created += await _add_evidence_file(
        db,
        incident_id,
        filename=f"ingestion-event-{event.id}.json",
        content_type="application/json",
        data=_json_bytes(snapshot),
        description="Full ingestion snapshot (event + payload + ML provenance)",
        tags='["ingestion","event-snapshot"]',
    )

    http_log = build_http_log_excerpt(data.payload)
    if http_log:
        created += await _add_evidence_file(
            db,
            incident_id,
            filename=f"http-access-{event.id}.log",
            content_type="text/plain",
            data=http_log.encode("utf-8"),
            description="HTTP access log excerpt from integration payload",
            tags='["ingestion","http-log"]',
        )

    ctx = extract_endpoint_context(data.payload or {})
    flows = ctx.get("network_features")
    if flows:
        flow_doc = {
            "captured_at": ts,
            "security_event_id": str(event.id),
            "network": {
                k: v
                for k, v in ctx.items()
                if k != "network_features"
            },
            "network_features": flows,
        }
        created += await _add_evidence_file(
            db,
            incident_id,
            filename=f"network-flow-{event.id}.json",
            content_type="application/json",
            data=_json_bytes(flow_doc),
            description="Network flow features (ML input vector)",
            tags='["ingestion","network-flow"]',
        )

    return created


async def _add_evidence_file(
    db: AsyncSession,
    incident_id: uuid.UUID,
    *,
    filename: str,
    content_type: str,
    data: bytes,
    description: str,
    tags: str,
) -> int:
    sha = compute_sha256(data)
    ev = Evidence(
        incident_id=incident_id,
        filename=filename,
        original_filename=filename,
        content_type=content_type,
        file_size=len(data),
        sha256_hash=sha,
        description=description,
        tags=tags,
        uploaded_by=None,
        file_data=data,
        is_immutable=True,
    )
    db.add(ev)
    await db.flush()

    custody = ChainOfCustody(
        evidence_id=ev.id,
        action="ingested",
        performed_by=None,
        performed_by_name="LBRO Event Ingestion",
        notes=f"Auto-captured on POST /api/v1/events ({filename})",
        hash_at_time=sha,
    )
    db.add(custody)
    await db.flush()
    return 1
