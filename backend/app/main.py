"""LBRO FastAPI application entry point."""
from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

import structlog
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
from app.routers import (
    auth, incidents, evidence, notifications, compliance,
    users, ml, dashboard, audit, infrastructure,
    security_score, reports, projects,
)
from app.routers import demo
from app.routers import platform as platform_router
from app.routers import events as events_router

_log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

logging.basicConfig(
    level=_log_level,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

_shared_processors: list = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.processors.TimeStamper(fmt="iso"),
]

if settings.ENVIRONMENT in ("development", "dev") or settings.DEBUG:
    structlog.configure(
        processors=_shared_processors + [structlog.dev.ConsoleRenderer()],
        wrapper_class=structlog.make_filtering_bound_logger(_log_level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
else:
    structlog.configure(
        processors=_shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(_log_level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup", version=settings.APP_VERSION, env=settings.ENVIRONMENT)
    if settings.ENVIRONMENT not in ("test",) and (settings.AWS_ENDPOINT_URL or settings.AWS_ACCESS_KEY_ID):
        try:
            from app.services.s3_service import s3_service
            s3_service.ensure_bucket(settings.S3_BUCKET_EVIDENCE)
            s3_service.ensure_bucket(settings.S3_BUCKET_REPORTS)
        except Exception as exc:
            logger.warning("s3_bucket_init_failed", error=str(exc))
    yield
    logger.info("shutdown")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Law-aware Breach Response Orchestrator — automated incident response platform",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan,
)

# ── Middleware (outermost first) ──────────────────────────────────────────────
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)

# TrustedHostMiddleware — restrict Host header to known values
if settings.ENVIRONMENT == "test":
    _allowed_hosts = ["*"]
elif settings.ENVIRONMENT in ("development", "dev"):
    # Local dev: browsers hit localhost; also allow container name "api"
    _allowed_hosts = ["localhost", "127.0.0.1", "api", "lbro.local", "0.0.0.0"]
else:
    # Production: restrict to explicitly configured hostnames
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


# ── Request ID + timing middleware ────────────────────────────────────────────
@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 1)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{duration_ms}ms"
    logger.info(
        "http_request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=duration_ms,
    )
    return response


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router,           prefix="/api/v1")
app.include_router(incidents.router,      prefix="/api/v1")
app.include_router(evidence.router,       prefix="/api/v1")
app.include_router(notifications.router,  prefix="/api/v1")
app.include_router(compliance.router,     prefix="/api/v1")
app.include_router(users.router,          prefix="/api/v1")
app.include_router(ml.router,             prefix="/api/v1")
app.include_router(dashboard.router,      prefix="/api/v1")
app.include_router(audit.router,          prefix="/api/v1")
app.include_router(infrastructure.router, prefix="/api/v1")
app.include_router(security_score.router, prefix="/api/v1")
app.include_router(reports.router,        prefix="/api/v1")
app.include_router(projects.router,       prefix="/api/v1")
app.include_router(demo.router,           prefix="/api/v1")
app.include_router(platform_router.router, prefix="/api/v1")
app.include_router(events_router.router,   prefix="/api/v1")


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok", "version": settings.APP_VERSION, "env": settings.ENVIRONMENT}
