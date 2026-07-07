#!/usr/bin/env python3
"""
LBRO Demo Data Seeder
=====================
Populates PostgreSQL with realistic demonstration data suitable for
portfolio review, interviews, and frontend integration testing.

Seeded (idempotent — safe to re-run):
  • 10 users  (1 admin, 4 analysts, 5 viewers)
  • 100 incidents  (CICIDS2017 attack distribution, realistic IPs/ports/timestamps)
  • 150 evidence records  (pcap, json, txt, zip, png, pdf) with chain-of-custody
  •  50 regulatory notifications  (GDPR / HIPAA / DPDPA)
  •  ~80 compliance records  (triggered by jurisdiction / data flags)
  • 500 audit log entries

Frontend pages covered by seeded data:
  Dashboard · Incidents · Incident Detail · Evidence Vault · Notifications
  Compliance · Compliance Audit PDF · Threat Intel · ML Insights · Security Score
  Weekly Report · Audit Logs · Users · Settings

Usage:
  python scripts/seed_demo_data.py         # idempotent — skips existing data
  python scripts/seed_demo_data.py --wipe  # wipe demo data then re-seed

Environment:
  DATABASE_URL  postgresql+asyncpg://user:pass@host/db
  (Falls back to backend/.env if not set in environment)
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import random
import secrets
import sys
import uuid
from datetime import datetime, timedelta, timezone

# ── Path setup ────────────────────────────────────────────────────────────────
_here = os.path.dirname(os.path.abspath(__file__))
for _candidate in [os.path.join(_here, "..", "backend"), "/app"]:
    _candidate = os.path.normpath(_candidate)
    if os.path.isdir(os.path.join(_candidate, "app")):
        sys.path.insert(0, _candidate)
        break

# Load backend/.env if present
_env_path = os.path.join(_here, "..", "backend", ".env")
if os.path.exists(_env_path):
    for _line in open(_env_path):
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

from sqlalchemy import delete as sa_delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.audit import AuditLog
from app.models.compliance import ComplianceRecord
from app.models.evidence import Evidence, ChainOfCustody
from app.models.incident import Incident, IncidentAction
from app.models.notification import Notification, NotificationRecipient
from app.models.user import User

# ─────────────────────────────────────────────────────────────────────────────
# Data pools
# ─────────────────────────────────────────────────────────────────────────────

DEMO_EMAIL_DOMAIN = "lbro.demo"

DEMO_USERS = [
    # (full_name, email, role, password)
    ("Priya Sharma",      f"priya.sharma@lbro.demo",    "admin",   "Admin@Demo1!"),
    ("James Okafor",      f"james.okafor@lbro.demo",    "analyst", "Analyst@Demo1!"),
    ("Mei-Ling Chen",     f"mei.chen@lbro.demo",        "analyst", "Analyst@Demo2!"),
    ("Rafael Torres",     f"rafael.torres@lbro.demo",   "analyst", "Analyst@Demo3!"),
    ("Aisha Mohammed",    f"aisha.mohammed@lbro.demo",  "analyst", "Analyst@Demo4!"),
    ("Dmitri Volkov",     f"dmitri.volkov@lbro.demo",   "viewer",  "Viewer@Demo1!"),
    ("Yuki Tanaka",       f"yuki.tanaka@lbro.demo",     "viewer",  "Viewer@Demo2!"),
    ("Fatima Al-Rashid",  f"fatima.alrashid@lbro.demo", "viewer",  "Viewer@Demo3!"),
    ("Marcus Johnson",    f"marcus.johnson@lbro.demo",  "viewer",  "Viewer@Demo4!"),
    ("Lena Mueller",      f"lena.muller@lbro.demo",     "viewer",  "Viewer@Demo5!"),
]

# CICIDS2017 attack categories — weighted to match realistic intrusion distributions
ATTACK_WEIGHTS = [
    ("PortScan",                      22),
    ("DoS Hulk",                      18),
    ("DDoS",                          14),
    ("Web Attack - Brute Force",      12),
    ("Bot",                            9),
    ("DoS GoldenEye",                  7),
    ("FTP-Patator",                    5),
    ("SSH-Patator",                    5),
    ("Web Attack - XSS",               4),
    ("DoS slowloris",                  3),
    ("Web Attack - Sql Injection",     3),
    ("DoS Slowhttptest",               2),
    ("Infiltration",                   2),
    ("Heartbleed",                     1),
]
ATTACK_CATEGORIES = [a for a, _ in ATTACK_WEIGHTS]
ATTACK_W          = [w for _, w in ATTACK_WEIGHTS]

SEVERITY_WEIGHTS = [("critical", 10), ("high", 25), ("medium", 40), ("low", 25)]
SEVERITIES = [s for s, _ in SEVERITY_WEIGHTS]
SEVERITY_W = [w for _, w in SEVERITY_WEIGHTS]

STATUS_WEIGHTS = [
    ("new", 30), ("triaging", 20), ("contained", 15),
    ("eradicating", 10), ("recovering", 8), ("closed", 15), ("reopened", 2),
]
STATUSES = [s for s, _ in STATUS_WEIGHTS]
STATUS_W = [w for _, w in STATUS_WEIGHTS]

SOURCE_IP_PREFIXES = [
    ("185.220.101.", 30), ("194.165.16.", 20), ("103.224.182.", 15),
    ("45.142.212.",  15), ("198.98.56.",  10), ("81.161.64.",   10),
]
DEST_PORTS = [
    (80,   "HTTP",     20), (443,  "HTTPS",    18), (22,   "SSH",      16),
    (21,   "FTP",      12), (3306, "MySQL",     8), (5432, "Postgres",  6),
    (8080, "HTTP-Alt",  5), (445,  "SMB",       5), (3389, "RDP",       5),
    (6379, "Redis",     5),
]
PROTOCOLS = ["TCP", "UDP", "ICMP"]

# Jurisdictions that trigger compliance obligations
JURISDICTION_POOL = [
    ["EU"], ["EU", "DE"], ["EU", "FR"], ["US"], ["IN"],
    ["US", "EU"], ["UK"], ["AU"], ["SG"], [],
]

INCIDENT_TITLE_TEMPLATES = {
    "PortScan": [
        "External port scan detected from {ip}",
        "Network reconnaissance sweep on subnet {subnet}",
        "Automated port enumeration from {ip}",
    ],
    "DoS Hulk": [
        "HTTP flood attack targeting {endpoint}",
        "High-volume HTTP DoS from {ip}",
        "Application-layer denial-of-service on {endpoint}",
    ],
    "DDoS": [
        "Distributed denial-of-service attack in progress",
        "Multi-source volumetric DDoS targeting port {port}",
        "DDoS spike — {count}k req/s from {count2} source IPs",
    ],
    "Web Attack - Brute Force": [
        "Credential brute-force on {endpoint}",
        "SSH brute-force attack from {ip}",
        "Automated login attempts — {count}+ failed auth events",
    ],
    "Bot": [
        "Botnet C2 callback detected from {ip}",
        "Suspicious bot traffic on {endpoint}",
        "Malware beacon from internal host to {ip}",
    ],
    "DoS GoldenEye": [
        "GoldenEye DoS targeting {endpoint}",
        "HTTP keep-alive flood from {ip}",
    ],
    "FTP-Patator": [
        "FTP credential stuffing from {ip}",
        "Automated FTP login scanner detected",
    ],
    "SSH-Patator": [
        "SSH dictionary attack from {ip}",
        "Patator tool — {count}+ SSH auth attempts",
    ],
    "Web Attack - XSS": [
        "Cross-site scripting payload in request body",
        "Reflected XSS attempt on {endpoint}",
        "Stored XSS injection vector — {endpoint}",
    ],
    "DoS slowloris": [
        "Slowloris connection exhaustion on port {port}",
        "Low-and-slow HTTP DoS targeting {endpoint}",
    ],
    "Web Attack - Sql Injection": [
        "SQL injection attempt on {endpoint} parameter",
        "Blind SQLi payload in POST body",
        "SQL injection pattern detected — {endpoint}",
    ],
    "DoS Slowhttptest": [
        "Slow HTTP test attack on {endpoint}",
        "Partial-request DoS flooding web server",
    ],
    "Infiltration": [
        "Lateral movement detected from {ip}",
        "Potential data exfiltration to {ip}",
        "Internal host beaconing to external {ip}",
    ],
    "Heartbleed": [
        "Heartbleed exploitation attempt against TLS service",
        "CVE-2014-0160 probe from {ip}",
    ],
}

ENDPOINTS = [
    "/api/v1/auth/login", "/admin", "/wp-login.php", "/api/users",
    "/dashboard", "/api/v1/incidents", "/login", "/api/health",
]

AUDIT_ACTIONS = [
    # (action, resource_type, http_status, weight)
    ("auth:login",            "users",         200, 12),
    ("auth:logout",           "users",         200,  8),
    ("incidents:create",      "incidents",     201, 15),
    ("incidents:update",      "incidents",     200, 10),
    ("incidents:read",        "incidents",     200, 20),
    ("evidence:upload",       "evidence",      201,  5),
    ("evidence:read",         "evidence",      200,  8),
    ("audit:read",            "audit",         200,  4),
    ("users:read",            "users",         200,  6),
    ("compliance:read",       "compliance",    200,  4),
    ("notifications:read",    "notifications", 200,  3),
    ("notifications:approve", "notifications", 200,  2),
    ("auth:login_failed",     "users",         401,  3),
    ("incidents:delete",      "incidents",     403,  2),
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "LBRO-CLI/2.0 (api-key-auth)",
]

EVIDENCE_TYPES = [
    ("application/pcap", "network_capture_{}.pcap", (50_000,   5_000_000)),
    ("application/json", "system_logs_{}.json",     (10_000,     500_000)),
    ("text/plain",       "forensic_report_{}.txt",  (5_000,      100_000)),
    ("application/zip",  "memory_dump_{}.zip",      (1_000_000, 50_000_000)),
    ("image/png",        "screenshot_{}.png",       (100_000,   2_000_000)),
    ("application/pdf",  "ioc_report_{}.pdf",       (50_000,    800_000)),
]

CUSTODY_ACTIONS = ["UPLOADED", "VERIFIED", "ACCESSED", "EXPORTED", "REVIEWED"]

NOTIFICATION_AUTHORITIES = {
    "GDPR": [
        ("Bundesbeauftragter fuer den Datenschutz (BfDI)", "poststelle@bfdi.bund.de",     "EU"),
        ("Commission nationale de l'informatique (CNIL)",  "contact@cnil.fr",             "EU"),
        ("Information Commissioner's Office (ICO)",        "casework@ico.org.uk",         "UK"),
        ("Data Protection Commission (DPC)",               "info@dataprotection.ie",      "EU"),
    ],
    "HIPAA": [
        ("HHS Office for Civil Rights", "OCRPrivacy@hhs.gov", "US"),
    ],
    "DPDPA": [
        ("Data Protection Board of India", "dpboard@meity.gov.in", "IN"),
    ],
}

COMPLIANCE_OBLIGATIONS = {
    "GDPR": [
        ("Article 33 — 72-hour breach notification to supervisory authority",     72),
        ("Article 34 — Communication of breach to affected data subjects",        168),
        ("Article 32 — Implement appropriate technical & organisational measures", 720),
        ("Article 35 — Data Protection Impact Assessment (DPIA)",                 336),
    ],
    "HIPAA": [
        ("Section 164.408 — Breach notification to HHS Secretary within 60 days", 1440),
        ("Section 164.404 — Individual breach notification within 60 days",       1440),
        ("Section 164.406 — Media notice for large breaches",                     1440),
    ],
    "DPDPA": [
        ("Section 8(6) — Report breach to Data Protection Board",                 168),
        ("Section 8(7) — Notify affected Data Principals without delay",          336),
    ],
}

COMPLIANCE_NOTES = [
    "Submitted via authority portal; reference number logged.",
    "Notification sent via encrypted email; acknowledgement received.",
    "Completed by DPO; documentation archived in compliance system.",
    "Approved by legal counsel before submission.",
    "Evidence packet attached to submission with full incident timeline.",
    "Regulatory filing complete; tracking ID issued by authority.",
]

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ago(days: float = 0, hours: float = 0) -> datetime:
    return _now() - timedelta(days=days, hours=hours)


def _random_ip(prefix: str) -> str:
    return f"{prefix}{random.randint(1, 254)}"


def _source_ip() -> str:
    prefixes, weights = zip(*[(p, w) for p, w in SOURCE_IP_PREFIXES])
    return _random_ip(random.choices(prefixes, weights=weights)[0])  # type: ignore[arg-type]


def _dest_port() -> tuple[int, str]:
    entries = [(p, s) for p, s, _ in DEST_PORTS]
    weights = [w for _, _, w in DEST_PORTS]
    return random.choices(entries, weights=weights)[0]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _make_demo_file_data(content_type: str, filename: str) -> bytes:
    """Generate small but realistic synthetic bytes for each evidence type.

    Capped at ~2 KB so seeding stays fast while giving the download endpoint
    real data to serve.
    """
    uid = secrets.token_hex(4)
    ts  = datetime.now(timezone.utc).isoformat()

    if content_type == "application/json":
        import json as _json
        payload = {
            "source": "lbro-siem", "timestamp": ts, "event_id": uid,
            "severity": random.choice(["INFO", "WARNING", "CRITICAL"]),
            "host": f"server-{random.randint(1, 99):02d}.internal",
            "events": [
                {"time": ts, "action": random.choice(["LOGIN", "EXEC", "CONNECT"]),
                 "user": f"uid{random.randint(1000,9999)}", "pid": random.randint(1000, 65535)}
                for _ in range(random.randint(3, 8))
            ],
        }
        return _json.dumps(payload, indent=2).encode()

    if content_type == "text/plain":
        lines = [
            f"LBRO Forensic Report — {ts}",
            f"Evidence ID : {uid}",
            f"Analyst     : auto-generated",
            "",
            "--- BEGIN LOG ---",
        ]
        for i in range(random.randint(10, 20)):
            lines.append(
                f"{ts} [{random.choice(['INFO','WARN','ERROR'])}] "
                f"src={random.randint(1,254)}.{random.randint(0,254)}.{random.randint(0,254)}.{random.randint(1,254)} "
                f"event={random.choice(['port_scan','login_fail','exec','dns_query'])} "
                f"pid={random.randint(1000,65535)}"
            )
        lines.append("--- END LOG ---")
        return "\n".join(lines).encode()

    if content_type == "text/csv":
        rows = ["timestamp,src_ip,dst_ip,proto,bytes,action"]
        for _ in range(random.randint(5, 15)):
            rows.append(
                f"{ts},{random.randint(1,254)}.{random.randint(0,254)}.0.{random.randint(1,254)},"
                f"10.0.0.{random.randint(1,50)},"
                f"{random.choice(['TCP','UDP','ICMP'])},"
                f"{random.randint(64,9000)},"
                f"{random.choice(['ALLOW','DENY','ALERT'])}"
            )
        return "\n".join(rows).encode()

    if content_type in ("application/xml", "text/xml"):
        return (
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<forensic-report id="{uid}" ts="{ts}">\n'
            f'  <source>lbro-siem</source>\n'
            f'  <severity>{random.choice(["LOW","MEDIUM","HIGH","CRITICAL"])}</severity>\n'
            f'  <events count="{random.randint(1,10)}" />\n'
            f'</forensic-report>\n'
        ).encode()

    if content_type == "application/vnd.tcpdump.pcap" or "pcap" in filename:
        # Minimal valid libpcap global header (24 bytes) + one dummy packet (16 + 4 byte payload)
        import struct
        magic   = 0xA1B2C3D4          # big-endian magic
        hdr     = struct.pack(">IHHiIII", magic, 2, 4, 0, 0, 65535, 1)  # LINKTYPE_ETHERNET
        ts_sec  = int(datetime.now(timezone.utc).timestamp())
        pkt_hdr = struct.pack(">IIII", ts_sec, 0, 4, 4)
        payload = secrets.token_bytes(4)
        return hdr + pkt_hdr + payload

    if content_type == "application/zip":
        # Minimal valid ZIP (end-of-central-directory record only = empty archive)
        return (
            b'PK\x05\x06'   # EOCD signature
            + b'\x00' * 18  # all counts/offsets zero = empty archive
        )

    if content_type == "image/png":
        # Minimal valid 1×1 PNG (67 bytes)
        return bytes([
            0x89,0x50,0x4e,0x47,0x0d,0x0a,0x1a,0x0a,  # PNG signature
            0x00,0x00,0x00,0x0d,0x49,0x48,0x44,0x52,  # IHDR length + type
            0x00,0x00,0x00,0x01,0x00,0x00,0x00,0x01,  # width=1, height=1
            0x08,0x02,0x00,0x00,0x00,0x90,0x77,0x53,  # 8-bit RGB, CRC
            0xde,0x00,0x00,0x00,0x0c,0x49,0x44,0x41,  # IDAT length + type
            0x54,0x08,0xd7,0x63,0xf8,0xcf,0xc0,0x00,  # zlib-compressed 1 red pixel
            0x00,0x00,0x02,0x00,0x01,0xe2,0x21,0xbc,  # CRC
            0x33,0x00,0x00,0x00,0x00,0x49,0x45,0x4e,  # IEND length + type
            0x44,0xae,0x42,0x60,0x82,                  # IEND CRC
        ])

    if content_type == "application/pdf":
        # Minimal valid single-page PDF
        body = (
            b"%PDF-1.4\n"
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
            b"xref\n0 4\n0000000000 65535 f \n"
            b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n9\n%%EOF\n"
        )
        return body

    # Fallback: random binary
    return secrets.token_bytes(512)


def _incident_title(category: str) -> str:
    templates = INCIDENT_TITLE_TEMPLATES.get(category, [f"{category} detected"])
    port, _ = _dest_port()
    return random.choice(templates).format(
        ip=_source_ip(),
        subnet=f"10.0.{random.randint(0, 9)}.0/24",
        endpoint=random.choice(ENDPOINTS),
        port=port,
        count=random.randint(200, 9999),
        count2=random.randint(50, 500),
    )


def _spread(start_days: float, end_days: float) -> datetime:
    """Random UTC timestamp between end_days ago and start_days ago."""
    span = (start_days - end_days) * 86400
    return _now() - timedelta(seconds=end_days * 86400 + random.random() * span)


def _applicable_regulations(
    jurisdictions: list[str],
    personal_data: bool,
    health_data: bool,
) -> list[str]:
    """
    Mirrors ComplianceService.generate_obligations logic so seeded records
    match exactly what the real service would create.
    """
    eu_jurs = {"EU", "DE", "FR", "AT", "BE", "DK", "ES", "FI", "IT", "NL", "PL", "SE"}
    regs: list[str] = []
    if personal_data or any(j in eu_jurs for j in jurisdictions) or "UK" in jurisdictions:
        regs.append("GDPR")
    if health_data or "US" in jurisdictions:
        regs.append("HIPAA")
    if personal_data or "IN" in jurisdictions:
        regs.append("DPDPA")
    return regs or ["GDPR"]


# ─────────────────────────────────────────────────────────────────────────────
# Wipe helper (shared with clear_demo_data.py)
# ─────────────────────────────────────────────────────────────────────────────

async def _wipe_demo_data(db: AsyncSession) -> int:
    """
    Delete all rows associated with demo users (email ends with @lbro.demo).
    Deletes in correct FK dependency order. Returns the number of users removed.
    """
    rows = (await db.execute(
        select(User.id, User.email).where(User.email.like("%@lbro.demo"))
    )).all()

    if not rows:
        print("   No demo users found — nothing to wipe.")
        return 0

    user_ids = [r[0] for r in rows]
    print(f"   Found {len(user_ids)} demo users")

    inc_ids = [
        r[0] for r in (await db.execute(
            select(Incident.id).where(Incident.created_by.in_(user_ids))
        )).all()
    ]
    print(f"   Found {len(inc_ids)} demo incidents")

    if inc_ids:
        await db.execute(sa_delete(IncidentAction).where(IncidentAction.incident_id.in_(inc_ids)))
        ev_subq = select(Evidence.id).where(Evidence.incident_id.in_(inc_ids)).scalar_subquery()
        await db.execute(sa_delete(ChainOfCustody).where(ChainOfCustody.evidence_id.in_(ev_subq)))
        await db.execute(sa_delete(Evidence).where(Evidence.incident_id.in_(inc_ids)))
        notif_subq = select(Notification.id).where(Notification.incident_id.in_(inc_ids)).scalar_subquery()
        await db.execute(sa_delete(NotificationRecipient).where(
            NotificationRecipient.notification_id.in_(notif_subq)
        ))
        await db.execute(sa_delete(Notification).where(Notification.incident_id.in_(inc_ids)))
        await db.execute(sa_delete(ComplianceRecord).where(ComplianceRecord.incident_id.in_(inc_ids)))
        await db.execute(sa_delete(Incident).where(Incident.id.in_(inc_ids)))

    await db.execute(sa_delete(AuditLog).where(AuditLog.user_id.in_(user_ids)))
    await db.execute(sa_delete(User).where(User.id.in_(user_ids)))
    await db.commit()
    print(f"   Removed {len(user_ids)} demo users and all cascaded data")
    return len(user_ids)


# ─────────────────────────────────────────────────────────────────────────────
# Main seeder
# ─────────────────────────────────────────────────────────────────────────────

async def seed(wipe: bool = False) -> None:
    async with AsyncSessionLocal() as db:
        print("━" * 64)
        print("  LBRO Demo Data Seeder")
        print("━" * 64)

        # ── Optional wipe ─────────────────────────────────────────────
        if wipe:
            print("\nWiping existing demo data...")
            await _wipe_demo_data(db)
            print()

        # ── 1. Users ──────────────────────────────────────────────────
        print("[1/7] Creating 10 demo users...")
        users: list[User] = []
        skipped = 0
        for full_name, email, role, password in DEMO_USERS:
            existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if existing:
                users.append(existing)
                skipped += 1
                continue
            u = User(
                email=email,
                username=email.split("@")[0].replace(".", "_"),
                full_name=full_name,
                hashed_password=hash_password(password),
                role=role,
                is_active=True,
                is_verified=True,
                api_key=f"lbro-demo-{secrets.token_urlsafe(24)}",
                last_login=_ago(days=random.uniform(0.1, 5)),
            )
            db.add(u)
            users.append(u)
        await db.commit()
        for u in users:
            await db.refresh(u)
        if skipped:
            print(f"   {skipped} already existed, skipped")
        print(f"   {len(users)} users ready")

        analysts   = [u for u in users if u.role in ("admin", "analyst")]
        admin_user = next(u for u in users if u.role == "admin")

        # ── Idempotency check ─────────────────────────────────────────
        already_seeded = (await db.execute(
            select(Incident).where(Incident.created_by == admin_user.id).limit(1)
        )).scalar_one_or_none() is not None

        if already_seeded:
            print("\n   Incidents already seeded — loading existing for summary.")
            print("   Use --wipe to reset and re-seed from scratch.\n")
            incidents = list((await db.execute(select(Incident).limit(500))).scalars().all())
        else:
            incidents = []

        # ── 2. Incidents ──────────────────────────────────────────────
        print("[2/7] Creating 100 incidents...")
        if not already_seeded:
            for i in range(100):
                # Weighted distribution: 60% last 30 days, 24% last 31-60, 16% last 61-90
                if random.random() < 0.60:
                    detected = _spread(30, 0)
                elif random.random() < 0.80:
                    detected = _spread(60, 30)
                else:
                    detected = _spread(90, 60)

                attack_cat    = random.choices(ATTACK_CATEGORIES, weights=ATTACK_W)[0]
                severity      = random.choices(SEVERITIES, weights=SEVERITY_W)[0]
                status        = random.choices(STATUSES, weights=STATUS_W)[0]
                confidence    = round(random.uniform(0.61, 0.99), 4)
                port, svc     = _dest_port()
                jurisdictions = random.choice(JURISDICTION_POOL)
                personal_data = bool(jurisdictions) and random.random() < 0.35
                health_data   = ("US" in jurisdictions) and random.random() < 0.25

                inc = Incident(
                    id=uuid.uuid4(),
                    external_id=f"INC-{_now().year}-DEMO-{str(i + 1).zfill(4)}",
                    title=_incident_title(attack_cat),
                    description=(
                        f"ML detection flagged {attack_cat} traffic pattern "
                        f"(confidence {confidence:.1%}). "
                        f"Protocol: {random.choice(PROTOCOLS)} on port {port} ({svc}). "
                        f"Initial triage {'completed' if status not in ('new', 'triaging') else 'in progress'}."
                    ),
                    status=status,
                    severity=severity,
                    attack_category=attack_cat,
                    confidence_score=confidence,
                    ml_model_version="1.0.0",
                    needs_analyst_review=(confidence < 0.75),
                    source_ip=_source_ip(),
                    destination_ip=f"10.0.{random.randint(0, 5)}.{random.randint(10, 250)}",
                    source_port=random.randint(1024, 65535),
                    destination_port=port,
                    protocol=random.choice(PROTOCOLS),
                    network_features={
                        "destination_port":     port,
                        "flow_duration":        random.randint(10_000, 10_000_000),
                        "total_fwd_packets":    random.randint(1, 5000),
                        "total_bwd_packets":    random.randint(0, 2000),
                        "flow_bytes_per_sec":   round(random.uniform(100.0, 500_000.0), 2),
                        "flow_packets_per_sec": round(random.uniform(1.0, 5000.0), 2),
                        "syn_flag_count":       random.randint(0, 200),
                        "fwd_iat_mean":         round(random.uniform(0.0, 100_000.0), 2),
                        "bwd_iat_mean":         round(random.uniform(0.0, 100_000.0), 2),
                    },
                    affected_jurisdictions=jurisdictions or None,
                    personal_data_involved=personal_data,
                    health_data_involved=health_data,
                    assigned_to=(random.choice(analysts).id if random.random() > 0.25 else None),
                    created_by=admin_user.id,
                    detected_at=detected,
                    created_at=detected,
                    updated_at=detected + timedelta(minutes=random.randint(1, 120)),
                    closed_at=(
                        detected + timedelta(hours=random.randint(2, 96))
                        if status == "closed" else None
                    ),
                )
                db.add(inc)
                incidents.append(inc)

                # Incident actions (1–3 per incident)
                action_specs = [
                    ("triage",      "Initial triage complete — attack vector confirmed via packet capture."),
                    ("containment", "Source IP blocked at perimeter firewall; affected systems isolated."),
                    ("analysis",    "Forensic analysis complete — no lateral movement; IOCs extracted."),
                    ("escalation",  "Escalated to senior analyst; legal team notified per compliance policy."),
                    ("remediation", "Patch applied; system returned to service. 48h monitoring initiated."),
                ]
                for j, (atype, desc) in enumerate(random.sample(action_specs, k=random.randint(1, 3))):
                    db.add(IncidentAction(
                        incident_id=inc.id,
                        action_type=atype,
                        description=desc,
                        performed_by=random.choice(analysts).id,
                        automated=(atype == "triage" and random.random() > 0.6),
                        result="completed",
                        created_at=detected + timedelta(minutes=random.randint(5, 90) * (j + 1)),
                    ))

            await db.commit()
        print(f"   {len(incidents)} incidents ready")

        # ── 3. Evidence ───────────────────────────────────────────────
        print("[3/7] Creating 150 evidence records...")
        ev_count = 0
        if not already_seeded:
            for _ in range(150):
                inc     = random.choice(incidents)
                ct, tmpl, sr = random.choice(EVIDENCE_TYPES)
                uid     = secrets.token_hex(4)
                fname   = tmpl.format(uid)
                analyst = random.choice(analysts)
                ev_ts   = inc.detected_at + timedelta(minutes=random.randint(10, 480))

                # Generate realistic synthetic file bytes so the download endpoint
                # has real data to serve (capped at ~2 KB each for seeding speed).
                file_bytes = _make_demo_file_data(ct, fname)
                sha        = _sha256(file_bytes)
                fsize      = len(file_bytes)

                ev = Evidence(
                    incident_id=inc.id,
                    filename=fname,
                    original_filename=fname,
                    content_type=ct,
                    file_size=fsize,
                    s3_key=f"evidence/{inc.id}/{fname}",
                    s3_bucket="lbro-prod-evidence",
                    sha256_hash=sha,
                    file_data=file_bytes,
                    description=f"Forensic artifact from {inc.attack_category or 'incident'} investigation.",
                    tags='["demo","automated","ml-flagged"]',
                    is_immutable=True,
                    uploaded_by=analyst.id,
                    created_at=ev_ts,
                )
                db.add(ev)

                # Chain of custody (1–3 steps)
                coc_ts = ev_ts
                for action in random.sample(CUSTODY_ACTIONS, k=random.randint(1, 3)):
                    coc_ts += timedelta(minutes=random.randint(5, 180))
                    db.add(ChainOfCustody(
                        evidence=ev,
                        action=action,
                        performed_by=random.choice(analysts).id,
                        performed_by_name=random.choice(analysts).full_name,
                        notes=(
                            "Hash verified against upload SHA-256."
                            if action == "VERIFIED"
                            else f"{action.lower().capitalize()} by "
                                 f"{random.choice(['automated system', 'analyst', 'DPO'])}."
                        ),
                        hash_at_time=sha,
                        ip_address=f"10.0.0.{random.randint(1, 50)}",
                        created_at=coc_ts,
                    ))
                ev_count += 1
            await db.commit()
        print(f"   {ev_count or 'pre-existing'} evidence records with chain-of-custody")

        # ── 4. Regulatory Notifications ───────────────────────────────
        print("[4/7] Creating ~50 regulatory notifications...")
        notif_count = 0
        if not already_seeded:
            regulated_pool = [
                i for i in incidents
                if (i.affected_jurisdictions and len(i.affected_jurisdictions) > 0)
                or i.personal_data_involved
                or i.health_data_involved
            ]
            random.shuffle(regulated_pool)

            for inc in regulated_pool[:50]:
                jurisdictions = inc.affected_jurisdictions or []
                regs = _applicable_regulations(jurisdictions, inc.personal_data_involved, inc.health_data_involved)
                reg  = random.choice(regs)

                authorities = NOTIFICATION_AUTHORITIES.get(reg, NOTIFICATION_AUTHORITIES["GDPR"])
                auth_name, auth_email, jur = random.choice(authorities)
                deadline_h = {"GDPR": 72, "HIPAA": 1440, "DPDPA": 72}.get(reg, 72)
                status     = random.choices(
                    ["pending", "approved", "sent", "sent"],
                    weights=[20, 20, 35, 25],
                )[0]
                created  = inc.detected_at + timedelta(hours=random.randint(1, 12))
                deadline = created + timedelta(hours=deadline_h)

                notif = Notification(
                    incident_id=inc.id,
                    regulation=reg,
                    jurisdiction=jur,
                    authority=auth_name,
                    authority_email=auth_email,
                    status=status,
                    subject=(
                        f"{reg} Art. 33 Personal Data Breach Notification: {inc.title[:80]}"
                        if reg == "GDPR"
                        else f"{reg} Breach Notification: {inc.title[:80]}"
                    ),
                    body=(
                        f"We are writing to notify you of a personal data breach affecting individuals "
                        f"in your jurisdiction. Detected: {inc.detected_at.strftime('%Y-%m-%d %H:%M UTC')}. "
                        f"Classification: {inc.severity.upper()} severity — {inc.attack_category}. "
                        f"Immediate containment measures applied. A full incident report will follow "
                        f"within the required regulatory timeline."
                    ),
                    deadline=deadline,
                    sent_at=(
                        created + timedelta(hours=random.randint(1, 48))
                        if status == "sent" else None
                    ),
                    approved_by=(admin_user.id if status in ("approved", "sent") else None),
                    approved_at=(created + timedelta(hours=1) if status in ("approved", "sent") else None),
                    retry_count=0,
                    created_at=created,
                    updated_at=created,
                )
                db.add(notif)
                db.add(NotificationRecipient(
                    notification=notif,
                    email=auth_email,
                    name=auth_name,
                    recipient_type="primary",
                ))
                notif_count += 1
            await db.commit()
        print(f"   {notif_count or 'pre-existing'} regulatory notifications")

        # ── 5. Compliance Records ─────────────────────────────────────
        print("[5/7] Creating compliance records...")
        compliance_count = 0
        if not already_seeded:
            # Filter incidents that trigger compliance (matches ComplianceService logic)
            regulated = [
                i for i in incidents
                if i.personal_data_involved
                or i.health_data_involved
                or (i.affected_jurisdictions and len(i.affected_jurisdictions) > 0)
            ]
            random.shuffle(regulated)

            for inc in regulated[:40]:
                jurisdictions = inc.affected_jurisdictions or []
                regs = _applicable_regulations(
                    jurisdictions, inc.personal_data_involved, inc.health_data_involved
                )
                for reg in regs:
                    obligations = COMPLIANCE_OBLIGATIONS.get(reg, [])
                    chosen = random.sample(obligations, k=min(random.randint(1, 2), len(obligations)))
                    for obligation_text, deadline_hours in chosen:
                        deadline = inc.detected_at + timedelta(hours=deadline_hours)
                        is_met   = random.random() < 0.65
                        met_at   = None
                        notes    = None
                        if is_met:
                            met_at = inc.detected_at + timedelta(
                                hours=random.randint(
                                    max(1, int(deadline_hours * 0.1)),
                                    int(deadline_hours * 0.85),
                                )
                            )
                            notes = random.choice(COMPLIANCE_NOTES)

                        db.add(ComplianceRecord(
                            incident_id=inc.id,
                            regulation=reg,
                            jurisdiction=reg,   # free-text — use regulation label
                            obligation=obligation_text,
                            deadline=deadline,
                            is_met=is_met,
                            met_at=met_at,
                            notes=notes,
                            created_at=inc.detected_at,
                            updated_at=met_at or inc.detected_at,
                        ))
                        compliance_count += 1
            await db.commit()
        print(f"   {compliance_count or 'pre-existing'} compliance records")

        # ── 6. Audit Logs ─────────────────────────────────────────────
        print("[6/7] Creating 500 audit log entries...")
        audit_count = 0
        if not already_seeded:
            entries    = [(a, r, s) for a, r, s, _ in AUDIT_ACTIONS]
            audit_wts  = [w for _, _, _, w in AUDIT_ACTIONS]
            for _ in range(500):
                u = random.choice(users)
                action, rtype, status_code = random.choices(entries, weights=audit_wts)[0]
                inc_id = (
                    str(random.choice(incidents).id)
                    if rtype == "incidents" and incidents
                    else None
                )
                db.add(AuditLog(
                    user_id=u.id,
                    user_email=u.email,
                    action=action,
                    resource_type=rtype,
                    resource_id=inc_id,
                    ip_address=(
                        _source_ip() if random.random() > 0.6
                        else f"10.0.0.{random.randint(1, 50)}"
                    ),
                    user_agent=random.choice(USER_AGENTS),
                    request_method="GET" if ("read" in action or "login" in action) else "POST",
                    request_path=f"/api/v1/{rtype}",
                    response_status=status_code,
                    details={"demo": True, "seeded": True},
                    created_at=_spread(90, 0),
                ))
                audit_count += 1
            await db.commit()
        print(f"   {audit_count or 'pre-existing'} audit log entries")

        # -- 7. Summary ------------------------------------------------
        print("[7/7] Verifying totals...")
        totals = {
            "Users":              (await db.execute(text("SELECT COUNT(*) FROM users"))).scalar(),
            "Incidents":          (await db.execute(text("SELECT COUNT(*) FROM incidents"))).scalar(),
            "Evidence":           (await db.execute(text("SELECT COUNT(*) FROM evidence"))).scalar(),
            "Notifications":      (await db.execute(text("SELECT COUNT(*) FROM notifications"))).scalar(),
            "Compliance records": (await db.execute(text("SELECT COUNT(*) FROM compliance_records"))).scalar(),
            "Audit logs":         (await db.execute(text("SELECT COUNT(*) FROM audit_logs"))).scalar(),
        }
        print()
        print("  Demo data seeded successfully")
        print()
        for label, count in totals.items():
            print(f"  {label:<22} {count:>6}")
        print()
        print("  Demo credentials:")
        print("    Admin    priya.sharma@lbro.demo   Admin@Demo1!")
        print("    Analyst  james.okafor@lbro.demo   Analyst@Demo1!")
        print("    Viewer   dmitri.volkov@lbro.demo  Viewer@Demo1!")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed LBRO with realistic demo data")
    parser.add_argument(
        "--wipe",
        action="store_true",
        help="Remove existing demo data first, then re-seed from scratch",
    )
    args = parser.parse_args()
    asyncio.run(seed(wipe=args.wipe))
