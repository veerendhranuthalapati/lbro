"""Project CRUD and dashboard service."""
from __future__ import annotations

import secrets
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.compliance import ComplianceRecord
from app.models.evidence import Evidence
from app.models.incident import Incident, IncidentSeverity, IncidentStatus
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate, _slugify


class ProjectService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── CRUD ─────────────────────────────────────────────────────────────────

    async def create(self, data: ProjectCreate, owner_id: uuid.UUID) -> Project:
        base_slug = _slugify(data.name)
        slug = await self._unique_slug(base_slug)

        project = Project(
            name=data.name,
            slug=slug,
            description=data.description,
            environment=data.environment,
            status="active",
            owner_id=owner_id,
        )
        self.db.add(project)
        await self.db.flush()
        return project

    async def get(self, project_id: uuid.UUID) -> Project:
        result = await self.db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        if not project:
            raise NotFoundError("Project")
        return project

    async def get_by_slug(self, slug: str) -> Project:
        result = await self.db.execute(
            select(Project).where(Project.slug == slug)
        )
        project = result.scalar_one_or_none()
        if not project:
            raise NotFoundError("Project")
        return project

    async def get_by_api_key(self, api_key: str) -> Optional[Project]:
        """Identify a project by its external API key (for log ingestion)."""
        result = await self.db.execute(
            select(Project).where(Project.api_key == api_key)
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        owner_id: Optional[uuid.UUID] = None,
        include_archived: bool = False,
    ) -> tuple[list[Project], int]:
        """Return all projects visible to a user.

        Admin users pass owner_id=None to see every project.
        Regular users pass their own ID to see only their projects.
        """
        query = select(Project)
        count_q = select(func.count(Project.id))

        if owner_id is not None:
            query = query.where(Project.owner_id == owner_id)
            count_q = count_q.where(Project.owner_id == owner_id)

        if not include_archived:
            query = query.where(Project.status == "active")
            count_q = count_q.where(Project.status == "active")

        query = query.order_by(Project.created_at.desc())
        total = (await self.db.execute(count_q)).scalar_one()
        rows = (await self.db.execute(query)).scalars().all()
        return list(rows), total

    async def update(self, project_id: uuid.UUID, data: ProjectUpdate) -> Project:
        project = await self.get(project_id)

        if data.name is not None:
            project.name = data.name
            # Re-slug only if name changed — keep existing slug for stability
            base_slug = _slugify(data.name)
            project.slug = await self._unique_slug(base_slug, exclude_id=project_id)

        if data.description is not None:
            project.description = data.description

        if data.environment is not None:
            project.environment = data.environment

        if data.status is not None:
            project.status = data.status

        project.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return project

    async def regenerate_api_key(self, project_id: uuid.UUID) -> Project:
        project = await self.get(project_id)
        project.api_key = "proj_" + secrets.token_urlsafe(32)
        project.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return project

    async def delete(self, project_id: uuid.UUID) -> None:
        """Hard-delete a project and all its incidents (CASCADE in DB)."""
        project = await self.get(project_id)
        await self.db.delete(project)
        await self.db.flush()

    # ── Dashboard ─────────────────────────────────────────────────────────────

    async def get_dashboard(self, project_id: uuid.UUID) -> dict:
        """Return aggregated stats for the Project Overview page."""
        now = datetime.now(timezone.utc)
        open_statuses = [s.value for s in IncidentStatus if s != IncidentStatus.CLOSED]

        project = await self.get(project_id)

        # --- Incident counts ---
        open_incidents = (await self.db.execute(
            select(func.count(Incident.id)).where(
                Incident.project_id == project_id,
                Incident.status.in_(open_statuses),
            )
        )).scalar_one()

        critical_incidents = (await self.db.execute(
            select(func.count(Incident.id)).where(
                Incident.project_id == project_id,
                Incident.severity == IncidentSeverity.CRITICAL.value,
                Incident.status.in_(open_statuses),
            )
        )).scalar_one()

        # --- Evidence count (via incidents) ---
        evidence_count = (await self.db.execute(
            select(func.count(Evidence.id))
            .join(Incident, Evidence.incident_id == Incident.id)
            .where(Incident.project_id == project_id)
        )).scalar_one()

        # --- Overdue compliance ---
        overdue_compliance = (await self.db.execute(
            select(func.count(ComplianceRecord.id))
            .join(Incident, ComplianceRecord.incident_id == Incident.id)
            .where(
                Incident.project_id == project_id,
                ComplianceRecord.is_met == False,
                ComplianceRecord.deadline < now,
            )
        )).scalar_one()

        # --- Last activity (most recent incident update) ---
        last_row = (await self.db.execute(
            select(Incident.updated_at)
            .where(Incident.project_id == project_id)
            .order_by(Incident.updated_at.desc())
            .limit(1)
        )).scalar_one_or_none()

        # --- Most common attack category ---
        attack_rows = (await self.db.execute(
            select(Incident.attack_category, func.count(Incident.id).label("cnt"))
            .where(
                Incident.project_id == project_id,
                Incident.attack_category.isnot(None),
            )
            .group_by(Incident.attack_category)
            .order_by(func.count(Incident.id).desc())
            .limit(1)
        )).one_or_none()
        most_common_attack = attack_rows[0] if attack_rows else None

        # --- Most targeted port ---
        port_rows = (await self.db.execute(
            select(Incident.destination_port, func.count(Incident.id).label("cnt"))
            .where(
                Incident.project_id == project_id,
                Incident.destination_port.isnot(None),
            )
            .group_by(Incident.destination_port)
            .order_by(func.count(Incident.id).desc())
            .limit(1)
        )).one_or_none()
        most_targeted_port = port_rows[0] if port_rows else None

        # --- Security score (simplified; mirrors security_score router logic) ---
        score, grade = await self._quick_score(project_id, open_statuses, now)

        # --- Top recommendations ---
        recommendations = []
        if critical_incidents > 0:
            recommendations.append({
                "priority": "critical",
                "title": f"Resolve {critical_incidents} critical incident(s)",
                "link": f"/incidents?severity=critical",
            })
        if overdue_compliance > 0:
            recommendations.append({
                "priority": "medium",
                "title": f"Address {overdue_compliance} overdue compliance item(s)",
                "link": "/compliance",
            })

        return {
            "project_id": project_id,
            "project_name": project.name,
            "environment": project.environment,
            "status": project.status,
            "api_key": project.api_key,
            "security_score": score,
            "security_grade": grade,
            "open_incidents": open_incidents,
            "critical_incidents": critical_incidents,
            "evidence_count": evidence_count,
            "overdue_compliance": overdue_compliance,
            "last_activity": last_row,
            "most_common_attack": most_common_attack,
            "most_targeted_port": most_targeted_port,
            "top_recommendations": recommendations[:3],
        }

    async def _quick_score(
        self,
        project_id: uuid.UUID,
        open_statuses: list[str],
        now: datetime,
    ) -> tuple[int, str]:
        """Lightweight score: only incident + compliance data for this project."""
        open_critical = (await self.db.execute(
            select(func.count(Incident.id)).where(
                Incident.project_id == project_id,
                Incident.severity == IncidentSeverity.CRITICAL.value,
                Incident.status.in_(open_statuses),
            )
        )).scalar_one()

        open_high = (await self.db.execute(
            select(func.count(Incident.id)).where(
                Incident.project_id == project_id,
                Incident.severity == IncidentSeverity.HIGH.value,
                Incident.status.in_(open_statuses),
            )
        )).scalar_one()

        overdue = (await self.db.execute(
            select(func.count(ComplianceRecord.id))
            .join(Incident, ComplianceRecord.incident_id == Incident.id)
            .where(
                Incident.project_id == project_id,
                ComplianceRecord.is_met == False,
                ComplianceRecord.deadline < now,
            )
        )).scalar_one()

        score = 100
        score -= min(open_critical * 15, 45)
        score -= min(open_high * 8, 24)
        score -= min(overdue * 5, 15)
        score = max(0, min(100, score))

        if score >= 90:
            grade = "A"
        elif score >= 75:
            grade = "B"
        elif score >= 60:
            grade = "C"
        elif score >= 40:
            grade = "D"
        else:
            grade = "F"

        return score, grade

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _unique_slug(
        self, base: str, exclude_id: Optional[uuid.UUID] = None
    ) -> str:
        """Append a numeric suffix until the slug is unique."""
        slug = base
        suffix = 1
        while True:
            q = select(Project).where(Project.slug == slug)
            if exclude_id:
                q = q.where(Project.id != exclude_id)
            existing = (await self.db.execute(q)).scalar_one_or_none()
            if not existing:
                return slug
            slug = f"{base}-{suffix}"
            suffix += 1
