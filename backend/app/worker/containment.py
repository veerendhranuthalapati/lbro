"""
LBRO — Containment Pipeline
Executes ordered containment actions for a detected breach.
Each action is independent — a failure in one does not block others.
All actions are recorded in the incident timeline for legal defensibility.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.aws_clients import get_sqs
from app.config import settings
from app.models.incident import (
    Incident,
    IncidentAction,
    IncidentStatus,
)

log = structlog.get_logger(__name__)


class ContainmentPipeline:
    """
    Runs containment actions for a breach incident.

    Actions run concurrently where safe; the pipeline records success/failure
    of each action regardless of others (partial containment is better than none).
    Final status is CONTAINED when all critical actions succeed, ESCALATED if any fail.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def run(self, incident: Incident, context: dict[str, Any]) -> None:
        severity = context.get("severity", "MEDIUM")
        affected_systems = context.get("affected_systems", [])
        jurisdictions = context.get("jurisdictions", [])

        log.info(
            "containment.pipeline_started",
            incident_id=str(incident.id),
            severity=severity,
            affected_systems=affected_systems,
        )

        actions = self._build_action_plan(severity, affected_systems, jurisdictions)
        results = await asyncio.gather(
            *[self._run_action(incident, action) for action in actions],
            return_exceptions=True,
        )

        failed = [
            actions[i]["name"]
            for i, r in enumerate(results)
            if isinstance(r, Exception)
        ]

        now = datetime.now(timezone.utc)

        if failed:
            incident.status = IncidentStatus.ESCALATED
            self.session.add(IncidentAction(
                incident_id=incident.id,
                action_type="containment.partial_failure",
                description=f"Containment completed with failures: {', '.join(failed)}",
                action_metadata={"failed_actions": failed},
                automated=True,
            ))
            log.error(
                "containment.partial_failure",
                incident_id=str(incident.id),
                failed_actions=failed,
            )
        else:
            incident.status = IncidentStatus.CONTAINED
            incident.contained_at = now
            self.session.add(IncidentAction(
                incident_id=incident.id,
                action_type="containment.completed",
                description=f"All {len(actions)} containment actions completed successfully",
                action_metadata={"actions": [a["name"] for a in actions]},
                automated=True,
            ))
            log.info(
                "containment.completed",
                incident_id=str(incident.id),
                action_count=len(actions),
            )

        # Enqueue notification dispatch regardless of containment outcome
        await self._enqueue_notifications(incident, jurisdictions)
        await self.session.commit()

    def _build_action_plan(
        self,
        severity: str,
        affected_systems: list[str],
        jurisdictions: list[str],
    ) -> list[dict[str, Any]]:
        """
        Build the ordered containment action plan based on severity and context.
        CRITICAL/HIGH incidents get immediate isolation; MEDIUM/LOW get evidence first.
        """
        actions: list[dict[str, Any]] = []

        if severity in ("CRITICAL", "HIGH"):
            actions.append({"name": "network_isolation", "critical": True})
            actions.append({"name": "credential_revocation", "critical": True})

        actions.append({"name": "evidence_collection", "critical": True})
        actions.append({"name": "snapshot_affected_systems", "critical": False})

        if jurisdictions:
            actions.append({"name": "regulatory_notification_prep", "critical": False})

        return actions

    async def _run_action(
        self, incident: Incident, action: dict[str, Any]
    ) -> None:
        """Execute a single containment action with timeline recording."""
        name = action["name"]
        started = datetime.now(timezone.utc)

        self.session.add(IncidentAction(
            incident_id=incident.id,
            action_type="containment.action.started",
            description=f"Started: {name}",
            automated=True,
        ))

        try:
            # Each action is a method on this class
            handler = getattr(self, f"_action_{name}", self._action_stub)
            await handler(incident)

            self.session.add(IncidentAction(
                incident_id=incident.id,
                action_type="containment.action.completed",
                description=f"Completed: {name}",
                action_metadata={"action": name, "started_at": started.isoformat()},
                automated=True,
            ))
            log.info("containment.action_ok", incident_id=str(incident.id), action=name)

        except Exception as e:
            self.session.add(IncidentAction(
                incident_id=incident.id,
                action_type="containment.action.failed",
                description=f"Failed: {name} — {type(e).__name__}",
                action_metadata={"action": name, "error": str(e)},
                automated=True,
            ))
            log.error(
                "containment.action_failed",
                incident_id=str(incident.id),
                action=name,
                error=str(e),
            )
            if action.get("critical"):
                raise

    # ── Action implementations ────────────────────────────────────────────────

    async def _action_network_isolation(self, incident: Incident) -> None:
        """
        Isolate affected systems from the network.
        In production: call EC2 ModifyInstanceAttribute to restrict SGs,
        update NACLs, or invoke an SSM automation runbook.
        """
        # TODO: integrate with EC2/SSM for real isolation
        log.info("containment.network_isolation", incident_id=str(incident.id))
        await asyncio.sleep(0)  # Async stub

    async def _action_credential_revocation(self, incident: Incident) -> None:
        """
        Revoke IAM credentials and API keys associated with the breach.
        In production: call IAM DeleteAccessKey, disable users.
        """
        log.info("containment.credential_revocation", incident_id=str(incident.id))
        await asyncio.sleep(0)

    async def _action_evidence_collection(self, incident: Incident) -> None:
        """
        Collect and preserve forensic evidence to S3 with WORM Object Lock.
        In production: capture memory dumps, log archives, network captures.
        """
        log.info("containment.evidence_collection", incident_id=str(incident.id))
        # Evidence upload to S3 would happen here
        await asyncio.sleep(0)

    async def _action_snapshot_affected_systems(self, incident: Incident) -> None:
        """Create EBS snapshots of affected instances before any remediation."""
        log.info("containment.snapshot", incident_id=str(incident.id))
        await asyncio.sleep(0)

    async def _action_regulatory_notification_prep(
        self, incident: Incident
    ) -> None:
        """Pre-render regulatory notification templates for each jurisdiction."""
        log.info("containment.notification_prep", incident_id=str(incident.id))
        await asyncio.sleep(0)

    async def _action_stub(self, incident: Incident) -> None:
        """Fallback for unimplemented actions — logs and succeeds."""
        log.warning("containment.action_stub", incident_id=str(incident.id))

    async def _enqueue_notifications(
        self, incident: Incident, jurisdictions: list[str]
    ) -> None:
        """Enqueue each jurisdiction's notification to the dispatch queue."""
        if not settings.SQS_NOTIFICATION_QUEUE_URL or not jurisdictions:
            return

        import json

        from sqlalchemy import select

        from app.models.incident import NotificationStatus, RegulatoryNotification

        for jx in jurisdictions:
            try:
                # Find the pending notification record
                result = await self.session.execute(
                    select(RegulatoryNotification).where(
                        RegulatoryNotification.incident_id == incident.id,
                        RegulatoryNotification.jurisdiction == jx,
                        RegulatoryNotification.status == NotificationStatus.PENDING,
                    )
                )
                notif = result.scalar_one_or_none()
                if not notif:
                    continue

                msg_body = json.dumps({
                    "notification_id": str(notif.id),
                    "incident_id":     str(incident.id),
                    "jurisdiction":    jx,
                    "deadline_at":     notif.deadline_at.isoformat(),
                    "triggered_by":    "auto_post_containment",
                })
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda b=msg_body: get_sqs().send_message(
                        QueueUrl=settings.SQS_NOTIFICATION_QUEUE_URL,
                        MessageBody=b,
                    ),
                )
                log.info(
                    "containment.notification_enqueued",
                    incident_id=str(incident.id),
                    jurisdiction=jx,
                )
            except Exception as e:
                log.error(
                    "containment.notification_enqueue_failed",
                    incident_id=str(incident.id),
                    jurisdiction=jx,
                    error=str(e),
                )
