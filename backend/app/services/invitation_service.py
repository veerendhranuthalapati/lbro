"""Project invitation lifecycle."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, LBROException
from app.core.invitation_tokens import (
    generate_invitation_token,
    normalize_invitation_email,
    verify_invitation_token,
)
from app.models.project import Project
from app.models.project_invitation import ProjectInvitation
from app.models.project_member import ProjectMember
from app.models.user import User

INVITATION_TTL_DAYS = 7
VALID_INVITE_ROLES = frozenset({"admin", "analyst", "viewer"})


def _utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class InvitationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        project_id: uuid.UUID,
        email: str,
        role: str,
        invited_by: uuid.UUID,
    ) -> tuple[ProjectInvitation, str]:
        """Create invitation; return (invitation, plaintext_token)."""
        normalized = normalize_invitation_email(email)
        if role not in VALID_INVITE_ROLES:
            raise ConflictError("Invalid project role for invitation")

        project = await self._get_project(project_id)

        existing_member = await self.db.execute(
            select(ProjectMember)
            .join(User, User.id == ProjectMember.user_id)
            .where(
                ProjectMember.project_id == project_id,
                User.email == normalized,
            )
        )
        if existing_member.scalar_one_or_none():
            raise ConflictError("User is already a member of this project")

        pending = await self.db.execute(
            select(ProjectInvitation).where(
                ProjectInvitation.project_id == project_id,
                ProjectInvitation.invited_email == normalized,
                ProjectInvitation.status == "pending",
            )
        )
        if pending.scalar_one_or_none():
            raise ConflictError("A pending invitation already exists for this email")

        token, token_hash = generate_invitation_token()
        now = datetime.now(timezone.utc)
        invitation = ProjectInvitation(
            project_id=project_id,
            invited_email=normalized,
            role=role,
            invited_by=invited_by,
            token_hash=token_hash,
            status="pending",
            expires_at=now + timedelta(days=INVITATION_TTL_DAYS),
        )
        self.db.add(invitation)
        await self.db.flush()
        return invitation, token

    async def list_for_project(self, project_id: uuid.UUID) -> list[ProjectInvitation]:
        result = await self.db.execute(
            select(ProjectInvitation)
            .where(
                ProjectInvitation.project_id == project_id,
                ProjectInvitation.status == "pending",
            )
            .order_by(ProjectInvitation.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_pending_for_user(self, user: User) -> list[ProjectInvitation]:
        email = normalize_invitation_email(user.email)
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(ProjectInvitation)
            .join(Project, Project.id == ProjectInvitation.project_id)
            .where(
                ProjectInvitation.invited_email == email,
                ProjectInvitation.status == "pending",
                ProjectInvitation.expires_at > now,
                Project.status == "active",
            )
            .order_by(ProjectInvitation.created_at.desc())
        )
        return list(result.scalars().all())

    async def cancel(self, invitation_id: uuid.UUID, project_id: uuid.UUID) -> None:
        invitation = await self._get_invitation(invitation_id, project_id)
        if invitation.status != "pending":
            raise ConflictError("Invitation is no longer pending")
        invitation.status = "cancelled"
        await self.db.flush()

    async def decline(self, invitation_id: uuid.UUID, user: User) -> None:
        invitation = await self._get_invitation_by_id(invitation_id)
        self._assert_invitee(user, invitation)
        if invitation.status != "pending":
            raise ConflictError("Invitation is no longer pending")
        invitation.status = "cancelled"
        await self.db.flush()

    async def accept(
        self,
        invitation_id: uuid.UUID,
        user: User,
        token: Optional[str] = None,
    ) -> ProjectMember:
        invitation = await self._get_invitation_by_id(invitation_id)
        self._assert_invitee(user, invitation)
        return await self._accept_invitation(invitation, user, token)

    async def accept_by_token(self, token: str, user: User) -> ProjectMember:
        if not token:
            raise LBROException("Invitation token is required", 400)
        result = await self.db.execute(
            select(ProjectInvitation).where(ProjectInvitation.status == "pending")
        )
        invitation = None
        for row in result.scalars().all():
            if verify_invitation_token(token, row.token_hash):
                invitation = row
                break
        if not invitation:
            raise NotFoundError("Invitation")
        self._assert_invitee(user, invitation)
        return await self._accept_invitation(invitation, user, token)

    async def _accept_invitation(
        self,
        invitation: ProjectInvitation,
        user: User,
        token: Optional[str],
    ) -> ProjectMember:
        now = datetime.now(timezone.utc)
        if invitation.status != "pending":
            raise ConflictError("Invitation is no longer valid")
        if _utc(invitation.expires_at) <= now:
            invitation.status = "expired"
            await self.db.flush()
            raise LBROException("Invitation has expired", 410)

        if token and not verify_invitation_token(token, invitation.token_hash):
            raise LBROException("Invalid invitation token", 400)

        project = await self._get_project(invitation.project_id)
        if project.status != "active":
            raise LBROException("Project is not active", 400)

        existing = await self.db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == invitation.project_id,
                ProjectMember.user_id == user.id,
            )
        )
        if existing.scalar_one_or_none():
            invitation.status = "accepted"
            invitation.accepted_at = now
            invitation.accepted_by = user.id
            await self.db.flush()
            raise ConflictError("You are already a member of this project")

        member = ProjectMember(
            project_id=invitation.project_id,
            user_id=user.id,
            role=invitation.role,
            invited_by=invitation.invited_by,
        )
        self.db.add(member)
        invitation.status = "accepted"
        invitation.accepted_at = now
        invitation.accepted_by = user.id
        await self.db.flush()
        return member

    def _assert_invitee(self, user: User, invitation: ProjectInvitation) -> None:
        if normalize_invitation_email(user.email) != invitation.invited_email:
            raise LBROException(
                "This invitation was sent to a different email address",
                403,
            )

    async def _get_project(self, project_id: uuid.UUID) -> Project:
        result = await self.db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise NotFoundError("Project")
        return project

    async def _get_invitation(
        self, invitation_id: uuid.UUID, project_id: uuid.UUID
    ) -> ProjectInvitation:
        result = await self.db.execute(
            select(ProjectInvitation).where(
                ProjectInvitation.id == invitation_id,
                ProjectInvitation.project_id == project_id,
            )
        )
        invitation = result.scalar_one_or_none()
        if not invitation:
            raise NotFoundError("Invitation")
        return invitation

    async def _get_invitation_by_id(self, invitation_id: uuid.UUID) -> ProjectInvitation:
        result = await self.db.execute(
            select(ProjectInvitation).where(ProjectInvitation.id == invitation_id)
        )
        invitation = result.scalar_one_or_none()
        if not invitation:
            raise NotFoundError("Invitation")
        return invitation
