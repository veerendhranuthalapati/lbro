"""pytest fixtures for LBRO backend tests.

Design:
- SQLite in-memory for speed (no Postgres needed in CI)
- DB tables created once per session via sync asyncio.run() call
- Per-test session with rollback for isolation
- No deprecated event_loop fixture needed (asyncio_mode="auto")
"""
from __future__ import annotations

import asyncio
import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ── Environment setup MUST happen BEFORE any app imports ──────────────────────
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-minimum-32chars")
os.environ.setdefault("AWS_ENDPOINT_URL", "http://localhost:4566")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
os.environ.setdefault("ALLOW_PUBLIC_REGISTRATION", "true")
os.environ.setdefault("ENVIRONMENT", "test")

# Import app AFTER env vars are set
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
import app.models  # noqa: F401 — ensures all models register with Base.metadata  # noqa: E402

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Separate test engine — SQLite does NOT support pool_size / max_overflow
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)
TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ── One-time DB setup (sync, using asyncio.run to avoid event loop scope issues)

def _run(coro):
    """Run a coroutine synchronously; safe to call from session-scope fixtures."""
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """Create all tables once before any test in the session; drop them after."""
    async def _create():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def _drop():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    asyncio.run(_create())
    yield
    asyncio.run(_drop())


# ── Per-test DB session ───────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def db(create_tables) -> AsyncGenerator[AsyncSession, None]:  # noqa: ARG001
    """Fresh DB session per test; rolls back after the test to isolate state."""
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


# ── HTTP client with DB override ──────────────────────────────────────────────

@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c
    finally:
        app.dependency_overrides.clear()


# ── User fixtures ─────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def admin_user(db: AsyncSession):
    import uuid
    from app.models.user import User
    from app.core.security import hash_password

    user = User(
        id=uuid.uuid4(),
        email="admin@lbro.test",
        username="admin",
        full_name="Admin User",
        hashed_password=hash_password("TestPass123!"),
        role="admin",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def analyst_user(db: AsyncSession):
    import uuid
    from app.models.user import User
    from app.core.security import hash_password

    user = User(
        id=uuid.uuid4(),
        email="analyst@lbro.test",
        username="analyst",
        full_name="SOC Analyst",
        hashed_password=hash_password("Analyst123!"),
        role="analyst",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def viewer_user(db: AsyncSession):
    import uuid
    from app.models.user import User
    from app.core.security import hash_password

    user = User(
        id=uuid.uuid4(),
        email="viewer@lbro.test",
        username="viewer",
        full_name="Read Only Viewer",
        hashed_password=hash_password("Viewer123!"),
        role="viewer",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.flush()
    return user


# ── Token helpers ─────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def admin_token(client: AsyncClient, admin_user) -> str:  # noqa: ARG001
    resp = await client.post("/api/v1/auth/login", json={
        "email": "admin@lbro.test",
        "password": "TestPass123!",
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def analyst_token(client: AsyncClient, analyst_user) -> str:  # noqa: ARG001
    resp = await client.post("/api/v1/auth/login", json={
        "email": "analyst@lbro.test",
        "password": "Analyst123!",
    })
    assert resp.status_code == 200, f"Analyst login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture
def auth_headers(admin_token: str) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def analyst_headers(analyst_token: str) -> dict:
    return {"Authorization": f"Bearer {analyst_token}"}
