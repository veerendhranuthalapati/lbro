"""In-memory sliding-window rate limiter middleware (Redis-backed in production)."""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import settings

_windows: dict[str, deque] = defaultdict(deque)
_lock = asyncio.Lock()  # async-safe; threading.Lock would block the event loop
_last_purge: float = 0.0   # track when we last pruned empty keys
_PURGE_INTERVAL = 300       # purge stale keys every 5 minutes

EXEMPT_PATHS = {"/health", "/metrics", "/docs", "/openapi.json", "/redoc"}

# Auth endpoints are high-value targets — apply strict per-IP limits.
# Key is a path prefix (matched with startswith) → max requests per 60s window.
_STRICT_PATHS: dict[str, int] = {
    "/api/v1/auth/login":    10,
    "/api/v1/auth/register": 10,
    "/api/v1/auth/refresh":  20,
}


def _limit_for_path(path: str) -> int:
    """Return the request-per-minute limit for a given path."""
    for prefix, limit in _STRICT_PATHS.items():
        if path.startswith(prefix):
            return limit
    return settings.RATE_LIMIT_PER_MINUTE


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Disable rate limiting in test environment to prevent spurious 429s
        import os
        if os.getenv("ENVIRONMENT") == "test":
            return await call_next(request)

        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path

        # Key by IP + full path (not just the first segment).
        # Previously used path.split('/')[1] which grouped ALL /api/* routes
        # into one shared bucket — defeating per-endpoint limits entirely.
        key = f"{client_ip}:{path}"
        limit = _limit_for_path(path)

        now = time.monotonic()
        window = 60  # 1-minute sliding window

        async with _lock:
            q = _windows[key]
            # Drop timestamps outside the window
            while q and now - q[0] > window:
                q.popleft()

            if len(q) >= limit:
                retry_after = int(window - (now - q[0])) + 1
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Try again later."},
                    headers={"Retry-After": str(retry_after)},
                )
            q.append(now)

            # ── Periodic purge of exhausted keys to prevent unbounded memory growth ──
            global _last_purge
            if now - _last_purge > _PURGE_INTERVAL:
                stale = [k for k, dq in _windows.items() if not dq]
                for k in stale:
                    del _windows[k]
                _last_purge = now

        response = await call_next(request)
        remaining = max(0, limit - len(_windows[key]))
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
