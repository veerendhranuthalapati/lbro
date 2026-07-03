"""Authentication service."""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.config import settings
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.core.exceptions import ConflictError, LBROException


def _permissions_for(role: str) -> list:
    """Return permission list for role, embedded in JWT. Empty list on unknown role."""
    from app.core.rbac import Role as R, get_permissions_for_role
    try:
        return get_permissions_for_role(R(role))
    except ValueError:
        return []


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, data: RegisterRequest) -> User:
        result = await self.db.execute(select(User).where(User.email == data.email))
        if result.scalar_one_or_none():
            raise ConflictError("Email already registered")

        result = await self.db.execute(select(User).where(User.username == data.username))
        if result.scalar_one_or_none():
            raise ConflictError("Username already taken")

        user = User(
            email=data.email,
            username=data.username,
            full_name=data.full_name,
            hashed_password=hash_password(data.password),
            role="viewer",
            is_active=True,
            is_verified=False,
        )
        self.db.add(user)
        await self.db.flush()
        return user

    async def login(self, data: LoginRequest) -> TokenResponse:
        result = await self.db.execute(select(User).where(User.email == data.email))
        user = result.scalar_one_or_none()

        # Lockout check BEFORE bcrypt (prevents timing side-channel)
        if user and user.locked_until and user.locked_until > datetime.now(timezone.utc):
            raise LBROException("Account temporarily locked. Try again later.", 403)

        # Always run verify_password even for missing users (prevents timing leak)
        _DUMMY_HASH = "$2b$12$KIXOg5OcV2I8k/fNEaGm8uLK7s1Q1xXzQ0tYOF9n5Q6k4F3v9KBSW"
        pw_ok = verify_password(data.password, user.hashed_password if user else _DUMMY_HASH)

        if not user or not pw_ok:
            if user:
                from datetime import timedelta
                user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
                if user.failed_login_attempts >= 5:
                    user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
                await self.db.flush()
            raise LBROException("Invalid credentials", 401)

        if not user.is_active:
            raise LBROException("Account is inactive", 403)

        user.failed_login_attempts = 0
        user.last_login = datetime.now(timezone.utc)
        await self.db.flush()

        access_token = create_access_token(
            user.id,
            {"role": user.role, "email": user.email, "permissions": _permissions_for(user.role)},
        )
        refresh_token = create_refresh_token(user.id)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def refresh(self, refresh_token: str) -> TokenResponse:
        try:
            payload = decode_token(refresh_token)
            if payload.get("type") != "refresh":
                raise ValueError("Not a refresh token")
            user_id = uuid.UUID(payload["sub"])
        except (ValueError, KeyError):
            raise LBROException("Invalid refresh token", 401)

        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise LBROException("User not found or inactive", 401)

        access_token = create_access_token(
            user.id,
            {"role": user.role, "email": user.email, "permissions": _permissions_for(user.role)},
        )
        new_refresh = create_refresh_token(user.id)

        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def rotate_api_key(self, user: User) -> str:
        new_key = secrets.token_urlsafe(48)
        user.api_key = new_key
        await self.db.flush()
        return new_key
