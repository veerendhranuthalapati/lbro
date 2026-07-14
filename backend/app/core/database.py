"""
LBRO — Async SQLAlchemy engine and session management

Scalability settings:
  pool_size        — persistent connections kept ready
  max_overflow     — extra connections allowed under burst load
  pool_timeout     — how long to wait for a connection before raising
  pool_recycle     — recycle connections every 30 min to prevent stale TCP
  pool_pre_ping    — verify connection health before use (handles RDS failover)
  pool_use_lifo    — LIFO keeps fewer connections warm (reduces RDS idle load)
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# SQLite (used in tests) does not support connection pool sizing args.
_is_sqlite = settings.DATABASE_URL.startswith("sqlite")
_engine_kwargs: dict = {
    "echo": settings.ENVIRONMENT == "development",
}
if not _is_sqlite:
    _engine_kwargs["pool_size"] = settings.DATABASE_POOL_SIZE
    _engine_kwargs["max_overflow"] = settings.DATABASE_MAX_OVERFLOW
    _engine_kwargs["pool_timeout"] = 30
    _engine_kwargs["pool_recycle"] = 1800
    _engine_kwargs["pool_pre_ping"] = True
    _engine_kwargs["pool_use_lifo"] = True
else:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields a session and ensures cleanup."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
