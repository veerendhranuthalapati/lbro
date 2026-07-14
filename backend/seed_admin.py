#!/usr/bin/env python3
"""
Seed 2 demo accounts for every LBRO role (8 users total).
Run from the backend/ directory:
    python seed_admin.py

─────────────────────────────────────────────────────────────────
  DEMO CREDENTIALS
─────────────────────────────────────────────────────────────────
  SUPER ADMIN  (full platform access, bypasses all RBAC checks)
    superadmin1@lbro.local  /  SuperAdmin@LBRO1!
    superadmin2@lbro.local  /  SuperAdmin@LBRO2!

  ADMIN  (all project permissions)
    admin1@lbro.local       /  Admin@LBRO1!2026
    admin2@lbro.local       /  Admin@LBRO2!2026

  ANALYST  (create/update incidents, upload evidence, reports)
    analyst1@lbro.local     /  Analyst@LBRO1!2026
    analyst2@lbro.local     /  Analyst@LBRO2!2026

  VIEWER  (read-only: incidents, evidence, compliance, dashboard)
    viewer1@lbro.local      /  Viewer@LBRO1!2026
    viewer2@lbro.local      /  Viewer@LBRO2!2026
─────────────────────────────────────────────────────────────────
"""
import asyncio
import os
import sys
import uuid

os.environ.setdefault("DATABASE_URL",          "postgresql+asyncpg://lbro:lbro@localhost:5432/lbro")
os.environ.setdefault("SECRET_KEY",            "seed-secret-key-change-in-production-32c")
os.environ.setdefault("AWS_ACCESS_KEY_ID",     "dummy")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "dummy")
os.environ.setdefault("ENVIRONMENT",           "development")

sys.path.insert(0, os.path.dirname(__file__))

# 2 users × 4 roles = 8 demo accounts
SEED_USERS = [
    # role          email                          username         full_name             password
    ("super_admin", "superadmin1@lbro.local",     "superadmin1",   "Super Admin One",   "SuperAdmin@LBRO1!"),
    ("super_admin", "superadmin2@lbro.local",     "superadmin2",   "Super Admin Two",   "SuperAdmin@LBRO2!"),
    ("admin",       "admin1@lbro.local",           "admin1",        "Admin One",         "Admin@LBRO1!2026"),
    ("admin",       "admin2@lbro.local",           "admin2",        "Admin Two",         "Admin@LBRO2!2026"),
    ("analyst",     "analyst1@lbro.local",         "analyst1",      "Analyst One",       "Analyst@LBRO1!2026"),
    ("analyst",     "analyst2@lbro.local",         "analyst2",      "Analyst Two",       "Analyst@LBRO2!2026"),
    ("viewer",      "viewer1@lbro.local",          "viewer1",       "Viewer One",        "Viewer@LBRO1!2026"),
    ("viewer",      "viewer2@lbro.local",          "viewer2",       "Viewer Two",        "Viewer@LBRO2!2026"),
]


async def main():
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    import app.models  # noqa: F401 — register all ORM models
    from app.database import Base
    from app.models.user import User
    from app.core.security import hash_password
    from app.config import settings

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    created = updated = 0
    async with SessionLocal() as db:
        for (role, email, username, full_name, password) in SEED_USERS:
            result = await db.execute(select(User).where(User.email == email))
            existing = result.scalar_one_or_none()
            if existing:
                existing.hashed_password = hash_password(password)
                existing.role            = role
                existing.is_active       = True
                existing.is_verified     = True
                updated += 1
                status = "updated"
            else:
                db.add(User(
                    id=uuid.uuid4(),
                    email=email,
                    username=username,
                    full_name=full_name,
                    hashed_password=hash_password(password),
                    role=role,
                    is_active=True,
                    is_verified=True,
                    mfa_enabled=False,
                    failed_login_attempts=0,
                ))
                created += 1
                status = "created"
            print(f"  [{status}]  {role:<12}  {email:<32}  {password}")

        await db.commit()

    print()
    print("═" * 65)
    print("  LBRO demo accounts ready")
    print("═" * 65)
    print(f"  {'ROLE':<13} {'EMAIL':<32} {'PASSWORD'}")
    print("─" * 65)
    for (role, email, _, _, password) in SEED_USERS:
        print(f"  {role:<13} {email:<32} {password}")
    print("═" * 65)
    print(f"\n  Created: {created}   Updated: {updated}   Total: {created + updated}")


asyncio.run(main())
