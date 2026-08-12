"""Projects router.

Provides full CRUD for projects plus membership, SDK download, and dashboard.
All authenticated users can create projects; project admins can update/delete.
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.project_access import assert_project_access, assert_project_admin
from app.core.rbac import Permission
from app.database import get_db
from app.dependencies import require_permission
from app.models.user import User
from app.schemas.project import (
    ProjectCreate,
    ProjectCreatedResponse,
    ProjectInvitationCreate,
    ProjectInvitationCreatedResponse,
    ProjectInvitationListResponse,
    ProjectInvitationResponse,
    ProjectListResponse,
    ProjectMemberCreate,
    ProjectMemberListResponse,
    ProjectMemberResponse,
    ProjectMemberUpdate,
    ProjectResponse,
    ProjectUpdate,
)
from app.services.project_service import ProjectService
from app.services.invitation_service import InvitationService
from app.services.sdk_generator import build_python_sdk_zip

router = APIRouter(prefix="/projects", tags=["projects"])


def _project_response(project, my_role: str | None = None) -> ProjectResponse:
    data = ProjectResponse.model_validate(project).model_dump()
    data["my_role"] = my_role
    return ProjectResponse(**data)


# ── List / Create ─────────────────────────────────────────────────────────────

@router.get("", response_model=ProjectListResponse)
async def list_projects(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_DASHBOARD))],
    include_archived: bool = False,
):
    """Return projects the user owns or is a member of (platform admins see all)."""
    svc = ProjectService(db)
    items, total = await svc.list_accessible(current_user, include_archived=include_archived)
    return ProjectListResponse(
        items=[_project_response(p, role) for p, role in items],
        total=total,
    )


@router.post("", response_model=ProjectCreatedResponse, status_code=201)
async def create_project(
    data: ProjectCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_DASHBOARD))],
):
    svc = ProjectService(db)
    project, plaintext = await svc.create(data, owner_id=current_user.id)
    return ProjectCreatedResponse(
        **_project_response(project, "admin").model_dump(),
        api_key=plaintext,
    )


# ── Single project ────────────────────────────────────────────────────────────

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_DASHBOARD))],
):
    from app.core.project_access import get_effective_project_role

    project = await assert_project_access(db, project_id, current_user)
    role = await get_effective_project_role(db, current_user, project)
    return _project_response(project, role)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    data: ProjectUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_DASHBOARD))],
):
    from app.core.project_access import get_effective_project_role

    await assert_project_admin(db, project_id, current_user)
    svc = ProjectService(db)
    project = await svc.update(project_id, data)
    role = await get_effective_project_role(db, current_user, project)
    return _project_response(project, role)


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_DASHBOARD))],
):
    await assert_project_admin(db, project_id, current_user)
    svc = ProjectService(db)
    await svc.delete(project_id)


# ── Project API key ───────────────────────────────────────────────────────────

@router.post("/{project_id}/regenerate-key", response_model=ProjectCreatedResponse)
async def regenerate_api_key(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_DASHBOARD))],
):
    """Rotate the project API key. The old key is immediately invalidated."""
    await assert_project_admin(db, project_id, current_user)
    svc = ProjectService(db)
    project, plaintext = await svc.regenerate_api_key(project_id)
    return ProjectCreatedResponse(
        **_project_response(project, "admin").model_dump(),
        api_key=plaintext,
    )


# ── Project members ───────────────────────────────────────────────────────────

@router.get("/{project_id}/members", response_model=ProjectMemberListResponse)
async def list_project_members(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_DASHBOARD))],
):
    await assert_project_access(db, project_id, current_user)
    svc = ProjectService(db)
    members = await svc.list_members(project_id)
    return ProjectMemberListResponse(
        items=[ProjectMemberResponse(**m) for m in members],
        total=len(members),
    )


@router.post("/{project_id}/members", response_model=ProjectMemberResponse, status_code=201)
async def add_project_member(
    project_id: uuid.UUID,
    data: ProjectMemberCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_DASHBOARD))],
):
    await assert_project_admin(db, project_id, current_user)
    svc = ProjectService(db)
    member = await svc.add_member(
        project_id, data.user_id, data.role, invited_by=current_user.id
    )
    from sqlalchemy import select
    from app.models.user import User as UserModel

    user_row = (
        await db.execute(select(UserModel).where(UserModel.id == member.user_id))
    ).scalar_one()
    project = await svc.get(project_id)
    return ProjectMemberResponse(
        id=member.id,
        project_id=member.project_id,
        user_id=member.user_id,
        role=member.role,
        email=user_row.email,
        full_name=user_row.full_name,
        is_owner=project.owner_id == member.user_id,
        invited_by=member.invited_by,
        created_at=member.created_at,
    )


@router.patch("/{project_id}/members/{member_id}", response_model=ProjectMemberResponse)
async def update_project_member(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    data: ProjectMemberUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_DASHBOARD))],
):
    await assert_project_admin(db, project_id, current_user)
    svc = ProjectService(db)
    member = await svc.update_member_role(
        project_id, member_id, data.role, actor_id=current_user.id
    )
    from sqlalchemy import select
    from app.models.user import User as UserModel

    user_row = (
        await db.execute(select(UserModel).where(UserModel.id == member.user_id))
    ).scalar_one()
    project = await svc.get(project_id)
    return ProjectMemberResponse(
        id=member.id,
        project_id=member.project_id,
        user_id=member.user_id,
        role=member.role,
        email=user_row.email,
        full_name=user_row.full_name,
        is_owner=project.owner_id == member.user_id,
        invited_by=member.invited_by,
        created_at=member.created_at,
    )


@router.delete("/{project_id}/members/{member_id}", status_code=204)
async def remove_project_member(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_DASHBOARD))],
):
    await assert_project_admin(db, project_id, current_user)
    svc = ProjectService(db)
    await svc.remove_member(project_id, member_id, actor_id=current_user.id)


# ── Project invitations ───────────────────────────────────────────────────────

async def _invitation_response(db: AsyncSession, invitation) -> ProjectInvitationResponse:
    from sqlalchemy import select
    from app.models.project import Project

    project_name = None
    result = await db.execute(select(Project).where(Project.id == invitation.project_id))
    project = result.scalar_one_or_none()
    if project:
        project_name = project.name
    return ProjectInvitationResponse(
        id=invitation.id,
        project_id=invitation.project_id,
        invited_email=invitation.invited_email,
        role=invitation.role,
        invited_by=invitation.invited_by,
        status=invitation.status,
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
        project_name=project_name,
    )


@router.get("/{project_id}/invitations", response_model=ProjectInvitationListResponse)
async def list_project_invitations(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_DASHBOARD))],
):
    await assert_project_admin(db, project_id, current_user)
    svc = InvitationService(db)
    items = await svc.list_for_project(project_id)
    responses = [await _invitation_response(db, inv) for inv in items]
    return ProjectInvitationListResponse(items=responses, total=len(responses))


@router.post(
    "/{project_id}/invitations",
    response_model=ProjectInvitationCreatedResponse,
    status_code=201,
)
async def create_project_invitation(
    project_id: uuid.UUID,
    data: ProjectInvitationCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_DASHBOARD))],
):
    """Create a pending invitation. Email is NOT sent unless SMTP is configured."""
    await assert_project_admin(db, project_id, current_user)
    svc = InvitationService(db)
    invitation, token = await svc.create(
        project_id, data.email, data.role, invited_by=current_user.id
    )
    base = await _invitation_response(db, invitation)
    return ProjectInvitationCreatedResponse(**base.model_dump(), invite_token=token)


@router.delete("/{project_id}/invitations/{invitation_id}", status_code=204)
async def cancel_project_invitation(
    project_id: uuid.UUID,
    invitation_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_DASHBOARD))],
):
    await assert_project_admin(db, project_id, current_user)
    svc = InvitationService(db)
    await svc.cancel(invitation_id, project_id)


# ── SDK download ──────────────────────────────────────────────────────────────

@router.get("/{project_id}/sdk/python")
async def download_python_sdk(
    project_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_DASHBOARD))],
):
    """Download a Python SDK example zip (no API key embedded)."""
    project = await assert_project_access(db, project_id, current_user)
    base_url = str(request.base_url).rstrip("/")
    if base_url.endswith("/api/v1"):
        base_url = base_url[: -len("/api/v1")]
    content = build_python_sdk_zip(base_url, project.name)
    slug = project.slug or "project"
    return Response(
        content=content,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="lbro-sdk-{slug}.zip"',
        },
    )


# ── Project dashboard ─────────────────────────────────────────────────────────

@router.get("/{project_id}/dashboard")
async def project_dashboard(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_DASHBOARD))],
):
    """Aggregated security stats for a single project."""
    await assert_project_access(db, project_id, current_user)
    svc = ProjectService(db)
    return await svc.get_dashboard(project_id)
