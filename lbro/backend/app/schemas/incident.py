"""
LBRO — Pydantic schemas (API contract)
"""
import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.incident import (
    IncidentSeverity,
    IncidentStatus,
    Jurisdiction,
    NotificationStatus,
)

# ── Incident ──────────────────────────────────────────────────────────────────

class IncidentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    description: Optional[str] = None
    severity: IncidentSeverity
    source_system: str = Field(..., min_length=1, max_length=128)
    source_ip: Optional[str] = None
    affected_systems: Optional[list[str]] = None
    affected_records_count: Optional[int] = Field(None, ge=0)
    external_id: Optional[str] = None
    contains_pii: bool = False
    contains_phi: bool = False
    raw_payload: Optional[dict[str, Any]] = None


class IncidentUpdate(BaseModel):
    status: Optional[IncidentStatus] = None
    affected_records_count: Optional[int] = Field(None, ge=0)
    contains_pii: Optional[bool] = None
    contains_phi: Optional[bool] = None


class TimelineEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: str
    actor: str
    description: str
    event_metadata: Optional[dict] = None
    occurred_at: datetime


class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    external_id: Optional[str]
    title: str
    description: Optional[str]
    severity: IncidentSeverity
    status: IncidentStatus
    source_system: str
    source_ip: Optional[str]
    affected_systems: Optional[list]
    affected_records_count: Optional[int]
    jurisdictions: Optional[list]
    contains_pii: bool
    contains_phi: bool
    detected_at: datetime
    contained_at: Optional[datetime]
    closed_at: Optional[datetime]
    response_time_seconds: Optional[float]
    created_at: datetime
    updated_at: datetime


class IncidentDetail(IncidentOut):
    timeline: list[TimelineEventOut] = []
    evidence_count: int = 0
    notification_count: int = 0


# ── Evidence ──────────────────────────────────────────────────────────────────

class ChainOfCustodyEntry(BaseModel):
    timestamp: datetime
    action: str
    actor: str
    details: Optional[str] = None


class EvidencePackageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    incident_id: uuid.UUID
    s3_bucket: str
    s3_key: str
    s3_version_id: Optional[str]
    sha256_hash: str
    collected_by: str
    collection_method: str
    chain_of_custody: list
    package_type: str
    size_bytes: Optional[int]
    collected_at: datetime


# ── Notifications ─────────────────────────────────────────────────────────────

class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    incident_id: uuid.UUID
    jurisdiction: Jurisdiction
    status: NotificationStatus
    deadline_at: datetime
    dispatched_at: Optional[datetime]
    acknowledged_at: Optional[datetime]
    template_version: str
    recipient_authority: str
    hours_remaining: float
    is_overdue: bool
    archive_s3_key: Optional[str]
    created_at: datetime


# ── Health ────────────────────────────────────────────────────────────────────

class HealthOut(BaseModel):
    status: str
    version: str
    env: str
    checks: dict[str, str]


# ── Pagination ────────────────────────────────────────────────────────────────

class PagedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[Any]

class PagedIncidentResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[IncidentOut]
