"""Authentication router."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models.revoked_token import RevokedToken
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(data: RegisterRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    """Self-registration endpoint. Disabled in production unless ALLOW_PUBLIC_REGISTRATION=true.
    In production, create users via POST /api/v1/users (admin-only)."""
    from fastapi import HTTPException
    from app.config import settings
    if not settings.ALLOW_PUBLIC_REGISTRATION:
        raise HTTPException(
            status_code=403,
            detail="Self-registration is disabled. Contact an administrator.",
        )
    svc = AuthService(db)
    user = await svc.register(data)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    svc = AuthService(db)
    return await svc.login(data)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    svc = AuthService(db)
    return await svc.refresh(data.refresh_token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: Annotated[User, Depends(get_current_active_user)]):
    return current_user


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Invalidate the session server-side by revoking the token's jti claim.

    The token's jti is stored in the revoked_tokens table until it naturally
    expires, after which it is eligible for periodic cleanup.
    Clients must also discard stored tokens on receipt of this 204.
    """
    try:
        from app.core.security import decode_token
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            raw_token = auth_header.removeprefix("Bearer ")
            payload = decode_token(raw_token)
            jti = payload.get("jti")
            exp = payload.get("exp")
            if jti and exp:
                expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
                db.add(RevokedToken(jti=jti, expires_at=expires_at))
                await db.flush()
    except Exception:
        # Never fail logout -- even if we cannot revoke, the client discards the token
        pass
    return
