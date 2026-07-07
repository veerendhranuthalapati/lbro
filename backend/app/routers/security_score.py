"""Security Score endpoint.

Calculates a 0–100 security posture score from real backend data.
Designed for developer-first audiences who need plain-English explanations.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Permission
from app.database import get_db
from app.dependencies import require_permission
from app.models.audit import AuditLog
from app.models.compliance import ComplianceRecord
from app.models.incident import Incident, IncidentSeverity, IncidentStatus
from app.models.user import User

router = APIRouter(prefix="/security-score", tags=["security-score"])

# ── Grade thresholds ──────────────────────────────────────────────────────────
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


@router.get("")
async def get_security_score(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_DASHBOARD))],
):
    """
    Calculate and return the current security posture score.

    Score is derived entirely from live database state — no hardcoded values.
    """
    now = datetime.now(timezone.utc)
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)

    # ── Incident data ─────────────────────────────────────────────────────────
    open_statuses = [s.value for s in IncidentStatus if s != IncidentStatus.CLOSED]

    open_critical = (await db.execute(
        select(func.count(Incident.id)).where(
            Incident.severity == IncidentSeverity.CRITICAL.value,
            Incident.status.in_(open_statuses),
        )
    )).scalar_one()

    open_high = (await db.execute(
        select(func.count(Incident.id)).where(
            Incident.severity == IncidentSeverity.HIGH.value,
            Incident.status.in_(open_statuses),
        )
    )).scalar_one()

    open_medium_low = (await db.execute(
        select(func.count(Incident.id)).where(
            Incident.severity.in_([IncidentSeverity.MEDIUM.value, IncidentSeverity.LOW.value]),
            Incident.status.in_(open_statuses),
        )
    )).scalar_one()

    # ── User data ─────────────────────────────────────────────────────────────
    total_users = (await db.execute(select(func.count(User.id)))).scalar_one()

    users_without_mfa = (await db.execute(
        select(func.count(User.id)).where(
            User.mfa_enabled == False,
            User.is_active == True,
        )
    )).scalar_one()

    users_with_failed_logins = (await db.execute(
        select(func.count(User.id)).where(User.failed_login_attempts > 3)
    )).scalar_one()

    locked_users = (await db.execute(
        select(func.count(User.id)).where(User.locked_until > now)
    )).scalar_one()

    # ── Compliance data ───────────────────────────────────────────────────────
    overdue_compliance = (await db.execute(
        select(func.count(ComplianceRecord.id)).where(
            ComplianceRecord.is_met == False,
            ComplianceRecord.deadline < now,
        )
    )).scalar_one()

    unmet_compliance = (await db.execute(
        select(func.count(ComplianceRecord.id)).where(
            ComplianceRecord.is_met == False,
        )
    )).scalar_one()

    # ── Audit log: attack signal (403s from non-user sources) ────────────────
    recent_403s = (await db.execute(
        select(func.count(AuditLog.id)).where(
            AuditLog.response_status == 403,
            AuditLog.created_at >= last_24h,
        )
    )).scalar_one()

    # ── Score calculation ─────────────────────────────────────────────────────
    score = 100
    positive_factors = []
    negative_factors = []
    recommendations = []

    # Critical incidents: -15 each, capped at -45
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

    # High severity incidents: -8 each, capped at -24
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

    # Medium/low incidents: -2 each, capped at -10
    if open_medium_low > 0:
        deduction = min(open_medium_low * 2, 10)
        score -= deduction
        negative_factors.append({
            "label": f"{open_medium_low} open medium/low incident{'s' if open_medium_low != 1 else ''}",
            "detail": "Lower severity incidents accumulate risk when left unresolved.",
            "impact": -deduction,
        })

    # MFA: -4 per user without it, capped at -20
    if users_without_mfa > 0 and total_users > 0:
        deduction = min(users_without_mfa * 4, 20)
        score -= deduction
        pct = round(users_without_mfa / total_users * 100)
        negative_factors.append({
            "label": f"{users_without_mfa} user{'s' if users_without_mfa != 1 else ''} ({pct}%) without MFA",
            "detail": "Accounts without MFA are the most common entry point for attackers.",
            "impact": -deduction,
        })
        recommendations.append({
            "priority": "high",
            "title": "Enable MFA for all team members",
            "detail": (
                f"{users_without_mfa} of your {total_users} accounts have no second factor. "
                "Enabling MFA blocks over 99% of automated credential attacks."
            ),
            "action": "Manage users",
            "link": "/users",
        })
    else:
        score += 5  # Bonus: all users have MFA
        positive_factors.append({
            "label": "All accounts have MFA enabled",
            "detail": "Strong authentication protects against credential attacks.",
            "impact": 5,
        })

    # Failed login attempts: -5 per affected user, capped at -15
    if users_with_failed_logins > 0:
        deduction = min(users_with_failed_logins * 5, 15)
        score -= deduction
        negative_factors.append({
            "label": f"{users_with_failed_logins} account{'s' if users_with_failed_logins != 1 else ''} with repeated login failures",
            "detail": "This may indicate a brute-force or credential-stuffing attack in progress.",
            "impact": -deduction,
        })
        recommendations.append({
            "priority": "medium",
            "title": "Investigate repeated login failures",
            "detail": (
                "Repeated failures on an account are often early signs of a brute-force attack. "
                "Review audit logs and consider temporarily locking those accounts."
            ),
            "action": "View audit logs",
            "link": "/audit-logs",
        })
    else:
        positive_factors.append({
            "label": "No accounts with repeated login failures",
            "detail": "No signs of active credential attacks.",
            "impact": 0,
        })

    # Locked accounts: -3 each, capped at -9
    if locked_users > 0:
        deduction = min(locked_users * 3, 9)
        score -= deduction
        negative_factors.append({
            "label": f"{locked_users} account{'s' if locked_users != 1 else ''} currently locked",
            "detail": "Accounts lock automatically after repeated failed login attempts.",
            "impact": -deduction,
        })

    # Overdue compliance: -5 each, capped at -15
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

    # 403 burst (potential attack traffic): -10 if >50 in last 24h
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

    # Bonus: all compliance met
    if unmet_compliance == 0 and overdue_compliance == 0:
        score += 5
        positive_factors.append({
            "label": "All compliance requirements met",
            "detail": "You're meeting your regulatory and policy obligations.",
            "impact": 5,
        })

    # Clamp to [0, 100]
    score = max(0, min(100, score))
    grade, color, status = _grade(score)

    # ── Plain-English summary ─────────────────────────────────────────────────
    if score >= 90:
        summary = "Your application has a strong security posture. Keep it up."
    elif score >= 75:
        summary = "Good overall security, but a few items need attention."
    elif score >= 60:
        summary = (
            f"Your security posture needs improvement. "
            f"{'Resolve open critical incidents. ' if open_critical else ''}"
            f"{'Enable MFA for your team. ' if users_without_mfa else ''}"
            f"{'Address overdue compliance items.' if overdue_compliance else ''}"
        ).strip() or "Review the recommendations below to improve your score."
    elif score >= 40:
        summary = (
            "Your application is at risk. Active threats or weak authentication "
            "controls are leaving you exposed. Address the critical recommendations below."
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
        # Flat array with impact:'positive'|'negative' — matches frontend ScoreFactor interface
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
            "total_users": total_users,
            "users_without_mfa": users_without_mfa,
            "users_with_failed_logins": users_with_failed_logins,
            "locked_users": locked_users,
            "overdue_compliance": overdue_compliance,
            "recent_403s_24h": recent_403s,
        },
        "calculated_at": now.isoformat(),
    }
