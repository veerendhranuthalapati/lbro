"""ML signing key policy — shared by Settings validation and startup checks."""
from __future__ import annotations

import os

# Keys used in tests/docs only; must never appear when ENVIRONMENT=production.
KNOWN_TEST_SIGNING_KEYS: frozenset[str] = frozenset(
    {
        "test-ml-signing-key-minimum-32-characters-long",
        "test-signing-key-for-lbro-ml-bundle-min-32",
        "dev-only-ml-signing-key-not-for-production-use",
    }
)

MIN_SIGNING_KEY_LENGTH = 32


def validate_signing_key_for_environment(key: str | None, environment: str) -> None:
    """
    Raise ValueError when the key is missing, too short, or a known test key in production.

    Dev/test may use the documented test key; production must use a unique secret from a vault.
    """
    env = (environment or os.getenv("ENVIRONMENT", "production")).lower()
    if env != "production":
        if key and len(key) < MIN_SIGNING_KEY_LENGTH:
            raise ValueError(
                f"ML_MODEL_SIGNING_KEY must be at least {MIN_SIGNING_KEY_LENGTH} characters"
            )
        return

    if not key:
        allow_unsigned = os.getenv("ML_ALLOW_UNSIGNED_MODEL", "").lower() == "true"
        if allow_unsigned:
            return
        raise ValueError("ML_MODEL_SIGNING_KEY is required when ENVIRONMENT=production")

    if len(key) < MIN_SIGNING_KEY_LENGTH:
        raise ValueError(
            f"ML_MODEL_SIGNING_KEY must be at least {MIN_SIGNING_KEY_LENGTH} characters in production"
        )

    if key in KNOWN_TEST_SIGNING_KEYS:
        raise ValueError(
            "ML_MODEL_SIGNING_KEY must not be a documented test/dev key in production"
        )
