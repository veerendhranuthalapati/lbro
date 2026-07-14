"""Platform router — SUPER_ADMIN only.

All endpoints in this router require the super_admin role.
Project admins, analysts, and viewers receive 403 on every route here.

Endpoints:
  GET  /platform/dashboard    — global metrics across ALL projects
  GET  /platform/projects     — list all projects (active + archived)
  POST /platform/projects     — create a project on behalf of any user
  PATCH  /platform/projects/{id}/archive   — archive a project
  DELETE /platform/projects/{id}           — hard-delete a project
  GET  /platform/users        — list all platform users
  POST /platform/users        — create a new user
  PATCH  /platform/users/{id}/disable  — disable a user account
  DELETE /platform/users/{id}          — delete a user
  PATCH  /platform/users/{id}/role     — change a user role
  POST /platform/users/{id}/reset-password — force password reset
  POST /platform/projects/{id}/assign-admin — assign a project admin
  GET  /platform/audit        — all audit logs across all projects
  GET  /platform/incidents    — all incidents across all projects
  GET  /platform/health       — Docker / API / ML health status
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Role
from app.core.security import hash_password as get_password_hash
from app.database import get_db
from app.dependencies import require_super_admin
from app.models.audit import AuditLog
from app.models.evidence import Evidence
from app.models.incident import Incident, IncidentSeverity, IncidentStatus
from app.models.project import Project
from app.models.security_event import SecurityEvent
from app.models.user import User

router = APIRouter(prefix="/platform", tags=["platform"])

# Shorthand: all platform routes require super_admin
_SA = Depends(require_super_admin())


# ─────────────────────────────────────────────────────────────────────────────
# Schemas (inline — platform-specific, not shared)
# ─────────────────────────────────────────────────────────────────────────────

class PlatformUserCreate(BaseModel):
    email: EmailStr
    username: str
    full_name: str
    password: str
    role: str = "viewer"


class PlatformUserRoleUpdate(BaseModel):
    role: str


class PlatformProjectAssignAdmin(BaseModel):
    user_id: uuid.UUID


class PlatformPasswordReset(BaseModel):
    new_password: str


# ─────────────────────────────────────────────────────────────────────────────
# Global Dashboard
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/dashboard")
async def platform_dashboard(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, _SA],
):
    """Global metrics across ALL projects — Super Admin only."""
    now = datetime.now(timezone.utc)
    last_24h = now - timedelta(hours=24)

    # ── Counts ────────────────────────────────────────────────────────────
    total_projects = (await db.execute(
        select(func.count(Project.id))
    )).scalar_one()

    active_projects = (await db.execute(
        select(func.count(Project.id)).where(Project.status == "active")
    )).scalar_one()

    total_users = (await db.execute(
        select(func.count(User.id))
    )).scalar_one()

    active_users = (await db.execute(
        select(func.count(User.id)).where(User.is_active == True)  # noqa: E712
    )).scalar_one()

    total_incidents = (await db.execute(
        select(func.count(Incident.id))
    )).scalar_one()

    critical_incidents = (await db.execute(
        select(func.count(Incident.id)).where(
            Incident.severity == IncidentSeverity.CRITICAL.value,
            Incident.status.notin_(["closed"]),
        )
    )).scalar_one()

    open_incidents = (await db.execute(
        select(func.count(Incident.id)).where(Incident.status.notin_(["closed"]))
    )).scalar_one()

    total_evidence = (await db.execute(
        select(func.count(Evidence.id))
    )).scalar_one()

    # ── Events ingestion stats ────────────────────────────────────────────
    total_events = (await db.execute(
        select(func.count(SecurityEvent.id))
    )).scalar_one()

    events_24h = (await db.execute(
        select(func.count(SecurityEvent.id)).where(SecurityEvent.created_at >= last_24h)
    )).scalar_one()

    # ── Attack category breakdown ─────────────────────────────────────────
    attack_rows = (await db.execute(
        select(Incident.attack_category, func.count(Incident.id))
        .where(Incident.attack_category.isnot(None))
        .group_by(Incident.attack_category)
        .order_by(desc(func.count(Incident.id)))
        .limit(10)
    )).all()
    top_attack_types = [{"category": cat, "count": cnt} for cat, cnt in attack_rows]
    most_common_attack = top_attack_types[0]["category"] if top_attack_types else None

    # ── Top source IPs across all projects ───────────────────────────────
    top_ip_rows = (await db.execute(
        select(SecurityEvent.source_ip, func.count(SecurityEvent.id))
        .where(SecurityEvent.source_ip.isnot(None))
        .group_by(SecurityEvent.source_ip)
        .order_by(desc(func.count(SecurityEvent.id)))
        .limit(10)
    )).all()
    top_source_ips = [{"ip": ip, "count": cnt} for ip, cnt in top_ip_rows]

    # ── Most active projects (by incident count) ──────────────────────────
    project_incident_rows = (await db.execute(
        select(Incident.project_id, func.count(Incident.id).label("cnt"))
        .where(Incident.project_id.isnot(None))
        .group_by(Incident.project_id)
        .order_by(desc(func.count(Incident.id)))
        .limit(5)
    )).all()

    most_targeted_project_id = project_incident_rows[0][0] if project_incident_rows else None
    most_targeted_project = None
    if most_targeted_project_id:
        proj = (await db.execute(
            select(Project).where(Project.id == most_targeted_project_id)
        )).scalar_one_or_none()
        if proj:
            most_targeted_project = proj.name

    most_active_projects = []
    for pid, cnt in project_incident_rows:
        proj = (await db.execute(select(Project).where(Project.id == pid))).scalar_one_or_none()
        if proj:
            most_active_projects.append({"project_id": str(pid), "name": proj.name, "incident_count": cnt})

    # ── Latest incidents across ALL projects ──────────────────────────────
    latest_incidents_rows = (await db.execute(
        select(Incident, Project.name.label("project_name"))
        .outerjoin(Project, Incident.project_id == Project.id)
        .order_by(desc(Incident.created_at))
        .limit(20)
    )).all()

    latest_incidents = [
        {
            "id": str(i.id),
            "title": i.title,
            "severity": i.severity,
            "status": i.status,
            "attack_category": i.attack_category,
            "project_id": str(i.project_id) if i.project_id else None,
            "project_name": pname,
            "created_at": i.created_at.isoformat(),
        }
        for i, pname in latest_incidents_rows
    ]

    # ── Severity breakdown (global) ───────────────────────────────────────
    sev_rows = (await db.execute(
        select(Incident.severity, func.count(Incident.id)).group_by(Incident.severity)
    )).all()
    severity_breakdown = {s.value: 0 for s in IncidentSeverity}
    for sev, cnt in sev_rows:
        if sev in severity_breakdown:
            severity_breakdown[sev] = cnt

    # ── ML prediction stats ───────────────────────────────────────────────
    ml_stats_rows = (await db.execute(
        select(SecurityEvent.ml_attack_category, func.count(SecurityEvent.id))
        .where(SecurityEvent.ml_attack_category.isnot(None))
        .group_by(SecurityEvent.ml_attack_category)
        .order_by(desc(func.count(SecurityEvent.id)))
    )).all()
    ml_prediction_stats = [{"category": cat, "count": cnt} for cat, cnt in ml_stats_rows]

    # ── Most active users (by audit log entries, last 7 days) ────────────
    last_7d = now - timedelta(days=7)
    active_user_rows = (await db.execute(
        select(AuditLog.user_email, func.count(AuditLog.id))
        .where(AuditLog.created_at >= last_7d, AuditLog.user_email.isnot(None))
        .group_by(AuditLog.user_email)
        .order_by(desc(func.count(AuditLog.id)))
        .limit(10)
    )).all()
    most_active_users = [{"email": email, "action_count": cnt} for email, cnt in active_user_rows]

    return {
        # Project stats
        "total_projects": total_projects,
        "active_projects": active_projects,
        "archived_projects": total_projects - active_projects,

        # User stats
        "total_users": total_users,
        "active_users": active_users,

        # Incident stats
        "total_incidents": total_incidents,
        "open_incidents": open_incidents,
        "critical_incidents": critical_incidents,
        "severity_breakdown": severity_breakdown,

        # Evidence & events
        "total_evidence": total_evidence,
        "total_events_ingested": total_events,
        "events_last_24h": events_24h,

        # Intelligence
        "most_targeted_project": most_targeted_project,
        "most_common_attack": most_common_attack,
        "top_attack_types": top_attack_types,
        "top_source_ips": top_source_ips,
        "ml_prediction_stats": ml_prediction_stats,

        # Activity
        "most_active_projects": most_active_projects,
        "most_active_users": most_active_users,
        "latest_incidents": latest_incidents,

        "generated_at": now.isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Project Management
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/projects")
async def platform_list_projects(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, _SA],
    include_archived: bool = False,
    page: int = 1,
    page_size: int = 50,
):
    """List ALL projects on the platform."""
    q = select(Project)
    if not include_archived:
        q = q.where(Project.status == "active")
    total = (await db.execute(
        select(func.count()).select_from(q.subquery())
    )).scalar_one()
    items = (await db.execute(
        q.order_by(desc(Project.created_at))
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return {
        "items": [_project_to_dict(p) for p in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.patch("/projects/{project_id}/archive", status_code=200)
async def platform_archive_project(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, _SA],
):
    project = await _get_project_or_404(db, project_id)
    project.status = "archived"
    await db.flush()
    await _platform_audit(db, current_user, "project_archived", str(project_id),
                          {"project_name": project.name})
    return {"id": str(project.id), "status": project.status}


@router.delete("/projects/{project_id}", status_code=204)
async def platform_delete_project(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, _SA],
):
    project = await _get_project_or_404(db, project_id)
    name = project.name
    await db.delete(project)
    await db.flush()
    await _platform_audit(db, current_user, "project_deleted", str(project_id),
                          {"project_name": name})


@router.post("/projects/{project_id}/assign-admin", status_code=200)
async def platform_assign_project_admin(
    project_id: uuid.UUID,
    body: PlatformProjectAssignAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, _SA],
):
    """Assign a user as admin for a specific project (creates ProjectMember)."""
    project = await _get_project_or_404(db, project_id)
    user = await _get_user_or_404(db, body.user_id)

    from app.models.project_member import ProjectMember
    # Upsert: update role if membership already exists
    existing = (await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == body.user_id,
        )
    )).scalar_one_or_none()

    if existing:
        existing.role = "admin"
    else:
        db.add(ProjectMember(
            project_id=project_id,
            user_id=body.user_id,
            role="admin",
            invited_by=current_user.id,
        ))
    await db.flush()
    await _platform_audit(db, current_user, "project_admin_assigned", str(project_id),
                          {"user_email": user.email, "project_name": project.name})
    return {"project_id": str(project_id), "user_id": str(body.user_id), "role": "admin"}


@router.post("/projects/{project_id}/regenerate-key", status_code=200)
async def platform_regenerate_project_key(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, _SA],
):
    """Regenerate project API key. Old key is immediately invalidated."""
    import secrets
    project = await _get_project_or_404(db, project_id)
    old_prefix = project.api_key[:10] if project.api_key else "none"
    project.api_key = "proj_" + secrets.token_urlsafe(32)
    await db.flush()
    await _platform_audit(db, current_user, "api_key_regenerated", str(project_id),
                          {"project_name": project.name, "old_prefix": old_prefix})
    return {"id": str(project.id), "api_key": project.api_key}


# ─────────────────────────────────────────────────────────────────────────────
# User Management
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/users")
async def platform_list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, _SA],
    page: int = 1,
    page_size: int = 50,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
):
    q = select(User)
    if role:
        q = q.where(User.role == role)
    if is_active is not None:
        q = q.where(User.is_active == is_active)
    total = (await db.execute(
        select(func.count()).select_from(q.subquery())
    )).scalar_one()
    items = (await db.execute(
        q.order_by(desc(User.created_at))
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return {
        "items": [_user_to_dict(u) for u in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/users", status_code=201)
async def platform_create_user(
    body: PlatformUserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, _SA],
):
    # Validate role
    valid_roles = {r.value for r in Role}
    if body.role not in valid_roles:
        raise HTTPException(status_code=422, detail=f"Invalid role. Must be one of {sorted(valid_roles)}")

    # Check uniqueness
    existing = (await db.execute(
        select(User).where(
            (User.email == body.email) | (User.username == body.username)
        )
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Email or username already in use")

    user = User(
        email=body.email,
        username=body.username,
        full_name=body.full_name,
        hashed_password=get_password_hash(body.password),
        role=body.role,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.flush()
    await _platform_audit(db, current_user, "user_created", str(user.id),
                          {"email": user.email, "role": user.role})
    return _user_to_dict(user)


@router.patch("/users/{user_id}/disable", status_code=200)
async def platform_disable_user(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, _SA],
):
    user = await _get_user_or_404(db, user_id)
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot disable your own account")
    user.is_active = False
    await db.flush()
    await _platform_audit(db, current_user, "user_disabled", str(user_id),
                          {"email": user.email})
    return _user_to_dict(user)


@router.delete("/users/{user_id}", status_code=204)
async def platform_delete_user(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, _SA],
):
    user = await _get_user_or_404(db, user_id)
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    email = user.email
    await db.delete(user)
    await db.flush()
    await _platform_audit(db, current_user, "user_deleted", str(user_id),
                          {"email": email})


@router.patch("/users/{user_id}/role", status_code=200)
async def platform_change_user_role(
    user_id: uuid.UUID,
    body: PlatformUserRoleUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, _SA],
):
    valid_roles = {r.value for r in Role}
    if body.role not in valid_roles:
        raise HTTPException(status_code=422, detail=f"Invalid role. Must be one of {sorted(valid_roles)}")
    user = await _get_user_or_404(db, user_id)
    old_role = user.role
    user.role = body.role
    await db.flush()
    await _platform_audit(db, current_user, "role_changed", str(user_id),
                          {"email": user.email, "old_role": old_role, "new_role": body.role})
    return _user_to_dict(user)


@router.post("/users/{user_id}/reset-password", status_code=200)
async def platform_reset_password(
    user_id: uuid.UUID,
    body: PlatformPasswordReset,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, _SA],
):
    if len(body.new_password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")
    user = await _get_user_or_404(db, user_id)
    user.hashed_password = get_password_hash(body.new_password)
    user.failed_login_attempts = 0
    user.locked_until = None
    await db.flush()
    await _platform_audit(db, current_user, "password_reset", str(user_id),
                          {"email": user.email})
    return {"message": "Password reset successfully", "user_id": str(user_id)}


# ─────────────────────────────────────────────────────────────────────────────
# Platform-wide Audit Logs
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/audit")
async def platform_audit_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, _SA],
    page: int = 1,
    page_size: int = 100,
    action: Optional[str] = None,
    user_email: Optional[str] = None,
):
    q = select(AuditLog)
    if action:
        q = q.where(AuditLog.action == action)
    if user_email:
        q = q.where(AuditLog.user_email == user_email)
    total = (await db.execute(
        select(func.count()).select_from(q.subquery())
    )).scalar_one()
    items = (await db.execute(
        q.order_by(desc(AuditLog.created_at))
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return {
        "items": [
            {
                "id": str(a.id),
                "user_email": a.user_email,
                "action": a.action,
                "resource_type": a.resource_type,
                "resource_id": a.resource_id,
                "ip_address": a.ip_address,
                "request_path": a.request_path,
                "response_status": a.response_status,
                "details": a.details,
                "created_at": a.created_at.isoformat(),
            }
            for a in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ─────────────────────────────────────────────────────────────────────────────
# System Health
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/health")
async def platform_system_health(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, _SA],
):
    """Platform system health — DB, ML model, API."""
    # DB connectivity
    try:
        await db.execute(select(func.count(User.id)))
        db_status = "ok"
        db_error = None
    except Exception as e:
        db_status = "error"
        db_error = str(e)

    # ML model status
    try:
        from app.ml.classifier import get_classifier
        clf = get_classifier()
        clf._load()  # trigger lazy initialisation if not yet done
        ml_status = "loaded" if clf._model is not None else "heuristic_fallback"
        ml_model_version = getattr(clf, "_version", "unknown")
    except Exception as e:
        ml_status = "error"
        ml_model_version = None

    # Recent events throughput (last 5 minutes)
    five_min_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
    recent_events = (await db.execute(
        select(func.count(SecurityEvent.id)).where(SecurityEvent.created_at >= five_min_ago)
    )).scalar_one()

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "database": {"status": db_status, "error": db_error},
        "ml": {"status": ml_status, "model_version": ml_model_version},
        "api": {"status": "ok"},
        "ingestion": {
            "events_last_5min": recent_events,
            "throughput_per_min": recent_events / 5,
        },
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _get_project_or_404(db: AsyncSession, project_id: uuid.UUID) -> Project:
    p = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return p


async def _get_user_or_404(db: AsyncSession, user_id: uuid.UUID) -> User:
    u = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    return u


async def _platform_audit(
    db: AsyncSession,
    actor: User,
    action: str,
    resource_id: str,
    details: dict,
) -> None:
    """Write a platform-level audit log entry."""
    try:
        log = AuditLog(
            user_id=actor.id,
            user_email=actor.email,
            action=action,
            resource_type="platform",
            resource_id=resource_id,
            details={**details, "actor_role": actor.role, "platform_action": True},
        )
        db.add(log)
        await db.flush()
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error("Failed to write platform audit: %s", exc)


def _project_to_dict(p: Project) -> dict:
    return {
        "id": str(p.id),
        "name": p.name,
        "slug": p.slug,
        "description": p.description,
        "environment": p.environment,
        "status": p.status,
        "owner_id": str(p.owner_id) if p.owner_id else None,
        # Never return the actual API key in list views — only in regenerate response
        "api_key_prefix": p.api_key[:10] + "..." if p.api_key else None,
        "created_at": p.created_at.isoformat(),
        "updated_at": p.updated_at.isoformat(),
    }


def _user_to_dict(u: User) -> dict:
    return {
        "id": str(u.id),
        "email": u.email,
        "username": u.username,
        "full_name": u.full_name,
        "role": u.role,
        "is_active": u.is_active,
        "is_verified": u.is_verified,
        "last_login": u.last_login.isoformat() if u.last_login else None,
        "created_at": u.created_at.isoformat(),
    }
