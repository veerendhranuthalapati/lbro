"""Compliance router."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Permission
from app.database import get_db
from app.dependencies import require_permission
from app.models.user import User
from app.schemas.compliance import ComplianceDashboard, ComplianceRecordResponse, MarkMetRequest
from app.services.compliance_service import ComplianceService

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.get("/dashboard", response_model=ComplianceDashboard)
async def compliance_dashboard(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_COMPLIANCE))],
):
    svc = ComplianceService(db)
    data = await svc.get_dashboard()
    return ComplianceDashboard(**data)


@router.post("/records/{record_id}/mark-met", response_model=ComplianceRecordResponse)
async def mark_met(
    record_id: uuid.UUID,
    body: MarkMetRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.MANAGE_COMPLIANCE))],
):
    svc = ComplianceService(db)
    return await svc.mark_met(record_id, body.notes or "")
