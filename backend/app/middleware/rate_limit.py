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


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        # Key by IP + path prefix
        client_ip = request.client.host if request.client else "unknown"
        key = f"{client_ip}:{request.url.path.split('/')[1]}"

        now = time.monotonic()
        window = 60  # 1-minute window

        async with _lock:
            q = _windows[key]
            # Drop timestamps outside the window
            while q and now - q[0] > window:
                q.popleft()

            if len(q) >= settings.RATE_LIMIT_PER_MINUTE:
                retry_after = int(window - (now - q[0])) + 1
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Try again later."},
                    headers={"Retry-After": str(retry_after)},
                )
            q.append(now)

            # ── Periodic purge of exhausted keys to prevent unbounded memory growth ──
            # Without this, every unique IP that ever hit the service stays in memory.
            global _last_purge
            if now - _last_purge > _PURGE_INTERVAL:
                stale = [k for k, dq in _windows.items() if not dq]
                for k in stale:
                    del _windows[k]
                _last_purge = now

        response = await call_next(request)
        remaining = max(0, settings.RATE_LIMIT_PER_MINUTE - len(_windows[key]))
        response.headers["X-RateLimit-Limit"] = str(settings.RATE_LIMIT_PER_MINUTE)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
