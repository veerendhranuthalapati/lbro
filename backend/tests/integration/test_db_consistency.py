"""
Database consistency tests — LBRO
Verifies that API operations produce the correct DB state:
- Row counts after create/delete
- SHA256 hash integrity stored in evidence
- Compliance obligation uniqueness constraint (upsert)
- Soft delete vs hard delete semantics
- No plain-text passwords in users table
"""
from __future__ import annotations

import hashlib
import io
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.incident import Incident
from app.models.evidence import Evidence
from app.models.user import User
from app.models.compliance import ComplianceObligation


class TestIncidentConsistency:
    async def test_create_incident_adds_exactly_one_row(
        self, client: AsyncClient, alice_h: dict,
        portfolio_project: dict, db: AsyncSession
    ):
        before = (await db.execute(select(func.count(Incident.id)))).scalar_one()

        resp = await client.post("/api/v1/incidents", json={
            "title": "DB Consistency Check Incident",
            "severity": "low",
            "project_id": portfolio_project["id"],
        }, headers=alice_h)
        assert resp.status_code == 201

        after = (await db.execute(select(func.count(Incident.id)))).scalar_one()
        assert after == before + 1

    async def test_delete_incident_removes_row(
        self, client: AsyncClient, alice_h: dict,
        portfolio_project: dict, db: AsyncSession
    ):
        # Create
        create_resp = await client.post("/api/v1/incidents", json={
            "title": "Incident To Be Deleted",
            "severity": "info",
            "project_id": portfolio_project["id"],
        }, headers=alice_h)
        assert create_resp.status_code == 201
        incident_id = create_resp.json()["id"]

        before = (await db.execute(select(func.count(Incident.id)))).scalar_one()

        # Delete
        del_resp = await client.delete(
            f"/api/v1/incidents/{incident_id}",
            headers=alice_h,
        )
        assert del_resp.status_code in (200, 204)

        after = (await db.execute(select(func.count(Incident.id)))).scalar_one()
        assert after == before - 1

    async def test_incident_row_stores_correct_project_id(
        self, client: AsyncClient, alice_h: dict,
        portfolio_project: dict, db: AsyncSession
    ):
        resp = await client.post("/api/v1/incidents", json={
            "title": "Project ID DB Verification",
            "severity": "medium",
            "project_id": portfolio_project["id"],
        }, headers=alice_h)
        assert resp.status_code == 201
        incident_id = uuid.UUID(resp.json()["id"])

        row = (await db.execute(
            select(Incident).where(Incident.id == incident_id)
        )).scalar_one_or_none()

        assert row is not None
        assert str(row.project_id) == portfolio_project["id"]


class TestEvidenceConsistency:
    async def test_evidence_sha256_in_db_matches_uploaded_content(
        self, client: AsyncClient, alice_h: dict,
        sql_injection_incident: dict, db: AsyncSession
    ):
        content = b"exact content for sha256 verification in database"
        expected_hash = hashlib.sha256(content).hexdigest()

        resp = await client.post(
            f"/api/v1/incidents/{sql_injection_incident['id']}/evidence",
            files={"file": ("verify.txt", io.BytesIO(content), "text/plain")},
            headers=alice_h,
        )
        assert resp.status_code == 201
        evidence_id = uuid.UUID(resp.json()["id"])

        row = (await db.execute(
            select(Evidence).where(Evidence.id == evidence_id)
        )).scalar_one_or_none()

        assert row is not None
        assert row.sha256_hash == expected_hash

    async def test_evidence_file_size_stored_correctly(
        self, client: AsyncClient, alice_h: dict,
        sql_injection_incident: dict, db: AsyncSession
    ):
        content = b"A" * 512  # exactly 512 bytes
        resp = await client.post(
            f"/api/v1/incidents/{sql_injection_incident['id']}/evidence",
            files={"file": ("sized.txt", io.BytesIO(content), "text/plain")},
            headers=alice_h,
        )
        assert resp.status_code == 201
        evidence_id = uuid.UUID(resp.json()["id"])

        row = (await db.execute(
            select(Evidence).where(Evidence.id == evidence_id)
        )).scalar_one_or_none()

        assert row is not None
        assert row.file_size == 512

    async def test_delete_mutable_evidence_removes_db_row(
        self, client: AsyncClient, alice_h: dict,
        sql_injection_incident: dict, portfolio_project: dict, db: AsyncSession
    ):
        """Create evidence with is_immutable=False directly, then verify deletion removes the row."""
        ev_id = uuid.uuid4()
        ev = Evidence(
            id=ev_id,
            incident_id=uuid.UUID(sql_injection_incident["id"]),
            filename="db_del_test.txt",
            original_filename="db_del_test.txt",
            content_type="text/plain",
            file_size=10,
            sha256_hash="b" * 64,
            is_immutable=False,
        )
        db.add(ev)
        await db.flush()

        # Confirm row exists
        row_before = (await db.execute(
            select(Evidence).where(Evidence.id == ev_id)
        )).scalar_one_or_none()
        assert row_before is not None

        # Delete via API
        del_resp = await client.delete(
            f"/api/v1/evidence/{ev_id}",
            params={"project_id": portfolio_project["id"]},
            headers=alice_h,
        )
        assert del_resp.status_code in (200, 204)

        # Row must be gone
        row_after = (await db.execute(
            select(Evidence).where(Evidence.id == ev_id)
        )).scalar_one_or_none()
        assert row_after is None


class TestUserSecurityConsistency:
    async def test_no_plain_text_passwords_in_users_table(
        self, client: AsyncClient, db: AsyncSession, alice, bob, carol  # noqa: ARG002
    ):
        """All user rows must have bcrypt-hashed passwords, never plain text."""
        users = (await db.execute(select(User))).scalars().all()
        assert len(users) >= 3

        for user in users:
            # bcrypt hashes start with $2b$ or $2a$
            assert user.hashed_password.startswith(("$2b$", "$2a$")), (
                f"User {user.email} has non-bcrypt password hash: {user.hashed_password[:20]}"
            )
            # Verify the plain password is NOT stored
            assert "Demo1!" not in user.hashed_password
            assert "Alice@" not in user.hashed_password

    async def test_registered_user_gets_viewer_role_by_default(
        self, client: AsyncClient, db: AsyncSession
    ):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "newuser_role@test.com",
            "full_name": "New Role User",
            "password": "NewUser@Pass1!",
        })
        assert resp.status_code == 201

        user = (await db.execute(
            select(User).where(User.email == "newuser_role@test.com")
        )).scalar_one_or_none()

        assert user is not None
        assert user.role == "viewer"


class TestComplianceConsistency:
    async def test_compliance_upsert_does_not_create_duplicate_rows(
        self, client: AsyncClient, alice_h: dict,
        portfolio_project: dict, db: AsyncSession
    ):
        payload = {
            "framework": "GDPR",
            "control_id": "UniqueConstraintTest", "control_name": "UniqueConstraintTest",
            "description": "Test upsert row count",
            "status": "not_started",
        }
        params = {"project_id": portfolio_project["id"]}

        await client.post("/api/v1/compliance/obligations", json=payload, params=params, headers=alice_h)
        count1 = (await db.execute(
            select(func.count(ComplianceObligation.id)).where(
                ComplianceObligation.control_id == "UniqueConstraintTest"
            )
        )).scalar_one()

        # Second call — must update, not insert
        payload["status"] = "in_progress"
        await client.post("/api/v1/compliance/obligations", json=payload, params=params, headers=alice_h)
        count2 = (await db.execute(
            select(func.count(ComplianceObligation.id)).where(
                ComplianceObligation.control_id == "UniqueConstraintTest"
            )
        )).scalar_one()

        assert count1 == 1
        assert count2 == 1  # upsert — still exactly one row

    async def test_compliance_obligation_stored_with_correct_project_id(
        self, client: AsyncClient, alice_h: dict,
        portfolio_project: dict, db: AsyncSession
    ):
        resp = await client.post(
            "/api/v1/compliance/obligations",
            json={
                "framework": "ISO27001",
                "control_id": "ProjectIDCheck", "control_name": "ProjectIDCheck",
                "description": "Verify project_id stored",
                "status": "not_started",
            },
            params={"project_id": portfolio_project["id"]},
            headers=alice_h,
        )
        assert resp.status_code == 200
        ob_id = uuid.UUID(resp.json()["id"])

        row = (await db.execute(
            select(ComplianceObligation).where(ComplianceObligation.id == ob_id)
        )).scalar_one_or_none()

        assert row is not None
        assert str(row.project_id) == portfolio_project["id"]
