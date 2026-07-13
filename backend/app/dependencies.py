"""FastAPI dependency injection.

Auth flow:
  Bearer JWT        -> decode -> user_id -> DB lookup -> User
  X-API-Key         -> constant-time compare -> User  (user-level, legacy)
  Bearer proj_key   -> Project lookup -> project-scoped auth

Permission flow:
  require_permission(P)       -> 403 + AuditLog if role lacks P
  require_any_permission(P)   -> 403 + AuditLog if role lacks ALL of P
  require_role(R...)          -> 403 if role not in R
  require_super_admin()       -> 403 + AuditLog if not super_admin
  get_project_from_api_key()  -> Project resolved from Bearer proj_* key

SUPER_ADMIN bypass:
  SUPER_ADMIN holds every permission, so require_permission() passes.
  All SUPER_ADMIN accesses are audit-logged with the "super_admin_access" action
  so that every privileged action is traceable.

Every 403 is audit-logged with: timestamp, user, role, permission_requested,
endpoint, IP, user agent, and reason.  401s are not audit-logged (user unknown).
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, APIKeyHeader

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.core.rbac import Permission, Role, has_permission, has_any_permission, is_super_admin
from app.database import get_db
from app.models.revoked_token import RevokedToken
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


# ─────────────────────────────────────────────────────────────────────────────
# Authentication dependencies
# ─────────────────────────────────────────────────────────────────────────────

async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
    api_key: Annotated[str | None, Depends(api_key_header)] = None,
) -> User:
    if credentials:
        token = credentials.credentials
        # Reject project API keys used as user bearer tokens
        if token.startswith("proj_"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "invalid_token", "message": "Project API keys must be used on /api/v1/events, not as user tokens"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            payload = decode_token(token)
            if payload.get("type") != "access":
                raise ValueError("Not an access token")
            user_id = uuid.UUID(payload["sub"])
        except (ValueError, KeyError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "invalid_token", "message": "Invalid or expired token"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check token revocation
        jti = payload.get("jti")
        if jti:
            revoked = (await db.execute(
                select(RevokedToken).where(RevokedToken.jti == jti)
            )).scalar_one_or_none()
            if revoked:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={"error": "token_revoked", "message": "Token has been revoked"},
                    headers={"WWW-Authenticate": "Bearer"},
                )

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "user_not_found", "message": "User not found"},
            )
        return user

    elif api_key:
        result = await db.execute(
            select(User).where(
                User.api_key == api_key,
                User.is_active == True,  # noqa: E712
            )
        )
        matched_user = result.scalar_one_or_none()
        if not matched_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "invalid_api_key", "message": "Invalid API key"},
            )
        return matched_user

    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "not_authenticated", "message": "Not authenticated"},
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "account_inactive", "message": "Account is inactive"},
        )
    return current_user


# ─────────────────────────────────────────────────────────────────────────────
# Project API key dependency — for event ingestion endpoints
# ─────────────────────────────────────────────────────────────────────────────

async def get_project_from_api_key(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> "Project":  # type: ignore[name-defined]
    """Resolve a Project from a Bearer project API key.

    SECURITY: project_id is NEVER trusted from the request body or query string.
    It is ALWAYS derived from the authenticated API key.  This prevents any
    client from submitting events to a project it does not own.
    """
    from app.models.project import Project

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "not_authenticated", "message": "Project API key required as Bearer token"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    if not token.startswith("proj_"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_api_key", "message": "Invalid project API key format"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(
        select(Project).where(
            Project.api_key == token,
            Project.status == "active",
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_api_key", "message": "Invalid or revoked project API key"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return project


# ─────────────────────────────────────────────────────────────────────────────
# Internal helper: write audit log for authz failures and privileged access
# ─────────────────────────────────────────────────────────────────────────────

async def _write_audit_log(
    db: AsyncSession,
    user: User,
    action: str,
    resource: str,
    request: Request | None,
    details: dict,
    status_code: int = 200,
) -> None:
    """Best-effort audit log write — never raises."""
    try:
        from app.models.audit import AuditLog
        ip = request.client.host if request and request.client else None
        ua = request.headers.get("user-agent") if request else None
        method = request.method if request else None
        path = str(request.url.path) if request else None

        log = AuditLog(
            user_id=user.id,
            user_email=user.email,
            action=action,
            resource_type="permission",
            resource_id=resource,
            ip_address=ip,
            user_agent=ua,
            request_method=method,
            request_path=path,
            response_status=status_code,
            details=details,
        )
        db.add(log)
        await db.flush()
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error("Failed to write audit log: %s", exc)


async def _audit_authz_failure(
    db: AsyncSession,
    user: User,
    permission_requested: str,
    request: Request | None,
    reason: str,
) -> None:
    await _write_audit_log(
        db, user, "authz_failure", permission_requested, request,
        {"role": user.role, "permission_requested": permission_requested, "reason": reason},
        status_code=403,
    )


async def _audit_super_admin_access(
    db: AsyncSession,
    user: User,
    permission_requested: str,
    request: Request | None,
) -> None:
    """Every SUPER_ADMIN bypass is audit-logged — intentional and traceable."""
    await _write_audit_log(
        db, user, "super_admin_access", permission_requested, request,
        {"role": user.role, "permission_requested": permission_requested,
         "note": "super_admin_bypass_intentional"},
        status_code=200,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Permission dependency factories
# ─────────────────────────────────────────────────────────────────────────────

def require_permission(permission: Permission):
    """Dependency factory: 403 + audit log if current user lacks *permission*.

    SUPER_ADMIN automatically passes all permission checks (platform bypass).
    The bypass is audit-logged with action="super_admin_access".
    """

    async def _dep(
        request: Request,
        db: Annotated[AsyncSession, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        # SUPER_ADMIN bypass — logged for every privileged access
        if is_super_admin(current_user.role):
            await _audit_super_admin_access(db, current_user, permission.value, request)
            return current_user

        try:
            role = Role(current_user.role)
        except ValueError:
            await _audit_authz_failure(
                db, current_user, permission.value, request,
                "unrecognized_role:" + current_user.role,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "forbidden",
                    "message": "Unrecognized role '" + current_user.role + "'",
                    "permission_required": permission.value,
                },
            )

        if not has_permission(role, permission):
            await _audit_authz_failure(
                db, current_user, permission.value, request,
                "insufficient_permissions",
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "forbidden",
                    "message": "Permission '" + permission.value + "' required",
                    "permission_required": permission.value,
                    "your_role": current_user.role,
                },
            )
        return current_user

    return _dep


def require_any_permission(*permissions: Permission):
    """Dependency factory: 403 + audit log if user lacks ALL of the given permissions."""
    perm_values = " | ".join(p.value for p in permissions)

    async def _dep(
        request: Request,
        db: Annotated[AsyncSession, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        # SUPER_ADMIN bypass
        if is_super_admin(current_user.role):
            await _audit_super_admin_access(db, current_user, perm_values, request)
            return current_user

        try:
            role = Role(current_user.role)
        except ValueError:
            await _audit_authz_failure(
                db, current_user, perm_values, request,
                "unrecognized_role:" + current_user.role,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "forbidden",
                    "message": "Unrecognized role '" + current_user.role + "'",
                    "permissions_required_any": [p.value for p in permissions],
                },
            )

        if not has_any_permission(role, *permissions):
            await _audit_authz_failure(
                db, current_user, perm_values, request,
                "insufficient_permissions",
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "forbidden",
                    "message": "One of " + str([p.value for p in permissions]) + " required",
                    "permissions_required_any": [p.value for p in permissions],
                    "your_role": current_user.role,
                },
            )
        return current_user

    return _dep


def require_super_admin():
    """Dependency factory: 403 + audit log if user is not SUPER_ADMIN.

    Use this for platform-only routes that project admins must never reach.
    """
    async def _dep(
        request: Request,
        db: Annotated[AsyncSession, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        if not is_super_admin(current_user.role):
            await _audit_authz_failure(
                db, current_user, "platform:super_admin", request,
                "not_super_admin",
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "forbidden",
                    "message": "Platform super_admin role required",
                    "your_role": current_user.role,
                },
            )
        # Log every super_admin platform route access
        await _audit_super_admin_access(db, current_user, "platform:super_admin", request)
        return current_user

    return _dep


def require_role(*roles: Role):
    """Dependency factory: 403 if user role not in *roles*.

    Prefer require_permission for new endpoints.
    """
    async def _dep(
        request: Request,
        db: Annotated[AsyncSession, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        if current_user.role not in [r.value for r in roles]:
            await _audit_authz_failure(
                db, current_user,
                "role:" + ",".join(r.value for r in roles), request,
                "role_not_in_allowed_set",
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "forbidden",
                    "message": "Role must be one of " + str([r.value for r in roles]),
                    "your_role": current_user.role,
                },
            )
        return current_user

    return _dep
