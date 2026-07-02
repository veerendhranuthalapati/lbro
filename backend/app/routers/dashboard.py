"""Dashboard aggregation router."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Permission
from app.database import get_db
from app.dependencies import require_permission
from app.models.incident import Incident, IncidentStatus, IncidentSeverity
from app.models.notification import Notification
from app.models.compliance import ComplianceRecord
from app.models.evidence import Evidence
from app.models.user import User
from datetime import datetime, timedelta, timezone

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
async def dashboard_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_DASHBOARD))],
):
    now = datetime.now(timezone.utc)
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)

    total_incidents = (await db.execute(select(func.count(Incident.id)))).scalar_one()
    new_24h = (
        await db.execute(
            select(func.count(Incident.id)).where(Incident.created_at >= last_24h)
        )
    ).scalar_one()
    open_incidents = (
        await db.execute(
            select(func.count(Incident.id)).where(
                Incident.status.notin_(["closed"])
            )
        )
    ).scalar_one()
    critical = (
        await db.execute(
            select(func.count(Incident.id)).where(Incident.severity == "critical")
        )
    ).scalar_one()
    pending_notifications = (
        await db.execute(
            select(func.count(Notification.id)).where(Notification.status == "pending")
        )
    ).scalar_one()
    overdue_compliance = (
        await db.execute(
            select(func.count(ComplianceRecord.id)).where(
                ComplianceRecord.is_met == False,
                ComplianceRecord.deadline < now,
            )
        )
    ).scalar_one()
    total_evidence = (await db.execute(select(func.count(Evidence.id)))).scalar_one()
    needs_review = (
        await db.execute(
            select(func.count(Incident.id)).where(Incident.needs_analyst_review == True)
        )
    ).scalar_one()

    # Recent incidents
    recent_result = await db.execute(
        select(Incident).order_by(Incident.created_at.desc()).limit(5)
    )
    recent_incidents = recent_result.scalars().all()

    # Severity breakdown
    severity_breakdown = {}
    for s in IncidentSeverity:
        count = (
            await db.execute(
                select(func.count(Incident.id)).where(Incident.severity == s.value)
            )
        ).scalar_one()
        severity_breakdown[s.value] = count

    # Status breakdown
    status_breakdown = {}
    for s in IncidentStatus:
        count = (
            await db.execute(
                select(func.count(Incident.id)).where(Incident.status == s.value)
            )
        ).scalar_one()
        status_breakdown[s.value] = count

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
