"""Compliance obligation generator for GDPR, HIPAA, DPDPA."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.compliance import ComplianceRecord
from app.models.incident import Incident
from app.models.notification import Notification


REGULATION_RULES = {
    "GDPR": {
        "jurisdictions": ["EU", "EEA", "UK"],
        "hours": 72,
        "authority": "Data Protection Authority",
        "obligations": [
            "Notify supervisory authority within 72 hours of becoming aware",
            "Notify affected data subjects without undue delay if high risk",
            "Document the breach in Article 33(5) register",
            "Assess risk to natural persons",
        ],
    },
    "HIPAA": {
        "jurisdictions": ["US"],
        "hours": 60 * 24,  # 60 days for HHS, immediate for individuals if >500
        "authority": "HHS Office for Civil Rights",
        "obligations": [
            "Notify HHS within 60 days of discovery",
            "Notify affected individuals without unreasonable delay",
            "Notify media if breach affects >500 residents of a state",
            "Maintain breach log for 6 years",
        ],
    },
    "DPDPA": {
        "jurisdictions": ["IN"],
        "hours": 72,
        "authority": "Data Protection Board of India",
        "obligations": [
            "Notify Data Protection Board within 72 hours",
            "Notify affected data principals",
            "Submit detailed breach report",
        ],
    },
}


class ComplianceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_obligations(self, incident: Incident) -> list[ComplianceRecord]:
        records = []
        now = datetime.now(timezone.utc)
        jurisdictions = incident.affected_jurisdictions or []

        for regulation, rules in REGULATION_RULES.items():
            # Check if any jurisdiction matches
            matched = any(j in rules["jurisdictions"] for j in jurisdictions)

            # Also trigger HIPAA if health data involved
            if regulation == "HIPAA" and incident.health_data_involved:
                matched = True
            # Trigger GDPR/DPDPA if personal data involved
            if regulation in ("GDPR", "DPDPA") and incident.personal_data_involved:
                matched = True

            if not matched:
                continue

            deadline = now + timedelta(hours=rules["hours"])

            for obligation in rules["obligations"]:
                record = ComplianceRecord(
                    incident_id=incident.id,
                    regulation=regulation,
                    jurisdiction=",".join(rules["jurisdictions"]),
                    obligation=obligation,
                    deadline=deadline,
                )
                self.db.add(record)
                records.append(record)

        await self.db.flush()
        return records

    async def get_dashboard(self) -> dict:
        now = datetime.now(timezone.utc)
        summaries = []

        for regulation in REGULATION_RULES:
            total = (
                await self.db.execute(
                    select(func.count(ComplianceRecord.id)).where(
                        ComplianceRecord.regulation == regulation
                    )
                )
            ).scalar_one()

            met = (
                await self.db.execute(
                    select(func.count(ComplianceRecord.id)).where(
                        ComplianceRecord.regulation == regulation,
                        ComplianceRecord.is_met == True,
                    )
                )
            ).scalar_one()

            overdue = (
                await self.db.execute(
                    select(func.count(ComplianceRecord.id)).where(
                        ComplianceRecord.regulation == regulation,
                        ComplianceRecord.is_met == False,
                        ComplianceRecord.deadline < now,
                    )
                )
            ).scalar_one()

            summaries.append({
                "regulation": regulation,
                "total": total,
                "met": met,
                "overdue": overdue,
                "pending": total - met - overdue,
            })

        # Overdue records
        overdue_result = await self.db.execute(
            select(ComplianceRecord)
            .where(ComplianceRecord.is_met == False, ComplianceRecord.deadline < now)
            .order_by(ComplianceRecord.deadline.asc())
            .limit(20)
        )
        overdue_records = overdue_result.scalars().all()

        # Upcoming (next 48h)
        upcoming_result = await self.db.execute(
            select(ComplianceRecord)
            .where(
                ComplianceRecord.is_met == False,
                ComplianceRecord.deadline >= now,
                ComplianceRecord.deadline <= now + timedelta(hours=48),
            )
            .order_by(ComplianceRecord.deadline.asc())
            .limit(20)
        )
        upcoming_records = upcoming_result.scalars().all()

        return {
            "summaries": summaries,
            "overdue_records": overdue_records,
            "upcoming_deadlines": upcoming_records,
        }

    async def mark_met(self, record_id: uuid.UUID, notes: str = "") -> ComplianceRecord:
        from app.core.exceptions import NotFoundError
        result = await self.db.execute(
            select(ComplianceRecord).where(ComplianceRecord.id == record_id)
        )
        record = result.scalar_one_or_none()
        if not record:
            raise NotFoundError("Compliance record")
        record.is_met = True
        record.met_at = datetime.now(timezone.utc)
        record.notes = notes
        await self.db.flush()
        return record
