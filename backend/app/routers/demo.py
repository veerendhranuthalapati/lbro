"""Demo data generation router.

POST /api/v1/demo/generate  — inserts sample incidents/evidence/compliance
POST /api/v1/demo/events    — injects SecurityEvents into a project (triggers SSE)
"""
from __future__ import annotations

import random
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Permission
from app.database import get_db
from app.dependencies import require_permission, get_current_active_user
from app.models.compliance import ComplianceRecord
from app.models.evidence import Evidence
from app.models.incident import Incident
from app.models.project import Project
from app.models.security_event import SecurityEvent
from app.models.user import User

router = APIRouter(prefix="/demo", tags=["demo"])

# ── Rate limiting ──────────────────────────────────────────────────────────────
_demo_last_called: dict[str, float] = defaultdict(float)
DEMO_RATE_LIMIT_SECONDS = 60

def _check_demo_rate_limit(user_id: str) -> None:
    now = time.monotonic()
    last = _demo_last_called[user_id]
    if now - last < DEMO_RATE_LIMIT_SECONDS:
        wait = int(DEMO_RATE_LIMIT_SECONDS - (now - last))
        raise HTTPException(status_code=429, detail=f"Demo generation rate limited. Try again in {wait}s.")
    _demo_last_called[user_id] = now

# ── Sample data pools ──────────────────────────────────────────────────────────
_INCIDENTS = [
    {"title": "SQL Injection Attempt on /api/v1/users",   "attack_category": "SQLi",            "severity": "critical", "source_ip": "185.220.101.42", "destination_port": 443},
    {"title": "XSS Payload in Search Parameter",          "attack_category": "XSS",             "severity": "high",     "source_ip": "94.102.49.190",  "destination_port": 80},
    {"title": "Brute Force Login Attempts Detected",      "attack_category": "BruteForce",      "severity": "high",     "source_ip": "198.51.100.23",  "destination_port": 443},
    {"title": "Suspicious Port Scan from External IP",    "attack_category": "Recon",           "severity": "medium",   "source_ip": "203.0.113.55",   "destination_port": 22},
    {"title": "Unusual Data Exfiltration Pattern",        "attack_category": "DataExfiltration","severity": "critical", "source_ip": "10.0.0.15",      "destination_port": 8080},
    {"title": "Command Injection in File Upload",         "attack_category": "CMDi",            "severity": "critical", "source_ip": "162.158.120.90", "destination_port": 443},
    {"title": "Directory Traversal Attack",               "attack_category": "PathTraversal",   "severity": "high",     "source_ip": "172.16.254.1",   "destination_port": 80},
    {"title": "CSRF Token Missing on Form Submit",        "attack_category": "CSRF",            "severity": "medium",   "source_ip": "192.168.1.200",  "destination_port": 443},
    {"title": "Rate Limit Bypass via Header Spoofing",    "attack_category": "RateLimitBypass", "severity": "medium",   "source_ip": "45.33.32.156",   "destination_port": 443},
    {"title": "Credential Stuffing Attack Detected",      "attack_category": "BruteForce",      "severity": "high",     "source_ip": "104.21.14.101",  "destination_port": 443},
    {"title": "SSRF Probe on Internal Metadata API",      "attack_category": "SSRF",            "severity": "high",     "source_ip": "54.93.211.40",   "destination_port": 80},
    {"title": "JWT Algorithm Confusion Attack",           "attack_category": "AuthBypass",      "severity": "critical", "source_ip": "188.114.96.3",   "destination_port": 443},
]

_STATUSES = ["new", "triaging", "contained", "closed"]

_EVIDENCE_NAMES = [
    "access.log", "nginx_error.log", "packet_capture.pcap",
    "memory_dump.bin", "request_payload.json", "db_query_log.txt",
]

_COMPLIANCE_REQS = [
    {"regulation": "GDPR",    "jurisdiction": "EU",     "obligation": "Article 33 — 72-hour breach notification to supervisory authority",    "is_met": False},
    {"regulation": "HIPAA",   "jurisdiction": "US",     "obligation": "164.308 — Implement incident response procedures",                     "is_met": False},
    {"regulation": "PCI-DSS", "jurisdiction": "Global", "obligation": "Requirement 12.10 — Security incident response plan",                  "is_met": False},
    {"regulation": "GDPR",    "jurisdiction": "EU",     "obligation": "Article 32 — Technical security measures for data processing",          "is_met": True},
    {"regulation": "SOC2",    "jurisdiction": "US",     "obligation": "CC7.3 — Evaluate and communicate security incidents to stakeholders",   "is_met": False},
]

_DEMO_EVENTS = [
    {"event_type": "sql_injection",      "severity": "critical", "source_ip": "185.220.101.42", "message": "SQL injection in /api/users?id=1 OR 1=1"},
    {"event_type": "brute_force",        "severity": "high",     "source_ip": "94.102.49.190",  "message": "429 failed login attempts in 60 seconds"},
    {"event_type": "xss",                "severity": "high",     "source_ip": "198.51.100.23",  "message": "XSS payload detected in search parameter"},
    {"event_type": "port_scan",          "severity": "medium",   "source_ip": "203.0.113.55",   "message": "SYN scan across ports 1-65535"},
    {"event_type": "auth_failure",       "severity": "medium",   "source_ip": "104.21.14.101",  "message": "Credential stuffing: 200 distinct usernames tried"},
    {"event_type": "suspicious_request", "severity": "high",     "source_ip": "162.158.120.90", "message": "Directory traversal: /../../../etc/passwd"},
    {"event_type": "firewall_event",     "severity": "low",      "source_ip": "172.16.254.1",   "message": "Blocked inbound connection on port 3389 (RDP)"},
    {"event_type": "nginx_log",          "severity": "medium",   "source_ip": "54.93.211.40",   "message": "4xx rate spike: 340 errors/min from single IP"},
    {"event_type": "linux_audit",        "severity": "critical", "source_ip": "10.0.0.15",      "message": "Privilege escalation: sudo -s executed by www-data"},
    {"event_type": "windows_event",      "severity": "high",     "source_ip": "192.168.1.200",  "message": "Event 4625: 80 failed logons on domain controller"},
]


# ── Schemas ────────────────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    """Optional body for the /generate endpoint.

    If project_id is supplied the demo data is scoped to that project;
    otherwise the endpoint falls back to the user's first active project.
    """
    project_id: str | None = None


class GenerateResponse(BaseModel):
    incidents_created: int
    evidence_created: int
    compliance_created: int
    message: str


class DemoEventsRequest(BaseModel):
    project_id: str
    count: int = 5


class DemoEventsResponse(BaseModel):
    injected: int
    project_id: str
    message: str


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/generate", response_model=GenerateResponse, status_code=status.HTTP_201_CREATED)
async def generate_demo_data(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: GenerateRequest = None,
):
    """Insert realistic sample data scoped to the current user's project.

    Pass ``{"project_id": "<uuid>"}`` in the request body to target a specific
    project; omit the body to auto-select the user's first active project.
    """
    _check_demo_rate_limit(str(current_user.id))
    if body is None:
        body = GenerateRequest()

    project = None
    # Prefer explicitly supplied project_id
    if body.project_id:
        try:
            import uuid as _uuid_mod
            proj_uuid = _uuid_mod.UUID(body.project_id)
            result = await db.execute(
                select(Project).where(Project.id == proj_uuid).limit(1)
            )
            project = result.scalar_one_or_none()
        except ValueError:
            pass

    # Fallback: first active project owned by this user
    if project is None:
        result = await db.execute(
            select(Project)
            .where(Project.owner_id == current_user.id, Project.status == "active")
            .order_by(Project.created_at)
            .limit(1)
        )
        project = result.scalar_one_or_none()

    project_id = project.id if project else None

    now = datetime.now(timezone.utc)
    incidents_created = 0
    evidence_created = 0
    compliance_created = 0

    created_incidents: list[Incident] = []
    for tmpl in random.sample(_INCIDENTS, min(8, len(_INCIDENTS))):
        detected_at = now - timedelta(hours=random.randint(1, 72))
        inc = Incident(
            title=tmpl["title"],
            description="[Demo] Automated detection of " + tmpl["attack_category"] + " pattern. "
                        "This is sample data generated for demonstration purposes.",
            status=random.choice(_STATUSES),
            severity=tmpl["severity"],
            attack_category=tmpl["attack_category"],
            source_ip=tmpl["source_ip"],
            destination_ip="10.0.1.5",
            destination_port=tmpl["destination_port"],
            confidence_score=round(random.uniform(0.72, 0.99), 4),
            detected_at=detected_at,
            project_id=project_id,
        )
        db.add(inc)
        created_incidents.append(inc)
        incidents_created += 1

    await db.flush()

    for inc in created_incidents[:3]:
        fname = random.choice(_EVIDENCE_NAMES)
        sample_content = "[Demo evidence for " + inc.title + "]\nTimestamp: " + inc.detected_at.isoformat() + "\nSource IP: " + (inc.source_ip or "unknown") + "\n"
        import hashlib as _hl
        _content_bytes = sample_content.encode()
        ev = Evidence(
            incident_id=inc.id,
            filename=fname,
            original_filename=fname,
            content_type="text/plain",
            file_size=len(_content_bytes),
            file_data=_content_bytes,
            sha256_hash=_hl.sha256(_content_bytes).hexdigest(),
            uploaded_by=current_user.id,
            description="Sample " + fname + " captured during incident",
        )
        db.add(ev)
        evidence_created += 1

    if created_incidents:
        for req in _COMPLIANCE_REQS:
            deadline = now + timedelta(hours=random.choice([6, 24, 48, 72]))
            cr = ComplianceRecord(
                incident_id=created_incidents[0].id,
                regulation=req["regulation"],
                jurisdiction=req["jurisdiction"],
                obligation=req["obligation"],
                deadline=deadline,
                is_met=req["is_met"],
                notes="[Demo] Sample compliance record generated for demonstration.",
            )
            db.add(cr)
            compliance_created += 1

    await db.flush()

    return GenerateResponse(
        incidents_created=incidents_created,
        evidence_created=evidence_created,
        compliance_created=compliance_created,
        message="Created " + str(incidents_created) + " sample incidents, " + str(evidence_created) + " evidence files, and " + str(compliance_created) + " compliance records.",
    )


_demo_events_last: dict[str, float] = defaultdict(float)
DEMO_EVENTS_RATE_LIMIT = 10


@router.post("/events", response_model=DemoEventsResponse, status_code=status.HTTP_201_CREATED)
async def generate_demo_events(
    body: DemoEventsRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Inject demo SecurityEvents into a project to demonstrate the live SSE stream."""
    count = max(1, min(body.count, 10))

    now = time.monotonic()
    if now - _demo_events_last[body.project_id] < DEMO_EVENTS_RATE_LIMIT:
        wait = int(DEMO_EVENTS_RATE_LIMIT - (now - _demo_events_last[body.project_id]))
        raise HTTPException(status_code=429, detail="Wait " + str(wait) + "s before generating more demo events.")
    _demo_events_last[body.project_id] = now

    import uuid as _uuid
    try:
        project_uuid = _uuid.UUID(body.project_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid project_id format.")

    project = await db.get(Project, project_uuid)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    from app.routers.events import _bus_publish, _event_to_response, _classify_event, SecurityEventCreate

    injected = 0
    samples = random.sample(_DEMO_EVENTS, min(count, len(_DEMO_EVENTS)))

    for tmpl in samples:
        ev = SecurityEvent(
            project_id=project.id,
            event_type=tmpl["event_type"],
            severity=tmpl["severity"],
            source_ip=tmpl["source_ip"],
            message="[Demo] " + tmpl["message"],
            source_application="lbro-demo",
            processing_status="pending",
        )
        db.add(ev)
        await db.flush()

        try:
            fake_data = SecurityEventCreate(
                event_type=tmpl["event_type"],
                severity=tmpl["severity"],
                source_ip=tmpl["source_ip"],
                message=tmpl["message"],
            )
            ml = await _classify_event(fake_data)
            if ml:
                ev.ml_attack_category = ml.get("attack_category")
                ev.ml_confidence = ml.get("confidence")
                ev.ml_model_version = ml.get("model_version")
        except Exception:
            pass

        if tmpl["severity"] in ("critical", "high"):
            try:
                inc = Incident(
                    project_id=project.id,
                    title="[Demo] " + tmpl["message"][:200],
                    description="Auto-created demo incident from " + tmpl["event_type"] + " event.",
                    severity=tmpl["severity"],
                    status="new",
                    attack_category=ev.ml_attack_category,
                    confidence_score=ev.ml_confidence,
                    source_ip=tmpl["source_ip"],
                    needs_analyst_review=True,
                )
                db.add(inc)
                await db.flush()
                ev.incident_id = inc.id
            except Exception:
                pass

        ev.processing_status = "processed"
        await db.flush()

        try:
            _bus_publish(str(project.id), _event_to_response(ev))
        except Exception:
            pass

        injected += 1

    return DemoEventsResponse(
        injected=injected,
        project_id=body.project_id,
        message="Injected " + str(injected) + " demo security events into project.",
    )
