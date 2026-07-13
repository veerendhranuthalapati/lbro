"""Compliance tracking ORM models."""
from __future__ import annotations

from typing import TYPE_CHECKING

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.incident import Incident
    from app.models.project import Project


class ComplianceRecord(Base):
    __tablename__ = "compliance_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    regulation: Mapped[str] = mapped_column(String(50), nullable=False)  # GDPR, HIPAA, DPDPA
    jurisdiction: Mapped[str] = mapped_column(String(100), nullable=False)
    obligation: Mapped[str] = mapped_column(String(500), nullable=False)
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_met: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    met_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    incident: Mapped["Incident"] = relationship("Incident", back_populates="compliance_records")


class ComplianceObligation(Base):
    """Per-project compliance obligation checklist item (e.g., GDPR Art-32 control).

    Stores the persistent checked/unchecked state of each compliance obligation
    for a given project+framework combination.  Replaces the previous localStorage
    approach in the frontend.
    """
    __tablename__ = "compliance_obligations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Regulation framework: GDPR, HIPAA, DPDPA, etc.
    framework: Mapped[str] = mapped_column(String(50), nullable=False)
    # Short control ID as used in the frontend, e.g. "g1", "h1", "d1"
    control_id: Mapped[str] = mapped_column(String(100), nullable=False)
    # Human-readable control name
    control_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # not_started | in_progress | compliant | non_compliant | not_applicable
    status: Mapped[str] = mapped_column(String(50), default="not_started", nullable=False)
    evidence_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    recommendations: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_updated: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    project: Mapped["Project"] = relationship("Project", back_populates="compliance_obligations")


class ComplianceAssessment(Base):
    """Snapshot of compliance posture for a project+framework at a point in time."""
    __tablename__ = "compliance_assessments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    framework: Mapped[str] = mapped_column(String(50), nullable=False)
    overall_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_controls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    compliant_controls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    assessment_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    project: Mapped["Project"] = relationship("Project", back_populates="compliance_assessments")
