"""ProjectMember ORM model.

Maps a User to a Project with a project-scoped role.  This provides
per-project RBAC so that a user can be an admin in one project and a
viewer in another, independently of their platform role.

Role hierarchy within a project:
  admin > analyst > viewer

SUPER_ADMIN users bypass project membership checks entirely — they can
access every project regardless of membership.

Future: when an Organisation layer is added, add org_id here.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ProjectMember(Base):
    __tablename__ = "project_members"

    __table_args__ = (
        # One membership record per (project, user) pair
        UniqueConstraint("project_id", "user_id", name="uq_project_member"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Project-scoped role: admin | analyst | viewer
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="viewer")
    invited_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<ProjectMember project={self.project_id} user={self.user_id} role={self.role}>"
