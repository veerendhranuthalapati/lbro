"""Event ingestion router — public API for external applications.

Authentication:
  Bearer <PROJECT_API_KEY>   (format: proj_<random>)

The project_id is ALWAYS resolved from the authenticated API key.
It is NEVER accepted from the request body, query string, or any
client-supplied field.  This is the security contract.

Ingestion pipeline:
  1. Project API key auth  -> resolve project_id
  2. Schema validation     -> FastAPI Pydantic
  3. SecurityEvent created -> stored with processing_status=pending
  4. ML classification     -> classify if ML features available
  5. Incident auto-create  -> for high/critical severity events
  6. Mark processed        -> processing_status=processed
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_project_from_api_key
from app.models.project import Project
from app.models.security_event import SecurityEvent

router = APIRouter(tags=["events"])

# ── Allowed event types ───────────────────────────────────────────────────────
ALLOWED_EVENT_TYPES = {
    "auth_failure",
    "sql_injection",
    "xss",
    "brute_force",
    "port_scan",
    "suspicious_request",
    "system_log",
    "application_log",
    "nginx_log",
    "apache_log",
    "firewall_event",
    "windows_event",
    "linux_audit",
    "custom",
}

ALLOWED_SEVERITIES = {"critical", "high", "medium", "low", "info"}

# event_type -> CICIDS2017 attack category (heuristic fallback when no ML features)
_SEVERITY_TO_ATTACK = {
    "sql_injection":      "Web Attack - Sql Injection",
    "xss":                "Web Attack - XSS",
    "brute_force":        "Web Attack - Brute Force",
    "port_scan":          "PortScan",
    "auth_failure":       "Web Attack - Brute Force",
    "firewall_event":     "PortScan",
    "suspicious_request": "Web Attack - Brute Force",
    "system_log":         "Bot",
    "application_log":    "Bot",
    "nginx_log":          "Web Attack - Brute Force",
    "apache_log":         "Web Attack - Brute Force",
    "windows_event":      "Infiltration",
    "linux_audit":        "Infiltration",
    "custom":             "BENIGN",
}


# ── Schema ─────────────────────────────────────────────────────────────────────

class SecurityEventCreate(BaseModel):
    event_type: str = Field(..., description="Type of security event")
    severity: str = Field("medium", description="Event severity: critical/high/medium/low/info")
    source_ip: str | None = Field(None, description="Source IP address of the event")
    source_host: str | None = Field(None, description="Hostname of the source system")
    source_application: str | None = Field(None, description="Application name that generated the event")
    source_agent_version: str | None = Field(None, description="LBRO agent version (if sent via agent)")
    message: str | None = Field(None, description="Human-readable event summary")
    event_timestamp: datetime | None = Field(None, description="When the event occurred (UTC ISO8601)")
    payload: dict[str, Any] = Field(default_factory=dict, description="Raw event data as key-value pairs")

    model_config = {"extra": "ignore"}


class SecurityEventBatch(BaseModel):
    events: list[SecurityEventCreate] = Field(..., min_length=1, max_length=1000)

    model_config = {"extra": "ignore"}


class SecurityEventResponse(BaseModel):
    id: str
    project_id: str
    event_type: str
    severity: str
    processing_status: str
    incident_id: str | None
    ml_attack_category: str | None
    ml_confidence: float | None
    created_at: str


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/events", status_code=202, response_model=SecurityEventResponse)
async def ingest_event(
    body: SecurityEventCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    project: Annotated[Project, Depends(get_project_from_api_key)],
):
    """Ingest a single security event.

    Authenticated via project API key (Bearer proj_*).
    project_id is resolved from the key — never from the request body.
    """
    event = await _ingest_single(db, project, body)
    return _event_to_response(event)


@router.post("/events/batch", status_code=202)
async def ingest_event_batch(
    body: SecurityEventBatch,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    project: Annotated[Project, Depends(get_project_from_api_key)],
):
    """Ingest up to 1000 events in a single request.

    Returns accepted/rejected counts per event type.
    Partial success is possible — invalid events are skipped.
    """
    results = []
    errors = []
    for i, ev_data in enumerate(body.events):
        try:
            ev = await _ingest_single(db, project, ev_data)
            results.append(_event_to_response(ev))
        except Exception as exc:
            errors.append({"index": i, "error": str(exc)})

    return {
        "accepted": len(results),
        "rejected": len(errors),
        "events": results,
        "errors": errors,
    }


@router.get("/events")
async def list_project_events(
    db: Annotated[AsyncSession, Depends(get_db)],
    project: Annotated[Project, Depends(get_project_from_api_key)],
    page: int = 1,
    page_size: int = 100,
    event_type: str | None = None,
):
    """List events for the authenticated project.

    Only returns events belonging to the project that owns the API key.
    """
    from sqlalchemy import func, desc
    q = select(SecurityEvent).where(SecurityEvent.project_id == project.id)
    if event_type:
        q = q.where(SecurityEvent.event_type == event_type)

    from sqlalchemy import func
    total = (await db.execute(
        select(func.count()).select_from(q.subquery())
    )).scalar_one()

    items = (await db.execute(
        q.order_by(SecurityEvent.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()

    return {
        "project_id": str(project.id),
        "items": [_event_to_response(e) for e in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ── Ingestion helpers ──────────────────────────────────────────────────────────

async def _ingest_single(
    db: AsyncSession,
    project: Project,
    data: SecurityEventCreate,
) -> SecurityEvent:
    """Core ingestion logic for a single event."""

    # Validate event_type
    if data.event_type not in ALLOWED_EVENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown event_type '{data.event_type}'. Allowed: {sorted(ALLOWED_EVENT_TYPES)}",
        )

    # Validate severity
    if data.severity not in ALLOWED_SEVERITIES:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown severity '{data.severity}'. Allowed: {sorted(ALLOWED_SEVERITIES)}",
        )

    # Create SecurityEvent
    event = SecurityEvent(
        project_id=project.id,
        event_type=data.event_type,
        severity=data.severity,
        source_ip=data.source_ip,
        source_host=data.source_host,
        source_application=data.source_application,
        source_agent_version=data.source_agent_version,
        message=data.message,
        payload=data.payload,
        event_timestamp=data.event_timestamp,
        processing_status="pending",
    )
    db.add(event)
    await db.flush()

    # ── ML classification ─────────────────────────────────────────────────
    ml_attack_category = None
    ml_confidence = None
    ml_version = None
    try:
        ml_result = await _classify_event(data)
        if ml_result:
            ml_attack_category = ml_result.get("attack_category")
            ml_confidence = ml_result.get("confidence")
            ml_version = ml_result.get("model_version")
            event.ml_attack_category = ml_attack_category
            event.ml_confidence = ml_confidence
            event.ml_model_version = ml_version
    except Exception:
        pass

    # ── Auto-create incident for high/critical events ─────────────────────
    incident_id = None
    if data.severity in ("critical", "high"):
        try:
            incident_id = await _auto_create_incident(db, project, event, data)
            event.incident_id = incident_id
        except Exception:
            pass

    event.processing_status = "processed"
    await db.flush()

    # Publish to SSE bus so live stream subscribers receive the event immediately
    try:
        _bus_publish(str(project.id), _event_to_response(event))
    except Exception:
        pass  # SSE publish never blocks ingestion

    return event


async def _classify_event(data: SecurityEventCreate) -> dict | None:
    """Run ML classification on the event payload."""
    try:
        from app.ml.classifier import get_classifier
        clf = get_classifier()

        features: dict = {}
        payload = data.payload or {}

        field_map = {
            "flow_duration": "flow_duration",
            "total_fwd_packets": "total_fwd_packets",
            "total_bwd_packets": "total_bwd_packets",
            "flow_packets_per_sec": "flow_packets_per_sec",
            "destination_port": "destination_port",
            "source_port": "source_port",
        }
        for k, v in field_map.items():
            if k in payload:
                features[v] = payload[k]

        if not features:
            attack = _SEVERITY_TO_ATTACK.get(data.event_type, "Unknown")
            return {
                "attack_category": attack,
                "confidence": 0.65,
                "model_version": "heuristic",
                "needs_review": True,
                "probabilities": {attack: 0.65},
                "top_features": [],
            }

        result = clf.classify(features)
        return result
    except Exception:
        return None


async def _auto_create_incident(
    db: AsyncSession,
    project: Project,
    event: SecurityEvent,
    data: SecurityEventCreate,
) -> uuid.UUID | None:
    """Auto-create an incident for high/critical events."""
    from app.models.incident import Incident

    title = (
        data.message
        or f"{data.event_type.replace('_', ' ').title()} from {data.source_ip or 'unknown'}"
    )
    incident = Incident(
        project_id=project.id,
        title=title[:500],
        description=f"Auto-created from security event {event.id}. Source: {data.source_application or 'API'}.",
        severity=data.severity,
        status="new",
        attack_category=event.ml_attack_category,
        confidence_score=event.ml_confidence,
        ml_model_version=event.ml_model_version,
        source_ip=data.source_ip,
        needs_analyst_review=True,
    )
    db.add(incident)
    await db.flush()
    return incident.id


def _event_to_response(e: SecurityEvent) -> dict:
    return {
        "id": str(e.id),
        "project_id": str(e.project_id),
        "event_type": e.event_type,
        "severity": e.severity,
        "processing_status": e.processing_status,
        "incident_id": str(e.incident_id) if e.incident_id else None,
        "ml_attack_category": e.ml_attack_category,
        "ml_confidence": e.ml_confidence,
        "created_at": e.created_at.isoformat(),
    }


# ── In-process event bus for SSE ─────────────────────────────────────────────
import asyncio
import json as _json

from fastapi.responses import StreamingResponse

_event_bus: dict[str, list] = {}


def _bus_publish(project_id: str, payload: dict) -> None:
    for q in list(_event_bus.get(project_id, [])):
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            pass


async def _bus_subscribe(project_id: str):
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    _event_bus.setdefault(project_id, []).append(q)
    try:
        while True:
            try:
                item = await asyncio.wait_for(q.get(), timeout=25.0)
                yield item
            except asyncio.TimeoutError:
                yield {"__keepalive": True}
    finally:
        bucket = _event_bus.get(project_id, [])
        if q in bucket:
            bucket.remove(q)
        if not bucket:
            _event_bus.pop(project_id, None)


@router.get("/events/stream")
async def stream_events(
    project: Annotated[Project, Depends(get_project_from_api_key)],
):
    """Server-Sent Events stream for real-time SecurityEvent delivery.

    Authenticate with Bearer <proj_key> (same as POST /events).
    Keepalive sent every ~25 s.
    """
    project_id = str(project.id)

    async def generate():
        yield "data: " + _json.dumps({"type": "connected", "project_id": project_id}) + "\n\n"
        async for payload in _bus_subscribe(project_id):
            if payload.get("__keepalive"):
                yield ": keepalive\n\n"
            else:
                yield "data: " + _json.dumps(payload) + "\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
