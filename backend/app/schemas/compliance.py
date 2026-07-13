"""Compliance schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Existing incident-linked compliance record schemas (unchanged)
# ---------------------------------------------------------------------------

class ComplianceRecordResponse(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    regulation: str
    jurisdiction: str
    obligation: str
    deadline: datetime
    is_met: bool
    met_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ComplianceSummary(BaseModel):
    regulation: str
    total: int
    met: int
    overdue: int
    pending: int


class ComplianceDashboard(BaseModel):
    summaries: List[ComplianceSummary]
    overdue_records: List[ComplianceRecordResponse]
    upcoming_deadlines: List[ComplianceRecordResponse]


class MarkMetRequest(BaseModel):
    notes: Optional[str] = Field(None, max_length=2000)


# ---------------------------------------------------------------------------
# New project-scoped obligation schemas
# ---------------------------------------------------------------------------

class ObligationCreate(BaseModel):
    """Body for POST /compliance/obligations (upsert by project+framework+control_id)."""
    framework: str = Field(..., max_length=50, description="e.g. GDPR, HIPAA, DPDPA")
    control_id: str = Field(..., max_length=100, description="Short ID used in the UI, e.g. g1, h2")
    control_name: str = Field(..., max_length=255)
    description: Optional[str] = None
    status: str = Field("not_started", max_length=50)
    evidence_reference: Optional[str] = None
    recommendations: Optional[str] = None


class ObligationUpdate(BaseModel):
    """Body for PATCH /compliance/obligations/{id}."""
    status: Optional[str] = Field(None, max_length=50)
    evidence_reference: Optional[str] = None
    recommendations: Optional[str] = None
    score: Optional[float] = None


class ObligationResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    framework: str
    control_id: str
    control_name: str
    description: Optional[str]
    status: str
    evidence_reference: Optional[str]
    score: float
    recommendations: Optional[str]
    last_updated: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class ScoreResponse(BaseModel):
    project_id: uuid.UUID
    framework: Optional[str]
    overall_score: float
    total_controls: int
    compliant_controls: int
    non_compliant_controls: int
    in_progress_controls: int


class AssessmentResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    framework: str
    overall_score: float
    total_controls: int
    compliant_controls: int
    assessment_date: Optional[datetime]
    notes: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
