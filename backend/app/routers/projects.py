"""Projects router.

Provides full CRUD for projects plus a per-project dashboard endpoint.
All authenticated users can create projects; only the owner (or an admin)
can update, regenerate the API key, or delete.
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Permission, Role
from app.database import get_db
from app.dependencies import require_permission
from app.models.user import User
from app.schemas.project import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


def _assert_owner_or_admin(project_owner_id, current_user: User) -> None:
    """Raise 403 if the user is not the owner and not an admin."""
    if current_user.role != Role.ADMIN and project_owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the project owner or an admin can perform this action.",
        )


# ── List / Create ─────────────────────────────────────────────────────────────

@router.get("", response_model=ProjectListResponse)
async def list_projects(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_DASHBOARD))],
    include_archived: bool = False,
):
    """Return projects owned by the current user (admin sees all)."""
    svc = ProjectService(db)
    owner_filter = None if current_user.role == Role.ADMIN else current_user.id
    items, total = await svc.list_for_user(
        owner_id=owner_filter, include_archived=include_archived
    )
    return ProjectListResponse(items=items, total=total)


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    data: ProjectCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_DASHBOARD))],
):
    svc = ProjectService(db)
    project = await svc.create(data, owner_id=current_user.id)
    return project


# ── Single project ────────────────────────────────────────────────────────────

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_DASHBOARD))],
):
    svc = ProjectService(db)
    return await svc.get(project_id)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    data: ProjectUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_DASHBOARD))],
):
    svc = ProjectService(db)
    project = await svc.get(project_id)
    _assert_owner_or_admin(project.owner_id, current_user)
    return await svc.update(project_id, data)


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_DASHBOARD))],
):
    svc = ProjectService(db)
    project = await svc.get(project_id)
    _assert_owner_or_admin(project.owner_id, current_user)
    await svc.delete(project_id)


# ── Project API key ───────────────────────────────────────────────────────────

@router.post("/{project_id}/regenerate-key", response_model=ProjectResponse)
async def regenerate_api_key(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_DASHBOARD))],
):
    """Rotate the project API key. The old key is immediately invalidated."""
    svc = ProjectService(db)
    project = await svc.get(project_id)
    _assert_owner_or_admin(project.owner_id, current_user)
    return await svc.regenerate_api_key(project_id)


# ── Project dashboard ─────────────────────────────────────────────────────────

@router.get("/{project_id}/dashboard")
async def project_dashboard(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_DASHBOARD))],
):
    """Aggregated security stats for a single project."""
    svc = ProjectService(db)
    return await svc.get_dashboard(project_id)
