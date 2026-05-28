"""
Integration test fixtures.

Key design:
- Sync psycopg2 schema bootstrap — no async loop dependency at setup time.
- Function-scoped NullPool async engine per test — no cross-loop connection reuse.
- settings.API_KEY patched before the app processes any request (not at import time).
"""
import os

import psycopg2  # noqa: F401 (imported for sync bootstrap)
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

DB_URL_ASYNC = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://lbro:lbro_test@localhost:5432/lbro_test",
)
DB_URL_SYNC = DB_URL_ASYNC.replace("postgresql+asyncpg://", "postgresql://")

TEST_API_KEY = "ci-test-api-key-for-tests-only"


def _sync_create_tables() -> None:
    from app.core.database import Base
    from app.models import incident  # noqa: F401 — registers all ORM models

    engine = create_engine(DB_URL_SYNC)
    Base.metadata.create_all(engine)
    engine.dispose()


def _sync_truncate_tables() -> None:
    from app.core.database import Base

    engine = create_engine(DB_URL_SYNC)
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f'TRUNCATE TABLE "{table.name}" CASCADE'))
    engine.dispose()


# Schema created once at conftest import — before any test runs
_sync_create_tables()


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(DB_URL_ASYNC, poolclass=NullPool, echo=False)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def clean_db():
    _sync_truncate_tables()
    yield


@pytest_asyncio.fixture
async def client(db_engine):
    from app.core import config as _cfg
    from app.core.database import get_db
    from app.main import app

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    # Patch the live settings singleton — the same object security.py reads at call time
    original_api_key = _cfg.settings.API_KEY
    _cfg.settings.API_KEY = TEST_API_KEY

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-LBRO-API-Key": TEST_API_KEY},
    ) as c:
        yield c

    app.dependency_overrides.clear()
    _cfg.settings.API_KEY = original_api_key  # restore original value
