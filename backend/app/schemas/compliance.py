"""Compliance schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


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
