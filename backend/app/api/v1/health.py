"""
LBRO — Health check endpoints

/health       — liveness probe (ECS health check, ALB target health)
/health/ready — readiness probe (DB + SQS + S3 config validation)

Health endpoints are exempt from API key auth and rate limiting
so ALB probes and ECS health checks always reach them.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.schemas.incident import HealthOut

log = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/health", response_model=HealthOut, summary="Liveness probe")
async def health_liveness() -> HealthOut:
    """Shallow — confirms the process is alive. Never checks dependencies."""
    return HealthOut(
        status="ok",
        version=settings.APP_VERSION,
        env=settings.APP_ENV,
        checks={},
    )


@router.get("/health/ready", response_model=HealthOut, summary="Readiness probe")
async def health_readiness(
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> JSONResponse:
    """
    Deep readiness check — verifies all critical dependencies before
    ECS marks the task as healthy and routes traffic to it.

    Checks:
      database — SELECT 1 through RDS Proxy
      sqs      — queue URL configured (not a live SQS call — avoids IAM cost)
      config   — API_KEY set (fail-safe: catch misconfiguration early)
    """
    checks: dict[str, str] = {}
    overall = "ok"

    # Database — actual connectivity check
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {type(e).__name__}"
        overall = "degraded"
        log.error("health.db_failed", error=str(e))

    # SQS — configuration check (validates secret injection worked)
    if settings.SQS_QUEUE_URL:
        checks["sqs"] = "configured"
    else:
        checks["sqs"] = "not_configured"
        overall = "degraded"
        log.warning("health.sqs_not_configured")

    # API key — catches missing secret injection before traffic arrives
    if settings.API_KEY:
        checks["auth"] = "ok"
    else:
        checks["auth"] = "api_key_missing"
        # Degraded but not fatal — health/ready still returns 503
        # so the task won't receive traffic until the secret is injected
        overall = "degraded"
        log.warning("health.api_key_missing")

    status_code = 200 if overall == "ok" else 503
    return JSONResponse(
        status_code=status_code,
        content=HealthOut(
            status=overall,
            version=settings.APP_VERSION,
            env=settings.APP_ENV,
            checks=checks,
        ).model_dump(),
    )
