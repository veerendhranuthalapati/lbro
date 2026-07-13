"""Incident CRUD and orchestration service."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, ConflictError
from app.models.incident import Incident, IncidentAction, IncidentStatus, IncidentSeverity
from app.models.user import User
from app.schemas.incident import IncidentCreate, IncidentUpdate
from app.services.sqs_service import sqs_service


class IncidentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        data: IncidentCreate,
        created_by: User,
        project_id: Optional[uuid.UUID] = None,
    ) -> Incident:
        features = data.network_features.model_dump() if data.network_features else None

        year = datetime.now(timezone.utc).year
        short_id = uuid.uuid4().hex[:6].upper()
        external_id = f"INC-{year}-{short_id}"

        incident = Incident(
            external_id=external_id,
            title=data.title,
            description=data.description,
            severity=data.severity or IncidentSeverity.MEDIUM.value,
            status=IncidentStatus.NEW.value,
            source_ip=data.source_ip,
            destination_ip=data.destination_ip,
            source_port=data.source_port,
            destination_port=data.destination_port,
            protocol=data.protocol,
            network_features=features,
            affected_jurisdictions=data.affected_jurisdictions,
            personal_data_involved=data.personal_data_involved,
            health_data_involved=data.health_data_involved,
            created_by=created_by.id,
            project_id=project_id,
        )
        self.db.add(incident)
        await self.db.flush()

        action = IncidentAction(
            incident_id=incident.id,
            action_type="created",
            description=f"Incident created by {created_by.full_name}",
            performed_by=created_by.id,
            automated=False,
        )
        self.db.add(action)
        await self.db.flush()

        if features:
            try:
                sqs_service.enqueue_incident(str(incident.id), "classify")
            except Exception:
                pass

        return incident

    async def get(self, incident_id: uuid.UUID, project_id: Optional[uuid.UUID] = None) -> Incident:
        query = (
            select(Incident)
            .where(Incident.id == incident_id)
            .options(selectinload(Incident.actions))
        )
        if project_id is not None:
            query = query.where(Incident.project_id == project_id)
        result = await self.db.execute(query)
        incident = result.scalar_one_or_none()
        if not incident:
            raise NotFoundError("Incident")
        return incident

    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        assigned_to: Optional[uuid.UUID] = None,
        needs_review: Optional[bool] = None,
        search: Optional[str] = None,
        project_id: Optional[uuid.UUID] = None,
    ) -> tuple[list[Incident], int]:
        query = select(Incident).options(selectinload(Incident.actions))
        count_query = select(func.count(Incident.id))

        if project_id is not None:
            query = query.where(Incident.project_id == project_id)
            count_query = count_query.where(Incident.project_id == project_id)
        if status:
            query = query.where(Incident.status == status)
            count_query = count_query.where(Incident.status == status)
        if severity:
            query = query.where(Incident.severity == severity)
            count_query = count_query.where(Incident.severity == severity)
        if assigned_to:
            query = query.where(Incident.assigned_to == assigned_to)
            count_query = count_query.where(Incident.assigned_to == assigned_to)
        if needs_review is not None:
            query = query.where(Incident.needs_analyst_review == needs_review)
            count_query = count_query.where(Incident.needs_analyst_review == needs_review)
        if search:
            query = query.where(Incident.title.ilike(f"%{search}%"))
            count_query = count_query.where(Incident.title.ilike(f"%{search}%"))

        total = (await self.db.execute(count_query)).scalar_one()
        query = (
            query.order_by(Incident.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        return result.scalars().all(), total

    async def update(self, incident_id: uuid.UUID, data: IncidentUpdate, actor: User) -> Incident:
        incident = await self.get(incident_id)
        changes = []

        for field, value in data.model_dump(exclude_none=True).items():
            old = getattr(incident, field)
            if old != value:
                setattr(incident, field, value)
                changes.append(f"{field}: {old} → {value}")

        if changes:
            action = IncidentAction(
                incident_id=incident.id,
                action_type="updated",
                description=f"Updated by {actor.full_name}: {'; '.join(changes)}",
                performed_by=actor.id,
                automated=False,
            )
            self.db.add(action)

        await self.db.flush()
        return incident

    async def transition_status(
        self, incident_id: uuid.UUID, new_status: str, actor: User, notes: str = ""
    ) -> Incident:
        incident = await self.get(incident_id)

        valid_transitions = {
            IncidentStatus.NEW.value: [IncidentStatus.TRIAGING.value],
            IncidentStatus.TRIAGING.value: [IncidentStatus.CONTAINED.value, IncidentStatus.CLOSED.value],
            IncidentStatus.CONTAINED.value: [IncidentStatus.ERADICATING.value, IncidentStatus.CLOSED.value],
            IncidentStatus.ERADICATING.value: [IncidentStatus.RECOVERING.value],
            IncidentStatus.RECOVERING.value: [IncidentStatus.CLOSED.value],
            IncidentStatus.CLOSED.value: [IncidentStatus.REOPENED.value],
            IncidentStatus.REOPENED.value: [IncidentStatus.TRIAGING.value, IncidentStatus.CLOSED.value],
        }

        allowed = valid_transitions.get(incident.status, [])
        if new_status not in allowed:
            raise ConflictError(
                f"Cannot transition from '{incident.status}' to '{new_status}'. "
                f"Allowed: {allowed}"
            )

        old_status = incident.status
        incident.status = new_status

        if new_status == IncidentStatus.CLOSED.value:
            incident.closed_at = datetime.now(timezone.utc)
        elif new_status == IncidentStatus.REOPENED.value:
            incident.closed_at = None

        action = IncidentAction(
            incident_id=incident.id,
            action_type="status_change",
            description=f"Status changed from '{old_status}' to '{new_status}' by {actor.full_name}. {notes}".strip(),
            performed_by=actor.id,
            automated=False,
        )
        self.db.add(action)
        await self.db.flush()
        return incident

    async def delete(self, incident_id: uuid.UUID) -> None:
        incident = await self.get(incident_id)
        await self.db.delete(incident)
        await self.db.flush()

    async def get_stats(self, project_id: Optional[uuid.UUID] = None) -> dict:
        def _filter(q):
            if project_id is not None:
                q = q.where(Incident.project_id == project_id)
            return q

        total = (await self.db.execute(_filter(select(func.count(Incident.id))))).scalar_one()

        by_status = {}
        for status in IncidentStatus:
            count = (await self.db.execute(
                _filter(select(func.count(Incident.id))).where(Incident.status == status.value)
            )).scalar_one()
            by_status[status.value] = count

        by_severity = {}
        for severity in IncidentSeverity:
            count = (await self.db.execute(
                _filter(select(func.count(Incident.id))).where(Incident.severity == severity.value)
            )).scalar_one()
            by_severity[severity.value] = count

        needs_review = (await self.db.execute(
            _filter(select(func.count(Incident.id))).where(Incident.needs_analyst_review == True)
        )).scalar_one()

        return {
            "total": total,
            "by_status": by_status,
            "by_severity": by_severity,
            "needs_analyst_review": needs_review,
        }
