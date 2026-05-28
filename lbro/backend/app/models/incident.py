"""
LBRO — ORM Models
"""
import enum
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IncidentSeverity(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class IncidentStatus(str, enum.Enum):
    DETECTED = "detected"
    TRIAGING = "triaging"
    CONTAINING = "containing"
    CONTAINED = "contained"
    NOTIFYING = "notifying"
    CLOSED = "closed"
    ESCALATED = "escalated"


class Jurisdiction(str, enum.Enum):
    GDPR = "GDPR"
    HIPAA = "HIPAA"
    DPDPA = "DPDPA"


class NotificationStatus(str, enum.Enum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    ACKNOWLEDGED = "acknowledged"
    OVERDUE = "overdue"


# ── Incident ──────────────────────────────────────────────────────────────────

class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    severity: Mapped[IncidentSeverity] = mapped_column(Enum(IncidentSeverity), nullable=False, index=True)
    status: Mapped[IncidentStatus] = mapped_column(
        Enum(IncidentStatus), nullable=False, default=IncidentStatus.DETECTED, index=True
    )

    source_system: Mapped[str] = mapped_column(String(128), nullable=False)
    source_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    affected_systems: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    affected_records_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    jurisdictions: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    contains_pii: Mapped[bool] = mapped_column(Boolean, default=False)
    contains_phi: Mapped[bool] = mapped_column(Boolean, default=False)

    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    contained_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    sqs_message_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    evidence_packages: Mapped[list["EvidencePackage"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )
    notifications: Mapped[list["RegulatoryNotification"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )
    timeline: Mapped[list["IncidentTimelineEvent"]] = relationship(
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="IncidentTimelineEvent.occurred_at",
    )

    @property
    def response_time_seconds(self) -> Optional[float]:
        if self.contained_at:
            return (self.contained_at - self.detected_at).total_seconds()
        return None


# ── Evidence ──────────────────────────────────────────────────────────────────

class EvidencePackage(Base):
    __tablename__ = "evidence_packages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id"), nullable=False, index=True)

    s3_bucket: Mapped[str] = mapped_column(String(256), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    s3_version_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    collected_by: Mapped[str] = mapped_column(String(256), nullable=False)
    collection_method: Mapped[str] = mapped_column(String(128), nullable=False)
    chain_of_custody: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    package_type: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    incident: Mapped["Incident"] = relationship(back_populates="evidence_packages")

    __table_args__ = (
        UniqueConstraint("s3_bucket", "s3_key", name="uq_evidence_s3_location"),
    )


# ── Regulatory Notifications ──────────────────────────────────────────────────

class RegulatoryNotification(Base):
    __tablename__ = "regulatory_notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id"), nullable=False, index=True)

    jurisdiction: Mapped[Jurisdiction] = mapped_column(Enum(Jurisdiction), nullable=False)
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus), nullable=False, default=NotificationStatus.PENDING, index=True
    )

    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dispatched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    template_version: Mapped[str] = mapped_column(String(32), nullable=False)
    rendered_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recipient_authority: Mapped[str] = mapped_column(String(512), nullable=False)
    archive_s3_key: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    incident: Mapped["Incident"] = relationship(back_populates="notifications")

    @property
    def hours_remaining(self) -> float:
        return (self.deadline_at - datetime.now(timezone.utc)).total_seconds() / 3600

    @property
    def is_overdue(self) -> bool:
        return datetime.now(timezone.utc) > self.deadline_at and self.status == NotificationStatus.PENDING


# ── Timeline ──────────────────────────────────────────────────────────────────

class IncidentTimelineEvent(Base):
    __tablename__ = "incident_timeline"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id"), nullable=False, index=True)

    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    actor: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    event_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)

    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    incident: Mapped["Incident"] = relationship(back_populates="timeline")
