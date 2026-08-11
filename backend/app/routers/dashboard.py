"""Dashboard aggregation router."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import false, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.project_access import resolve_project_scope
from app.core.rbac import Permission
from app.database import get_db
from app.dependencies import require_permission
from app.models.incident import Incident, IncidentStatus, IncidentSeverity
from app.models.notification import Notification
from app.models.compliance import ComplianceRecord
from app.models.evidence import Evidence
from app.models.user import User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _apply_project_scope(q, scope_ids: Optional[list[uuid.UUID]]):
    """Filter incident-scoped queries by resolved project IDs."""
    if scope_ids is None:
        return q
    if not scope_ids:
        return q.where(false())
    return q.where(Incident.project_id.in_(scope_ids))


@router.get("/summary")
async def dashboard_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_DASHBOARD))],
    project_id: Optional[uuid.UUID] = Query(None, description="Scope summary to a project"),
):
    scope_ids = await resolve_project_scope(db, current_user, project_id)
    now = datetime.now(timezone.utc)
    last_24h = now - timedelta(hours=24)

    def _pf(q):
        return _apply_project_scope(q, scope_ids)

    total_incidents = (await db.execute(_pf(select(func.count(Incident.id))))).scalar_one()

    new_24h = (await db.execute(
        _pf(select(func.count(Incident.id))).where(Incident.created_at >= last_24h)
    )).scalar_one()

    open_incidents = (await db.execute(
        _pf(select(func.count(Incident.id))).where(Incident.status.notin_(["closed"]))
    )).scalar_one()

    critical = (await db.execute(
        _pf(select(func.count(Incident.id))).where(Incident.severity == "critical")
    )).scalar_one()

    pending_notifications = (await db.execute(
        _apply_project_scope(
            select(func.count(Notification.id))
            .join(Incident, Notification.incident_id == Incident.id)
            .where(Notification.status == "pending"),
            scope_ids,
        )
    )).scalar_one()

    overdue_compliance = (await db.execute(
        _apply_project_scope(
            select(func.count(ComplianceRecord.id))
            .join(Incident, ComplianceRecord.incident_id == Incident.id)
            .where(
                ComplianceRecord.is_met == False,
                ComplianceRecord.deadline < now,
            ),
            scope_ids,
        )
    )).scalar_one()

    total_evidence = (await db.execute(
        _apply_project_scope(
            select(func.count(Evidence.id))
            .join(Incident, Evidence.incident_id == Incident.id),
            scope_ids,
        )
    )).scalar_one()

    needs_review = (await db.execute(
        _pf(select(func.count(Incident.id))).where(Incident.needs_analyst_review == True)
    )).scalar_one()

    recent_q = _pf(select(Incident)).order_by(Incident.created_at.desc()).limit(5)
    recent_result = await db.execute(recent_q)
    recent_incidents = recent_result.scalars().all()

    sev_q = _pf(select(Incident.severity, func.count(Incident.id)).group_by(Incident.severity))
    severity_rows = (await db.execute(sev_q)).all()
    severity_breakdown = {s.value: 0 for s in IncidentSeverity}
    for sev, cnt in severity_rows:
        severity_breakdown[sev] = cnt

    st_q = _pf(select(Incident.status, func.count(Incident.id)).group_by(Incident.status))
    status_rows = (await db.execute(st_q)).all()
    status_breakdown = {s.value: 0 for s in IncidentStatus}
    for st, cnt in status_rows:
        status_breakdown[st] = cnt

    return {
        "total_incidents": total_incidents,
        "new_last_24h": new_24h,
        "open_incidents": open_incidents,
        "critical_incidents": critical,
        "pending_notifications": pending_notifications,
        "overdue_compliance": overdue_compliance,
        "total_evidence": total_evidence,
        "needs_analyst_review": needs_review,
        "severity_breakdown": severity_breakdown,
        "status_breakdown": status_breakdown,
        "recent_incidents": [
            {
                "id": str(i.id),
                "title": i.title,
                "severity": i.severity,
                "status": i.status,
                "created_at": i.created_at.isoformat(),
            }
            for i in recent_incidents
        ],
    }
