"""Application configuration via pydantic-settings."""
from __future__ import annotations

import secrets
from functools import lru_cache
from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "LBRO"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    # ── Security ─────────────────────────────────────────────────────────────
    SECRET_KEY: str = secrets.token_urlsafe(32)  # MUST be overridden via env in production
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        if v in ("change-me-generate-with-secrets-token-urlsafe-32", "dev-secret-key-change-in-production-minimum-32-chars"):
            import os
            if os.getenv("ENVIRONMENT", "development") == "production":
                raise ValueError("SECRET_KEY must be changed from the default value in production")
        return v

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://lbro:lbro@localhost:5432/lbro"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # ── Redis / Rate limiting ─────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_BURST: int = 20

    # ── AWS ──────────────────────────────────────────────────────────────────
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_ENDPOINT_URL: Optional[str] = None  # localstack

    # ── S3 ───────────────────────────────────────────────────────────────────
    S3_BUCKET_EVIDENCE: str = "lbro-evidence"
    S3_BUCKET_REPORTS: str = "lbro-reports"
    S3_PRESIGNED_URL_EXPIRY: int = 3600

    # ── SQS ──────────────────────────────────────────────────────────────────
    SQS_INCIDENT_QUEUE_URL: str = ""
    SQS_NOTIFICATION_QUEUE_URL: str = ""
    SQS_DLQ_URL: str = ""
    SQS_VISIBILITY_TIMEOUT: int = 300
    SQS_MAX_MESSAGES: int = 10
    SQS_WAIT_TIME_SECONDS: int = 20

    # ── ML ───────────────────────────────────────────────────────────────────
    ML_MODEL_PATH: str = "/app/ml/models/cicids2017_classifier.pkl"
    ML_SCALER_PATH: str = "/app/ml/models/scaler.pkl"
    ML_CONFIDENCE_THRESHOLD: float = 0.75
    ML_REVIEW_QUEUE_THRESHOLD: float = 0.60
    ML_MODEL_VERSION: str = "1.0.0"

    # ── CORS ─────────────────────────────────────────────────────────────────
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:80",
        "http://frontend:80",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # ── Email / Notifications ─────────────────────────────────────────────────
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: str = "noreply@lbro.local"

    # ── Compliance ────────────────────────────────────────────────────────────
    GDPR_NOTIFICATION_HOURS: int = 72
    HIPAA_NOTIFICATION_HOURS: int = 60 * 24  # HHS 60-day but immediate breach notice
    DPDPA_NOTIFICATION_HOURS: int = 72

    # ── Registration control ──────────────────────────────────────────────────
    # Set to True only in controlled dev/staging environments.
    # In production, all users should be created by an admin via POST /users.
    ALLOW_PUBLIC_REGISTRATION: bool = False

    # ── Logging ──────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
