"""Incident exposure and obligation inference endpoints."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.core.project_access import assert_project_access, incident_access_scope
from app.core.rbac import Permission
from app.database import get_db
from app.dependencies import require_permission
from app.models.asset import Asset, IncidentAsset
from app.models.compliance import ComplianceRecord
from app.models.incident import Incident
from app.models.user import User
from app.schemas.assets import (
    ExposureAssessmentResponse,
    IncidentAssetLinkRequest,
    IncidentAssetResponse,
    IncidentAssetUpdateRequest,
    ObligationDecisionRequest,
)
from app.schemas.compliance import ComplianceRecordResponse
from app.services.audit_helper import write_audit
from app.services.exposure_service import ExposureService, enqueue_exposure_recompute

router = APIRouter(tags=["exposure"])


async def _incident_in_scope(
    db: AsyncSession, incident_id: uuid.UUID, user: User
) -> Incident:
    scope = incident_access_scope(user)
    q = select(Incident).where(Incident.id == incident_id)
    if scope is not None:
        q = q.where(scope)
    incident = (await db.execute(q)).scalar_one_or_none()
    if not incident:
        raise NotFoundError("Incident")
    if incident.project_id:
        await assert_project_access(db, incident.project_id, user)
    return incident


@router.get("/incidents/{incident_id}/assets", response_model=list[IncidentAssetResponse])
async def list_incident_assets(
    incident_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_ASSETS))],
):
    incident = await _incident_in_scope(db, incident_id, current_user)
    q = (
        select(IncidentAsset)
        .where(IncidentAsset.incident_id == incident.id)
        .options(selectinload(IncidentAsset.asset))
    )
    links = (await db.execute(q)).scalars().all()
    return [
        IncidentAssetResponse(
            id=link.id,
            incident_id=link.incident_id,
            asset_id=link.asset_id,
            asset_name=link.asset.name,
            link_source=link.link_source,
            match_reason=link.match_reason,
            match_confidence=link.match_confidence,
            exposure_fraction=link.exposure_fraction,
            status=link.status,
            confirmed_at=link.confirmed_at,
        )
        for link in links
    ]


@router.post("/incidents/{incident_id}/assets", response_model=IncidentAssetResponse, status_code=201)
async def link_incident_asset(
    incident_id: uuid.UUID,
    body: IncidentAssetLinkRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.MANAGE_ASSETS))],
):
    incident = await _incident_in_scope(db, incident_id, current_user)
    if not incident.project_id:
        raise HTTPException(400, "Incident has no project")
    asset = (
        await db.execute(
            select(Asset).where(
                Asset.id == body.asset_id, Asset.project_id == incident.project_id
            )
        )
    ).scalar_one_or_none()
    if not asset:
        raise NotFoundError("Asset")
    link = IncidentAsset(
        incident_id=incident.id,
        asset_id=asset.id,
        link_source="manual",
        match_confidence="high",
        exposure_fraction=body.exposure_fraction,
        status="confirmed",
        confirmed_by=current_user.id,
        confirmed_at=datetime.now(UTC),
    )
    db.add(link)
    await write_audit(
        db,
        user=current_user,
        project_id=incident.project_id,
        action="incident_asset.linked",
        resource_type="incident",
        resource_id=str(incident.id),
        details={"asset_id": str(asset.id)},
    )
    await db.flush()
    enqueue_exposure_recompute(incident.id)
    return IncidentAssetResponse(
        id=link.id,
        incident_id=link.incident_id,
        asset_id=link.asset_id,
        asset_name=asset.name,
        link_source=link.link_source,
        match_reason=link.match_reason,
        match_confidence=link.match_confidence,
        exposure_fraction=link.exposure_fraction,
        status=link.status,
        confirmed_at=link.confirmed_at,
    )


@router.patch("/incidents/{incident_id}/assets/{link_id}", response_model=IncidentAssetResponse)
async def update_incident_asset(
    incident_id: uuid.UUID,
    link_id: uuid.UUID,
    body: IncidentAssetUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.CONFIRM_EXPOSURE))],
):
    incident = await _incident_in_scope(db, incident_id, current_user)
    link = (
        await db.execute(
            select(IncidentAsset)
            .where(IncidentAsset.id == link_id, IncidentAsset.incident_id == incident.id)
            .options(selectinload(IncidentAsset.asset))
        )
    ).scalar_one_or_none()
    if not link:
        raise NotFoundError("IncidentAsset")
    if body.exposure_fraction is not None:
        link.exposure_fraction = body.exposure_fraction
    if body.status is not None:
        link.status = body.status
        if body.status == "confirmed":
            link.confirmed_by = current_user.id
            link.confirmed_at = datetime.now(UTC)
    await write_audit(
        db,
        user=current_user,
        project_id=incident.project_id,
        action="incident_asset.updated",
        resource_type="incident",
        resource_id=str(incident.id),
        details={"link_id": str(link_id), "status": link.status},
    )
    await db.flush()
    enqueue_exposure_recompute(incident.id)
    return IncidentAssetResponse(
        id=link.id,
        incident_id=link.incident_id,
        asset_id=link.asset_id,
        asset_name=link.asset.name,
        link_source=link.link_source,
        match_reason=link.match_reason,
        match_confidence=link.match_confidence,
        exposure_fraction=link.exposure_fraction,
        status=link.status,
        confirmed_at=link.confirmed_at,
    )


@router.delete("/incidents/{incident_id}/assets/{link_id}", status_code=204)
async def unlink_incident_asset(
    incident_id: uuid.UUID,
    link_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.MANAGE_ASSETS))],
):
    incident = await _incident_in_scope(db, incident_id, current_user)
    link = (
        await db.execute(
            select(IncidentAsset).where(
                IncidentAsset.id == link_id, IncidentAsset.incident_id == incident.id
            )
        )
    ).scalar_one_or_none()
    if not link:
        raise NotFoundError("IncidentAsset")
    await db.delete(link)
    enqueue_exposure_recompute(incident.id)


@router.get("/incidents/{incident_id}/exposure", response_model=ExposureAssessmentResponse)
async def get_exposure(
    incident_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_ASSETS))],
):
    await _incident_in_scope(db, incident_id, current_user)
    svc = ExposureService(db)
    assessment = await svc.get_latest_assessment(incident_id)
    if not assessment:
        raise NotFoundError("ExposureAssessment")
    return ExposureAssessmentResponse.model_validate(assessment)


@router.post("/incidents/{incident_id}/exposure", response_model=ExposureAssessmentResponse)
async def recompute_exposure(
    incident_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.CONFIRM_EXPOSURE))],
):
    await _incident_in_scope(db, incident_id, current_user)
    svc = ExposureService(db)
    incident = await svc.get_incident_for_exposure(incident_id)
    await svc.auto_match_assets(incident)
    assessment = await svc.recompute(incident_id, actor=current_user)
    return ExposureAssessmentResponse.model_validate(assessment)


@router.get("/incidents/{incident_id}/obligations", response_model=list[ComplianceRecordResponse])
async def list_obligations(
    incident_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_COMPLIANCE))],
):
    await _incident_in_scope(db, incident_id, current_user)
    rows = (
        await db.execute(
            select(ComplianceRecord)
            .where(ComplianceRecord.incident_id == incident_id)
            .order_by(ComplianceRecord.created_at.desc())
        )
    ).scalars().all()
    return [ComplianceRecordResponse.model_validate(r) for r in rows]


@router.post(
    "/incidents/{incident_id}/obligations/{record_id}/accept",
    response_model=ComplianceRecordResponse,
)
async def accept_obligation(
    incident_id: uuid.UUID,
    record_id: uuid.UUID,
    body: ObligationDecisionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.CONFIRM_EXPOSURE))],
):
    await _incident_in_scope(db, incident_id, current_user)
    svc = ExposureService(db)
    record = await svc.accept_obligation(record_id, current_user, body.reason)
    return ComplianceRecordResponse.model_validate(record)


@router.post(
    "/incidents/{incident_id}/obligations/{record_id}/dismiss",
    response_model=ComplianceRecordResponse,
)
async def dismiss_obligation(
    incident_id: uuid.UUID,
    record_id: uuid.UUID,
    body: ObligationDecisionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.CONFIRM_EXPOSURE))],
):
    await _incident_in_scope(db, incident_id, current_user)
    if not body.reason:
        raise HTTPException(400, "reason is required to dismiss")
    svc = ExposureService(db)
    record = await svc.dismiss_obligation(record_id, current_user, body.reason)
    return ComplianceRecordResponse.model_validate(record)
