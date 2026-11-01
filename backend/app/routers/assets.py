"""Asset data map API."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.project_access import assert_project_access
from app.core.rbac import Permission
from app.database import get_db
from app.dependencies import require_permission
from app.models.user import User
from app.schemas.assets import (
    AssetCreate,
    AssetImportRequest,
    AssetImportResult,
    AssetListResponse,
    AssetResponse,
    AssetUpdate,
    ExposureSimulationRequest,
)
from app.services.asset_service import AssetService

router = APIRouter(prefix="/assets", tags=["assets"])


def _asset_response(asset) -> AssetResponse:
    data = AssetResponse.model_validate(asset)
    return data


@router.get("", response_model=AssetListResponse)
async def list_assets(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_ASSETS))],
    project_id: uuid.UUID = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    asset_type: str | None = Query(None),
    classification: str | None = Query(None),
    jurisdiction: str | None = Query(None),
    category: str | None = Query(None),
):
    await assert_project_access(db, project_id, current_user)
    svc = AssetService(db)
    items, total = await svc.list_assets(
        project_id,
        page=page,
        page_size=page_size,
        asset_type=asset_type,
        classification=classification,
        jurisdiction=jurisdiction,
        category=category,
    )
    return AssetListResponse(
        items=[_asset_response(a) for a in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=AssetResponse, status_code=201)
async def create_asset(
    body: AssetCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.MANAGE_ASSETS))],
    project_id: uuid.UUID = Query(...),
):
    await assert_project_access(db, project_id, current_user)
    svc = AssetService(db)
    asset = await svc.create(project_id, body, current_user)
    return _asset_response(asset)


@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(
    asset_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_ASSETS))],
    project_id: uuid.UUID = Query(...),
):
    await assert_project_access(db, project_id, current_user)
    svc = AssetService(db)
    return _asset_response(await svc.get(project_id, asset_id))


@router.patch("/{asset_id}", response_model=AssetResponse)
async def update_asset(
    asset_id: uuid.UUID,
    body: AssetUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.MANAGE_ASSETS))],
    project_id: uuid.UUID = Query(...),
):
    await assert_project_access(db, project_id, current_user)
    svc = AssetService(db)
    return _asset_response(await svc.update(project_id, asset_id, body, current_user))


@router.delete("/{asset_id}", status_code=204)
async def delete_asset(
    asset_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.MANAGE_ASSETS))],
    project_id: uuid.UUID = Query(...),
):
    await assert_project_access(db, project_id, current_user)
    svc = AssetService(db)
    await svc.delete(project_id, asset_id, current_user)


@router.post("/import", response_model=AssetImportResult)
async def import_assets(
    body: AssetImportRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.MANAGE_ASSETS))],
    project_id: uuid.UUID = Query(...),
):
    await assert_project_access(db, project_id, current_user)
    svc = AssetService(db)
    return await svc.import_assets(project_id, body, current_user)


@router.get("/export/csv")
async def export_assets_csv(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_ASSETS))],
    project_id: uuid.UUID = Query(...),
):
    await assert_project_access(db, project_id, current_user)
    svc = AssetService(db)
    items, _ = await svc.list_assets(project_id, page=1, page_size=10000, active_only=False)
    csv_text = svc.export_csv(items)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="assets-export.csv"'},
    )


@router.post("/{asset_id}/exposure-simulation")
async def exposure_simulation(
    asset_id: uuid.UUID,
    body: ExposureSimulationRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_ASSETS))],
    project_id: uuid.UUID = Query(...),
):
    await assert_project_access(db, project_id, current_user)
    svc = AssetService(db)
    return await svc.simulate_exposure(
        project_id, asset_id, body.attack_category, body.confidence
    )
