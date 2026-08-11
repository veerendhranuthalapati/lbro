"""Project ORM model.

Each Project is an isolated security monitoring context (one API, one app, one service).
Users can own many projects. All incidents, evidence, compliance records, and reports
are scoped to a project.

Future: add an Organisation layer above Project for multi-team SaaS.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.compliance import ComplianceObligation, ComplianceAssessment


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("api_key_prefix", "api_key_hash", name="uq_projects_api_key_prefix_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # development | staging | production
    environment: Mapped[str] = mapped_column(String(50), nullable=False, default="production")

    # active | archived
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active", index=True)

    # Project owner — the user who created it
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Per-project API key — prefix + HMAC hash only; full key shown once at creation.
    api_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    api_key_prefix: Mapped[str] = mapped_column(String(16), nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    incidents: Mapped[list] = relationship(
        "Incident", back_populates="project", cascade="all, delete-orphan"
    )
    compliance_obligations: Mapped[list["ComplianceObligation"]] = relationship(
        "ComplianceObligation", back_populates="project", cascade="all, delete-orphan"
    )
    compliance_assessments: Mapped[list["ComplianceAssessment"]] = relationship(
        "ComplianceAssessment", back_populates="project", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Project {self.name!r} [{self.environment}]>"
