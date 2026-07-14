"""Incidents router — including investigation workspace endpoints."""
from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone
from typing import Annotated, Optional, List

from fastapi import APIRouter, Depends, Header, Query, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, or_, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Permission
from app.database import get_db
from app.dependencies import require_permission, get_current_active_user
from app.models.user import User
from app.schemas.incident import (
    IncidentCreate,
    IncidentListResponse,
    IncidentResponse,
    IncidentUpdate,
    StatusChangeRequest,
    ReopenRequest,
)
from app.services.incident_service import IncidentService
from app.services.compliance_service import ComplianceService
from app.services.notification_service import NotificationService
from app.services.project_service import ProjectService

router = APIRouter(prefix="/incidents", tags=["incidents"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _resolve_project_id(
    db: AsyncSession,
    body_project_id: Optional[uuid.UUID],
    x_project_key: Optional[str],
) -> Optional[uuid.UUID]:
    if body_project_id is not None:
        return body_project_id
    if x_project_key:
        svc = ProjectService(db)
        project = await svc.get_by_api_key(x_project_key)
        if project:
            return project.id
    return None


# ---------------------------------------------------------------------------
# Standard CRUD
# ---------------------------------------------------------------------------

@router.post("", response_model=IncidentResponse, status_code=201)
async def create_incident(
    data: IncidentCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.CREATE_INCIDENT))],
    x_project_key: Annotated[Optional[str], Header(alias="X-Project-Key")] = None,
):
    project_id = await _resolve_project_id(db, getattr(data, "project_id", None), x_project_key)
    svc = IncidentService(db)
    incident = await svc.create(data, current_user, project_id=project_id)
    if incident.affected_jurisdictions or incident.personal_data_involved or incident.health_data_involved:
        comp_svc = ComplianceService(db)
        await comp_svc.generate_obligations(incident)
        notif_svc = NotificationService(db)
        await notif_svc.generate_for_incident(incident)
    incident = await svc.get(incident.id)
    return incident


@router.get("", response_model=IncidentListResponse)
async def list_incidents(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.READ_INCIDENT))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    severity: Optional[str] = None,
    needs_review: Optional[bool] = None,
    search: Optional[str] = Query(None, max_length=200),
    project_id: Optional[uuid.UUID] = Query(None),
    source_ip: Optional[str] = Query(None, max_length=45),
    attack_category: Optional[str] = Query(None, max_length=100),
):
    svc = IncidentService(db)
    items, total = await svc.list(
        page=page,
        page_size=page_size,
        status=status,
        severity=severity,
        needs_review=needs_review,
        search=search,
        project_id=project_id,
    )
    return IncidentListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/stats")
async def incident_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.READ_INCIDENT))],
    project_id: Optional[uuid.UUID] = Query(None),
):
    svc = IncidentService(db)
    return await svc.get_stats(project_id=project_id)


@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(
    incident_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.READ_INCIDENT))],
    project_id: Optional[uuid.UUID] = Query(None),
):
    svc = IncidentService(db)
    return await svc.get(incident_id, project_id=project_id)


@router.patch("/{incident_id}", response_model=IncidentResponse)
async def update_incident(
    incident_id: uuid.UUID,
    data: IncidentUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.UPDATE_INCIDENT))],
    project_id: Optional[uuid.UUID] = Query(None),
):
    svc = IncidentService(db)
    await svc.get(incident_id, project_id=project_id)
    return await svc.update(incident_id, data, current_user)


@router.post("/{incident_id}/status")
async def change_status(
    incident_id: uuid.UUID,
    body: StatusChangeRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.UPDATE_INCIDENT))],
    project_id: Optional[uuid.UUID] = Query(None),
):
    svc = IncidentService(db)
    await svc.get(incident_id, project_id=project_id)
    incident = await svc.transition_status(incident_id, body.status, current_user, body.notes or "")
    return {"id": incident.id, "status": incident.status}


@router.post("/{incident_id}/reopen")
async def reopen_incident(
    incident_id: uuid.UUID,
    body: ReopenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.UPDATE_INCIDENT))],
    project_id: Optional[uuid.UUID] = Query(None),
):
    from app.models.incident import IncidentStatus
    svc = IncidentService(db)
    await svc.get(incident_id, project_id=project_id)
    incident = await svc.transition_status(
        incident_id, IncidentStatus.REOPENED.value, current_user, body.reason or ""
    )
    return {"id": incident.id, "status": incident.status}


@router.delete("/{incident_id}", status_code=204)
async def delete_incident(
    incident_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.DELETE_INCIDENT))],
    project_id: Optional[uuid.UUID] = Query(None),
):
    svc = IncidentService(db)
    await svc.get(incident_id, project_id=project_id)
    await svc.delete(incident_id)


# ---------------------------------------------------------------------------
# Explain
# ---------------------------------------------------------------------------

@router.get("/{incident_id}/explain")
async def explain_incident(
    incident_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.READ_INCIDENT))],
    project_id: Optional[uuid.UUID] = Query(None),
):
    """Return a plain-English explanation for this incident's attack type."""
    from app.services.incident_explainer import explain_incident as _explain

    svc = IncidentService(db)
    incident = await svc.get(incident_id, project_id=project_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    explanation = _explain(
        attack_category=incident.attack_category or "Unknown",
        incident_title=incident.title,
        incident_severity=incident.severity,
        source_ip=getattr(incident, "source_ip", None),
        destination_port=getattr(incident, "destination_port", None),
        flow_duration_ms=getattr(incident, "flow_duration_ms", None),
    )
    return {
        "incident_id": str(incident.id),
        "incident_title": incident.title,
        "incident_severity": incident.severity,
        "attack_category": incident.attack_category,
        **explanation,
    }


# ---------------------------------------------------------------------------
# Investigation Timeline
# ---------------------------------------------------------------------------

@router.get("/{incident_id}/timeline")
async def get_investigation_timeline(
    incident_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.READ_INCIDENT))],
    project_id: Optional[uuid.UUID] = Query(None),
):
    """
    Return a chronological list of all events for this incident.
    Combines: synthetic lifecycle events, IncidentActions, evidence uploads,
    and compliance/notification records.
    """
    from app.models.incident import Incident, IncidentAction
    from app.models.evidence import Evidence
    from app.models.notification import Notification
    from app.models.compliance import ComplianceRecord
    from sqlalchemy.orm import selectinload

    svc = IncidentService(db)
    incident = await svc.get(incident_id, project_id=project_id)

    events: list[dict] = []

    # 1. Incident created
    events.append({
        "event_type": "CREATED",
        "actor": "system",
        "description": f"Incident created with severity {incident.severity.upper()}.",
        "occurred_at": incident.created_at.isoformat(),
        "color": "#6b6560",
        "icon": "plus",
    })

    # 2. Detected (may differ from created if ingest pipeline detected first)
    if incident.detected_at != incident.created_at:
        events.append({
            "event_type": "DETECTED",
            "actor": incident.ml_model_version or "ML classifier",
            "description": (
                f"Attack detected: {incident.attack_category or 'Unknown'}. "
                f"Confidence: {round((incident.confidence_score or 0) * 100)}%."
            ),
            "occurred_at": incident.detected_at.isoformat(),
            "color": "#e54e1b",
            "icon": "zap",
        })

    # 3. ML classification (if model info available)
    if incident.attack_category and incident.confidence_score is not None:
        events.append({
            "event_type": "ML_CLASSIFIED",
            "actor": incident.ml_model_version or "ML classifier",
            "description": (
                f"Classified as '{incident.attack_category}' "
                f"with {round(incident.confidence_score * 100)}% confidence."
            ),
            "occurred_at": incident.detected_at.isoformat(),
            "color": "#8b5cf6",
            "icon": "cpu",
        })

    # 4. IncidentActions (status changes, assignments, analyst actions)
    result = await db.execute(
        select(IncidentAction)
        .where(IncidentAction.incident_id == incident_id)
        .order_by(IncidentAction.created_at)
    )
    actions = result.scalars().all()
    for action in actions:
        events.append({
            "event_type": action.action_type.upper().replace(" ", "_"),
            "actor": "analyst" if not action.automated else "system",
            "description": action.description,
            "occurred_at": action.created_at.isoformat(),
            "color": "#3a7a50" if "close" in action.action_type.lower() else "#d97706",
            "icon": "activity",
        })

    # 5. Evidence uploads
    ev_result = await db.execute(
        select(Evidence)
        .where(Evidence.incident_id == incident_id)
        .order_by(Evidence.created_at)
    )
    evidence_items = ev_result.scalars().all()
    for ev in evidence_items:
        events.append({
            "event_type": "EVIDENCE_UPLOADED",
            "actor": "analyst",
            "description": f"Evidence file uploaded: {ev.filename} ({ev.file_size} bytes).",
            "occurred_at": ev.created_at.isoformat(),
            "color": "#0ea5e9",
            "icon": "paperclip",
        })

    # 6. Compliance records generated
    comp_result = await db.execute(
        select(ComplianceRecord)
        .where(ComplianceRecord.incident_id == incident_id)
        .order_by(ComplianceRecord.created_at)
    )
    comp_records = comp_result.scalars().all()
    for cr in comp_records:
        events.append({
            "event_type": "COMPLIANCE_GENERATED",
            "actor": "system",
            "description": f"Compliance obligation generated: {cr.regulation} — deadline {cr.deadline.strftime('%Y-%m-%d %H:%M') if cr.deadline else 'TBD'}.",
            "occurred_at": cr.created_at.isoformat(),
            "color": "#3b82f6",
            "icon": "shield",
        })

    # 7. Closed
    if incident.closed_at:
        events.append({
            "event_type": "CLOSED",
            "actor": "analyst",
            "description": "Incident reviewed and closed.",
            "occurred_at": incident.closed_at.isoformat(),
            "color": "#3a7a50",
            "icon": "check-circle",
        })

    # Sort chronologically
    events.sort(key=lambda e: e["occurred_at"])

    return {"incident_id": str(incident_id), "events": events}


# ---------------------------------------------------------------------------
# Related Incidents
# ---------------------------------------------------------------------------

@router.get("/{incident_id}/related")
async def get_related_incidents(
    incident_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.READ_INCIDENT))],
    project_id: Optional[uuid.UUID] = Query(None),
    limit: int = Query(10, ge=1, le=50),
):
    """Return incidents related by IP, attack type, or project."""
    from app.models.incident import Incident

    svc = IncidentService(db)
    incident = await svc.get(incident_id, project_id=project_id)

    clauses = [Incident.id != incident_id]
    if project_id:
        clauses.append(Incident.project_id == project_id)

    or_filters = []
    if incident.source_ip:
        or_filters.append(Incident.source_ip == incident.source_ip)
    if incident.attack_category:
        or_filters.append(Incident.attack_category == incident.attack_category)
    if incident.assigned_to:
        or_filters.append(Incident.assigned_to == incident.assigned_to)
    if incident.destination_ip:
        or_filters.append(Incident.destination_ip == incident.destination_ip)

    if not or_filters:
        # Fall back to same project
        if incident.project_id:
            or_filters.append(Incident.project_id == incident.project_id)

    if or_filters:
        clauses.append(or_(*or_filters))

    result = await db.execute(
        select(Incident)
        .where(and_(*clauses))
        .order_by(Incident.detected_at.desc())
        .limit(limit)
    )
    related = result.scalars().all()

    def _relation(r: "Incident") -> list[str]:
        reasons = []
        if incident.source_ip and r.source_ip == incident.source_ip:
            reasons.append("same_ip")
        if incident.attack_category and r.attack_category == incident.attack_category:
            reasons.append("same_attack")
        if incident.project_id and r.project_id == incident.project_id:
            reasons.append("same_project")
        if incident.assigned_to and r.assigned_to == incident.assigned_to:
            reasons.append("same_analyst")
        if incident.destination_ip and r.destination_ip == incident.destination_ip:
            reasons.append("same_dest_ip")
        return reasons or ["unknown"]

    return {
        "incident_id": str(incident_id),
        "related": [
            {
                "id": str(r.id),
                "title": r.title,
                "severity": r.severity,
                "status": r.status,
                "attack_category": r.attack_category,
                "source_ip": r.source_ip,
                "destination_ip": r.destination_ip,
                "detected_at": r.detected_at.isoformat(),
                "relations": _relation(r),
            }
            for r in related
        ],
    }


# ---------------------------------------------------------------------------
# IOC Extraction
# ---------------------------------------------------------------------------

@router.get("/{incident_id}/ioc")
async def get_incident_ioc(
    incident_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.READ_INCIDENT))],
    project_id: Optional[uuid.UUID] = Query(None),
):
    """Extract Indicators of Compromise from the incident and its evidence."""
    from app.models.evidence import Evidence

    svc = IncidentService(db)
    incident = await svc.get(incident_id, project_id=project_id)

    # Evidence hashes
    ev_result = await db.execute(
        select(Evidence).where(Evidence.incident_id == incident_id)
    )
    evidence_items = ev_result.scalars().all()
    hashes = [
        {"hash": ev.sha256_hash, "type": "sha256", "filename": ev.filename}
        for ev in evidence_items
        if ev.sha256_hash
    ]

    # Extract IPs
    ips = []
    if incident.source_ip:
        ips.append({"ip": incident.source_ip, "role": "source", "type": "ipv4"})
    if incident.destination_ip:
        ips.append({"ip": incident.destination_ip, "role": "destination", "type": "ipv4"})

    # Ports
    ports = []
    if incident.source_port:
        ports.append({"port": incident.source_port, "role": "source", "protocol": incident.protocol or "unknown"})
    if incident.destination_port:
        ports.append({"port": incident.destination_port, "role": "destination", "protocol": incident.protocol or "unknown"})

    # Build MITRE / OWASP references from explanation
    from app.services.incident_explainer import explain_incident as _explain
    exp = _explain(
        attack_category=incident.attack_category or "Unknown",
        incident_title=incident.title,
        incident_severity=incident.severity,
    )

    return {
        "incident_id": str(incident_id),
        "ips": ips,
        "ports": ports,
        "hashes": hashes,
        "protocols": [incident.protocol] if incident.protocol else [],
        "attack_category": incident.attack_category,
        "mitre_techniques": exp.get("mitre_attack", []),
        "owasp_category": exp.get("owasp"),
        "domains": [],
        "urls": [],
        "user_agents": [],
    }


# ---------------------------------------------------------------------------
# Investigation Notes
# ---------------------------------------------------------------------------

class NoteCreate(BaseModel):
    content: str = Field(min_length=1, max_length=10_000)


class NoteUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=10_000)


def _note_dict(note, author_email: str | None = None, author_name: str | None = None) -> dict:
    return {
        "id": str(note.id),
        "incident_id": str(note.incident_id),
        "author_id": str(note.author_id) if note.author_id else None,
        "author_email": author_email,
        "author_name": author_name,
        "content": note.content,
        "created_at": note.created_at.isoformat(),
        "updated_at": note.updated_at.isoformat(),
    }


@router.get("/{incident_id}/notes")
async def list_investigation_notes(
    incident_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.READ_INCIDENT))],
    project_id: Optional[uuid.UUID] = Query(None),
):
    from app.models.investigation_note import InvestigationNote
    from app.models.user import User as UserModel
    from sqlalchemy.orm import aliased

    svc = IncidentService(db)
    await svc.get(incident_id, project_id=project_id)

    AuthorAlias = aliased(UserModel)
    result = await db.execute(
        select(InvestigationNote, AuthorAlias)
        .outerjoin(AuthorAlias, InvestigationNote.author_id == AuthorAlias.id)
        .where(InvestigationNote.incident_id == incident_id)
        .order_by(InvestigationNote.created_at.desc())
    )
    rows = result.all()

    return {
        "incident_id": str(incident_id),
        "notes": [
            _note_dict(note, author.email if author else None, author.full_name if author else None)
            for note, author in rows
        ],
    }


@router.post("/{incident_id}/notes", status_code=201)
async def add_investigation_note(
    incident_id: uuid.UUID,
    body: NoteCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.UPDATE_INCIDENT))],
    project_id: Optional[uuid.UUID] = Query(None),
):
    from app.models.investigation_note import InvestigationNote

    svc = IncidentService(db)
    await svc.get(incident_id, project_id=project_id)

    note = InvestigationNote(
        incident_id=incident_id,
        author_id=current_user.id,
        content=body.content.strip(),
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)

    return _note_dict(note, current_user.email, current_user.full_name)


@router.patch("/{incident_id}/notes/{note_id}", status_code=200)
async def update_investigation_note(
    incident_id: uuid.UUID,
    note_id: uuid.UUID,
    body: NoteUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.UPDATE_INCIDENT))],
    project_id: Optional[uuid.UUID] = Query(None),
):
    from app.models.investigation_note import InvestigationNote

    svc = IncidentService(db)
    await svc.get(incident_id, project_id=project_id)

    result = await db.execute(
        select(InvestigationNote).where(
            InvestigationNote.id == note_id,
            InvestigationNote.incident_id == incident_id,
        )
    )
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    note.content = body.content.strip()
    note.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(note)

    return _note_dict(note, current_user.email, current_user.full_name)


@router.delete("/{incident_id}/notes/{note_id}", status_code=204)
async def delete_investigation_note(
    incident_id: uuid.UUID,
    note_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.UPDATE_INCIDENT))],
    project_id: Optional[uuid.UUID] = Query(None),
):
    from app.models.investigation_note import InvestigationNote

    svc = IncidentService(db)
    await svc.get(incident_id, project_id=project_id)

    result = await db.execute(
        select(InvestigationNote).where(
            InvestigationNote.id == note_id,
            InvestigationNote.incident_id == incident_id,
        )
    )
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    await db.delete(note)
    await db.commit()


# ---------------------------------------------------------------------------
# PDF Report Generation
# ---------------------------------------------------------------------------

@router.get("/{incident_id}/report")
async def generate_incident_report(
    incident_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.READ_INCIDENT))],
    project_id: Optional[uuid.UUID] = Query(None),
):
    """Generate and stream a professional PDF incident report."""
    from app.models.evidence import Evidence
    from app.models.notification import Notification
    from app.services.incident_explainer import explain_incident as _explain

    svc = IncidentService(db)
    incident = await svc.get(incident_id, project_id=project_id)

    # Evidence
    ev_result = await db.execute(
        select(Evidence).where(Evidence.incident_id == incident_id)
    )
    evidence_items = ev_result.scalars().all()

    # Notifications
    notif_result = await db.execute(
        select(Notification).where(Notification.incident_id == incident_id)
    )
    notifications = notif_result.scalars().all()

    # Explanation
    exp = _explain(
        attack_category=incident.attack_category or "Unknown",
        incident_title=incident.title,
        incident_severity=incident.severity,
        source_ip=incident.source_ip,
        destination_port=incident.destination_port,
    )

    # --- Build PDF ---
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, PageBreak,
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()
    ORANGE = colors.HexColor("#e54e1b")
    DARK   = colors.HexColor("#111111")
    GRAY   = colors.HexColor("#6b6560")
    CREAM  = colors.HexColor("#f9f5ef")
    GREEN  = colors.HexColor("#3a7a50")
    BORDER = colors.HexColor("#c8c2b8")

    title_style = ParagraphStyle("TitleStyle", parent=styles["Title"],
        fontSize=22, textColor=DARK, spaceAfter=4, fontName="Helvetica-Bold")
    h1_style = ParagraphStyle("H1", parent=styles["Heading1"],
        fontSize=14, textColor=ORANGE, spaceBefore=14, spaceAfter=6, fontName="Helvetica-Bold")
    h2_style = ParagraphStyle("H2", parent=styles["Heading2"],
        fontSize=11, textColor=DARK, spaceBefore=10, spaceAfter=4, fontName="Helvetica-Bold")
    body_style = ParagraphStyle("Body", parent=styles["Normal"],
        fontSize=9, textColor=DARK, leading=14, spaceAfter=4)
    mono_style = ParagraphStyle("Mono", parent=styles["Normal"],
        fontSize=8, fontName="Courier", textColor=colors.HexColor("#3a7a50"),
        backColor=colors.HexColor("#f0ebe2"), leftIndent=6, rightIndent=6,
        borderPadding=(4, 4, 4, 4))
    small_style = ParagraphStyle("Small", parent=styles["Normal"],
        fontSize=8, textColor=GRAY, leading=12)
    center_style = ParagraphStyle("Center", parent=styles["Normal"],
        fontSize=9, alignment=TA_CENTER, textColor=GRAY)

    now = datetime.now(timezone.utc)
    story = []

    # ── Cover ──────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph("LBRO", ParagraphStyle("Logo", parent=styles["Normal"],
        fontSize=32, fontName="Helvetica-Bold", textColor=ORANGE, alignment=TA_CENTER)))
    story.append(Paragraph("Security Incident Report", ParagraphStyle("Sub", parent=styles["Normal"],
        fontSize=14, textColor=GRAY, alignment=TA_CENTER, spaceAfter=6)))
    story.append(HRFlowable(width="100%", thickness=1, color=ORANGE, spaceAfter=10))

    sev_color = {"critical": "#ef4444", "high": "#f97316", "medium": "#f59e0b",
                 "low": "#22c55e", "info": "#3b82f6"}.get(incident.severity, "#6b6560")

    cover_data = [
        ["Incident", str(incident.id)],
        ["Title", incident.title],
        ["Severity", incident.severity.upper()],
        ["Status", incident.status.upper()],
        ["Attack Type", incident.attack_category or "Unknown"],
        ["ML Confidence", f"{round((incident.confidence_score or 0) * 100)}%"],
        ["Detected", incident.detected_at.strftime("%Y-%m-%d %H:%M UTC")],
        ["Generated", now.strftime("%Y-%m-%d %H:%M UTC")],
        ["Prepared By", current_user.full_name or current_user.email],
    ]
    cover_table = Table(cover_data, colWidths=[1.5 * inch, 5.5 * inch])
    cover_table.setStyle(TableStyle([
        ("FONTNAME",    (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE",    (0, 0), (-1, -1), 9),
        ("FONTNAME",    (0, 0), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR",   (0, 0), (0, -1), GRAY),
        ("TEXTCOLOR",   (1, 0), (1, -1), DARK),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [CREAM, colors.white]),
        ("GRID",        (0, 0), (-1, -1), 0.3, BORDER),
        ("TOPPADDING",  (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(cover_table)
    story.append(Spacer(1, 0.2 * inch))
    story.append(PageBreak())

    # ── Executive Summary ──────────────────────────────────────────────────
    story.append(Paragraph("1. Executive Summary", h1_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=6))
    story.append(Paragraph(exp["plain_english"], body_style))
    if exp.get("context"):
        story.append(Paragraph(exp["context"], ParagraphStyle("Ctx", parent=body_style, textColor=GRAY)))

    # Business / Technical impact
    story.append(Spacer(1, 0.1 * inch))
    impact_data = [
        [Paragraph("<b>Business Impact</b>", body_style), Paragraph("<b>Technical Impact</b>", body_style)],
        [Paragraph(exp["business_impact"], small_style), Paragraph(exp["technical_impact"], small_style)],
    ]
    impact_table = Table(impact_data, colWidths=[3.5 * inch, 3.5 * inch])
    impact_table.setStyle(TableStyle([
        ("GRID",       (0, 0), (-1, -1), 0.3, BORDER),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0ebe2")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN",     (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(impact_table)

    # ── Network Context ────────────────────────────────────────────────────
    story.append(Paragraph("2. Network Context", h1_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=6))
    net_rows = [["Field", "Value"]]
    for label, val in [
        ("Source IP",   incident.source_ip or "—"),
        ("Destination IP", incident.destination_ip or "—"),
        ("Source Port", str(incident.source_port) if incident.source_port else "—"),
        ("Destination Port", str(incident.destination_port) if incident.destination_port else "—"),
        ("Protocol",    incident.protocol or "—"),
    ]:
        net_rows.append([label, val])
    net_table = Table(net_rows, colWidths=[2 * inch, 5 * inch])
    net_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e54e1b")),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ("FONTNAME",   (0, 1), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR",  (0, 1), (0, -1), GRAY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [CREAM, colors.white]),
        ("GRID",       (0, 0), (-1, -1), 0.3, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(net_table)

    # ── ML Analysis ───────────────────────────────────────────────────────
    story.append(Paragraph("3. ML Analysis", h1_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=6))
    story.append(Paragraph(
        f"The LBRO ML classifier (model: <b>{incident.ml_model_version or 'heuristic'}</b>) "
        f"classified this event as <b>{incident.attack_category or 'Unknown'}</b> with "
        f"<b>{round((incident.confidence_score or 0) * 100)}% confidence</b>. "
        f"{'Manual analyst review is recommended.' if incident.needs_analyst_review else 'Confidence meets the auto-classify threshold.'}",
        body_style
    ))

    # MITRE / OWASP
    if exp.get("mitre_attack") or exp.get("owasp"):
        story.append(Spacer(1, 0.1 * inch))
        taxonomy_data = [["Framework", "Reference"]]
        if exp.get("owasp"):
            taxonomy_data.append(["OWASP", exp["owasp"]])
        for m in exp.get("mitre_attack", []):
            taxonomy_data.append(["MITRE ATT&CK", m])
        tax_table = Table(taxonomy_data, colWidths=[1.5 * inch, 5.5 * inch])
        tax_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#8b5cf6")),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",   (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [CREAM, colors.white]),
            ("GRID",       (0, 0), (-1, -1), 0.3, BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(tax_table)

    # ── Evidence ──────────────────────────────────────────────────────────
    story.append(Paragraph("4. Evidence", h1_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=6))
    if evidence_items:
        ev_data = [["Filename", "Type", "Size", "SHA-256"]]
        for ev in evidence_items:
            ev_data.append([
                ev.filename[:40],
                ev.content_type.split("/")[-1].upper(),
                f"{ev.file_size:,} B",
                (ev.sha256_hash or "")[:24] + "…" if ev.sha256_hash else "—",
            ])
        ev_table = Table(ev_data, colWidths=[2.5 * inch, 0.8 * inch, 0.8 * inch, 2.9 * inch])
        ev_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), DARK),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",   (0, 0), (-1, -1), 8),
            ("FONTNAME",   (1, 1), (3, -1), "Courier"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [CREAM, colors.white]),
            ("GRID",       (0, 0), (-1, -1), 0.3, BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(ev_table)
    else:
        story.append(Paragraph("No evidence files attached to this incident.", small_style))

    # ── Recommendations ───────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("5. Recommendations", h1_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=6))
    for i, fix in enumerate(exp.get("recommended_fixes", []), 1):
        story.append(Paragraph(f"{i}. {fix}", body_style))

    # ── Compliance Impact ─────────────────────────────────────────────────
    story.append(Paragraph("6. Compliance Impact", h1_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=6))
    story.append(Paragraph(
        f"Personal data involved: <b>{'Yes' if incident.personal_data_involved else 'No'}</b><br/>"
        f"Health data involved: <b>{'Yes' if incident.health_data_involved else 'No'}</b><br/>"
        f"Affected jurisdictions: <b>{', '.join(incident.affected_jurisdictions or []) or 'None'}</b>",
        body_style
    ))
    if notifications:
        story.append(Spacer(1, 0.1 * inch))
        notif_data = [["Regulation", "Authority", "Deadline", "Status"]]
        for n in notifications:
            notif_data.append([
                getattr(n, "regulation", None) or getattr(n, "jurisdiction", "—"),
                getattr(n, "authority", "—"),
                n.deadline.strftime("%Y-%m-%d") if n.deadline else "—",
                n.status.upper(),
            ])
        notif_table = Table(notif_data, colWidths=[1.3 * inch, 2.5 * inch, 1.5 * inch, 1.7 * inch])
        notif_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3b82f6")),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",   (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [CREAM, colors.white]),
            ("GRID",       (0, 0), (-1, -1), 0.3, BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(notif_table)

    # ── Footer ─────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.3 * inch))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=4))
    story.append(Paragraph(
        f"LBRO Incident Report · {now.strftime('%Y-%m-%d %H:%M UTC')} · CONFIDENTIAL",
        center_style
    ))

    doc.build(story)
    buf.seek(0)

    safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in incident.title[:40])
    filename = f"LBRO_Incident_{incident.external_id or str(incident_id)[:8]}_{safe_title}.pdf"

    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
