"""User-scoped project invitation endpoints (accept/decline/pending list)."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Permission
from app.database import get_db
from app.dependencies import require_permission
from app.models.project import Project
from app.models.user import User
from app.schemas.project import (
    ProjectInvitationAccept,
    ProjectInvitationListResponse,
    ProjectInvitationResponse,
    ProjectMemberResponse,
)
from app.services.invitation_service import InvitationService
from sqlalchemy import select

router = APIRouter(prefix="/invitations", tags=["invitations"])


async def _invitation_response(db: AsyncSession, invitation) -> ProjectInvitationResponse:
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


@router.get("/pending", response_model=ProjectInvitationListResponse)
async def list_pending_invitations(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_DASHBOARD))],
):
    svc = InvitationService(db)
    items = await svc.list_pending_for_user(current_user)
    responses = [await _invitation_response(db, inv) for inv in items]
    return ProjectInvitationListResponse(items=responses, total=len(responses))


@router.post("/{invitation_id}/accept", response_model=ProjectMemberResponse)
async def accept_invitation(
    invitation_id: uuid.UUID,
    body: ProjectInvitationAccept,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_DASHBOARD))],
):
    svc = InvitationService(db)
    member = await svc.accept(invitation_id, current_user, token=body.token)
    from app.services.project_service import ProjectService

    project_svc = ProjectService(db)
    project = await project_svc.get(member.project_id)
    return ProjectMemberResponse(
        id=member.id,
        project_id=member.project_id,
        user_id=member.user_id,
        role=member.role,
        email=current_user.email,
        full_name=current_user.full_name,
        is_owner=project.owner_id == current_user.id,
        invited_by=member.invited_by,
        created_at=member.created_at,
    )


@router.post("/{invitation_id}/decline", status_code=204)
async def decline_invitation(
    invitation_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_DASHBOARD))],
):
    svc = InvitationService(db)
    await svc.decline(invitation_id, current_user)


@router.post("/accept-token", response_model=ProjectMemberResponse)
async def accept_invitation_by_token(
    body: ProjectInvitationAccept,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_DASHBOARD))],
):
    svc = InvitationService(db)
    member = await svc.accept_by_token(body.token or "", current_user)
    from app.services.project_service import ProjectService

    project_svc = ProjectService(db)
    project = await project_svc.get(member.project_id)
    return ProjectMemberResponse(
        id=member.id,
        project_id=member.project_id,
        user_id=member.user_id,
        role=member.role,
        email=current_user.email,
        full_name=current_user.full_name,
        is_owner=project.owner_id == current_user.id,
        invited_by=member.invited_by,
        created_at=member.created_at,
    )
