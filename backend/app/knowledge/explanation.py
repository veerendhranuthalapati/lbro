"""Compose incident-specific attack explanations from guides + ML facts."""
from __future__ import annotations

from typing import Any

from app.knowledge.loader import DECISION_SUPPORT_DISCLAIMER, get_guide, load_attack_guides
from app.models.incident import Incident


def _uncertainty_banner(incident: Incident) -> dict[str, Any] | None:
    """Return banner when detection should not be read as confirmed attack."""
    status = (incident.ml_classification_status or "").lower()
    model = incident.ml_model_version or ""

    reasons: list[str] = []
    if status in ("heuristic", "fallback", "pending"):
        reasons.append("Classification used heuristic or pending path — verify with independent telemetry.")
    if model and "demo" in model.lower():
        reasons.append("Demo/synthetic model — use for training only, not operational proof.")
    if incident.attack_category == "BENIGN":
        reasons.append("Benign classification — no malicious activity implied.")

    if not reasons:
        return None
    return {
        "level": "caution",
        "title": "Verify before acting",
        "messages": reasons,
    }


def compose_incident_explanation(incident: Incident, *, audience: str = "analyst") -> dict[str, Any]:
    """Build explanation payload; never invent fields not on the incident."""
    bundle = load_attack_guides()
    class_id = incident.attack_category or "BENIGN"
    guide = get_guide(class_id)
    if guide is None:
        guide = get_guide("BENIGN")

    executive = audience == "executive"
    g = guide.model_dump(mode="json") if guide else {}

    why_flagged = [
        f"Attack category assigned: {class_id}.",
        f"Incident severity: {incident.severity}.",
    ]
    if incident.ml_model_version:
        why_flagged.append(f"Model version: {incident.ml_model_version}.")
    if incident.ml_classification_status:
        why_flagged.append(f"Classification status: {incident.ml_classification_status}.")

    return {
        "incident_id": str(incident.id),
        "class_id": class_id,
        "audience": audience,
        "content_version": bundle.content_version,
        "disclaimer": DECISION_SUPPORT_DISCLAIMER,
        "uncertainty_banner": _uncertainty_banner(incident),
        "why_flagged": why_flagged,
        "guide": {
            "title": g.get("title"),
            "summary_plain": g.get("summary_plain") if executive else g.get("how_it_works"),
            "immediate_actions": g.get("immediate_actions"),
            "containment": g.get("containment"),
            "recovery": g.get("recovery"),
            "prevention": g.get("prevention"),
            "detection_tips": g.get("detection_tips"),
            "mitre_techniques": g.get("mitre_techniques"),
            "references": g.get("references"),
            "data_at_risk_hint": g.get("data_at_risk_hint"),
        },
    }
