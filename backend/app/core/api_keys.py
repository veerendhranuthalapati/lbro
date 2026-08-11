"""API key generation, hashing, and verification.

Full keys are shown only once at creation/regeneration. Only prefix + hash are stored.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

from app.config import settings

# Prefix length used for indexed lookup (includes "proj_" or "lbro_" prefix segment)
_PREFIX_LEN = 16


def generate_project_api_key() -> tuple[str, str, str]:
    """Return (full_key, prefix, hash)."""
    full = "proj_" + secrets.token_urlsafe(32)
    return full, api_key_prefix(full), hash_api_key(full)


def generate_user_api_key() -> tuple[str, str, str]:
    """Return (full_key, prefix, hash)."""
    full = "lbro_" + secrets.token_urlsafe(32)
    return full, api_key_prefix(full), hash_api_key(full)


def api_key_prefix(key: str) -> str:
    return key[:_PREFIX_LEN]


def hash_api_key(key: str) -> str:
    """HMAC-SHA256 with server secret — fast verify for high-volume event ingestion."""
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        key.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_api_key(key: str, stored_hash: str) -> bool:
    if not key or not stored_hash:
        return False
    expected = hash_api_key(key)
    return hmac.compare_digest(expected, stored_hash)


def mask_api_key_prefix(prefix: str | None) -> str:
    """Safe display value — never reconstructs the full key."""
    if not prefix:
        return "not set"
    return prefix + "…"
