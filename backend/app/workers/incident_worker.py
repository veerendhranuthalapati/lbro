"""Incident worker — ML classification, audit trail, and containment recommendations."""
from __future__ import annotations

import logging
import uuid

from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.ml.classifier import classifier
from app.ml.features import SEVERITY_MAP
from app.models.incident import Incident, IncidentAction, IncidentStatus
from app.services.ml_audit_service import log_ml_system_action

logger = logging.getLogger(__name__)


async def process_incident_message(body: dict) -> None:
    """Handle SQS incident jobs; malformed messages are logged and skipped (no crash loop)."""
    if not isinstance(body, dict):
        logger.error("Malformed incident message (not a dict): %r", body)
        return

    incident_id = body.get("incident_id")
    action = body.get("action", "classify")
    message_id = body.get("_sqs_message_id")

    if not incident_id:
        logger.error("Missing incident_id in message: %s", body)
        return

    if action == "classify":
        await classify_incident(uuid.UUID(str(incident_id)), dedupe_key=message_id)
    else:
        logger.warning("Unknown incident action: %s", action)


async def classify_incident(incident_id: uuid.UUID, dedupe_key: str | None = None) -> None:
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(select(Incident).where(Incident.id == incident_id))
            incident = result.scalar_one_or_none()
            if not incident:
                logger.warning("Incident %s not found", incident_id)
                return

            if incident.ml_classification_status == "completed":
                logger.info("Incident %s already classified — idempotent skip", incident_id)
                return

            existing = await db.execute(
                select(IncidentAction.id)
                .where(
                    IncidentAction.incident_id == incident.id,
                    IncidentAction.action_type == "ml_classification",
                )
                .limit(1)
            )
            if existing.scalar_one_or_none() is not None and incident.ml_classification_status != "pending":
                logger.info("Incident %s has ml_classification action — idempotent skip", incident_id)
                return

            if not incident.network_features:
                logger.info("No network features for incident %s, skipping ML", incident_id)
                incident.ml_classification_status = "completed"
                await db.commit()
                return

            prediction = classifier.predict_result(incident.network_features)

            incident.attack_category = prediction.attack_category
            incident.confidence_score = prediction.confidence
            incident.ml_model_version = prediction.model_version
            incident.needs_analyst_review = prediction.needs_review

            if prediction.source == "model" and not prediction.needs_review:
                ml_severity = SEVERITY_MAP.get(prediction.attack_category, "medium")
                incident.severity = ml_severity

            action = IncidentAction(
                incident_id=incident.id,
                action_type="ml_classification",
                description=(
                    f"ML classified as '{prediction.attack_category}' "
                    f"source={prediction.source} confidence={prediction.confidence:.1%} "
                    f"coverage={prediction.feature_coverage:.0%} "
                    f"(model: {prediction.model_version})"
                ),
                automated=True,
                result=f"severity={incident.severity}, review_needed={incident.needs_analyst_review}",
                metadata=prediction.to_dict(),
            )
            db.add(action)

            await log_ml_system_action(
                db,
                action="ml.classification",
                resource_type="incident",
                resource_id=str(incident.id),
                project_id=incident.project_id,
                details={
                    "dedupe_key": dedupe_key,
                    "prediction": prediction.to_dict(),
                },
            )

            await _handle_containment_policy(db, incident, prediction)

            incident.ml_classification_status = "completed"
            await db.commit()
            logger.info(
                "Classified incident %s as %s (source=%s confidence=%.2f)",
                incident_id,
                prediction.attack_category,
                prediction.source,
                prediction.confidence,
            )
        except Exception as exc:
            await db.rollback()
            logger.error("Failed to classify incident %s: %s", incident_id, exc)
            raise


async def _handle_containment_policy(db, incident, prediction) -> None:
    """
    Default: record containment recommendation only (no status change).

    Auto-containment changes incident status only — real EC2/SSM isolation is not implemented.
    """
    from app.models.project import Project

    project_opt_in = False
    if incident.project_id:
        proj = await db.get(Project, incident.project_id)
        project_opt_in = bool(proj and proj.allow_ml_auto_contain)

    eligible_for_auto = (
        settings.ML_AUTO_CONTAIN_ENABLED
        and project_opt_in
        and prediction.source == "model"
        and not prediction.ood_flag
        and prediction.confidence >= settings.ML_AUTO_CONTAIN_THRESHOLD
        and prediction.attack_category not in ("BENIGN",)
        and prediction.severity == "critical"
        and not prediction.needs_review
    )

    if eligible_for_auto:
        await _auto_contain_status_only(db, incident, prediction)
        return

    rec = IncidentAction(
        incident_id=incident.id,
        action_type="containment_recommended",
        description=(
            "ML recommends analyst review containment — automated isolation not applied "
            f"(source={prediction.source}, confidence={prediction.confidence:.1%})"
        ),
        automated=True,
        result="containment_not_executed",
        metadata=prediction.to_dict(),
    )
    db.add(rec)
    incident.needs_analyst_review = True

    await log_ml_system_action(
        db,
        action="ml.containment_recommended",
        resource_type="incident",
        resource_id=str(incident.id),
        project_id=incident.project_id,
        details={"prediction": prediction.to_dict(), "auto_contain_enabled": settings.ML_AUTO_CONTAIN_ENABLED},
    )


async def _auto_contain_status_only(db, incident, prediction) -> None:
    """Apply status transitions only — does not isolate hosts."""
    logger.warning(
        "Auto-contain status transition for incident %s (no real network isolation)",
        incident.id,
    )
    if incident.status == IncidentStatus.NEW.value:
        incident.status = IncidentStatus.TRIAGING.value
        db.add(
            IncidentAction(
                incident_id=incident.id,
                action_type="status_change",
                description="Automated transition new → triaging before containment",
                automated=True,
                result="triaging",
            )
        )
    if incident.status == IncidentStatus.TRIAGING.value:
        incident.status = IncidentStatus.CONTAINED.value
        incident.containment_actions = ["ml_auto_contain_status_only"]

    db.add(
        IncidentAction(
            incident_id=incident.id,
            action_type="auto_containment",
            description=(
                "ML auto-contain policy applied (status=contained only; "
                "network isolation not implemented)"
            ),
            automated=True,
            result="status_contained",
            metadata=prediction.to_dict(),
        )
    )
    await log_ml_system_action(
        db,
        action="ml.auto_containment",
        resource_type="incident",
        resource_id=str(incident.id),
        project_id=incident.project_id,
        details={"prediction": prediction.to_dict()},
    )
