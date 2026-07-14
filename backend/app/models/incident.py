"""Incident and IncidentAction ORM models."""
from __future__ import annotations

from typing import TYPE_CHECKING

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.project import Project

import enum


class IncidentStatus(str, enum.Enum):
    NEW = "new"
    TRIAGING = "triaging"
    CONTAINED = "contained"
    ERADICATING = "eradicating"
    RECOVERING = "recovering"
    CLOSED = "closed"
    REOPENED = "reopened"


class IncidentSeverity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AttackCategory(str, enum.Enum):
    BENIGN = "BENIGN"
    DOS_HULK = "DoS Hulk"
    PORT_SCAN = "PortScan"
    DDOS = "DDoS"
    DOS_GOLDEN_EYE = "DoS GoldenEye"
    FTP_PATATOR = "FTP-Patator"
    SSH_PATATOR = "SSH-Patator"
    DOS_SLOWLORIS = "DoS slowloris"
    DOS_SLOWHTTPTEST = "DoS Slowhttptest"
    BOT = "Bot"
    WEB_ATTACK_BRUTE_FORCE = "Web Attack - Brute Force"
    WEB_ATTACK_XSS = "Web Attack - XSS"
    INFILTRATION = "Infiltration"
    WEB_ATTACK_SQL_INJECTION = "Web Attack - Sql Injection"
    HEARTBLEED = "Heartbleed"
    UNKNOWN = "Unknown"


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    external_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=IncidentStatus.NEW.value, index=True
    )
    severity: Mapped[str] = mapped_column(
        String(50), nullable=False, default=IncidentSeverity.MEDIUM.value, index=True
    )
    attack_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ml_model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    needs_analyst_review: Mapped[bool] = mapped_column(default=False, nullable=False)

    source_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    destination_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    source_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    destination_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    protocol: Mapped[str | None] = mapped_column(String(20), nullable=True)

    network_features: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    containment_actions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    containment_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    affected_jurisdictions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    personal_data_involved: Mapped[bool] = mapped_column(default=False, nullable=False)
    health_data_involved: Mapped[bool] = mapped_column(default=False, nullable=False)

    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    project: Mapped["Project | None"] = relationship("Project", back_populates="incidents")
    assigned_to_user: Mapped["User | None"] = relationship(
        "User", back_populates="incidents", foreign_keys=[assigned_to]
    )
    evidence: Mapped[list] = relationship("Evidence", back_populates="incident", cascade="all, delete-orphan")
    notifications: Mapped[list] = relationship("Notification", back_populates="incident")
    actions: Mapped[list["IncidentAction"]] = relationship(
        "IncidentAction", back_populates="incident",
        cascade="all, delete-orphan", lazy="selectin"
    )
    compliance_records: Mapped[list] = relationship("ComplianceRecord", back_populates="incident")
    notes: Mapped[list] = relationship(
        "InvestigationNote", back_populates="incident",
        cascade="all, delete-orphan", lazy="select",
        order_by="InvestigationNote.created_at",
    )

    def __repr__(self) -> str:
        return f"<Incident {self.id} [{self.severity}]>"


class IncidentAction(Base):
    __tablename__ = "incident_actions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    performed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    automated: Mapped[bool] = mapped_column(default=False, nullable=False)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    incident: Mapped["Incident"] = relationship("Incident", back_populates="actions")
