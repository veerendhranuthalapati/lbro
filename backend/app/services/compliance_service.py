"""Compliance obligation generator and persistence service for GDPR, HIPAA, DPDPA."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compliance import ComplianceRecord, ComplianceObligation, ComplianceAssessment
from app.models.incident import Incident
from app.schemas.compliance import ObligationCreate, ObligationUpdate


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
        "hours": 60 * 24,
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
            matched = any(j in rules["jurisdictions"] for j in jurisdictions)
            if regulation == "HIPAA" and incident.health_data_involved:
                matched = True
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

    async def get_dashboard(self, project_id: Optional[uuid.UUID] = None) -> dict:
        now = datetime.now(timezone.utc)
        summaries = []

        def _base(q):
            """Join through incidents to filter by project when needed."""
            if project_id is not None:
                q = q.join(Incident, ComplianceRecord.incident_id == Incident.id).where(
                    Incident.project_id == project_id
                )
            return q

        for regulation in REGULATION_RULES:
            total = (await self.db.execute(
                _base(select(func.count(ComplianceRecord.id))).where(
                    ComplianceRecord.regulation == regulation
                )
            )).scalar_one()

            met = (await self.db.execute(
                _base(select(func.count(ComplianceRecord.id))).where(
                    ComplianceRecord.regulation == regulation,
                    ComplianceRecord.is_met == True,
                )
            )).scalar_one()

            overdue = (await self.db.execute(
                _base(select(func.count(ComplianceRecord.id))).where(
                    ComplianceRecord.regulation == regulation,
                    ComplianceRecord.is_met == False,
                    ComplianceRecord.deadline < now,
                )
            )).scalar_one()

            summaries.append({
                "regulation": regulation,
                "total": total,
                "met": met,
                "overdue": overdue,
                "pending": total - met - overdue,
            })

        overdue_q = _base(select(ComplianceRecord)).where(
            ComplianceRecord.is_met == False, ComplianceRecord.deadline < now
        ).order_by(ComplianceRecord.deadline.asc()).limit(20)
        overdue_records = (await self.db.execute(overdue_q)).scalars().all()

        upcoming_q = _base(select(ComplianceRecord)).where(
            ComplianceRecord.is_met == False,
            ComplianceRecord.deadline >= now,
            ComplianceRecord.deadline <= now + timedelta(hours=48),
        ).order_by(ComplianceRecord.deadline.asc()).limit(20)
        upcoming_records = (await self.db.execute(upcoming_q)).scalars().all()

        return {
            "summaries": summaries,
            "overdue_records": overdue_records,
            "upcoming_deadlines": upcoming_records,
        }

    async def mark_met(self, record_id: uuid.UUID, notes: str = "", project_id: Optional[uuid.UUID] = None) -> ComplianceRecord:
        from app.core.exceptions import NotFoundError
        query = select(ComplianceRecord).where(ComplianceRecord.id == record_id)
        if project_id is not None:
            query = (
                query.join(Incident, ComplianceRecord.incident_id == Incident.id)
                .where(Incident.project_id == project_id)
            )
        result = await self.db.execute(query)
        record = result.scalar_one_or_none()
        if not record:
            raise NotFoundError("Compliance record")
        record.is_met = True
        record.met_at = datetime.now(timezone.utc)
        if notes:
            record.notes = notes
        await self.db.flush()
        return record

    # -----------------------------------------------------------------------
    # Project-scoped obligation persistence (replaces localStorage in frontend)
    # -----------------------------------------------------------------------

    async def get_obligations(
        self,
        project_id: uuid.UUID,
        framework: Optional[str] = None,
    ) -> list[ComplianceObligation]:
        """Return all obligations for a project, optionally filtered by framework."""
        q = select(ComplianceObligation).where(
            ComplianceObligation.project_id == project_id
        )
        if framework:
            q = q.where(ComplianceObligation.framework == framework)
        q = q.order_by(ComplianceObligation.framework, ComplianceObligation.control_id)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def upsert_obligation(
        self,
        project_id: uuid.UUID,
        data: ObligationCreate,
    ) -> ComplianceObligation:
        """Create or update an obligation identified by (project_id, framework, control_id)."""
        result = await self.db.execute(
            select(ComplianceObligation).where(
                ComplianceObligation.project_id == project_id,
                ComplianceObligation.framework == data.framework,
                ComplianceObligation.control_id == data.control_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Update mutable fields only when a value is provided
            for field in ("control_name", "description", "status", "evidence_reference", "recommendations"):
                value = getattr(data, field, None)
                if value is not None:
                    setattr(existing, field, value)
            existing.last_updated = datetime.now(timezone.utc)
            # Score: compliant -> 100, not_started -> 0, everything else stays
            if data.status == "compliant":
                existing.score = 100.0
            elif data.status == "not_started":
                existing.score = 0.0
            await self.db.flush()
            return existing

        # Create new
        score = 100.0 if data.status == "compliant" else 0.0
        obligation = ComplianceObligation(
            project_id=project_id,
            framework=data.framework,
            control_id=data.control_id,
            control_name=data.control_name,
            description=data.description,
            status=data.status,
            evidence_reference=data.evidence_reference,
            recommendations=data.recommendations,
            score=score,
            last_updated=datetime.now(timezone.utc),
        )
        self.db.add(obligation)
        await self.db.flush()
        return obligation

    async def update_obligation(
        self,
        obligation_id: uuid.UUID,
        data: ObligationUpdate,
    ) -> ComplianceObligation:
        """Update an obligation by its primary key."""
        from app.core.exceptions import NotFoundError
        result = await self.db.execute(
            select(ComplianceObligation).where(ComplianceObligation.id == obligation_id)
        )
        obligation = result.scalar_one_or_none()
        if not obligation:
            raise NotFoundError("Compliance obligation")

        if data.status is not None:
            obligation.status = data.status
            # Auto-compute score when status changes
            if data.score is None:
                obligation.score = 100.0 if data.status == "compliant" else 0.0
        if data.evidence_reference is not None:
            obligation.evidence_reference = data.evidence_reference
        if data.recommendations is not None:
            obligation.recommendations = data.recommendations
        if data.score is not None:
            obligation.score = data.score
        obligation.last_updated = datetime.now(timezone.utc)
        await self.db.flush()
        return obligation

    async def get_score(
        self,
        project_id: uuid.UUID,
        framework: Optional[str] = None,
    ) -> dict:
        """Compute compliance score from DB obligations for a project."""
        q = select(ComplianceObligation).where(
            ComplianceObligation.project_id == project_id
        )
        if framework:
            q = q.where(ComplianceObligation.framework == framework)
        result = await self.db.execute(q)
        obligations = list(result.scalars().all())

        total = len(obligations)
        compliant = sum(1 for o in obligations if o.status == "compliant")
        non_compliant = sum(1 for o in obligations if o.status == "non_compliant")
        in_progress = sum(1 for o in obligations if o.status == "in_progress")
        overall_score = round((compliant / total * 100) if total > 0 else 0.0, 2)

        return {
            "project_id": project_id,
            "framework": framework,
            "overall_score": overall_score,
            "total_controls": total,
            "compliant_controls": compliant,
            "non_compliant_controls": non_compliant,
            "in_progress_controls": in_progress,
        }

    async def create_assessment(
        self,
        project_id: uuid.UUID,
        framework: str,
        notes: Optional[str] = None,
    ) -> ComplianceAssessment:
        """Compute current score and persist it as a point-in-time assessment."""
        score_data = await self.get_score(project_id, framework)
        assessment = ComplianceAssessment(
            project_id=project_id,
            framework=framework,
            overall_score=score_data["overall_score"],
            total_controls=score_data["total_controls"],
            compliant_controls=score_data["compliant_controls"],
            assessment_date=datetime.now(timezone.utc),
            notes=notes,
        )
        self.db.add(assessment)
        await self.db.flush()
        return assessment

    async def get_assessments(
        self,
        project_id: uuid.UUID,
        framework: Optional[str] = None,
    ) -> list[ComplianceAssessment]:
        """Return assessments for a project, newest first."""
        q = select(ComplianceAssessment).where(
            ComplianceAssessment.project_id == project_id
        )
        if framework:
            q = q.where(ComplianceAssessment.framework == framework)
        q = q.order_by(ComplianceAssessment.assessment_date.desc())
        result = await self.db.execute(q)
        return list(result.scalars().all())
