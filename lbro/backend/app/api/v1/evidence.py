"""
LBRO — Evidence API router

Endpoints:
  GET /api/v1/incidents/{id}/evidence                     — list packages
  GET /api/v1/incidents/{id}/evidence/{eid}/download      — presigned S3 URL

Rate limits:
  list     — 60/minute  supports automated tooling
  download — 10/minute  presigned URL generation hits S3; one analyst rarely needs >10/min
"""
import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.aws_clients import get_s3
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.core.security import RequireAPIKey
from app.models.incident import EvidencePackage
from app.schemas.incident import EvidencePackageOut

log = structlog.get_logger(__name__)
router = APIRouter(dependencies=[RequireAPIKey])


@router.get(
    "/incidents/{incident_id}/evidence",
    response_model=list[EvidencePackageOut],
    summary="List evidence packages for an incident",
)
@limiter.limit("60/minute")
async def list_evidence(
    request: Request,
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    result = await db.execute(
        select(EvidencePackage)
        .where(EvidencePackage.incident_id == incident_id)
        .order_by(EvidencePackage.collected_at)
    )
    return result.scalars().all()


@router.get(
    "/incidents/{incident_id}/evidence/{evidence_id}/download",
    summary="Get a presigned S3 download URL (expires in 15 minutes)",
)
@limiter.limit("10/minute")
async def download_evidence(
    request: Request,
    incident_id: uuid.UUID,
    evidence_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    result = await db.execute(
        select(EvidencePackage).where(
            EvidencePackage.id == evidence_id,
            EvidencePackage.incident_id == incident_id,
        )
    )
    pkg = result.scalar_one_or_none()
    if not pkg:
        raise HTTPException(status_code=404, detail="Evidence package not found")

    try:
        url = get_s3().generate_presigned_url(
            "get_object",
            Params={"Bucket": pkg.s3_bucket, "Key": pkg.s3_key},
            ExpiresIn=900,
        )
    except Exception as e:
        log.error("evidence.presign_failed", evidence_id=str(evidence_id), error=str(e))
        raise HTTPException(
            status_code=500, detail="Could not generate download URL"
        ) from e

    return {
        "url": url,
        "expires_in_seconds": 900,
        "sha256": pkg.sha256_hash,
        "package_type": pkg.package_type,
    }
