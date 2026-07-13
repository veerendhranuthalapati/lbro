"""SecurityEvent ORM model — raw events ingested via the public API.

Events arrive from external applications via POST /api/v1/events using a
Project API key.  The project_id is ALWAYS resolved from the API key, never
from the request body, preventing cross-project injection.

Each event is processed through the ingestion pipeline:
  1. Schema validation (FastAPI)
  2. ML classification (async, inline for now)
  3. Incident auto-creation (severity: high/critical)
  4. Evidence generation (raw event stored)
  5. Compliance evaluation (trigger applicable obligations)
  6. Dashboard update (aggregation cache invalidation)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SecurityEvent(Base):
    __tablename__ = "security_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Always resolved from the authenticating API key — never trusted from client
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Event classification ────────────────────────────────────────────────
    # Types: auth_failure, sql_injection, xss, brute_force, port_scan,
    #        suspicious_request, system_log, application_log, nginx_log,
    #        apache_log, firewall_event, windows_event, linux_audit, custom
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Severity as submitted by the source (may be overridden by ML)
    severity: Mapped[str] = mapped_column(String(50), nullable=False, default="medium", index=True)

    # ── Source info ────────────────────────────────────────────────────────
    source_ip: Mapped[str | None] = mapped_column(String(45), nullable=True, index=True)
    source_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_application: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_agent_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # ── Payload ────────────────────────────────────────────────────────────
    # Full event data as submitted — stored as JSON for schema flexibility
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Human-readable summary extracted from payload
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── ML results ────────────────────────────────────────────────────────
    ml_attack_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ml_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    ml_model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # ── Outcome ────────────────────────────────────────────────────────────
    # Whether this event triggered an incident auto-creation
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # processed | pending | failed
    processing_status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending", index=True)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Timestamps ────────────────────────────────────────────────────────
    # Event time as reported by the source (may differ from ingestion time)
    event_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # When LBRO received and stored the event
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<SecurityEvent {self.event_type} project={self.project_id}>"
