"""
LBRO — Incidents API router

Endpoints:
  POST  /api/v1/incidents            — ingest a breach alert
  GET   /api/v1/incidents            — list with filters + pagination
  GET   /api/v1/incidents/{id}       — detail with full timeline
  PATCH /api/v1/incidents/{id}       — update status / metadata

Rate limits (per client IP, sourced from X-Forwarded-For set by ALB):
  POST  — 60/minute, 500/hour   prevents SQS flooding from runaway detectors
  GET   — 120/minute            supports dashboard polling at 2 req/s
  PATCH — 30/minute             status updates are infrequent operator actions
"""
import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.rate_limit import limiter
from app.core.security import RequireAPIKey
from app.models.incident import Incident, IncidentSeverity, IncidentStatus
from app.schemas.incident import (
    IncidentCreate,
    IncidentDetail,
    IncidentOut,
    IncidentUpdate,
    PagedIncidentResponse,
)
from app.services.incident_service import IncidentService

log = structlog.get_logger(__name__)
router = APIRouter(dependencies=[RequireAPIKey])


@router.post(
    "/incidents",
    response_model=IncidentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a breach alert",
)
@limiter.limit("60/minute;500/hour")
async def create_incident(
    request: Request,  # required by slowapi
    payload: IncidentCreate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Accepts a breach alert from any detector (SIEM, GuardDuty, custom).
    Persists, detects jurisdictions, creates notification deadlines,
    and enqueues for containment — all atomically.
    """
    svc = IncidentService(db)
    incident = await svc.create_and_dispatch(payload)
    log.info(
        "incident.created",
        incident_id=str(incident.id),
        severity=incident.severity,
        source=incident.source_system,
    )
    return incident


@router.get(
    "/incidents",
    response_model=PagedIncidentResponse,
    summary="List incidents",
)
@limiter.limit("120/minute")
async def list_incidents(
    request: Request,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    status: Optional[IncidentStatus] = Query(None),  # noqa: B008
    severity: Optional[IncidentSeverity] = Query(None),  # noqa: B008
    page: int = Query(1, ge=1),  # noqa: B008
    page_size: int = Query(20, ge=1, le=100),  # noqa: B008
):
    offset = (page - 1) * page_size
    query = select(Incident)

    if status:
        query = query.where(Incident.status == status)
    if severity:
        query = query.where(Incident.severity == severity)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = (
        await db.execute(
            query.order_by(Incident.detected_at.desc()).offset(offset).limit(page_size)
        )
    ).scalars().all()
    items = [IncidentOut.model_validate(r) for r in rows]

    return PagedIncidentResponse(total=total, page=page, page_size=page_size, items=items)


@router.get(
    "/incidents/{incident_id}",
    response_model=IncidentDetail,
    summary="Get incident detail with full timeline",
)
@limiter.limit("120/minute")
async def get_incident(
    request: Request,
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    result = await db.execute(
        select(Incident)
        .where(Incident.id == incident_id)
        .options(
            selectinload(Incident.timeline),
            selectinload(Incident.evidence_packages),
            selectinload(Incident.notifications),
        )
    )
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    data = IncidentDetail.model_validate(incident)
    data.evidence_count = len(incident.evidence_packages)
    data.notification_count = len(incident.notifications)
    return data


@router.patch(
    "/incidents/{incident_id}",
    response_model=IncidentOut,
    summary="Update incident status or metadata",
)
@limiter.limit("30/minute")
async def update_incident(
    request: Request,
    incident_id: uuid.UUID,
    payload: IncidentUpdate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    svc = IncidentService(db)
    incident = await svc.update_status(incident, payload)
    log.info(
        "incident.updated",
        incident_id=str(incident_id),
        updates=payload.model_dump(exclude_none=True),
    )
    return incident
