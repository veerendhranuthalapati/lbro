"""Persist exposure assessments and inferred compliance obligations."""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.compliance.engine.pipeline import run_exposure_assessment
from app.compliance.engine.serialize import assessment_result_to_dict, trace_to_json
from app.compliance.engine.types import (
    AssetInput,
    ClassificationInput,
    EngineConfigInput,
    IncidentContextInput,
    ResidencyInput,
)
from app.compliance.knowledge.loader import ENGINE_VERSION, knowledge_versions_snapshot
from app.compliance.matching import collect_incident_match_values, match_assets_for_incident
from app.config import settings
from app.core.exceptions import ConflictError, NotFoundError
from app.models.asset import Asset, IncidentAsset, IncidentExposureAssessment
from app.models.compliance import ComplianceRecord
from app.models.incident import Incident, IncidentAction
from app.models.user import User
from app.services.audit_helper import write_audit
from app.services.ml_audit_service import log_ml_system_action
from app.services.sqs_service import sqs_service

logger = logging.getLogger(__name__)


def _classification_from_incident(incident: Incident) -> ClassificationInput:
    meta = {}
    for action in incident.actions or []:
        if action.action_type == "ml_classification" and action.action_metadata:
            meta = action.action_metadata
            break
    return ClassificationInput(
        attack_category=incident.attack_category,
        confidence=float(incident.confidence_score or 0.0),
        source=str(meta.get("source") or "unknown"),
        needs_review=bool(incident.needs_analyst_review),
        ood_flag=bool(meta.get("ood_flag")),
    )


def _asset_inputs(links: list[IncidentAsset]) -> tuple[AssetInput, ...]:
    inputs: list[AssetInput] = []
    for link in links:
        asset = link.asset
        residency = tuple(
            ResidencyInput(
                jurisdiction_code=r.jurisdiction_code,
                record_count=r.record_count,
                count_basis=r.count_basis,
                data_category=r.data_category,
            )
            for r in asset.residency
        )
        inputs.append(
            AssetInput(
                asset_id=str(asset.id),
                name=asset.name,
                data_categories=tuple(asset.data_categories or []),
                residency=residency,
                link_status=link.status,  # type: ignore[arg-type]
                match_confidence=link.match_confidence,  # type: ignore[arg-type]
                exposure_fraction=float(link.exposure_fraction),
            )
        )
    return tuple(inputs)


class ExposureService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_incident_for_exposure(self, incident_id: uuid.UUID) -> Incident:
        q = (
            select(Incident)
            .where(Incident.id == incident_id)
            .options(
                selectinload(Incident.linked_assets).selectinload(IncidentAsset.asset).selectinload(Asset.residency),
                selectinload(Incident.actions),
                selectinload(Incident.project),
            )
        )
        incident = (await self.db.execute(q)).scalar_one_or_none()
        if not incident:
            raise NotFoundError("Incident")
        return incident

    async def auto_match_assets(self, incident: Incident) -> list[IncidentAsset]:
        """Suggest asset links from identifiers; never auto-confirm low-confidence matches."""
        if not incident.project_id:
            return []
        assets = (
            await self.db.execute(
                select(Asset).where(
                    Asset.project_id == incident.project_id,
                    Asset.is_active == True,
                )
            )
        ).scalars().all()
        if not assets:
            return []
        values = collect_incident_match_values(
            source_ip=incident.source_ip,
            destination_ip=incident.destination_ip,
            title=incident.title,
            description=incident.description,
            network_features=incident.network_features,
        )
        asset_dicts = [
            {"id": str(a.id), "name": a.name, "identifiers": a.identifiers or []} for a in assets
        ]
        matches = match_assets_for_incident(asset_dicts, values)
        created: list[IncidentAsset] = []
        for m in matches:
            existing = (
                await self.db.execute(
                    select(IncidentAsset).where(
                        IncidentAsset.incident_id == incident.id,
                        IncidentAsset.asset_id == uuid.UUID(m.asset_id),
                    )
                )
            ).scalar_one_or_none()
            if existing:
                continue
            status = "confirmed" if m.auto_accept else "suggested"
            link = IncidentAsset(
                incident_id=incident.id,
                asset_id=uuid.UUID(m.asset_id),
                link_source="auto_match",
                match_reason=m.match_reason,
                match_confidence=m.match_confidence,
                exposure_fraction=1.0,
                status=status,
                confirmed_at=datetime.now(UTC) if status == "confirmed" else None,
            )
            self.db.add(link)
            created.append(link)
        if created:
            await self.db.flush()
        return created

    async def recompute(
        self,
        incident_id: uuid.UUID,
        *,
        actor: User | None = None,
        skip_if_unchanged: bool = False,
    ) -> IncidentExposureAssessment:
        incident = await self.get_incident_for_exposure(incident_id)
        project = incident.project
        mode = (project.compliance_inference_mode if project else "manual") or "manual"

        classification = _classification_from_incident(incident)
        ctx = IncidentContextInput(
            detected_at=incident.detected_at,
            confirmed_at=None,
            manual_jurisdictions=tuple(incident.affected_jurisdictions or []),
            personal_data_involved=incident.personal_data_involved,
            health_data_involved=incident.health_data_involved,
        )
        config = EngineConfigInput(mode, settings.ML_REVIEW_THRESHOLD)  # type: ignore[arg-type]
        links = (
            await self.db.execute(
                select(IncidentAsset)
                .where(IncidentAsset.incident_id == incident.id)
                .options(selectinload(IncidentAsset.asset).selectinload(Asset.residency))
            )
        ).scalars().all()
        assets = _asset_inputs(list(links))

        result = run_exposure_assessment(classification, ctx, assets, config)
        results_dict = assessment_result_to_dict(result)
        trace_json = trace_to_json(result.trace)

        if skip_if_unchanged:
            latest = await self.get_latest_assessment(incident_id)
            if latest and latest.inputs_hash == result.inputs_hash:
                return latest

        # Supersede prior assessments unless analyst confirmed the latest
        prior = await self.get_latest_assessment(incident_id)
        if prior and prior.status != "confirmed":
            prior.status = "superseded"
        elif prior and prior.status == "confirmed" and prior.inputs_hash != result.inputs_hash:
            self.db.add(
                IncidentAction(
                    incident_id=incident.id,
                    action_type="exposure_recomputed",
                    description=(
                        "New exposure assessment supersedes confirmed assessment — review required"
                    ),
                    performed_by=actor.id if actor else None,
                    automated=actor is None,
                    result="provisional",
                    action_metadata={"prior_assessment_id": str(prior.id)},
                )
            )
            prior.status = "superseded"

        assessment = IncidentExposureAssessment(
            incident_id=incident.id,
            engine_version=ENGINE_VERSION,
            knowledge_versions=knowledge_versions_snapshot(),
            inputs_hash=result.inputs_hash,
            overall_confidence=result.overall_confidence,
            status=result.status,
            results=results_dict,
            trace=trace_json,
        )
        self.db.add(assessment)
        await self.db.flush()

        if mode != "manual":
            await self._persist_inferred_obligations(incident, assessment, result)

        self.db.add(
            IncidentAction(
                incident_id=incident.id,
                action_type="exposure_assessment",
                description=f"Exposure assessment computed (status={result.status})",
                performed_by=actor.id if actor else None,
                automated=actor is None,
                result=result.status,
                action_metadata={"assessment_id": str(assessment.id), "inputs_hash": result.inputs_hash},
            )
        )

        if actor:
            await write_audit(
                self.db,
                user=actor,
                project_id=incident.project_id,
                action="exposure.recomputed",
                resource_type="incident",
                resource_id=str(incident.id),
                details={"assessment_id": str(assessment.id)},
            )
        else:
            await log_ml_system_action(
                self.db,
                action="exposure.recomputed",
                resource_type="incident",
                resource_id=str(incident.id),
                project_id=incident.project_id,
                details={"assessment_id": str(assessment.id), "engine_version": ENGINE_VERSION},
            )

        await self.db.flush()
        return assessment

    async def _persist_inferred_obligations(
        self, incident: Incident, assessment: IncidentExposureAssessment, result: Any
    ) -> None:
        """Create ComplianceRecord rows for inferred obligations — never auto-dispatch notifications."""
        for ob in result.obligations:
            key = f"{ob.rule_id}:{ob.obligation_id}"
            existing = (
                await self.db.execute(
                    select(ComplianceRecord).where(
                        ComplianceRecord.incident_id == incident.id,
                        ComplianceRecord.source == "inferred",
                        ComplianceRecord.rule_id == ob.rule_id,
                        ComplianceRecord.obligation == ob.description,
                        ComplianceRecord.analyst_decision.in_(("pending", "accepted")),
                    )
                )
            ).scalar_one_or_none()
            if existing:
                continue
            record = ComplianceRecord(
                incident_id=incident.id,
                regulation=ob.law,
                jurisdiction=ob.recipient,
                obligation=ob.description,
                deadline=ob.deadline_at or incident.detected_at,
                source="inferred",
                rule_id=ob.rule_id,
                rule_version=ob.rule_version,
                assessment_id=assessment.id,
                clock_start_at=ob.clock_start_at,
                analyst_decision="pending",
                provisional=ob.provisional,
            )
            self.db.add(record)
        await self.db.flush()

    async def get_latest_assessment(
        self, incident_id: uuid.UUID
    ) -> IncidentExposureAssessment | None:
        q = (
            select(IncidentExposureAssessment)
            .where(
                IncidentExposureAssessment.incident_id == incident_id,
                IncidentExposureAssessment.status != "superseded",
            )
            .order_by(IncidentExposureAssessment.computed_at.desc())
            .limit(1)
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def accept_obligation(
        self,
        record_id: uuid.UUID,
        user: User,
        reason: str | None = None,
    ) -> ComplianceRecord:
        record = await self._get_inferred_record(record_id)
        if record.analyst_decision == "accepted":
            raise ConflictError("Obligation already accepted")
        record.analyst_decision = "accepted"
        record.decision_reason = reason
        record.updated_at = datetime.now(UTC)
        await write_audit(
            self.db,
            user=user,
            project_id=await self._project_for_record(record),
            action="obligation.accepted",
            resource_type="compliance_record",
            resource_id=str(record.id),
            details={"reason": reason},
        )
        await self.db.flush()
        return record

    async def dismiss_obligation(
        self,
        record_id: uuid.UUID,
        user: User,
        reason: str,
    ) -> ComplianceRecord:
        if not reason or not reason.strip():
            raise ConflictError("Dismiss reason is required")
        record = await self._get_inferred_record(record_id)
        record.analyst_decision = "dismissed"
        record.decision_reason = reason.strip()
        record.updated_at = datetime.now(UTC)
        await write_audit(
            self.db,
            user=user,
            project_id=await self._project_for_record(record),
            action="obligation.dismissed",
            resource_type="compliance_record",
            resource_id=str(record.id),
            details={"reason": reason},
        )
        await self.db.flush()
        return record

    async def _get_inferred_record(self, record_id: uuid.UUID) -> ComplianceRecord:
        record = await self.db.get(ComplianceRecord, record_id)
        if not record or record.source != "inferred":
            raise NotFoundError("ComplianceRecord")
        return record

    async def _project_for_record(self, record: ComplianceRecord) -> uuid.UUID | None:
        inc = await self.db.get(Incident, record.incident_id)
        return inc.project_id if inc else None


def enqueue_exposure_recompute(incident_id: uuid.UUID) -> None:
    """Queue exposure recompute after ML classification or asset changes."""
    try:
        sqs_service.enqueue_incident(str(incident_id), "exposure_recompute")
    except Exception as exc:
        logger.warning("Failed to enqueue exposure recompute for %s: %s", incident_id, exc)


async def run_exposure_recompute_job(incident_id: uuid.UUID) -> None:
    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        try:
            svc = ExposureService(db)
            incident = await svc.get_incident_for_exposure(incident_id)
            await svc.auto_match_assets(incident)
            await svc.recompute(incident_id, actor=None)
            await db.commit()
        except Exception as exc:
            await db.rollback()
            logger.error("Exposure recompute failed for %s: %s", incident_id, exc)
