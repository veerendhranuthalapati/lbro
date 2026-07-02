"""Incident worker — ML classification and automated containment."""
from __future__ import annotations

import logging
import uuid

from app.database import AsyncSessionLocal
from app.ml.classifier import classifier
from app.ml.features import SEVERITY_MAP
from app.config import settings

logger = logging.getLogger(__name__)


async def process_incident_message(body: dict) -> None:
    incident_id = body.get("incident_id")
    action = body.get("action", "classify")

    if not incident_id:
        logger.error("Missing incident_id in message: %s", body)
        return

    if action == "classify":
        await classify_incident(uuid.UUID(incident_id))
    else:
        logger.warning("Unknown incident action: %s", action)


async def classify_incident(incident_id: uuid.UUID) -> None:
    from sqlalchemy import select
    from app.models.incident import Incident, IncidentAction

    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(select(Incident).where(Incident.id == incident_id))
            incident = result.scalar_one_or_none()
            if not incident:
                logger.warning("Incident %s not found", incident_id)
                return

            if not incident.network_features:
                logger.info("No network features for incident %s, skipping ML", incident_id)
                return

            prediction = classifier.predict(incident.network_features)

            incident.attack_category = prediction["attack_category"]
            incident.confidence_score = prediction["confidence"]
            incident.ml_model_version = prediction.get("model_version", settings.ML_MODEL_VERSION)
            incident.needs_analyst_review = prediction["needs_review"]

            # Override severity only if ML is confident
            if not prediction["needs_review"]:
                ml_severity = SEVERITY_MAP.get(prediction["attack_category"], "medium")
                incident.severity = ml_severity

            action = IncidentAction(
                incident_id=incident.id,
                action_type="ml_classification",
                description=(
                    f"ML classified as '{prediction['attack_category']}' "
                    f"with {prediction['confidence']:.1%} confidence "
                    f"(model: {prediction.get('model_version', 'unknown')})"
                ),
                automated=True,
                result=f"severity={incident.severity}, review_needed={incident.needs_analyst_review}",
                metadata={"probabilities": prediction.get("probabilities", {}),
                          "top_features": prediction.get("top_features", [])},
            )
            db.add(action)

            # Auto-containment for critical high-confidence threats
            if (
                incident.severity == "critical"
                and not prediction["needs_review"]
                and prediction["attack_category"] not in ("BENIGN",)
            ):
                await _auto_contain(db, incident)

            await db.commit()
            logger.info(
                "Classified incident %s as %s (confidence=%.2f)",
                incident_id, prediction["attack_category"], prediction["confidence"]
            )
        except Exception as exc:
            await db.rollback()
            logger.error("Failed to classify incident %s: %s", incident_id, exc)
            raise


async def _auto_contain(db, incident) -> None:
    from app.models.incident import IncidentAction, IncidentStatus
    logger.info("Auto-containing critical incident %s", incident.id)
    incident.status = IncidentStatus.CONTAINED.value
    incident.containment_actions = ["automated_network_isolation", "automated_alert_triggered"]
    action = IncidentAction(
        incident_id=incident.id,
        action_type="auto_containment",
        description="Automated containment triggered for critical incident",
        automated=True,
        result="network_isolation_applied",
    )
    db.add(action)
