"""Evidence vault router."""
from __future__ import annotations

import os
import re
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
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
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_UPLOAD_SIZE:
        raise HTTPException(413, "File exceeds 100 MB limit")

    data = await file.read()
    if len(data) > MAX_UPLOAD_SIZE:
        raise HTTPException(413, "File exceeds 100 MB limit")

    raw_name = file.filename or "unknown"
    safe_name = os.path.basename(raw_name.replace("\\", "/"))  # handle Windows-style paths
    safe_name = re.sub(r'[^\w.\-]', '_', safe_name)
    safe_name = safe_name[:255] if safe_name else "evidence_file"

    allowed_types = {
        "application/octet-stream", "text/plain", "application/json",
        "application/zip", "application/x-tar", "application/gzip",
        "image/png", "image/jpeg", "application/pdf",
        "text/csv", "application/vnd.tcpdump.pcap",
    }
    declared_type = file.content_type or "application/octet-stream"
    if declared_type not in allowed_types:
        raise HTTPException(400, f"Content type '{declared_type}' not allowed")

    DANGEROUS_SIGNATURES = [
        b'\x4d\x5a',
        b'\x7fELF',
        b'#!/',
        b'<script',
        b'<?php',
    ]
    for sig in DANGEROUS_SIGNATURES:
        if data[:len(sig)].lower() == sig.lower():
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
    result = []
    for ev in items:
        # Explicitly convert custody_chain ORM objects to dicts so Pydantic
        # never receives a raw SQLAlchemy relationship proxy.
        coc = [
            {
                "id": c.id,
                "action": c.action,
                "performed_by_name": c.performed_by_name,
                "ip_address": c.ip_address,
                "notes": c.notes,
                "hash_at_time": c.hash_at_time,
                "created_at": c.created_at,
            }
            for c in (ev.custody_chain or [])
        ]
        try:
            download_url = svc.get_download_url(ev)
        except Exception:
            download_url = None
        result.append({
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
            "custody_chain": coc,
            "download_url": download_url,
        })
    return EvidenceListResponse(items=result, total=len(result))


@router.get("/evidence", tags=["evidence"])
async def list_all_evidence(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.DOWNLOAD_EVIDENCE))],
    page: int = 1,
    page_size: int = 50,
    project_id: uuid.UUID | None = None,
):
    """Global paginated evidence listing across all incidents, optionally scoped to a project."""
    svc = EvidenceService(db)
    items, total = await svc.list_all(page, page_size, project_id=project_id)
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


@router.get("/evidence/{evidence_id}/download")
async def download_evidence(
    evidence_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.DOWNLOAD_EVIDENCE))],
    project_id: uuid.UUID | None = None,
):
    """Serve evidence file bytes directly from PostgreSQL storage.

    If project_id is provided, the evidence must belong to an incident in that project;
    otherwise 404 is returned, closing the IDOR gap on cross-project downloads.
    """
    ip = request.client.host if request.client else None
    svc = EvidenceService(db)
    ev = await svc.get(evidence_id, current_user, ip, project_id=project_id)
    file_data = await svc.get_file_data(evidence_id)

    if not file_data:
        raise HTTPException(404, "File data not available")

    # Use plain Response — all bytes are already in memory.
    # StreamingResponse + io.BytesIO iterates line-by-line and can corrupt binary.
    return Response(
        content=file_data,
        media_type=ev.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{ev.original_filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/evidence/{evidence_id}/verify")
async def verify_integrity(
    evidence_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.DOWNLOAD_EVIDENCE))],
):
    """Verify evidence SHA-256 hash against stored file_data."""
    from app.services.s3_service import compute_sha256
    ip = request.client.host if request.client else None
    svc = EvidenceService(db)
    ev = await svc.get(evidence_id, current_user, ip)
    file_data = await svc.get_file_data(evidence_id)
    if file_data is None:
        return {"ok": False, "hash": ev.sha256_hash, "error": "file_data not stored in database"}
    actual_hash = compute_sha256(file_data)
    ok = actual_hash == ev.sha256_hash
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
