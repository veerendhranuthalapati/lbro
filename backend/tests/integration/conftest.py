"""
Integration-test fixtures — LBRO

Builds on the root tests/conftest.py (SQLite in-memory, `db`, `client`).
Adds Alice / Bob / Carol user fixtures and seeded project / incident / evidence data.

Role assignments:
  alice  — admin     (owns Portfolio + Ecommerce projects)
  bob    — analyst   (owns Hospital project)
  carol  — viewer    (no owned projects)

The root conftest's `db` fixture wraps every test in an outer transaction that is
rolled back on teardown, so no data leaks between tests.
"""
from __future__ import annotations

import io
import uuid

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User


# ── Users ─────────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def alice(db: AsyncSession) -> User:
    """Admin user — owns Portfolio and Ecommerce projects."""
    user = User(
        id=uuid.uuid4(),
        email="alice@test.com",
        username="alice",
        full_name="Alice Admin",
        hashed_password=hash_password("Alice@Demo1!"),
        role="admin",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def bob(db: AsyncSession) -> User:
    """Analyst user — owns Hospital project."""
    user = User(
        id=uuid.uuid4(),
        email="bob@test.com",
        username="bob",
        full_name="Bob Analyst",
        hashed_password=hash_password("Bob@Demo1!"),
        role="analyst",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def carol(db: AsyncSession) -> User:
    """Viewer user — no owned projects."""
    user = User(
        id=uuid.uuid4(),
        email="carol@test.com",
        username="carol",
        full_name="Carol Viewer",
        hashed_password=hash_password("Carol@Demo1!"),
        role="viewer",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.flush()
    return user


# ── Tokens ────────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def alice_token(client: AsyncClient, alice: User) -> str:  # noqa: ARG001
    resp = await client.post("/api/v1/auth/login", json={
        "email": "alice@test.com",
        "password": "Alice@Demo1!",
    })
    assert resp.status_code == 200, f"Alice login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def bob_token(client: AsyncClient, bob: User) -> str:  # noqa: ARG001
    resp = await client.post("/api/v1/auth/login", json={
        "email": "bob@test.com",
        "password": "Bob@Demo1!",
    })
    assert resp.status_code == 200, f"Bob login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def carol_token(client: AsyncClient, carol: User) -> str:  # noqa: ARG001
    resp = await client.post("/api/v1/auth/login", json={
        "email": "carol@test.com",
        "password": "Carol@Demo1!",
    })
    assert resp.status_code == 200, f"Carol login failed: {resp.text}"
    return resp.json()["access_token"]


# ── Auth header helpers ────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def alice_h(alice_token: str) -> dict:
    return {"Authorization": f"Bearer {alice_token}"}


@pytest_asyncio.fixture
async def bob_h(bob_token: str) -> dict:
    return {"Authorization": f"Bearer {bob_token}"}


@pytest_asyncio.fixture
async def carol_h(carol_token: str) -> dict:
    return {"Authorization": f"Bearer {carol_token}"}


# ── Projects ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def portfolio_project(client: AsyncClient, alice_h: dict) -> dict:
    resp = await client.post("/api/v1/projects", json={"name": "Portfolio"}, headers=alice_h)
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest_asyncio.fixture
async def ecommerce_project(client: AsyncClient, alice_h: dict) -> dict:
    resp = await client.post("/api/v1/projects", json={"name": "Ecommerce"}, headers=alice_h)
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest_asyncio.fixture
async def hospital_project(client: AsyncClient, bob_h: dict) -> dict:
    resp = await client.post("/api/v1/projects", json={"name": "Hospital"}, headers=bob_h)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Incidents ─────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def sql_injection_incident(
    client: AsyncClient, alice_h: dict, portfolio_project: dict
) -> dict:
    resp = await client.post("/api/v1/incidents", json={
        "title": "SQL Injection in Login Form",
        "severity": "critical",
        "attack_category": "injection",
        "project_id": portfolio_project["id"],
    }, headers=alice_h)
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest_asyncio.fixture
async def port_scan_incident(
    client: AsyncClient, alice_h: dict, portfolio_project: dict
) -> dict:
    resp = await client.post("/api/v1/incidents", json={
        "title": "Port Scan Detected on Perimeter",
        "severity": "medium",
        "attack_category": "reconnaissance",
        "project_id": portfolio_project["id"],
    }, headers=alice_h)
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest_asyncio.fixture
async def brute_force_incident(
    client: AsyncClient, alice_h: dict, ecommerce_project: dict
) -> dict:
    resp = await client.post("/api/v1/incidents", json={
        "title": "Brute Force Attack on Admin Portal",
        "severity": "high",
        "attack_category": "credential_attack",
        "project_id": ecommerce_project["id"],
    }, headers=alice_h)
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest_asyncio.fixture
async def xss_incident(
    client: AsyncClient, bob_h: dict, hospital_project: dict
) -> dict:
    resp = await client.post("/api/v1/incidents", json={
        "title": "Cross-Site Scripting in Patient Portal",
        "severity": "high",
        "attack_category": "xss",
        "project_id": hospital_project["id"],
    }, headers=bob_h)
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest_asyncio.fixture
async def malware_incident(
    client: AsyncClient, bob_h: dict, hospital_project: dict
) -> dict:
    resp = await client.post("/api/v1/incidents", json={
        "title": "Malware Found on Workstation WS-042",
        "severity": "critical",
        "attack_category": "malware",
        "project_id": hospital_project["id"],
    }, headers=bob_h)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Evidence ──────────────────────────────────────────────────────────────────

def _pcap_file() -> bytes:
    """Minimal valid pcap-like binary (just plain bytes, not a real pcap)."""
    return b"PCAP_CAPTURE_DATA_PLACEHOLDER_" + b"\x00" * 100


@pytest_asyncio.fixture
async def portfolio_evidence(
    client: AsyncClient, alice_h: dict, sql_injection_incident: dict
) -> dict:
    resp = await client.post(
        f"/api/v1/incidents/{sql_injection_incident['id']}/evidence",
        files={"file": ("network_capture.txt", io.BytesIO(b"captured sql injection traffic log\n"), "text/plain")},
        data={"description": "Network capture showing SQL injection attempt"},
        headers=alice_h,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest_asyncio.fixture
async def hospital_evidence(
    client: AsyncClient, bob_h: dict, xss_incident: dict
) -> dict:
    resp = await client.post(
        f"/api/v1/incidents/{xss_incident['id']}/evidence",
        files={"file": ("xss_payload.txt", io.BytesIO(b"alert('xss') payload sample evidence"), "text/plain")},
        data={"description": "XSS payload captured from patient portal"},
        headers=bob_h,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Compliance Obligations ────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def portfolio_obligation(
    client: AsyncClient, alice_h: dict, portfolio_project: dict
) -> dict:
    resp = await client.post(
        "/api/v1/compliance/obligations",
        json={
            "framework": "GDPR",
            "control_id": "Art-32",
            "control_name": "Control Art-32",
            "description": "Implement appropriate technical measures",
            "status": "in_progress",
        },
        params={"project_id": portfolio_project["id"]},
        headers=alice_h,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest_asyncio.fixture
async def hospital_obligation(
    client: AsyncClient, bob_h: dict, hospital_project: dict
) -> dict:
    resp = await client.post(
        "/api/v1/compliance/obligations",
        json={
            "framework": "HIPAA",
            "control_id": "164.312(a)(1)",
            "control_name": "Control 164.312(a)(1)",
            "description": "Access control — unique user identification",
            "status": "met",
        },
        params={"project_id": hospital_project["id"]},
        headers=bob_h,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()
