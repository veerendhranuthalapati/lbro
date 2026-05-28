"""
LBRO — FastAPI application entrypoint
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1 import evidence, health, incidents, notifications
from app.core.config import settings
from app.core.database import Base, engine
from app.core.logging import configure_logging
from app.core.middleware import MetricsMiddleware, RequestTracingMiddleware
from app.core.rate_limit import limiter
from app.core.security import SecurityHeadersMiddleware

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    log.info("lbro.startup", version=settings.APP_VERSION, env=settings.APP_ENV)

    # Validate critical config at startup — fail fast before accepting traffic
    if settings.is_prod() and not settings.API_KEY:
        raise RuntimeError("API_KEY must be set in production")
    if settings.is_prod() and settings.SECRET_KEY == "dev-secret-change-me-never-use-in-prod":
        raise RuntimeError("SECRET_KEY must be set to a real value in production")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    log.info("lbro.shutdown")
    await engine.dispose()


app = FastAPI(
    title="LBRO — Law-aware Breach Response Orchestrator",
    version=settings.APP_VERSION,
    # Disable interactive docs in production — prevents schema enumeration
    docs_url="/docs" if settings.APP_ENV != "prod" else None,
    redoc_url="/redoc" if settings.APP_ENV != "prod" else None,
    openapi_url="/openapi.json" if settings.APP_ENV != "prod" else None,
    lifespan=lifespan,
)

# ── Rate limiter state ─────────────────────────────────────────────────────────
app.state.limiter = limiter

# ── Middleware (applied outer → inner) ─────────────────────────────────────────
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=[settings.API_KEY_HEADER, "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(RequestTracingMiddleware)
app.add_middleware(MetricsMiddleware)

# ── Exception handlers ─────────────────────────────────────────────────────────
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        # Never log exc directly — it may contain sensitive data
        error_type=type(exc).__name__,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": request.state.request_id},
    )


# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(health.router,        tags=["ops"])
app.include_router(incidents.router,     prefix="/api/v1", tags=["incidents"])
app.include_router(notifications.router, prefix="/api/v1", tags=["notifications"])
app.include_router(evidence.router,      prefix="/api/v1", tags=["evidence"])
