"""
LBRO — pytest conftest (session-level)
Sets env vars before any app module is imported.
"""
import os

# Must be set before app.core.config is imported
os.environ.setdefault("APP_ENV", "dev")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-tests-only")
os.environ.setdefault("SQS_QUEUE_URL", "")
os.environ.setdefault("S3_EVIDENCE_BUCKET", "")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://lbro:lbro_test@localhost:5432/lbro_test",
)

# Clear the settings cache so the app picks up the env vars we just set.
# lru_cache is set at import time; if tests import app before this runs, the
# empty API_KEY default gets cached. Clearing here forces a fresh load.
from app.core.config import get_settings

get_settings.cache_clear()
