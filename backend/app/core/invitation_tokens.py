"""Invitation token generation and verification (hashed storage only)."""
from __future__ import annotations

import hashlib
import hmac
import secrets

from app.config import settings


def normalize_invitation_email(email: str) -> str:
    return email.strip().lower()


def generate_invitation_token() -> tuple[str, str]:
    """Return (full_token, token_hash). Full token shown once at invite creation."""
    full = "inv_" + secrets.token_urlsafe(32)
    return full, hash_invitation_token(full)


def hash_invitation_token(token: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_invitation_token(token: str, stored_hash: str) -> bool:
    if not token or not stored_hash:
        return False
    expected = hash_invitation_token(token)
    return hmac.compare_digest(expected, stored_hash)
