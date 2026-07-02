"""LBRO FastAPI application entry point."""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.config import settings
from app.core.exceptions import (
    LBROException,
    lbro_exception_handler,
    generic_exception_handler,
)
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.routers import auth, incidents, evidence, notifications, compliance, users, ml, dashboard, audit

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("LBRO %s starting up (env=%s)", settings.APP_VERSION, settings.ENVIRONMENT)
    # Ensure S3 buckets exist (skip in test environment — no real S3/LocalStack running)
    if settings.ENVIRONMENT != "test" and (settings.AWS_ENDPOINT_URL or settings.AWS_ACCESS_KEY_ID):
        try:
            from app.services.s3_service import s3_service
            s3_service.ensure_bucket(settings.S3_BUCKET_EVIDENCE)
            s3_service.ensure_bucket(settings.S3_BUCKET_REPORTS)
        except Exception as exc:
            logger.warning("S3 bucket init failed: %s", exc)
    yield
    logger.info("LBRO shutting down")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Law-aware Breach Response Orchestrator — automated incident response platform",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan,
)

# ── Middleware (order matters: outermost first) ────────────────────────────────
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
# Block requests with forged Host headers (prevents host-header injection / SSRF)
if settings.ENVIRONMENT == "test":
    # In test env (pytest + ASGI transport), Host header is "test" — allow wildcard
    _allowed_hosts = ["*"]
elif settings.DEBUG:
    _allowed_hosts = ["localhost", "127.0.0.1", "api", "lbro.local"]
else:
    _allowed_hosts = ["lbro.local", "api"]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=_allowed_hosts)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-API-Key",
        "X-Request-ID",
        "X-Client-Version",
        "Accept",
        "Origin",
    ],
    expose_headers=["X-Process-Time", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
)

# ── Exception handlers ────────────────────────────────────────────────────────
app.add_exception_handler(LBROException, lbro_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# ── Request timing middleware ─────────────────────────────────────────────────
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    response.headers["X-Process-Time"] = f"{elapsed:.4f}s"
    return response


# ── Routers ───────────────────────────────────────────────────────────────────
API_PREFIX = "/api/v1"
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(incidents.router, prefix=API_PREFIX)
app.include_router(evidence.router, prefix=API_PREFIX)  # No prefix — paths are already fully specified
app.include_router(notifications.router, prefix=API_PREFIX)
app.include_router(compliance.router, prefix=API_PREFIX)
app.include_router(users.router, prefix=API_PREFIX)
app.include_router(ml.router, prefix=API_PREFIX)
app.include_router(dashboard.router, prefix=API_PREFIX)
app.include_router(audit.router, prefix=API_PREFIX)


# ── Health endpoints ──────────────────────────────────────────────────────────
@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}


@app.get("/health/ready", tags=["health"])
async def readiness():
    """Check DB connectivity."""
    from app.database import engine
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    status = "ok" if db_ok else "degraded"
    return {"status": status, "db": db_ok}
