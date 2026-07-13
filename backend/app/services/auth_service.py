from __future__ import annotations

import re
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
from app.models.user import User
from app.schemas.auth import LoginRequest, ProfileUpdateRequest, RegisterRequest, TokenResponse
from app.core.exceptions import ConflictError, LBROException, NotFoundError


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def register(self, data: RegisterRequest) -> TokenResponse:
        from app.config import settings
        if not settings.ALLOW_PUBLIC_REGISTRATION:
            raise LBROException("Public registration is disabled.", 403)

        result = await self.db.execute(select(User).where(User.email == data.email))
        if result.scalar_one_or_none():
            raise ConflictError("Email already registered")

        username = data.username
        if not username:
            local = data.email.split("@")[0]
            base = re.sub(r"[^a-zA-Z0-9_]", "", local)[:20] or "user"
            username = base
            suffix = 0
            while True:
                candidate = username if suffix == 0 else f"{username}{suffix}"
                r = await self.db.execute(select(User).where(User.username == candidate))
                if not r.scalar_one_or_none():
                    username = candidate
                    break
                suffix += 1

        new_user = User(
            email=data.email,
            username=username,
            full_name=data.full_name,
            hashed_password=hash_password(data.password),
            role="viewer",
            is_active=True,
            is_verified=True,
        )
        self.db.add(new_user)
        await self.db.flush()

        try:
            from app.services.project_service import ProjectService
            from app.schemas.project import ProjectCreate
            project_svc = ProjectService(self.db)
            await project_svc.create(
                ProjectCreate(
                    name="My First Project",
                    description="Your default project.",
                    environment="production",
                ),
                owner_id=new_user.id,
            )
        except Exception:
            pass

        from app.core.rbac import Role as RbacRole, get_permissions_for_role
        permissions = get_permissions_for_role(RbacRole(new_user.role))
        access_token = create_access_token(str(new_user.id), extra={
            "role": new_user.role,
            "email": new_user.email,
            "permissions": permissions,
        })
        refresh_token = create_refresh_token(str(new_user.id))

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def login(self, data: LoginRequest) -> TokenResponse:
        from app.config import settings
        result = await self.db.execute(select(User).where(User.email == data.email))
        user = result.scalar_one_or_none()

        if user and user.locked_until and user.locked_until > datetime.now(timezone.utc):
            raise LBROException("Account temporarily locked. Try again later.", 403)

        password_ok = verify_password(data.password, user.hashed_password) if user else False

        if not user or not password_ok:
            if user:
                user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
                if user.failed_login_attempts >= settings.MAX_LOGIN_ATTEMPTS:
                    from datetime import timedelta
                    user.locked_until = datetime.now(timezone.utc) + timedelta(
                        minutes=settings.LOCKOUT_DURATION_MINUTES
                    )
                await self.db.flush()
            raise LBROException("Invalid email or password", 401)

        if not user.is_active:
            raise LBROException("Account is deactivated", 403)

        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = datetime.now(timezone.utc)
        await self.db.flush()

        from app.core.rbac import Role as RbacRole, get_permissions_for_role
        permissions = get_permissions_for_role(RbacRole(user.role))
        access_token = create_access_token(str(user.id), extra={
            "role": user.role,
            "email": user.email,
            "permissions": permissions,
        })
        refresh_token = create_refresh_token(str(user.id))

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def refresh(self, refresh_token: str) -> TokenResponse:
        from app.config import settings
        try:
            payload = decode_token(refresh_token)
        except Exception:
            raise LBROException("Invalid or expired refresh token", 401)

        if payload.get("type") != "refresh":
            raise LBROException("Token is not a refresh token", 401)

        user_id = payload.get("sub")
        if not user_id:
            raise LBROException("Invalid refresh token payload", 401)

        result = await self.db.execute(select(User).where(User.id == uuid.UUID(user_id)))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise LBROException("User not found or deactivated", 401)

        from app.core.rbac import Role as RbacRole, get_permissions_for_role
        permissions = get_permissions_for_role(RbacRole(user.role))
        new_access_token = create_access_token(str(user.id), extra={
            "role": user.role,
            "email": user.email,
            "permissions": permissions,
        })

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def update_profile(self, user: User, data: ProfileUpdateRequest) -> User:
        if data.new_password:
            if not data.current_password:
                raise LBROException("Current password is required to set a new password", 400)
            if not verify_password(data.current_password, user.hashed_password):
                raise LBROException("Current password is incorrect", 400)
            user.hashed_password = hash_password(data.new_password)
        if data.full_name is not None:
            user.full_name = data.full_name
        if data.email is not None and data.email != user.email:
            r = await self.db.execute(select(User).where(User.email == data.email))
            if r.scalar_one_or_none():
                raise ConflictError("Email already in use")
            user.email = data.email
        await self.db.flush()
        return user
