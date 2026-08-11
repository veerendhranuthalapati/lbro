"""Project access control — enforce multi-tenant isolation.

Authorization model (v2):
  - Each Project has an owner_id (creator).
  - Platform roles: super_admin (all projects), admin (all projects — org-wide operator).
  - Project roles analyst/viewer are GLOBAL user roles scoped by project ownership:
    users only access resources in projects they own.
  - ProjectMember table exists for future per-project RBAC but is NOT used yet.
    Do not rely on ProjectMember for authorization until implemented end-to-end.
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.core.rbac import Role, is_super_admin
from app.models.incident import Incident
from app.models.project import Project
from app.models.user import User


def is_privileged_user(user: User) -> bool:
    """Platform admin or super_admin — may access all projects."""
    return user.role == Role.ADMIN.value or is_super_admin(user.role)


def incident_access_scope(user: User) -> Optional[ColumnElement]:
    """SQLAlchemy filter for incidents accessible to user.

    Returns None for privileged users (no filter). Otherwise owner-based scope.
    """
    if is_privileged_user(user):
        return None
    project_subq = select(Project.id).where(Project.owner_id == user.id).scalar_subquery()
    return or_(
        Incident.project_id.in_(project_subq),
        and_(Incident.project_id.is_(None), Incident.created_by == user.id),
    )


async def accessible_project_ids(
    db: AsyncSession,
    user: User,
) -> Optional[list[uuid.UUID]]:
    """Return None if user may access all projects; else list of owned project IDs."""
    if is_privileged_user(user):
        return None
    result = await db.execute(
        select(Project.id).where(Project.owner_id == user.id, Project.status == "active")
    )
    return list(result.scalars().all())


async def assert_project_access(
    db: AsyncSession,
    project_id: uuid.UUID,
    user: User,
) -> Project:
    """Return project if user may access it; otherwise raise 403/404."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Project not found"},
        )
    if not is_privileged_user(user) and project.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "forbidden",
                "message": "You do not have access to this project",
            },
        )
    return project


async def resolve_project_scope(
    db: AsyncSession,
    user: User,
    project_id: Optional[uuid.UUID],
) -> Optional[list[uuid.UUID]]:
    """Resolve which project IDs a query should filter to.

    - Privileged + explicit project_id: single project (after access check).
    - Privileged + no project_id: None (global).
    - Non-privileged + explicit project_id: single project (after access check).
    - Non-privileged + no project_id: all owned project IDs (may be empty).
    """
    if project_id is not None:
        await assert_project_access(db, project_id, user)
        return [project_id]
    return await accessible_project_ids(db, user)
