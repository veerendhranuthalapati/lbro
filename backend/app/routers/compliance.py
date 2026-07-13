"""Compliance router."""
from __future__ import annotations

import uuid
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Permission
from app.database import get_db
from app.dependencies import require_permission
from app.models.user import User
from app.schemas.compliance import (
    ComplianceDashboard,
    ComplianceRecordResponse,
    MarkMetRequest,
    ObligationCreate,
    ObligationUpdate,
    ObligationResponse,
    ScoreResponse,
    AssessmentResponse,
)
from app.services.compliance_service import ComplianceService

router = APIRouter(prefix="/compliance", tags=["compliance"])


# ---------------------------------------------------------------------------
# Existing incident-linked compliance endpoints (unchanged)
# ---------------------------------------------------------------------------

@router.get("/dashboard", response_model=ComplianceDashboard)
async def compliance_dashboard(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_COMPLIANCE))],
    project_id: Optional[uuid.UUID] = Query(None, description="Scope to a project"),
):
    svc = ComplianceService(db)
    data = await svc.get_dashboard(project_id=project_id)
    return ComplianceDashboard(**data)


@router.post("/records/{record_id}/mark-met", response_model=ComplianceRecordResponse)
async def mark_met(
    record_id: uuid.UUID,
    body: MarkMetRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.MANAGE_COMPLIANCE))],
    project_id: Optional[uuid.UUID] = Query(None, description="Scope to a project"),
):
    svc = ComplianceService(db)
    return await svc.mark_met(record_id, body.notes or "", project_id=project_id)


# ---------------------------------------------------------------------------
# New project-scoped obligation endpoints (DB persistence replacing localStorage)
# ---------------------------------------------------------------------------

@router.get("/obligations", response_model=List[ObligationResponse])
async def list_obligations(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_COMPLIANCE))],
    project_id: uuid.UUID = Query(..., description="Project to scope obligations to"),
    framework: Optional[str] = Query(None, description="Filter by framework, e.g. GDPR"),
):
    """Return all saved obligation states for a project."""
    svc = ComplianceService(db)
    return await svc.get_obligations(project_id=project_id, framework=framework)


@router.post("/obligations", response_model=ObligationResponse, status_code=200)
async def upsert_obligation(
    body: ObligationCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.MANAGE_COMPLIANCE))],
    project_id: uuid.UUID = Query(..., description="Project this obligation belongs to"),
):
    """Create or update an obligation (upsert by project + framework + control_id).

    Returns 200 whether it created or updated, so the frontend can use this as
    a simple upsert without needing to know whether the record already exists.
    """
    svc = ComplianceService(db)
    return await svc.upsert_obligation(project_id=project_id, data=body)


@router.patch("/obligations/{obligation_id}", response_model=ObligationResponse)
async def update_obligation(
    obligation_id: uuid.UUID,
    body: ObligationUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.MANAGE_COMPLIANCE))],
):
    """Partially update an existing obligation (status, evidence_reference, score, etc.)."""
    svc = ComplianceService(db)
    return await svc.update_obligation(obligation_id=obligation_id, data=body)


@router.get("/score", response_model=ScoreResponse)
async def get_compliance_score(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_COMPLIANCE))],
    project_id: uuid.UUID = Query(..., description="Project to compute score for"),
    framework: Optional[str] = Query(None, description="Filter by framework"),
):
    """Compute live compliance score from DB obligations."""
    svc = ComplianceService(db)
    data = await svc.get_score(project_id=project_id, framework=framework)
    return ScoreResponse(**data)


@router.post("/assess", response_model=AssessmentResponse, status_code=201)
async def create_assessment(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.MANAGE_COMPLIANCE))],
    project_id: uuid.UUID = Query(..., description="Project to assess"),
    framework: str = Query(..., description="Framework to assess, e.g. GDPR"),
    notes: Optional[str] = Query(None, description="Optional assessment notes"),
):
    """Compute current score and persist it as a point-in-time assessment snapshot."""
    svc = ComplianceService(db)
    return await svc.create_assessment(
        project_id=project_id, framework=framework, notes=notes
    )


@router.get("/assessments", response_model=List[AssessmentResponse])
async def list_assessments(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_COMPLIANCE))],
    project_id: uuid.UUID = Query(..., description="Project to list assessments for"),
    framework: Optional[str] = Query(None, description="Filter by framework"),
):
    """Return historical assessment snapshots for a project, newest first."""
    svc = ComplianceService(db)
    return await svc.get_assessments(project_id=project_id, framework=framework)
