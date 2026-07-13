"""
Diagnostic script — run from backend/ directory:
    .venv\Scripts\python.exe check_auth.py
"""
import asyncio
import os
import sys

os.environ.setdefault("DATABASE_URL",          "postgresql+asyncpg://lbro:lbro@localhost:5432/lbro")
os.environ.setdefault("SECRET_KEY",            "change-me-generate-with-secrets-token-urlsafe-32")
os.environ.setdefault("AWS_ACCESS_KEY_ID",     "dummy")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "dummy")
os.environ.setdefault("ENVIRONMENT",           "development")

sys.path.insert(0, os.path.dirname(__file__))

EMAIL = "priya.sharma@lbro.demo"
PASSWORD = "Admin@Demo1!"

async def main():
    print("=" * 60)
    print("LBRO Auth Diagnostic")
    print("=" * 60)

    # 1. Database connectivity
    print("\n[1] Testing database connection...")
    try:
        from sqlalchemy import text
        from app.database import engine
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        print("    PASS: Database reachable")
    except Exception as e:
        print(f"    FAIL: Cannot connect to database")
        print(f"          {type(e).__name__}: {e}")
        print("\nStop: fix database connectivity before proceeding.")
        return

    # 2. Users table exists
    print("\n[2] Checking users table exists...")
    try:
        from sqlalchemy import text
        from app.database import engine
        async with engine.connect() as conn:
            r = await conn.execute(text("SELECT COUNT(*) FROM users"))
            count = r.scalar()
        print(f"    PASS: users table exists ({count} row(s))")
    except Exception as e:
        print(f"    FAIL: {type(e).__name__}: {e}")
        print("    Tables not created. Run: alembic upgrade head")
        return

    # 3. User record
    print(f"\n[3] Looking up user: {EMAIL}")
    try:
        from sqlalchemy import text
        from app.database import engine
        async with engine.connect() as conn:
            r = await conn.execute(text(
                "SELECT email, role, is_active, locked_until, failed_login_attempts, hashed_password "
                "FROM users WHERE email = :email"
            ), {"email": EMAIL})
            row = r.fetchone()
        if row is None:
            print(f"    FAIL: No user with email '{EMAIL}' exists in the database.")
            print("    Fix: run  .venv\\Scripts\\python.exe seed_admin.py")
            return
        print(f"    PASS: User found")
        print(f"          role={row.role}  is_active={row.is_active}")
        print(f"          locked_until={row.locked_until}  failed_attempts={row.failed_login_attempts}")
    except Exception as e:
        print(f"    FAIL: {type(e).__name__}: {e}")
        return

    # 4. Password verification
    print(f"\n[4] Verifying password...")
    try:
        from app.core.security import verify_password
        ok = verify_password(PASSWORD, row.hashed_password)
        if ok:
            print(f"    PASS: Password '{PASSWORD}' is correct")
        else:
            print(f"    FAIL: Password '{PASSWORD}' does NOT match the stored hash")
            print("    Fix: re-run seed_admin.py to reset the password")
    except Exception as e:
        print(f"    FAIL: {type(e).__name__}: {e}")
        return

    # 5. Token generation
    print(f"\n[5] Testing JWT generation...")
    try:
        from app.core.security import create_access_token, create_refresh_token
        at = create_access_token(str(row.email), extra={"role": row.role})
        rt = create_refresh_token(str(row.email))
        print(f"    PASS: access_token  = {at[:40]}...")
        print(f"    PASS: refresh_token = {rt[:40]}...")
    except Exception as e:
        print(f"    FAIL: {type(e).__name__}: {e}")
        return

    print("\n" + "=" * 60)
    print("All checks passed. Authentication should work.")
    print("=" * 60)

asyncio.run(main())
