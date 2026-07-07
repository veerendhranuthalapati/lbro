"""Evidence vault service with chain-of-custody tracking."""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.models.evidence import Evidence, ChainOfCustody
from app.models.user import User
from app.services.s3_service import compute_sha256


class EvidenceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def upload(
        self,
        incident_id: uuid.UUID,
        filename: str,
        content_type: str,
        data: bytes,
        description: Optional[str],
        uploader: User,
        ip_address: Optional[str] = None,
    ) -> Evidence:
        sha256 = compute_sha256(data)

        # Store file binary directly in PostgreSQL — no S3 dependency.
        evidence = Evidence(
            incident_id=incident_id,
            filename=filename,
            original_filename=filename,
            content_type=content_type,
            file_size=len(data),
            s3_key=None,
            s3_bucket=None,
            sha256_hash=sha256,
            description=description,
            uploaded_by=uploader.id,
            file_data=data,
        )
        self.db.add(evidence)
        await self.db.flush()

        custody = ChainOfCustody(
            evidence_id=evidence.id,
            action="uploaded",
            performed_by=uploader.id,
            performed_by_name=uploader.full_name,
            ip_address=ip_address,
            hash_at_time=sha256,
            notes=f"Original upload: {filename}",
        )
        self.db.add(custody)
        await self.db.flush()
        return evidence

    async def get(self, evidence_id: uuid.UUID, accessor: User, ip_address: Optional[str] = None) -> Evidence:
        result = await self.db.execute(
            select(Evidence)
            .where(Evidence.id == evidence_id)
            .options(selectinload(Evidence.custody_chain))
        )
        evidence = result.scalar_one_or_none()
        if not evidence:
            raise NotFoundError("Evidence")

        # Record access in chain of custody
        custody = ChainOfCustody(
            evidence_id=evidence.id,
            action="accessed",
            performed_by=accessor.id,
            performed_by_name=accessor.full_name,
            ip_address=ip_address,
            hash_at_time=evidence.sha256_hash,
        )
        self.db.add(custody)
        await self.db.flush()
        return evidence

    async def list_for_incident(self, incident_id: uuid.UUID) -> list[Evidence]:
        result = await self.db.execute(
            select(Evidence)
            .where(Evidence.incident_id == incident_id)
            .options(selectinload(Evidence.custody_chain))
            .order_by(Evidence.created_at.desc())
        )
        return result.scalars().all()


    async def list_all(self, page: int = 1, page_size: int = 50) -> tuple[list[Evidence], int]:
        """Global evidence listing across all incidents — paginated."""
        from sqlalchemy import func
        offset = (page - 1) * page_size
        count_result = await self.db.execute(select(func.count(Evidence.id)))
        total: int = count_result.scalar_one() or 0
        result = await self.db.execute(
            select(Evidence)
            .options(selectinload(Evidence.custody_chain))
            .order_by(Evidence.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = list(result.scalars().all())
        return items, total
    def get_download_url(self, evidence: Evidence) -> str:
        """Return a direct backend download URL (served from PostgreSQL file_data)."""
        return f"/api/v1/evidence/{evidence.id}/download"

    async def get_file_data(self, evidence_id: uuid.UUID) -> bytes | None:
        """Load the deferred file_data column.

        Uses populate_existing=True so SQLAlchemy overwrites any cached
        Evidence instance (loaded earlier without file_data) in the identity map.
        """
        from sqlalchemy.orm import undefer
        result = await self.db.execute(
            select(Evidence)
            .where(Evidence.id == evidence_id)
            .options(undefer(Evidence.file_data)),
            execution_options={"populate_existing": True},
        )
        ev = result.scalar_one_or_none()
        return ev.file_data if ev else None

    async def delete(self, evidence_id: uuid.UUID, actor: User) -> None:
        result = await self.db.execute(select(Evidence).where(Evidence.id == evidence_id))
        evidence = result.scalar_one_or_none()
        if not evidence:
            raise NotFoundError("Evidence")
        if evidence.is_immutable:
            from app.core.exceptions import PermissionDeniedError
            raise PermissionDeniedError("Immutable evidence cannot be deleted")
        await self.db.delete(evidence)
        await self.db.flush()
