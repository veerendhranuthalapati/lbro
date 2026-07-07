"""Users management router."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Permission
from app.database import get_db
from app.dependencies import require_permission
from app.models.user import User
from app.schemas.user import UserCreate, UserListResponse, UserResponse, UserUpdate
from app.services.auth_service import AuthService
from app.schemas.auth import RegisterRequest

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=UserListResponse)
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.MANAGE_USERS))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    total = (await db.execute(select(func.count(User.id)))).scalar_one()
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    users = result.scalars().all()
    return UserListResponse(items=users, total=total, page=page, page_size=page_size)


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    data: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.MANAGE_USERS))],
):
    svc = AuthService(db)
    req = RegisterRequest(
        email=data.email,
        username=data.username,
        full_name=data.full_name,
        password=data.password,
    )
    user = await svc.register(req)
    user.role = data.role
    await db.flush()
    return user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.MANAGE_USERS))],
):
    from app.core.exceptions import NotFoundError
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User")
    return user


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    data: UserUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.MANAGE_USERS))],
):
    from app.core.exceptions import NotFoundError
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User")
    changes = data.model_dump(exclude_none=True)
    old_role = user.role if "role" in changes else None
    for field, value in changes.items():
        setattr(user, field, value)
    await db.flush()

    # Audit role changes — privilege escalation must be traceable
    if old_role is not None and old_role != user.role:
        from app.models.audit import AuditLog
        db.add(AuditLog(
            user_id=current_user.id,
            action="user.role_changed",
            resource_type="user",
            resource_id=str(user.id),
            details={
                "target_user": str(user.id),
                "old_role": old_role,
                "new_role": user.role,
                "changed_by": str(current_user.id),
            },
            ip_address=None,
        ))
        await db.flush()

    return user


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.MANAGE_USERS))],
):
    from app.core.exceptions import NotFoundError
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User")
    if user.id == current_user.id:
        from fastapi import HTTPException
        raise HTTPException(400, "Cannot delete your own account")
    await db.delete(user)
    await db.flush()
