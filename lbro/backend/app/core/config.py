"""
LBRO — Application configuration
All sensitive values come from environment variables injected by ECS from Secrets Manager.
No secrets are ever hard-coded or logged.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────────────────────────────
    APP_ENV: Literal["dev", "staging", "prod"] = "dev"
    APP_VERSION: str = "0.1.0"
    LOG_LEVEL: str = "INFO"

    # ── Authentication ────────────────────────────────────────────────────────
    # API_KEY must be set in Secrets Manager and injected at container start.
    # There is NO default — the app fails closed (503) if this is absent in prod.
    API_KEY: str = ""
    API_KEY_HEADER: str = "X-LBRO-API-Key"

    # SECRET_KEY is used for any internal signing (e.g. future HMAC payloads).
    # Default is only acceptable for local dev — ECS always injects a real value.
    SECRET_KEY: str = "dev-secret-change-me-never-use-in-prod"

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://lbro:lbro@localhost:5432/lbro"
    # When using RDS Proxy, the proxy manages the real DB connection pool.
    # Keep the app-side pool small — proxy handles multiplexing.
    # For direct DB (local dev, migrations): use higher values.
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30

    # ── AWS ───────────────────────────────────────────────────────────────────
    AWS_REGION: str = "ap-south-1"
    SQS_QUEUE_URL: str = ""
    SQS_CONTAINMENT_QUEUE_URL: str = ""
    SQS_NOTIFICATION_QUEUE_URL: str = ""
    S3_EVIDENCE_BUCKET: str = ""
    S3_NOTIFICATIONS_BUCKET: str = ""

    # ── CORS ──────────────────────────────────────────────────────────────────
    # In prod this must be set to the exact dashboard origin — never "*"
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # ── Regulatory deadlines ──────────────────────────────────────────────────
    GDPR_NOTIFICATION_HOURS: int = 72
    HIPAA_NOTIFICATION_DAYS: int = 60
    DPDPA_NOTIFICATION_HOURS: int = 72

    @field_validator("DATABASE_URL")
    @classmethod
    def ensure_asyncpg_and_ssl(cls, v: str) -> str:
        """Ensure async driver is used, and SSL is enforced in non-dev environments."""
        if v.startswith("postgresql://"):
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        # Add sslmode=require if not already present and not a local/test URL
        if "localhost" not in v and "127.0.0.1" not in v and "sslmode" not in v:
            sep = "&" if "?" in v else "?"
            v = f"{v}{sep}ssl=require"
        return v

    @field_validator("SECRET_KEY")
    @classmethod
    def warn_if_default_secret(cls, v: str) -> str:
        if v == "dev-secret-change-me-never-use-in-prod":
            import warnings
            warnings.warn(
                "SECRET_KEY is using the insecure default. Set a real value via Secrets Manager.",
                stacklevel=2,
            )
        return v

    def is_prod(self) -> bool:
        return self.APP_ENV == "prod"

    def __repr__(self) -> str:
        """Never include secrets in repr — prevents accidental logging."""
        return (
            f"Settings(APP_ENV={self.APP_ENV!r}, APP_VERSION={self.APP_VERSION!r}, "
            f"AWS_REGION={self.AWS_REGION!r})"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
