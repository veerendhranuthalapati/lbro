"""Asset inventory CRUD, import/export."""
from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import UTC
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictError, NotFoundError
from app.models.asset import Asset, AssetResidency
from app.models.user import User
from app.schemas.assets import (
    AssetCreate,
    AssetImportRequest,
    AssetImportResult,
    AssetImportRowError,
    AssetUpdate,
)
from app.services.audit_helper import write_audit


def _csv_escape_cell(value: str) -> str:
    """Mitigate CSV formula injection when exporting."""
    if value and value[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


class AssetService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_assets(
        self,
        project_id: uuid.UUID,
        *,
        page: int = 1,
        page_size: int = 50,
        asset_type: str | None = None,
        classification: str | None = None,
        jurisdiction: str | None = None,
        category: str | None = None,
        active_only: bool = True,
    ) -> tuple[list[Asset], int]:
        q = select(Asset).where(Asset.project_id == project_id).options(selectinload(Asset.residency))
        if active_only:
            q = q.where(Asset.is_active == True)
        if asset_type:
            q = q.where(Asset.asset_type == asset_type)
        if classification:
            q = q.where(Asset.classification == classification)
        if jurisdiction:
            q = q.join(AssetResidency).where(AssetResidency.jurisdiction_code == jurisdiction)
        # category filter applied in Python after fetch when JSON contains is unsupported

        count_q = select(func.count()).select_from(q.subquery())
        total = (await self.db.execute(count_q)).scalar_one()
        q = q.order_by(Asset.name).offset((page - 1) * page_size).limit(page_size)
        items = (await self.db.execute(q)).scalars().unique().all()
        if category:
            items = [a for a in items if category in (a.data_categories or [])]
            total = len(items)
            items = items[(page - 1) * page_size : page * page_size]
        return list(items), total

    async def get(self, project_id: uuid.UUID, asset_id: uuid.UUID) -> Asset:
        q = (
            select(Asset)
            .where(Asset.id == asset_id, Asset.project_id == project_id)
            .options(selectinload(Asset.residency))
        )
        asset = (await self.db.execute(q)).scalar_one_or_none()
        if not asset:
            raise NotFoundError("Asset")
        return asset

    async def create(
        self, project_id: uuid.UUID, data: AssetCreate, user: User
    ) -> Asset:
        existing = (
            await self.db.execute(
                select(Asset.id).where(Asset.project_id == project_id, Asset.name == data.name)
            )
        ).scalar_one_or_none()
        if existing:
            raise ConflictError(f"Asset name {data.name!r} already exists in project")
        asset = Asset(
            project_id=project_id,
            name=data.name,
            asset_type=data.asset_type,
            environment=data.environment,
            owner=data.owner,
            description=data.description,
            classification=data.classification,
            criticality=data.criticality,
            data_categories=list(data.data_categories),
            encrypted_at_rest=data.encrypted_at_rest,
            identifiers=list(data.identifiers),
            is_active=data.is_active,
            created_by=user.id,
        )
        self.db.add(asset)
        await self.db.flush()
        for row in data.residency:
            self.db.add(
                AssetResidency(
                    asset_id=asset.id,
                    jurisdiction_code=row.jurisdiction_code,
                    record_count=row.record_count,
                    count_basis=row.count_basis,
                    as_of=row.as_of,
                    data_category=row.data_category,
                    notes=row.notes,
                )
            )
        await write_audit(
            self.db,
            user=user,
            project_id=project_id,
            action="asset.created",
            resource_type="asset",
            resource_id=str(asset.id),
            details={"name": asset.name},
        )
        await self.db.flush()
        await self.db.refresh(asset, ["residency"])
        return asset

    async def update(
        self, project_id: uuid.UUID, asset_id: uuid.UUID, data: AssetUpdate, user: User
    ) -> Asset:
        asset = await self.get(project_id, asset_id)
        old = {"name": asset.name, "is_active": asset.is_active}
        for field in (
            "name",
            "asset_type",
            "environment",
            "owner",
            "description",
            "classification",
            "criticality",
            "encrypted_at_rest",
            "is_active",
        ):
            val = getattr(data, field)
            if val is not None:
                setattr(asset, field, val)
        if data.data_categories is not None:
            asset.data_categories = list(data.data_categories)
        if data.identifiers is not None:
            asset.identifiers = list(data.identifiers)
        if data.residency is not None:
            for r in list(asset.residency):
                await self.db.delete(r)
            await self.db.flush()
            for row in data.residency:
                self.db.add(
                    AssetResidency(
                        asset_id=asset.id,
                        jurisdiction_code=row.jurisdiction_code,
                        record_count=row.record_count,
                        count_basis=row.count_basis,
                        as_of=row.as_of,
                        data_category=row.data_category,
                        notes=row.notes,
                    )
                )
        await write_audit(
            self.db,
            user=user,
            project_id=project_id,
            action="asset.updated",
            resource_type="asset",
            resource_id=str(asset.id),
            details={"old": old, "new": {"name": asset.name, "is_active": asset.is_active}},
        )
        await self.db.flush()
        return await self.get(project_id, asset_id)

    async def delete(self, project_id: uuid.UUID, asset_id: uuid.UUID, user: User) -> None:
        asset = await self.get(project_id, asset_id)
        asset.is_active = False
        await write_audit(
            self.db,
            user=user,
            project_id=project_id,
            action="asset.deactivated",
            resource_type="asset",
            resource_id=str(asset.id),
            details={},
        )
        await self.db.flush()

    async def import_assets(
        self, project_id: uuid.UUID, body: AssetImportRequest, user: User
    ) -> AssetImportResult:
        errors: list[AssetImportRowError] = []
        valid: list[AssetCreate] = []
        for idx, row in enumerate(body.rows):
            try:
                AssetCreate.model_validate(row.model_dump() if hasattr(row, "model_dump") else row)
                valid.append(row)
            except Exception as exc:
                errors.append(AssetImportRowError(row=idx, error=str(exc)))
        if body.dry_run or errors:
            return AssetImportResult(
                dry_run=body.dry_run,
                valid_count=len(valid),
                errors=errors,
                imported=0,
            )
        imported = 0
        for row in valid:
            await self.create(project_id, row, user)
            imported += 1
        return AssetImportResult(
            dry_run=False, valid_count=len(valid), errors=[], imported=imported
        )

    def export_csv(self, assets: list[Asset]) -> str:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "name",
                "asset_type",
                "classification",
                "data_categories",
                "jurisdiction_code",
                "record_count",
            ]
        )
        for a in assets:
            cats = json.dumps(a.data_categories or [])
            if not a.residency:
                writer.writerow(
                    [
                        _csv_escape_cell(a.name),
                        a.asset_type,
                        a.classification,
                        _csv_escape_cell(cats),
                        "",
                        "",
                    ]
                )
            else:
                for r in a.residency:
                    writer.writerow(
                        [
                            _csv_escape_cell(a.name),
                            a.asset_type,
                            a.classification,
                            _csv_escape_cell(cats),
                            r.jurisdiction_code,
                            r.record_count if r.record_count is not None else "",
                        ]
                    )
        return buf.getvalue()

    async def simulate_exposure(
        self, project_id: uuid.UUID, asset_id: uuid.UUID, attack_category: str, confidence: float
    ) -> dict[str, Any]:
        from datetime import datetime

        from app.compliance.engine.pipeline import run_exposure_assessment
        from app.compliance.engine.serialize import assessment_result_to_dict
        from app.compliance.engine.types import (
            AssetInput,
            ClassificationInput,
            EngineConfigInput,
            IncidentContextInput,
            ResidencyInput,
        )
        from app.config import settings

        asset = await self.get(project_id, asset_id)
        residency = tuple(
            ResidencyInput(r.jurisdiction_code, r.record_count, r.count_basis, r.data_category)
            for r in asset.residency
        )
        assets = (
            AssetInput(
                str(asset.id),
                asset.name,
                tuple(asset.data_categories or []),
                residency,
                "confirmed",
                "high",
                1.0,
            ),
        )
        result = run_exposure_assessment(
            ClassificationInput(attack_category, confidence, "model", False, False),
            IncidentContextInput(datetime.now(UTC), None, (), True, False),
            assets,
            EngineConfigInput("inferred", settings.ML_REVIEW_THRESHOLD),
        )
        return assessment_result_to_dict(result)
