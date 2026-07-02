#!/usr/bin/env python3
"""
Seed an admin user into the LBRO database.
Run from the backend/ directory:
    python seed_admin.py
or with custom credentials:
    ADMIN_EMAIL=me@example.com ADMIN_PASSWORD=MyPass123 python seed_admin.py
"""
import asyncio
import os
import sys

# Env defaults — override via environment variables
ADMIN_EMAIL    = os.getenv("ADMIN_EMAIL",    "admin@lbro.local")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin1234!")
ADMIN_NAME     = os.getenv("ADMIN_NAME",     "LBRO Administrator")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")

# Must be set before importing app modules
os.environ.setdefault("DATABASE_URL",         "postgresql+asyncpg://lbro:lbro@localhost:5432/lbro")
os.environ.setdefault("SECRET_KEY",           "seed-secret-key-change-in-production-32c")
os.environ.setdefault("AWS_ACCESS_KEY_ID",    "dummy")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY","dummy")
os.environ.setdefault("ENVIRONMENT",          "development")

sys.path.insert(0, os.path.dirname(__file__))

async def main():
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    import app.models  # noqa: F401 — register all models
    from app.database import Base
    from app.models.user import User
    from app.core.security import hash_password
    from app.config import settings

    DATABASE_URL = settings.DATABASE_URL
    engine = create_async_engine(DATABASE_URL, echo=False)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        # Check if admin already exists
        result = await db.execute(select(User).where(User.email == ADMIN_EMAIL))
        existing = result.scalar_one_or_none()
        if existing:
            print(f"[LBRO] User already exists: {ADMIN_EMAIL}")
            print(f"       Role: {existing.role}")
            return

        import uuid
        user = User(
            id=uuid.uuid4(),
            email=ADMIN_EMAIL,
            username=ADMIN_USERNAME,
            full_name=ADMIN_NAME,
            hashed_password=hash_password(ADMIN_PASSWORD),
            role="admin",
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        await db.commit()
        print("[LBRO] Admin user created successfully")
        print(f"       Email:    {ADMIN_EMAIL}")
        print(f"       Password: {ADMIN_PASSWORD}")
        print(f"       Role:     admin")

asyncio.run(main())
