"""Weekly Security Report endpoints.

GET /api/v1/reports/weekly      → JSON report (for preview)
GET /api/v1/reports/weekly/pdf  → PDF file (for download)

All data is pulled from live DB state at request time.
"""
from __future__ import annotations

import uuid

import io
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Permission
from app.database import get_db
from app.dependencies import require_permission
from app.models.audit import AuditLog
from app.models.compliance import ComplianceRecord
from app.models.evidence import Evidence
from app.models.incident import Incident, IncidentSeverity, IncidentStatus
from app.models.user import User

router = APIRouter(prefix="/reports", tags=["reports"])


# ── Shared data builder ───────────────────────────────────────────────────────

async def _build_report_data(db: AsyncSession, project_id=None, days: int = 7) -> dict:
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=days)
    open_statuses = [s.value for s in IncidentStatus if s != IncidentStatus.CLOSED]

    def _pf(q):
        if project_id is not None:
            q = q.where(Incident.project_id == project_id)
        return q

    # ── Incident counts ───────────────────────────────────────────────────────
    total = (await db.execute(_pf(select(func.count(Incident.id))))).scalar_one()

    open_critical = (await db.execute(_pf(select(func.count(Incident.id)).where(
        Incident.severity == IncidentSeverity.CRITICAL.value,
        Incident.status.in_(open_statuses),
    )))).scalar_one()

    open_high = (await db.execute(_pf(select(func.count(Incident.id)).where(
        Incident.severity == IncidentSeverity.HIGH.value,
        Incident.status.in_(open_statuses),
    )))).scalar_one()

    open_medium = (await db.execute(_pf(select(func.count(Incident.id)).where(
        Incident.severity == IncidentSeverity.MEDIUM.value,
        Incident.status.in_(open_statuses),
    )))).scalar_one()

    open_low = (await db.execute(_pf(select(func.count(Incident.id)).where(
        Incident.severity == IncidentSeverity.LOW.value,
        Incident.status.in_(open_statuses),
    )))).scalar_one()

    new_this_week = (await db.execute(_pf(select(func.count(Incident.id)).where(
        Incident.created_at >= week_ago,
    )))).scalar_one()

    closed_this_week = (await db.execute(_pf(select(func.count(Incident.id)).where(
        Incident.status == IncidentStatus.CLOSED.value,
        Incident.updated_at >= week_ago,
    )))).scalar_one()

    # ── Top attack categories ─────────────────────────────────────────────────
    attack_rows = (await db.execute(
        _pf(select(Incident.attack_category, func.count(Incident.id).label("cnt"))
        .where(Incident.attack_category.isnot(None))
        .group_by(Incident.attack_category)
        .order_by(func.count(Incident.id).desc())
        .limit(5))
    )).all()
    top_attack_types = [{"category": r[0], "count": r[1]} for r in attack_rows]

    # ── Most targeted ports ───────────────────────────────────────────────────
    port_rows = (await db.execute(
        _pf(select(Incident.destination_port, func.count(Incident.id).label("cnt"))
        .where(Incident.destination_port.isnot(None))
        .group_by(Incident.destination_port)
        .order_by(func.count(Incident.id).desc())
        .limit(5))
    )).all()
    most_targeted_ports = [{"port": r[0], "count": r[1]} for r in port_rows]

    # ── Critical open incidents ───────────────────────────────────────────────
    crit_result = await db.execute(
        _pf(select(Incident)
        .where(
            Incident.severity == IncidentSeverity.CRITICAL.value,
            Incident.status.in_(open_statuses),
        )
        .order_by(Incident.created_at.desc())
        .limit(5))
    )
    critical_incidents = [
        {
            "id": str(i.id), "title": i.title,
            "severity": i.severity, "status": i.status,
            "created_at": i.created_at.isoformat(),
        }
        for i in crit_result.scalars().all()
    ]

    # ── Recently resolved incidents ───────────────────────────────────────────
    resolved_result = await db.execute(
        _pf(select(Incident)
        .where(
            Incident.status == IncidentStatus.CLOSED.value,
            Incident.updated_at >= week_ago,
        )
        .order_by(Incident.updated_at.desc())
        .limit(5))
    )
    resolved_incidents = [
        {
            "id": str(i.id), "title": i.title,
            "severity": i.severity, "resolved_at": i.updated_at.isoformat(),
        }
        for i in resolved_result.scalars().all()
    ]

    # ── Evidence ──────────────────────────────────────────────────────────────
    evidence_count = (await db.execute(select(func.count(Evidence.id)))).scalar_one()

    # ── Compliance ────────────────────────────────────────────────────────────
    compliance_total = (await db.execute(select(func.count(ComplianceRecord.id)))).scalar_one()
    compliance_met = (await db.execute(
        select(func.count(ComplianceRecord.id)).where(ComplianceRecord.is_met == True)
    )).scalar_one()

    # ── Users / MFA ───────────────────────────────────────────────────────────
    total_users = (await db.execute(select(func.count(User.id)))).scalar_one()
    users_without_mfa = (await db.execute(
        select(func.count(User.id)).where(User.mfa_enabled == False, User.is_active == True)
    )).scalar_one()

    # ── Audit: 403 spikes ────────────────────────────────────────────────────
    recent_403s = (await db.execute(
        select(func.count(AuditLog.id)).where(
            AuditLog.response_status == 403,
            AuditLog.created_at >= now - timedelta(hours=24),
        )
    )).scalar_one()

    # ── Security score (inline re-calc for report) ────────────────────────────
    score = 100
    score -= min(open_critical * 15, 45)
    score -= min(open_high * 8, 24)
    score -= min((open_medium + open_low) * 2, 10)
    score -= min(users_without_mfa * 4, 20)
    if recent_403s > 50:
        score -= 10
    overdue = (await db.execute(
        select(func.count(ComplianceRecord.id)).where(
            ComplianceRecord.is_met == False,
            ComplianceRecord.deadline < now,
        )
    )).scalar_one()
    score -= min(overdue * 5, 15)
    if users_without_mfa == 0 and total_users > 0:
        score += 5
    if compliance_total > 0 and compliance_met == compliance_total:
        score += 5
    score = max(0, min(100, score))

    if score >= 90:   grade, color, status_label = "A", "#22c55e", "Excellent"
    elif score >= 75: grade, color, status_label = "B", "#84cc16", "Good"
    elif score >= 60: grade, color, status_label = "C", "#f59e0b", "Needs Attention"
    elif score >= 40: grade, color, status_label = "D", "#f97316", "At Risk"
    else:             grade, color, status_label = "F", "#ef4444", "Critical"

    # ── Trend ─────────────────────────────────────────────────────────────────
    if closed_this_week > new_this_week:
        trend, trend_reason = "improving", f"Your team closed {closed_this_week} incidents vs {new_this_week} new ones this week."
    elif new_this_week > closed_this_week * 1.5:
        trend, trend_reason = "worsening", f"New incidents ({new_this_week}) are outpacing resolutions ({closed_this_week})."
    else:
        trend, trend_reason = "stable", f"{new_this_week} new incidents and {closed_this_week} closures this week."

    # ── Executive summary ─────────────────────────────────────────────────────
    parts = []
    if open_critical > 0:
        parts.append(f"{open_critical} critical incident{'s' if open_critical != 1 else ''} remain{'s' if open_critical == 1 else ''} open and require immediate attention.")
    if users_without_mfa > 0:
        parts.append(f"{users_without_mfa} user account{'s' if users_without_mfa != 1 else ''} {'do' if users_without_mfa != 1 else 'does'} not have MFA enabled.")
    if overdue > 0:
        parts.append(f"{overdue} compliance requirement{'s' if overdue != 1 else ''} {'are' if overdue != 1 else 'is'} overdue.")
    if not parts:
        if score >= 80:
            parts.append("Your security posture is strong this week. Continue monitoring for new threats.")
        else:
            parts.append("Several medium-priority items need attention. Review the recommendations below.")
    executive_summary = " ".join(parts)

    # ── Recommendations ───────────────────────────────────────────────────────
    recommendations = []
    if open_critical > 0:
        recommendations.append({
            "priority": "critical",
            "title": f"Resolve {open_critical} open critical incident{'s' if open_critical != 1 else ''}",
            "detail": "Critical incidents represent active or high-impact threats. Each day they remain open increases your exposure.",
        })
    if users_without_mfa > 0:
        recommendations.append({
            "priority": "high",
            "title": "Enable MFA for all team members",
            "detail": f"{users_without_mfa} accounts lack a second factor. MFA prevents over 99% of automated credential attacks.",
        })
    if overdue > 0:
        recommendations.append({
            "priority": "medium",
            "title": "Address overdue compliance requirements",
            "detail": f"{overdue} compliance item{'s' if overdue != 1 else ''} passed their deadline, increasing regulatory risk.",
        })
    if recent_403s > 50:
        recommendations.append({
            "priority": "medium",
            "title": "Investigate unusual authorization activity",
            "detail": f"{recent_403s} forbidden-access attempts in 24 hours exceeds normal baseline.",
        })

    return {
        "generated_at": now.isoformat(),
        "period_start": week_ago.isoformat(),
        "period_end": now.isoformat(),
        "security_score": score,
        "security_grade": grade,
        "security_color": color,
        "security_status": status_label,
        "executive_summary": executive_summary,
        "total_incidents": total,
        "incidents": {
            "open_critical": open_critical,
            "open_high": open_high,
            "open_medium": open_medium,
            "open_low": open_low,
            "new_this_week": new_this_week,
            "closed_this_week": closed_this_week,
            "top_attack_types": top_attack_types,
            "most_targeted_ports": most_targeted_ports,
            "critical_incidents": critical_incidents,
            "resolved_incidents": resolved_incidents,
        },
        "evidence_count": evidence_count,
        "compliance_met": compliance_met,
        "compliance_total": compliance_total,
        "top_recommendations": recommendations,
        "trend": trend,
        "trend_reason": trend_reason,
    }


# ── JSON endpoint ─────────────────────────────────────────────────────────────

@router.get("/weekly")
async def weekly_report_json(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_DASHBOARD))],
    project_id: Optional[uuid.UUID] = Query(None),
    days: Annotated[int, Query(ge=1, le=365)] = 7,
):
    """Return the weekly security report as JSON (used for the preview UI)."""
    return await _build_report_data(db, project_id=project_id, days=days)


# ── PDF endpoint ──────────────────────────────────────────────────────────────

@router.get("/weekly/pdf")
async def weekly_report_pdf(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_DASHBOARD))],
    project_id: Optional[uuid.UUID] = Query(None),
    days: Annotated[int, Query(ge=1, le=365)] = 7,
):
    """Generate and stream the weekly security report as a PDF file."""
    data = await _build_report_data(db, project_id=project_id, days=days)
    pdf_bytes = _generate_pdf(data)
    filename = f"lbro-security-report-{datetime.now().strftime('%Y-%m-%d')}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )


# ── PDF generation (reportlab) ────────────────────────────────────────────────

def _generate_pdf(data: dict) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, mm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, KeepTogether,
    )
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=25 * mm,  # extra bottom margin for page number footer
        title="LBRO Weekly Security Report",
    )

    # ── Colour palette ────────────────────────────────────────────────────────
    BLACK      = colors.HexColor("#111111")
    ORANGE     = colors.HexColor("#e54e1b")
    CREAM      = colors.HexColor("#f9f5ef")
    GRAY       = colors.HexColor("#6b6560")
    BORDER_COL = colors.HexColor("#c8c2b8")
    GREEN      = colors.HexColor("#22c55e")
    AMBER      = colors.HexColor("#f59e0b")
    RED        = colors.HexColor("#ef4444")

    score_color_map = {
        "A": GREEN, "B": colors.HexColor("#84cc16"),
        "C": AMBER, "D": colors.HexColor("#f97316"), "F": RED,
    }
    score_color = score_color_map.get(data["security_grade"], ORANGE)

    priority_colors = {"critical": RED, "high": ORANGE, "medium": AMBER, "low": GRAY}

    # ── Styles ────────────────────────────────────────────────────────────────
    styles = getSampleStyleSheet()

    def style(name, **kwargs):
        return ParagraphStyle(name, **kwargs)

    S = {
        "h1": style("H1", fontName="Helvetica-Bold", fontSize=28, textColor=BLACK,
                    spaceAfter=4, leading=32),
        "h2": style("H2", fontName="Helvetica-Bold", fontSize=14, textColor=BLACK,
                    spaceBefore=18, spaceAfter=6, leading=18),
        "h3": style("H3", fontName="Helvetica-Bold", fontSize=11, textColor=BLACK,
                    spaceBefore=10, spaceAfter=4, leading=14),
        "body": style("Body", fontName="Helvetica", fontSize=10, textColor=BLACK,
                      leading=14, spaceAfter=6),
        "small": style("Small", fontName="Helvetica", fontSize=8, textColor=GRAY, leading=11),
        "label": style("Label", fontName="Helvetica-Bold", fontSize=8, textColor=GRAY,
                       leading=10, spaceAfter=2),
        "orange": style("Orange", fontName="Helvetica-Bold", fontSize=10, textColor=ORANGE),
        "center": style("Center", fontName="Helvetica", fontSize=10, textColor=BLACK,
                        alignment=TA_CENTER, leading=14),
        "score": style("Score", fontName="Helvetica-Bold", fontSize=48,
                       textColor=score_color, alignment=TA_CENTER, leading=52),
        "grade": style("Grade", fontName="Helvetica-Bold", fontSize=20,
                       textColor=score_color, alignment=TA_CENTER, leading=24),
        "mono": style("Mono", fontName="Courier", fontSize=9, textColor=GRAY, leading=12),
    }

    content_width = A4[0] - 40 * mm  # usable width (A4 minus left+right margins)

    # ── Page footer with page numbers ─────────────────────────────────────────
    _gray_rgb = colors.HexColor("#6b6560")

    def _page_footer(canvas, doc):  # type: ignore[no-untyped-def]
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(_gray_rgb)
        page_num = canvas.getPageNumber()
        generated = datetime.fromisoformat(data["generated_at"]).strftime("%b %d, %Y")
        footer_text = (
            f"LBRO Security Platform  ·  Confidential  ·  "
            f"Generated {generated}  ·  Page {page_num}"
        )
        canvas.drawCentredString(A4[0] / 2, 10 * mm, footer_text)
        canvas.restoreState()

    story = []

    def hr():
        story.append(HRFlowable(width="100%", thickness=1, color=BORDER_COL, spaceAfter=6, spaceBefore=6))

    def section(title: str):
        story.append(Spacer(1, 4))
        story.append(Paragraph(title, S["h2"]))
        hr()

    # ── Cover block ───────────────────────────────────────────────────────────
    generated = datetime.fromisoformat(data["generated_at"]).strftime("%B %d, %Y at %H:%M UTC")
    period_start = datetime.fromisoformat(data["period_start"]).strftime("%b %d")
    period_end   = datetime.fromisoformat(data["period_end"]).strftime("%b %d, %Y")

    story.append(Paragraph("LBRO", S["h1"]))
    story.append(Paragraph(
        f"Weekly Security Report  ·  {period_start} – {period_end}",
        style("sub", fontName="Helvetica", fontSize=13, textColor=GRAY, leading=16, spaceAfter=4)
    ))
    story.append(Paragraph(f"Generated {generated}", S["small"]))
    story.append(Spacer(1, 14))
    hr()

    # ── Score + summary row ───────────────────────────────────────────────────
    score_cell = [
        Paragraph(str(data["security_score"]), S["score"]),
        Paragraph(f"Grade {data['security_grade']}  ·  {data['security_status']}", S["grade"]),
    ]
    summary_cell = [
        Paragraph("Executive Summary", S["h3"]),
        Spacer(1, 4),
        Paragraph(data["executive_summary"], S["body"]),
        Spacer(1, 8),
        Paragraph(f"Trend: {data['trend'].upper()}", S["label"]),
        Paragraph(data["trend_reason"], style("tr", fontName="Helvetica", fontSize=9,
                                               textColor=BLACK, leading=12)),
    ]
    tbl = Table([[score_cell, summary_cell]], colWidths=[1.8 * inch, content_width - 1.8 * inch])
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (0, 0), CREAM),
        ("BOX", (0, 0), (0, 0), 0.5, BORDER_COL),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (0, 0), 8),
        ("RIGHTPADDING", (0, 0), (0, 0), 8),
        ("LEFTPADDING", (1, 0), (1, 0), 16),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 14))

    # ── Incident summary ──────────────────────────────────────────────────────
    section("Incident Summary")
    inc = data["incidents"]
    stat_data = [
        ["New This Week", "Resolved", "Open Critical", "Open High"],
        [
            str(inc["new_this_week"]),
            str(inc["closed_this_week"]),
            str(inc["open_critical"]),
            str(inc["open_high"]),
        ],
    ]
    w4 = content_width / 4
    stat_tbl = Table(stat_data, colWidths=[w4] * 4)
    stat_tbl.setStyle(TableStyle([
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica"),
        ("FONTSIZE",   (0, 0), (-1, 0), 8),
        ("TEXTCOLOR",  (0, 0), (-1, 0), GRAY),
        ("FONTNAME",   (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 1), (-1, 1), 22),
        ("TEXTCOLOR",  (0, 1), (0, 1), BLACK),
        ("TEXTCOLOR",  (1, 1), (1, 1), GREEN),
        ("TEXTCOLOR",  (2, 1), (2, 1), RED if inc["open_critical"] > 0 else BLACK),
        ("TEXTCOLOR",  (3, 1), (3, 1), ORANGE if inc["open_high"] > 0 else BLACK),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("BACKGROUND", (0, 0), (-1, -1), CREAM),
        ("GRID",       (0, 0), (-1, -1), 0.5, BORDER_COL),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(stat_tbl)
    story.append(Spacer(1, 10))

    # ── Top attack types ──────────────────────────────────────────────────────
    if inc["top_attack_types"]:
        section("Top Attack Types This Week")
        atk_data = [["Attack Type", "Count"]] + [
            [r["category"], str(r["count"])] for r in inc["top_attack_types"]
        ]
        atk_tbl = Table(atk_data, colWidths=[content_width * 0.75, content_width * 0.25])
        atk_tbl.setStyle(TableStyle([
            ("FONTNAME",  (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",  (0, 0), (-1, 0), 9),
            ("TEXTCOLOR", (0, 0), (-1, 0), GRAY),
            ("FONTNAME",  (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE",  (0, 1), (-1, -1), 10),
            ("BACKGROUND",(0, 0), (-1, 0), CREAM),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CREAM]),
            ("GRID",      (0, 0), (-1, -1), 0.5, BORDER_COL),
            ("TOPPADDING",(0, 0), (-1, -1), 6),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("FONTNAME",  (1, 1), (1, -1), "Helvetica-Bold"),
            ("TEXTCOLOR", (1, 1), (1, -1), ORANGE),
            ("ALIGN",     (1, 0), (1, -1), "CENTER"),
        ]))
        story.append(atk_tbl)

    # ── Critical open incidents ───────────────────────────────────────────────
    if inc["critical_incidents"]:
        section("Open Critical Incidents")
        for ci in inc["critical_incidents"]:
            ts = datetime.fromisoformat(ci["created_at"]).strftime("%b %d, %Y")
            row_data = [[
                [Paragraph(ci["title"], S["h3"]),
                 Paragraph(f"Status: {ci['status'].upper()}  ·  Opened: {ts}", S["small"])],
                [Paragraph("CRITICAL", style("crit", fontName="Helvetica-Bold", fontSize=9,
                                              textColor=RED, alignment=TA_RIGHT))],
            ]]
            row_tbl = Table(row_data, colWidths=[content_width * 0.8, content_width * 0.2])
            row_tbl.setStyle(TableStyle([
                ("VALIGN",  (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (0, 0), 10),
                ("RIGHTPADDING", (1, 0), (1, 0), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fff5f5")),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, BORDER_COL),
                ("LINEBEFORE", (0, 0), (0, -1), 3, RED),
            ]))
            story.append(row_tbl)
        story.append(Spacer(1, 6))

    # ── Resolved incidents ────────────────────────────────────────────────────
    if inc["resolved_incidents"]:
        section("Resolved This Week")
        for ri in inc["resolved_incidents"]:
            ts = datetime.fromisoformat(ri["resolved_at"]).strftime("%b %d, %Y")
            sev = ri["severity"].upper()
            sev_color = {"CRITICAL": RED, "HIGH": ORANGE, "MEDIUM": AMBER}.get(sev, GRAY)
            row = [[
                Paragraph(f"✓  {ri['title']}", style("res", fontName="Helvetica", fontSize=10,
                                                       textColor=BLACK, leading=13)),
                Paragraph(f"{sev}  ·  {ts}", style("res2", fontName="Helvetica", fontSize=8,
                                                     textColor=sev_color, alignment=TA_RIGHT)),
            ]]
            tbl2 = Table(row, colWidths=[content_width * 0.7, content_width * 0.3])
            tbl2.setStyle(TableStyle([
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (0, 0), 10),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, BORDER_COL),
                ("LINEBEFORE", (0, 0), (0, -1), 3, GREEN),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0fff4")),
            ]))
            story.append(tbl2)
        story.append(Spacer(1, 6))

    # ── Evidence + Compliance ─────────────────────────────────────────────────
    section("Evidence & Compliance")
    comp_pct = (
        round(data["compliance_met"] / data["compliance_total"] * 100)
        if data["compliance_total"] > 0 else 100
    )
    ec_data = [
        ["Evidence Packages", "Compliance Requirements Met", "Compliance %"],
        [
            str(data["evidence_count"]),
            f"{data['compliance_met']} / {data['compliance_total']}",
            f"{comp_pct}%",
        ],
    ]
    ec_tbl = Table(ec_data, colWidths=[content_width / 3] * 3)
    ec_tbl.setStyle(TableStyle([
        ("FONTNAME",  (0, 0), (-1, 0), "Helvetica"),
        ("FONTSIZE",  (0, 0), (-1, 0), 8),
        ("TEXTCOLOR", (0, 0), (-1, 0), GRAY),
        ("FONTNAME",  (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE",  (0, 1), (-1, 1), 20),
        ("ALIGN",     (0, 0), (-1, -1), "CENTER"),
        ("BACKGROUND",(0, 0), (-1, -1), CREAM),
        ("GRID",      (0, 0), (-1, -1), 0.5, BORDER_COL),
        ("TOPPADDING",(0, 0), (-1, -1), 10),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (2, 1), (2, 1), GREEN if comp_pct == 100 else (AMBER if comp_pct >= 75 else RED)),
    ]))
    story.append(ec_tbl)

    # ── Recommendations ───────────────────────────────────────────────────────
    if data["top_recommendations"]:
        section("Recommendations")
        for i, rec in enumerate(data["top_recommendations"]):
            p_color = priority_colors.get(rec["priority"], GRAY)
            rec_data = [[
                Paragraph(f"{i + 1}", style(f"num{i}", fontName="Helvetica-Bold", fontSize=12,
                                             textColor=colors.white, alignment=TA_CENTER)),
                [
                    Paragraph(rec["title"], style(f"rt{i}", fontName="Helvetica-Bold", fontSize=11,
                                                   textColor=BLACK, spaceAfter=3)),
                    Paragraph(rec["detail"], S["body"]),
                ],
            ]]
            rec_tbl = Table(rec_data, colWidths=[0.35 * inch, content_width - 0.35 * inch])
            rec_tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (0, 0), p_color),
                ("VALIGN",     (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (1, 0), (1, 0), 12),
                ("LINEBELOW",  (0, 0), (-1, -1), 0.5, BORDER_COL),
            ]))
            story.append(rec_tbl)

    # ── Footer note (page numbers come from _page_footer callback) ────────────
    story.append(Spacer(1, 20))
    hr()
    story.append(Paragraph(
        f"This report was automatically generated by LBRO on {generated}. "
        "Data reflects live application state at the time of generation.",
        S["small"],
    ))

    doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return buf.getvalue()


# ── Compliance Audit PDF endpoint ─────────────────────────────────────────────

@router.get("/compliance/pdf")
async def compliance_report_pdf(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission(Permission.VIEW_COMPLIANCE))],
    project_id: Optional[uuid.UUID] = Query(None),
):
    """Generate and stream the compliance audit report as a PDF file."""
    pdf_bytes = await _generate_compliance_pdf(db, project_id=project_id)
    filename = f"lbro-compliance-audit-{datetime.now().strftime('%Y-%m-%d')}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )


async def _generate_compliance_pdf(db: AsyncSession, project_id=None) -> bytes:
    """Query compliance records and generate a PDF audit report."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
    )
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT

    now = datetime.now(timezone.utc)

    # ── Pull records from DB ──────────────────────────────────────────────────
    if project_id is not None:
        from sqlalchemy import join
        compliance_q = (
            select(ComplianceRecord)
            .join(Incident, ComplianceRecord.incident_id == Incident.id)
            .where(Incident.project_id == project_id)
            .order_by(ComplianceRecord.regulation, ComplianceRecord.obligation)
        )
    else:
        compliance_q = select(ComplianceRecord).order_by(
            ComplianceRecord.regulation,
            ComplianceRecord.obligation,
        )
    result = await db.execute(compliance_q)
    records = result.scalars().all()

    total     = len(records)
    met       = sum(1 for r in records if r.is_met)
    overdue   = sum(1 for r in records if not r.is_met and r.deadline < now)
    pending   = total - met - overdue

    regs: dict = {}
    for r in records:
        regs.setdefault(r.regulation, []).append(r)

    # ── Colour palette ────────────────────────────────────────────────────────
    BLACK      = colors.HexColor("#111111")
    ORANGE     = colors.HexColor("#e54e1b")
    CREAM      = colors.HexColor("#f9f5ef")
    GRAY       = colors.HexColor("#6b6560")
    BORDER_COL = colors.HexColor("#c8c2b8")
    GREEN      = colors.HexColor("#22c55e")
    AMBER      = colors.HexColor("#f59e0b")
    RED        = colors.HexColor("#ef4444")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=25 * mm,
        title="LBRO Compliance Audit Report",
    )

    cw = A4[0] - 40 * mm   # content width

    def s(name, **kw):
        return ParagraphStyle(name, **kw)

    S = {
        "h1":    s("H1",    fontName="Helvetica-Bold", fontSize=28, textColor=BLACK,   spaceAfter=4,  leading=32),
        "h2":    s("H2",    fontName="Helvetica-Bold", fontSize=14, textColor=BLACK,   spaceBefore=18,spaceAfter=6, leading=18),
        "h3":    s("H3",    fontName="Helvetica-Bold", fontSize=11, textColor=BLACK,   spaceBefore=8, spaceAfter=3, leading=14),
        "body":  s("Body",  fontName="Helvetica",      fontSize=10, textColor=BLACK,   leading=14,    spaceAfter=4),
        "small": s("Small", fontName="Helvetica",      fontSize=8,  textColor=GRAY,    leading=11),
        "label": s("Label", fontName="Helvetica-Bold", fontSize=8,  textColor=GRAY,    leading=10,    spaceAfter=2),
        "center":s("Center",fontName="Helvetica-Bold", fontSize=18, textColor=BLACK,   alignment=TA_CENTER, leading=22),
    }

    def hr():
        story.append(HRFlowable(width="100%", thickness=1, color=BORDER_COL, spaceAfter=6, spaceBefore=6))

    generated_str = now.strftime("%B %d, %Y at %H:%M UTC")

    def _footer(canvas, doc):  # type: ignore[no-untyped-def]
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(GRAY)
        page_num = canvas.getPageNumber()
        canvas.drawCentredString(
            A4[0] / 2, 10 * mm,
            f"LBRO Compliance Audit  ·  Confidential  ·  Generated {now.strftime('%b %d, %Y')}  ·  Page {page_num}",
        )
        canvas.restoreState()

    story: list = []

    # Title
    story.append(Paragraph("LBRO", S["h1"]))
    story.append(Paragraph("Compliance Audit Report", s("sub", fontName="Helvetica", fontSize=13, textColor=GRAY, leading=16, spaceAfter=4)))
    story.append(Paragraph(f"Generated {generated_str}", S["small"]))
    story.append(Spacer(1, 14))
    hr()

    # Summary stats
    pct = round(met / total * 100) if total > 0 else 100
    stat_data = [
        ["Total Requirements", "Met", "Overdue", "Pending", "Compliance %"],
        [str(total), str(met), str(overdue), str(pending), f"{pct}%"],
    ]
    w5 = cw / 5
    stat_tbl = Table(stat_data, colWidths=[w5] * 5)
    stat_tbl.setStyle(TableStyle([
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica"),
        ("FONTSIZE",      (0, 0), (-1, 0), 8),
        ("TEXTCOLOR",     (0, 0), (-1, 0), GRAY),
        ("FONTNAME",      (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 1), (-1, 1), 20),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("BACKGROUND",    (0, 0), (-1, -1), CREAM),
        ("GRID",          (0, 0), (-1, -1), 0.5, BORDER_COL),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR",     (1, 1), (1, 1), GREEN),
        ("TEXTCOLOR",     (2, 1), (2, 1), RED   if overdue > 0 else GREEN),
        ("TEXTCOLOR",     (4, 1), (4, 1), GREEN if pct == 100 else (AMBER if pct >= 75 else RED)),
    ]))
    story.append(stat_tbl)
    story.append(Spacer(1, 10))

    # Per-regulation breakdown
    for reg, reg_records in regs.items():
        reg_met = sum(1 for r in reg_records if r.is_met)
        reg_pct = round(reg_met / len(reg_records) * 100) if reg_records else 100

        story.append(Paragraph(f"{reg}  —  {reg_met}/{len(reg_records)} met ({reg_pct}%)", S["h2"]))
        hr()

        tbl_data = [["Obligation", "Status", "Deadline", "Notes"]]
        for r in reg_records:
            if r.is_met:
                status, status_color = "MET", GREEN
            elif r.deadline < now:
                status, status_color = "OVERDUE", RED
            else:
                status, status_color = "PENDING", AMBER

            deadline_str = r.deadline.strftime("%Y-%m-%d") if r.deadline else "—"
            notes = (r.notes or "—")[:60]

            tbl_data.append([
                Paragraph(r.obligation or "—", S["body"]),
                Paragraph(status, s(f"st_{r.id}", fontName="Helvetica-Bold", fontSize=9, textColor=status_color)),
                Paragraph(deadline_str, S["small"]),
                Paragraph(notes, S["small"]),
            ])

        col_widths = [cw * 0.45, cw * 0.12, cw * 0.15, cw * 0.28]
        reg_tbl = Table(tbl_data, colWidths=col_widths, repeatRows=1)
        reg_tbl.setStyle(TableStyle([
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, 0), 8),
            ("TEXTCOLOR",     (0, 0), (-1, 0), GRAY),
            ("BACKGROUND",    (0, 0), (-1, 0), CREAM),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, CREAM]),
            ("GRID",          (0, 0), (-1, -1), 0.5, BORDER_COL),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(reg_tbl)
        story.append(Spacer(1, 10))

    # Footer note
    story.append(Spacer(1, 20))
    hr()
    story.append(Paragraph(
        f"This compliance audit report was automatically generated by LBRO on {generated_str}. "
        "It reflects the current state of compliance records in the database and does not constitute a formal audit opinion.",
        S["small"],
    ))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
