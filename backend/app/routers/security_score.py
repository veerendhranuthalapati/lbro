"""Security Score endpoint.

Calculates a 0–100 security posture score from real backend data.
Designed for developer-first audiences who need plain-English explanations.
"""
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
from app.models.audit import AuditLog
from app.models.compliance import ComplianceRecord
from app.models.incident import Incident, IncidentSeverity, IncidentStatus
from app.models.user import User

router = APIRouter(prefix="/security-score", tags=["security-score"])


def _grade(score: int) -> tuple[str, str, str]:
    """Return (grade, color_hex, status_label)."""
    if score >= 90:
        return "A", "#22c55e", "Excellent"
    if score >= 75:
        return "B", "#84cc16", "Good"
    if score >= 60:
        return "C", "#f59e0b", "Needs Attention"
    if score >= 40:
        return "D", "#f97316", "At Risk"
    return "F", "#ef4444", "Critical"


def _apply_project_scope(q, scope_ids: Optional[list[uuid.UUID]]):
    if scope_ids is None:
        return q
    if not scope_ids:
        return q.where(false())
    return q.where(Incident.project_id.in_(scope_ids))


def _apply_compliance_scope(q, scope_ids: Optional[list[uuid.UUID]]):
    if scope_ids is None:
        return q
    if not scope_ids:
        return q.where(false())
    return q.join(Incident, ComplianceRecord.incident_id == Incident.id).where(
        Incident.project_id.in_(scope_ids)
    )


@router.get("")
async def get_security_score(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_DASHBOARD))],
    project_id: Optional[uuid.UUID] = Query(None, description="Scope score to a project"),
):
    """
    Calculate and return the current security posture score.

    Score is derived entirely from live database state — no hardcoded values.
    When project_id is supplied, only incidents belonging to that project are used.
    """
    scope_ids = await resolve_project_scope(db, current_user, project_id)
    now = datetime.now(timezone.utc)
    last_24h = now - timedelta(hours=24)

    def _pf(q):
        return _apply_project_scope(q, scope_ids)

    open_statuses = [s.value for s in IncidentStatus if s != IncidentStatus.CLOSED]

    open_critical = (await db.execute(
        _pf(select(func.count(Incident.id))).where(
            Incident.severity == IncidentSeverity.CRITICAL.value,
            Incident.status.in_(open_statuses),
        )
    )).scalar_one()

    open_high = (await db.execute(
        _pf(select(func.count(Incident.id))).where(
            Incident.severity == IncidentSeverity.HIGH.value,
            Incident.status.in_(open_statuses),
        )
    )).scalar_one()

    open_medium_low = (await db.execute(
        _pf(select(func.count(Incident.id))).where(
            Incident.severity.in_([IncidentSeverity.MEDIUM.value, IncidentSeverity.LOW.value]),
            Incident.status.in_(open_statuses),
        )
    )).scalar_one()

    overdue_compliance = (await db.execute(
        _apply_compliance_scope(
            select(func.count(ComplianceRecord.id)).where(
                ComplianceRecord.is_met == False,
                ComplianceRecord.deadline < now,
            ),
            scope_ids,
        )
    )).scalar_one()

    unmet_compliance = (await db.execute(
        _apply_compliance_scope(
            select(func.count(ComplianceRecord.id)).where(
                ComplianceRecord.is_met == False,
            ),
            scope_ids,
        )
    )).scalar_one()

    recent_403s = (await db.execute(
        select(func.count(AuditLog.id)).where(
            AuditLog.response_status == 403,
            AuditLog.created_at >= last_24h,
        )
    )).scalar_one()

    score = 100
    positive_factors = []
    negative_factors = []
    recommendations = []

    if open_critical > 0:
        deduction = min(open_critical * 15, 45)
        score -= deduction
        negative_factors.append({
            "label": f"{open_critical} open critical incident{'s' if open_critical != 1 else ''}",
            "detail": "Critical incidents indicate active or serious security events that need immediate action.",
            "impact": -deduction,
        })
        recommendations.append({
            "priority": "critical",
            "title": f"Resolve {open_critical} critical incident{'s' if open_critical != 1 else ''} immediately",
            "detail": (
                "Critical incidents often mean active attacks, data breaches, or service outages. "
                "Every hour they remain open increases your exposure."
            ),
            "action": "View critical incidents",
            "link": "/incidents?severity=critical",
        })
    else:
        positive_factors.append({
            "label": "No open critical incidents",
            "detail": "Your most severe threats are under control.",
            "impact": 0,
        })

    if open_high > 0:
        deduction = min(open_high * 8, 24)
        score -= deduction
        negative_factors.append({
            "label": f"{open_high} open high-severity incident{'s' if open_high != 1 else ''}",
            "detail": "High-severity incidents should be triaged within hours, not days.",
            "impact": -deduction,
        })
        if open_critical == 0:
            recommendations.append({
                "priority": "high",
                "title": f"Triage {open_high} high-severity incident{'s' if open_high != 1 else ''}",
                "detail": "High incidents can escalate to critical if not addressed. Assign an analyst and begin containment.",
                "action": "View high incidents",
                "link": "/incidents?severity=high",
            })
    else:
        positive_factors.append({
            "label": "No open high-severity incidents",
            "detail": "High-priority threats are resolved.",
            "impact": 0,
        })

    if open_medium_low > 0:
        deduction = min(open_medium_low * 2, 10)
        score -= deduction
        negative_factors.append({
            "label": f"{open_medium_low} open medium/low incident{'s' if open_medium_low != 1 else ''}",
            "detail": "Lower severity incidents accumulate risk when left unresolved.",
            "impact": -deduction,
        })

    if overdue_compliance > 0:
        deduction = min(overdue_compliance * 5, 15)
        score -= deduction
        negative_factors.append({
            "label": f"{overdue_compliance} overdue compliance requirement{'s' if overdue_compliance != 1 else ''}",
            "detail": "Overdue compliance items increase your legal and regulatory risk.",
            "impact": -deduction,
        })
        recommendations.append({
            "priority": "medium",
            "title": "Address overdue compliance requirements",
            "detail": (
                f"{overdue_compliance} compliance item{'s' if overdue_compliance != 1 else ''} "
                "passed their deadline. These create regulatory risk and should be resolved or rescheduled."
            ),
            "action": "View compliance",
            "link": "/compliance",
        })
    else:
        positive_factors.append({
            "label": "No overdue compliance requirements",
            "detail": "Your compliance posture is current.",
            "impact": 0,
        })

    if recent_403s > 50:
        score -= 10
        negative_factors.append({
            "label": f"{recent_403s} authorization failures in the last 24 hours",
            "detail": "A high volume of 403 errors may indicate automated probing or an insider threat.",
            "impact": -10,
        })
        recommendations.append({
            "priority": "medium",
            "title": "Investigate unusual authorization activity",
            "detail": (
                f"Your app logged {recent_403s} forbidden-access attempts in the last 24 hours. "
                "This volume is above normal and warrants a review of recent audit logs."
            ),
            "action": "View audit logs",
            "link": "/audit-logs",
        })

    if unmet_compliance == 0 and overdue_compliance == 0:
        score += 5
        positive_factors.append({
            "label": "All compliance requirements met",
            "detail": "You're meeting your regulatory and policy obligations.",
            "impact": 5,
        })

    score = max(0, min(100, score))
    grade, color, status = _grade(score)

    if score >= 90:
        summary = "Your application has a strong security posture. Keep it up."
    elif score >= 75:
        summary = "Good overall security, but a few items need attention."
    elif score >= 60:
        summary = (
            f"Your security posture needs improvement. "
            f"{'Resolve open critical incidents. ' if open_critical else ''}"
            f"{'Address overdue compliance items.' if overdue_compliance else ''}"
        ).strip() or "Review the recommendations below to improve your score."
    elif score >= 40:
        summary = (
            "Your application is at risk. Active threats or weak controls "
            "are leaving you exposed. Address the critical recommendations below."
        )
    else:
        summary = (
            "Critical security posture. You have multiple unresolved high-severity issues "
            "that require immediate attention."
        )

    return {
        "score": score,
        "grade": grade,
        "color": color,
        "status": status,
        "summary": summary,
        "factors": [
            {**f, "impact": "positive"} for f in positive_factors
        ] + [
            {**f, "impact": "negative"} for f in negative_factors
        ],
        "recommendations": sorted(
            recommendations,
            key=lambda r: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(r["priority"], 4),
        ),
        "data_snapshot": {
            "open_critical_incidents": open_critical,
            "open_high_incidents": open_high,
            "open_medium_low_incidents": open_medium_low,
            "overdue_compliance": overdue_compliance,
            "recent_403s_24h": recent_403s,
        },
        "calculated_at": now.isoformat(),
    }
