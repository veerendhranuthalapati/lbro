"""Asset inventory and incident exposure ORM models (data map)."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.incident import Incident
    from app.models.project import Project
    from app.models.user import User


class Asset(Base):
    """Project-scoped fictional asset metadata (counts only, no real PII)."""

    __tablename__ = "assets"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_assets_project_name"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)
    environment: Mapped[str | None] = mapped_column(String(50), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    classification: Mapped[str] = mapped_column(String(50), nullable=False, default="internal")
    criticality: Mapped[str | None] = mapped_column(String(50), nullable=True)
    data_categories: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    encrypted_at_rest: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    identifiers: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    project: Mapped["Project"] = relationship("Project", back_populates="assets")
    residency: Mapped[list["AssetResidency"]] = relationship(
        "AssetResidency", back_populates="asset", cascade="all, delete-orphan"
    )
    incident_links: Mapped[list["IncidentAsset"]] = relationship(
        "IncidentAsset", back_populates="asset", cascade="all, delete-orphan"
    )


class AssetResidency(Base):
    """Per-jurisdiction data-subject record counts for an asset."""

    __tablename__ = "asset_residency"
    __table_args__ = (
        UniqueConstraint(
            "asset_id",
            "jurisdiction_code",
            "data_category",
            name="uq_asset_residency_jurisdiction_category",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    jurisdiction_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    record_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    count_basis: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    as_of: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    asset: Mapped["Asset"] = relationship("Asset", back_populates="residency")


class IncidentAsset(Base):
    """Links an incident to affected assets with analyst confirmation workflow."""

    __tablename__ = "incident_assets"
    __table_args__ = (UniqueConstraint("incident_id", "asset_id", name="uq_incident_asset"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    link_source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    match_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    match_confidence: Mapped[str] = mapped_column(String(20), nullable=False, default="high")
    exposure_fraction: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="confirmed")

    incident: Mapped["Incident"] = relationship("Incident", back_populates="linked_assets")
    asset: Mapped["Asset"] = relationship("Asset", back_populates="incident_links")


class IncidentExposureAssessment(Base):
    """Versioned output of the compliance inference engine for an incident."""

    __tablename__ = "incident_exposure_assessments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    engine_version: Mapped[str] = mapped_column(String(32), nullable=False)
    knowledge_versions: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    inputs_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    overall_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="provisional")
    results: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    trace: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    incident: Mapped["Incident"] = relationship("Incident", back_populates="exposure_assessments")
