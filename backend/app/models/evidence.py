"""Evidence vault and chain-of-custody ORM models."""
from __future__ import annotations

from typing import TYPE_CHECKING, List

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, deferred, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.incident import Incident


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(200), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    # S3 fields: nullable — new uploads use PostgreSQL storage (file_data).
    # Kept for backward compatibility with any legacy S3-stored evidence.
    s3_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    s3_bucket: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # Primary storage: file binary stored directly in PostgreSQL (avoids S3 dependency).
    # Deferred so it is not loaded on list queries — only fetched on explicit download.
    file_data: Mapped[bytes | None] = deferred(mapped_column(LargeBinary, nullable=True))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array as text
    is_immutable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    incident: Mapped["Incident"] = relationship("Incident", back_populates="evidence")
    custody_chain: Mapped[List["ChainOfCustody"]] = relationship(
        "ChainOfCustody", back_populates="evidence", cascade="all, delete-orphan",
        order_by="ChainOfCustody.created_at", uselist=True,
    )

    def __repr__(self) -> str:
        return f"<Evidence {self.filename}>"


class ChainOfCustody(Base):
    __tablename__ = "chain_of_custody"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)  # uploaded, accessed, exported, verified
    performed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    performed_by_name: Mapped[str] = mapped_column(String(255), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    hash_at_time: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    evidence: Mapped["Evidence"] = relationship("Evidence", back_populates="custody_chain")
