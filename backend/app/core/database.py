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

from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=1800,        # Recycle connections every 30 min — prevents stale TCP
    pool_pre_ping=True,       # Test connection before use — handles RDS Proxy failover
    pool_use_lifo=True,       # LIFO: reuse most-recently-used connections (fewer idle)
    echo=settings.APP_ENV == "dev",
)

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
