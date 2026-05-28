"""
LBRO — API authentication & security headers

Authentication:
  All /api/v1/* endpoints require a static API key sent in the X-LBRO-API-Key header.
  The key is injected at container start from Secrets Manager (never hard-coded).
  Health endpoints are exempt — ALB probes must never be throttled or blocked.

  In a future iteration this should be replaced with short-lived JWT tokens issued
  by an IdP (Cognito, Auth0) so keys can be rotated without redeployment.

Security headers:
  Every response receives a hardened set of HTTP security headers via
  SecurityHeadersMiddleware. These are defence-in-depth on top of the ALB WAF.
"""
from __future__ import annotations

import hmac
from typing import Annotated

import structlog
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.config import settings

log = structlog.get_logger(__name__)

# ── API key scheme ─────────────────────────────────────────────────────────────

_api_key_header = APIKeyHeader(name=settings.API_KEY_HEADER, auto_error=False)


def verify_api_key(
    api_key: Annotated[str | None, Security(_api_key_header)],  # noqa: B008
) -> str:
    """
    FastAPI dependency — validates the API key on every protected endpoint.

    Uses hmac.compare_digest() to prevent timing-oracle attacks that would
    allow an attacker to brute-force the key character-by-character.

    Raises HTTP 401 when the header is absent, HTTP 403 when it is wrong.
    Both cases emit a structured audit log entry.
    """
    if not api_key:
        log.warning("auth.missing_api_key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": settings.API_KEY_HEADER},
        )

    expected = settings.API_KEY
    if not expected:
        # API_KEY not configured — fail closed, never open
        log.error("auth.api_key_not_configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service not configured",
        )

    # Constant-time comparison — immune to timing attacks
    if not hmac.compare_digest(
        api_key.encode("utf-8"),
        expected.encode("utf-8"),
    ):
        log.warning("auth.invalid_api_key", key_prefix=api_key[:4] + "****")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )

    return api_key


# Shorthand dependency for use in router decorators
RequireAPIKey = Depends(verify_api_key)  # noqa: B008


# ── Security headers middleware ────────────────────────────────────────────────

_SECURITY_HEADERS = {
    # Prevent MIME-type sniffing
    "X-Content-Type-Options": "nosniff",
    # Deny framing entirely (LBRO is an API, not a browser app)
    "X-Frame-Options": "DENY",
    # Force HTTPS for 1 year, include subdomains
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    # Minimal referrer — don't leak API paths to third parties
    "Referrer-Policy": "no-referrer",
    # Disable browser features not needed by an API
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    # Restrictive CSP — this is a pure API, no scripts/styles served
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    # Remove server fingerprint header added by uvicorn/starlette
    "Server": "LBRO",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Appends hardened HTTP security headers to every response."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        for header, value in _SECURITY_HEADERS.items():
            response.headers[header] = value
        # Remove headers that leak implementation details
        if "X-Powered-By" in response.headers:
            del response.headers["X-Powered-By"]
        return response
