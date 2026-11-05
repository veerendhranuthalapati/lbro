"""Incident API enrichment — surface integration payload on overview fields."""
from __future__ import annotations

from app.models.incident import Incident
from app.schemas.incident import IncidentResponse


def incident_to_response(incident: Incident) -> IncidentResponse:
    """Map ORM incident + integration_context to API shape the UI expects."""
    resp = IncidentResponse.model_validate(incident)
    ctx = incident.integration_context or {}

    updates: dict = {}
    for key in (
        "country",
        "user_agent",
        "application",
        "mitre_techniques",
        "owasp_category",
        "city",
        "region",
    ):
        if ctx.get(key) is not None:
            updates[key] = ctx[key]

    if updates:
        return resp.model_copy(update=updates)
    return resp
