"""Authentication router."""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models.revoked_token import RevokedToken
from app.models.user import User
from app.schemas.auth import LoginRequest, ProfileUpdateRequest, RefreshRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(data: RegisterRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    """Self-registration endpoint. Returns tokens for immediate auto-login.
    Disabled if ALLOW_PUBLIC_REGISTRATION=False."""
    from fastapi import HTTPException
    from app.config import settings
    if not settings.ALLOW_PUBLIC_REGISTRATION:
        raise HTTPException(
            status_code=403,
            detail="Self-registration is disabled. Contact an administrator.",
        )
    svc = AuthService(db)
    return await svc.register(data)


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


@router.patch("/profile", response_model=UserResponse)
async def update_profile(
    data: ProfileUpdateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update the current user's name, email, or password."""
    svc = AuthService(db)
    return await svc.update_profile(current_user, data)


@router.post("/api-key/rotate")
async def rotate_api_key(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Generate a new API key for the current user, invalidating the old one.

    The new key is returned exactly once — it cannot be retrieved again.
    Clients must store it securely immediately on receipt.
    """
    new_key = "lbro_" + secrets.token_urlsafe(32)
    current_user.api_key = new_key
    db.add(current_user)
    await db.commit()
    return {"api_key": new_key}


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
                revoked = RevokedToken(
                    jti=jti,
                    expires_at=datetime.fromtimestamp(exp, tz=timezone.utc),
                )
                db.add(revoked)
                await db.commit()
    except Exception:
        pass  # best-effort; client must discard tokens regardless
