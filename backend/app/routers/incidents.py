"""Incidents router."""
from __future__ import annotations

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Permission
from app.database import get_db
from app.dependencies import require_permission
from app.models.user import User
from app.schemas.incident import (
    IncidentCreate,
    IncidentListResponse,
    IncidentResponse,
    IncidentUpdate,
    StatusChangeRequest,
    ReopenRequest,
)
from app.services.incident_service import IncidentService
from app.services.compliance_service import ComplianceService
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.post("", response_model=IncidentResponse, status_code=201)
async def create_incident(
    data: IncidentCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.CREATE_INCIDENT))],
):
    svc = IncidentService(db)
    incident = await svc.create(data, current_user)

    # Auto-generate compliance obligations if applicable
    if incident.affected_jurisdictions or incident.personal_data_involved or incident.health_data_involved:
        comp_svc = ComplianceService(db)
        await comp_svc.generate_obligations(incident)
        notif_svc = NotificationService(db)
        await notif_svc.generate_for_incident(incident)

    # Reload with relationships eagerly loaded — async SQLAlchemy cannot lazy-load
    # during Pydantic serialization (raises MissingGreenlet), so we must use selectinload.
    incident = await svc.get(incident.id)
    return incident


@router.get("", response_model=IncidentListResponse)
async def list_incidents(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.READ_INCIDENT))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    severity: Optional[str] = None,
    needs_review: Optional[bool] = None,
    search: Optional[str] = Query(None, max_length=200),
):
    svc = IncidentService(db)
    items, total = await svc.list(
        page=page,
        page_size=page_size,
        status=status,
        severity=severity,
        needs_review=needs_review,
        search=search,
    )
    return IncidentListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/stats")
async def incident_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.READ_INCIDENT))],
):
    svc = IncidentService(db)
    return await svc.get_stats()


@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(
    incident_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.READ_INCIDENT))],
):
    svc = IncidentService(db)
    return await svc.get(incident_id)


@router.patch("/{incident_id}", response_model=IncidentResponse)
async def update_incident(
    incident_id: uuid.UUID,
    data: IncidentUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.UPDATE_INCIDENT))],
):
    svc = IncidentService(db)
    return await svc.update(incident_id, data, current_user)


@router.post("/{incident_id}/status")
async def change_status(
    incident_id: uuid.UUID,
    body: StatusChangeRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.UPDATE_INCIDENT))],
):
    svc = IncidentService(db)
    incident = await svc.transition_status(incident_id, body.status, current_user, body.notes or "")
    return {"id": incident.id, "status": incident.status}


@router.post("/{incident_id}/reopen")
async def reopen_incident(
    incident_id: uuid.UUID,
    body: ReopenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.UPDATE_INCIDENT))],
):
    from app.models.incident import IncidentStatus
    svc = IncidentService(db)
    incident = await svc.transition_status(
        incident_id,
        IncidentStatus.REOPENED.value,
        current_user,
        body.reason or "",
    )
    return {"id": incident.id, "status": incident.status}


@router.delete("/{incident_id}", status_code=204)
async def delete_incident(
    incident_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.DELETE_INCIDENT))],
):
    svc = IncidentService(db)
    await svc.delete(incident_id)


@router.get("/{incident_id}/explain")
async def explain_incident(
    incident_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.READ_INCIDENT))],
):
    """Return a plain-English explanation for this incident's attack type."""
    from sqlalchemy import select
    from app.models.incident import Incident
    from app.services.incident_explainer import explain_incident as _explain

    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if incident is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Incident not found")

    explanation = _explain(
        attack_category=incident.attack_category or "Unknown",
        incident_title=incident.title,
        incident_severity=incident.severity,
        source_ip=getattr(incident, "source_ip", None),
        destination_port=getattr(incident, "destination_port", None),
        flow_duration_ms=getattr(incident, "flow_duration_ms", None),
    )
    return {
        "incident_id": str(incident.id),
        "incident_title": incident.title,
        "incident_severity": incident.severity,
        "attack_category": incident.attack_category,
        **explanation,
    }
