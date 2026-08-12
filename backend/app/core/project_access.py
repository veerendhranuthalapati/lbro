"""Project access control — enforce multi-tenant isolation.

Authorization model:
  - Project.owner_id is the creator; owners have implicit admin role.
  - ProjectMember grants per-project roles (admin / analyst / viewer).
  - Platform super_admin and admin may access all projects (global operators).
  - Normal users see only projects they own or belong to via ProjectMember.
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
from app.models.project_member import ProjectMember
from app.models.user import User

PROJECT_ROLES = ("admin", "analyst", "viewer")
PROJECT_ROLE_RANK = {"viewer": 1, "analyst": 2, "admin": 3}


def is_privileged_user(user: User) -> bool:
    """Platform admin or super_admin — may access all projects."""
    return user.role == Role.ADMIN.value or is_super_admin(user.role)


def _rank(role: str) -> int:
    return PROJECT_ROLE_RANK.get(role, 0)


async def get_membership(
    db: AsyncSession,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
) -> Optional[ProjectMember]:
    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.user_id == user_id,
            ProjectMember.project_id == project_id,
        )
    )
    return result.scalar_one_or_none()


async def get_effective_project_role(
    db: AsyncSession,
    user: User,
    project: Project,
) -> Optional[str]:
    """Return the user's role within a project, or None if no access."""
    if is_privileged_user(user):
        return "admin"
    if project.owner_id == user.id:
        return "admin"
    membership = await get_membership(db, user.id, project.id)
    return membership.role if membership else None


async def accessible_project_ids(
    db: AsyncSession,
    user: User,
) -> Optional[list[uuid.UUID]]:
    """Return None if user may access all projects; else owned + member project IDs."""
    if is_privileged_user(user):
        return None

    owned = await db.execute(
        select(Project.id).where(
            Project.owner_id == user.id,
            Project.status == "active",
        )
    )
    member = await db.execute(
        select(ProjectMember.project_id)
        .join(Project, Project.id == ProjectMember.project_id)
        .where(
            ProjectMember.user_id == user.id,
            Project.status == "active",
        )
    )
    ids = set(owned.scalars().all()) | set(member.scalars().all())
    return list(ids)


def incident_access_scope(user: User) -> Optional[ColumnElement]:
    """SQLAlchemy filter for incidents accessible to user."""
    if is_privileged_user(user):
        return None

    owned_subq = select(Project.id).where(Project.owner_id == user.id).scalar_subquery()
    member_subq = (
        select(ProjectMember.project_id)
        .where(ProjectMember.user_id == user.id)
        .scalar_subquery()
    )
    return or_(
        Incident.project_id.in_(owned_subq),
        Incident.project_id.in_(member_subq),
        and_(Incident.project_id.is_(None), Incident.created_by == user.id),
    )


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
    if is_privileged_user(user):
        return project
    if project.owner_id == user.id:
        return project
    membership = await get_membership(db, user.id, project_id)
    if membership:
        return project
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error": "forbidden",
            "message": "You do not have access to this project",
        },
    )


async def assert_project_role(
    db: AsyncSession,
    project_id: uuid.UUID,
    user: User,
    min_role: str = "viewer",
) -> Project:
    """Require at least min_role within the project (admin > analyst > viewer)."""
    project = await assert_project_access(db, project_id, user)
    if is_privileged_user(user):
        return project
    role = await get_effective_project_role(db, user, project)
    if role and _rank(role) >= _rank(min_role):
        return project
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error": "forbidden",
            "message": f"This action requires project role '{min_role}' or higher",
        },
    )


async def assert_project_admin(
    db: AsyncSession,
    project_id: uuid.UUID,
    user: User,
) -> Project:
    """Require project owner, project admin member, or platform privileged user."""
    return await assert_project_role(db, project_id, user, min_role="admin")


async def resolve_project_scope(
    db: AsyncSession,
    user: User,
    project_id: Optional[uuid.UUID],
) -> Optional[list[uuid.UUID]]:
    """Resolve which project IDs a query should filter to."""
    if project_id is not None:
        await assert_project_access(db, project_id, user)
        return [project_id]
    return await accessible_project_ids(db, user)
