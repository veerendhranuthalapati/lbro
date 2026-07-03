"""Evidence vault router."""
from __future__ import annotations

import os
import re
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Permission
from app.database import get_db
from app.dependencies import require_permission
from app.models.user import User
from app.schemas.evidence import EvidenceListResponse, EvidenceResponse, EvidenceUploadResponse
from app.services.evidence_service import EvidenceService

router = APIRouter(tags=["evidence"])

MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100 MB


@router.post("/incidents/{incident_id}/evidence", response_model=EvidenceUploadResponse, status_code=201)
async def upload_evidence(
    incident_id: uuid.UUID,
    request: Request,
    file: Annotated[UploadFile, File(...)],
    description: Annotated[str | None, Form(max_length=2000)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    current_user: Annotated[User, Depends(require_permission(Permission.UPLOAD_EVIDENCE))] = None,
):
    data = await file.read()
    if len(data) > MAX_UPLOAD_SIZE:
        from fastapi import HTTPException
        raise HTTPException(400, "File exceeds 100 MB limit")

    # Sanitize filename: strip path components, collapse whitespace, block null bytes
    raw_name = file.filename or "unknown"
    safe_name = os.path.basename(raw_name)                          # strip path traversal
    safe_name = re.sub(r'[^\w.\-]', '_', safe_name)                 # allow only word chars, dots, dashes
    safe_name = safe_name[:255] if safe_name else "evidence_file"  # cap length

    # Validate content type against allowlist (client-supplied but used only for storage metadata)
    allowed_types = {
        "application/octet-stream", "text/plain", "application/json",
        "application/zip", "application/x-tar", "application/gzip",
        "image/png", "image/jpeg", "application/pdf",
        "text/csv", "application/vnd.tcpdump.pcap",
    }
    declared_type = file.content_type or "application/octet-stream"
    if declared_type not in allowed_types:
        from fastapi import HTTPException
        raise HTTPException(400, f"Content type '{declared_type}' not allowed")

    # Magic-byte sniff to catch disguised executables
    DANGEROUS_SIGNATURES = [
        b'\x4d\x5a',           # PE/EXE (MZ header)
        b'\x7fELF',            # ELF Linux executable
        b'#!/',                # Shell shebang
        b'<script',            # HTML/JS injection
        b'<?php',              # PHP script
    ]
    for sig in DANGEROUS_SIGNATURES:
        if data[:len(sig)].lower() == sig.lower():
            from fastapi import HTTPException
            raise HTTPException(400, "File type rejected by content inspection")

    ip = request.client.host if request.client else None
    svc = EvidenceService(db)
    evidence = await svc.upload(
        incident_id=incident_id,
        filename=safe_name,
        content_type=declared_type,
        data=data,
        description=description,
        uploader=current_user,
        ip_address=ip,
    )
    return EvidenceUploadResponse(
        id=evidence.id,
        filename=evidence.filename,
        sha256_hash=evidence.sha256_hash,
        file_size=evidence.file_size,
        created_at=evidence.created_at,
    )


@router.get("/incidents/{incident_id}/evidence", response_model=EvidenceListResponse)
async def list_evidence(
    incident_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.DOWNLOAD_EVIDENCE))],
):
    svc = EvidenceService(db)
    items = await svc.list_for_incident(incident_id)
    # Attach presigned URLs
    result = []
    for ev in items:
        ev_dict = {
            "id": ev.id,
            "incident_id": ev.incident_id,
            "filename": ev.filename,
            "original_filename": ev.original_filename,
            "content_type": ev.content_type,
            "file_size": ev.file_size,
            "sha256_hash": ev.sha256_hash,
            "description": ev.description,
            "tags": ev.tags,
            "is_immutable": ev.is_immutable,
            "uploaded_by": ev.uploaded_by,
            "created_at": ev.created_at,
            "custody_chain": ev.custody_chain,
        }
        try:
            ev_dict["download_url"] = svc.get_download_url(ev)
        except Exception:
            ev_dict["download_url"] = None
        result.append(ev_dict)
    return EvidenceListResponse(items=result, total=len(result))



@router.get("/evidence", tags=["evidence"])
async def list_all_evidence(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.DOWNLOAD_EVIDENCE))],
    page: int = 1,
    page_size: int = 50,
):
    """Global paginated evidence listing across all incidents. Required by EvidencePage."""
    svc = EvidenceService(db)
    items, total = await svc.list_all(page, page_size)
    result = []
    for ev in items:
        try:
            download_url = svc.get_download_url(ev)
        except Exception:
            download_url = None
        coc = [
            {
                "id": str(c.id),
                "action": c.action,
                "performed_by_name": getattr(c, "performed_by_name", "system"),
                "ip_address": getattr(c, "ip_address", None),
                "notes": getattr(c, "notes", None),
                "hash_at_time": getattr(c, "hash_at_time", None),
                "created_at": c.created_at.isoformat(),
            }
            for c in (ev.custody_chain or [])
        ]
        result.append({
            "id": str(ev.id),
            "incident_id": str(ev.incident_id),
            "filename": ev.filename,
            "original_filename": ev.original_filename,
            "content_type": ev.content_type,
            "file_size": ev.file_size,
            "sha256_hash": ev.sha256_hash,
            "description": ev.description,
            "tags": ev.tags,
            "is_immutable": ev.is_immutable,
            "uploaded_by": str(ev.uploaded_by) if ev.uploaded_by else None,
            "created_at": ev.created_at.isoformat(),
            "custody_chain": coc,
            "download_url": download_url,
        })
    return {"items": result, "total": total, "page": page, "page_size": page_size}


@router.get("/evidence/{evidence_id}/download-url")
async def get_download_url(
    evidence_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.DOWNLOAD_EVIDENCE))],
):
    ip = request.client.host if request.client else None
    svc = EvidenceService(db)
    ev = await svc.get(evidence_id, current_user, ip)
    try:
        url = svc.get_download_url(ev)
        expires_at = None
    except Exception:
        url = None
        expires_at = None
    return {"url": url, "expires_at": expires_at}


@router.post("/evidence/{evidence_id}/verify")
async def verify_integrity(
    evidence_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.DOWNLOAD_EVIDENCE))],
):
    """Verify evidence SHA-256 hash against S3 object."""
    from app.services.s3_service import s3_service, compute_sha256
    ip = request.client.host if request.client else None
    svc = EvidenceService(db)
    ev = await svc.get(evidence_id, current_user, ip)
    try:
        obj = s3_service.client.get_object(Bucket=ev.s3_bucket, Key=ev.s3_key)
        data = obj["Body"].read()
        actual_hash = compute_sha256(data)
        ok = actual_hash == ev.sha256_hash
    except Exception:
        ok = False
        actual_hash = ev.sha256_hash
    return {"ok": ok, "hash": actual_hash}


@router.get("/evidence/{evidence_id}", response_model=EvidenceResponse)
async def get_evidence_by_id(
    evidence_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.DOWNLOAD_EVIDENCE))],
):
    ip = request.client.host if request.client else None
    svc = EvidenceService(db)
    ev = await svc.get(evidence_id, current_user, ip)
    try:
        download_url = svc.get_download_url(ev)
    except Exception:
        download_url = None
    return {**ev.__dict__, "download_url": download_url}


@router.delete("/evidence/{evidence_id}", status_code=204)
async def delete_evidence(
    evidence_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.DELETE_EVIDENCE))],
):
    svc = EvidenceService(db)
    await svc.delete(evidence_id, current_user)
