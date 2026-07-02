"""Regulatory notifications router."""
from __future__ import annotations

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Permission
from app.database import get_db
from app.dependencies import get_current_active_user, require_permission
from app.models.user import User
from app.schemas.notification import NotificationListResponse, NotificationResponse
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.READ_NOTIFICATION))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    regulation: Optional[str] = None,
    incident_id: Optional[uuid.UUID] = None,
):
    svc = NotificationService(db)
    items, total = await svc.list(page, page_size, status, regulation, incident_id)
    return NotificationListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(
    notification_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.READ_NOTIFICATION))],
):
    svc = NotificationService(db)
    return await svc.get(notification_id)


@router.post("/{notification_id}/approve", response_model=NotificationResponse)
async def approve_notification(
    notification_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.APPROVE_NOTIFICATION))],
):
    svc = NotificationService(db)
    return await svc.approve(notification_id, current_user)


@router.post("/{notification_id}/dispatch", response_model=NotificationResponse)
async def dispatch_notification(
    notification_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.DISPATCH_NOTIFICATION))],
):
    """Alias for /send — used by frontend."""
    svc = NotificationService(db)
    # Auto-approve and send
    n = await svc.get(notification_id)
    if n.status == "pending":
        await svc.approve(notification_id, current_user)
    return await svc.send(notification_id)


@router.post("/{notification_id}/send", response_model=NotificationResponse)
async def send_notification(
    notification_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.DISPATCH_NOTIFICATION))],
):
    svc = NotificationService(db)
    return await svc.send(notification_id)
