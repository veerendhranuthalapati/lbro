"""JWT creation, verification, and password hashing."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from jwt.exceptions import PyJWTError
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Synchronous bcrypt hash — use hash_password_async from async request handlers."""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Synchronous verify — prefer verify_password_async in the event loop."""
    return pwd_context.verify(plain, hashed)


def password_needs_rehash(hashed: str) -> bool:
    """True when stored hash uses deprecated bcrypt parameters (passlib needs_update)."""
    return pwd_context.needs_update(hashed)


async def verify_password_async(plain: str, hashed: str) -> bool:
    """Run bcrypt in a worker thread so the asyncio loop stays responsive under login load."""
    import asyncio

    return await asyncio.to_thread(verify_password, plain, hashed)


async def hash_password_async(password: str) -> str:
    """Thread-pool bcrypt for registration/profile updates from async handlers."""
    import asyncio

    return await asyncio.to_thread(hash_password, password)


def create_access_token(subject: Any, extra: dict | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    # jti (JWT ID) is a unique claim used for token revocation on logout.
    # It lets us blacklist individual tokens without invalidating all user sessions.
    payload = {
        "sub": str(subject),
        "exp": expire,
        "type": "access",
        "jti": str(uuid.uuid4()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(subject: Any) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload = {"sub": str(subject), "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return payload
    except PyJWTError as exc:
        raise ValueError("Invalid or expired token") from exc
