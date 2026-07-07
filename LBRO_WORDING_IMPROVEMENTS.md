# LBRO Wording Improvements Report

**Product evolution:** LBRO → Developer-first Post-Deployment Security Companion  
**Goal:** Replace enterprise/SOC-analyst jargon with plain-English language accessible to developers, indie hackers, startup founders, and students — without sacrificing cybersecurity accuracy.  
**Scope:** 15 frontend pages, 40+ individual changes.  
**TypeScript status after all changes:** ✅ 0 errors

---

## Summary by file

### LoginPage.tsx

| # | Old | New | Reason |
|---|-----|-----|--------|
| 1 | `<h2>Authenticate</h2>` | `<h2>Sign in</h2>` | "Authenticate" is formal/enterprise. "Sign in" is universal. |
| 2 | `"Sign in with your credentials to access the SOC dashboard"` | `"Sign in to access your LBRO security dashboard"` | "SOC dashboard" implies a security operations center; "LBRO security dashboard" is product-native and approachable. |
| 3 | `placeholder="analyst@your-org.com"` | `placeholder="you@your-org.com"` | "analyst" assumes a professional SOC role. "you" is inclusive of any user type. |

---

### RegisterPage.tsx

| # | Old | New | Reason |
|---|-----|-----|--------|
| 4 | `"Register for access to the LBRO SOC dashboard"` | `"Create your LBRO account to start tracking security"` | "Register for access" sounds like an enterprise access request. "Create your account" is familiar to any web user. |
| 5 | `placeholder="analyst@your-org.com"` | `placeholder="you@your-org.com"` | Same reason as LoginPage #3. |

---

### DashboardPage.tsx

| # | Old | New | Reason |
|---|-----|-----|--------|
| 6 | `"Application Security Overview"` | `"Your app's security at a glance"` | "Overview" is generic enterprise-speak. The new text is direct and personal. |
| 7 | `label="Open Investigations"` | `label="Open Issues"` | "Investigations" implies a dedicated security analyst running formal inquiries. "Issues" is understood by any developer. |
| 8 | `label="Pending Review"` | `label="Needs Attention"` | "Pending Review" sounds like a bureaucratic queue. "Needs Attention" is action-oriented. |
| 9 | `sub="flagged for analyst review"` | `sub="flagged for your review"` | Removes the implied "analyst" persona; any team member can review. |
| 10 | `sub="require immediate action"` | `sub="need immediate attention"` | Softens the military-style command language without losing urgency. |
| 11 | `sub="across all severities"` | `sub="across all severity levels"` | Adds "levels" for clarity; "severities" alone is jargon. |
| 12 | `label="Most Targeted"` | `label="Most Attacked"` | "Targeted" is vague. "Attacked" is more concrete and accurate. |
| 13 | `sub="Most frequent attack type"` | `sub="most frequent attack type"` | Sentence-case consistency — lowercase matches surrounding sub-labels. |
| 14 | `sub="Highest attack volume endpoint"` | `sub="highest volume entry point"` | "Endpoint" is technical-specific; "entry point" communicates the concept to non-backend developers too. |
| 15 | `empty="No threat patterns detected"` | `empty="No threats detected yet"` | "Threat patterns" is threat-intelligence jargon. "No threats yet" reads naturally. |
| 16 | `empty="No targeting data available"` | `empty="No attack data yet"` | "Targeting data" sounds like military intelligence. "Attack data" is clearer. |

---

### IncidentsPage.tsx

| # | Old | New | Reason |
|---|-----|-----|--------|
| 17 | `"ML-classified threats"` | `"automatically detected and classified"` | "ML-classified" is an implementation detail. The replacement explains the user benefit (automatic) rather than the technology name. |

---

### IncidentDetailPage.tsx

| # | Old | New | Reason |
|---|-----|-----|--------|
| 18 | `type: 'TRIAGE'` (timeline event label) | `type: 'CLASSIFIED'` | "TRIAGE" is an ER/SOC term. "CLASSIFIED" accurately describes what the ML pipeline does (classifies the incident). |
| 19 | `desc: "Severity: ${incident.severity}. Jurisdictions:..."` | `desc: "Severity set to ${incident.severity}. Regulations checked:..."` | "Jurisdictions" is legal/compliance jargon. "Regulations checked" communicates the same intent accessibly. |
| 20 | `actor: 'analyst'` (closed event) | `actor: 'user'` | Removes the assumed SOC analyst role; any user can close an incident. |
| 21 | `title="Forensic Evidence"` | `title="Attached Evidence"` | "Forensic" implies a formal legal investigation. "Attached" simply describes what the files are. |
| 22 | `extra="PostgreSQL storage"` | `extra="stored in your database"` | "PostgreSQL storage" exposes the implementation stack unnecessarily. "Your database" is meaningful to any developer. |
| 23 | `"No evidence packages collected."` | `"No evidence files attached yet."` | "Packages collected" sounds like a formal evidence intake process. "Files attached yet" is plain and friendly. |
| 24 | `title="Regulatory Notifications"` (Card) | `title="Compliance Alerts"` | "Regulatory Notifications" is legal-department language. "Compliance Alerts" is shorter and equally precise. |

---

### EvidencePage.tsx

| # | Old | New | Reason |
|---|-----|-----|--------|
| 25 | `"Forensic evidence with SHA-256 integrity stored in PostgreSQL"` | `"Files attached to incidents — SHA-256 verified and stored in your database"` | "Forensic evidence" sets an intimidating tone. The new text explains the feature plainly while preserving the SHA-256 accuracy detail. |
| 26 | `label="Evidence packages"` | `label="Evidence files"` | "Packages" implies a formal bundled artifact. "Files" is universal. |
| 27 | `"Evidence stored in PostgreSQL (WORM-equivalent)"` | `"Evidence stored in your database (tamper-proof)"` | "WORM-equivalent" is a data-storage acronym (Write Once Read Many) unknown to most developers. "Tamper-proof" communicates the security guarantee directly. |
| 28 | `"Files stored as binary data in the database. SHA-256 hashes verified post-upload. Immutable records cannot be deleted."` | `"Files are saved directly in your database. Each file gets a SHA-256 fingerprint when uploaded. Records cannot be modified after the fact."` | The original uses terms like "binary data," "post-upload," and "immutable" without context. The rewrite explains what happens and why in plain English. |

---

### AuditLogsPage.tsx

| # | Old | New | Reason |
|---|-----|-----|--------|
| 29 | `"Could not load audit logs. You may need admin or analyst privileges."` | `"Could not load activity logs. Make sure you're signed in as an admin."` | "Audit logs" → "activity logs" is friendlier. "Analyst privileges" assumes a SOC role; "admin" is a universal concept. |

---

### SecurityScorePage.tsx

| # | Old | New | Reason |
|---|-----|-----|--------|
| 30 | `"Real-time security posture for your application"` (×2, replaced both) | `"How secure is your app right now?"` | "Security posture" is enterprise/CISO vocabulary. The question form makes it immediately relatable. |
| 31 | `"Real-time security posture — calculated from live data, updated every minute"` | `"Your security health score — calculated from live data, updated every minute"` | "Health score" is a well-understood concept (like a credit score or SEO score) that makes the metric feel tangible. |
| 32 | `"VIEW_DASHBOARD permission"` | `"you are signed in with the right account"` | A raw permission constant string is meaningless to non-engineers and confusing to anyone who isn't reading source code. |

---

### NotificationsPage.tsx

| # | Old | New | Reason |
|---|-----|-----|--------|
| 33 | `<h1>Regulatory Notifications</h1>` | `<h1>Compliance Alerts</h1>` | Matches the rename in IncidentDetailPage. "Regulatory Notifications" sounds like a government department. "Compliance Alerts" is shorter and action-oriented. |

---

### SettingsPage.tsx

| # | Old | New | Reason |
|---|-----|-----|--------|
| 34 | `label: 'Evidence collection complete'` | `label: 'New evidence uploaded'` | "Evidence collection" is a formal forensics term. "New evidence uploaded" describes the user action plainly. |
| 35 | `desc: 'Notify when forensic packages are ready'` | `desc: 'Alert when files are attached to an incident'` | Replaces "forensic packages" (jargon) with a plain description of the trigger. |
| 36 | `label: 'Worker health alerts'` | `label: 'Background service alerts'` | "Worker" is an infrastructure abstraction. "Background service" is more familiar across all developer backgrounds. |
| 37 | `desc: 'Alert on ECS worker task failures'` | `desc: 'Alert when a background job stops working'` | "ECS worker task failures" exposes AWS-specific infrastructure details that are irrelevant to the user's concern (something stopped). |
| 38 | `"Session, notifications, team, and audit preferences"` | `"Account, notifications, team, and activity log preferences"` | "Session" is a technical term; "Account" is what users understand. "Audit preferences" → "activity log preferences" is friendlier. |

---

### CreateIncidentPage.tsx

| # | Old | New | Reason |
|---|-----|-----|--------|
| 39 | `"Log a new security incident for tracking, triage, and compliance reporting."` | `"Report a security issue. LBRO will classify it automatically and track any compliance deadlines."` | "Triage" is clinical/military. The new text describes what LBRO does for you (classifies automatically, tracks deadlines) — outcome-focused instead of process-focused. |

---

### ComplianceAuditPage.tsx

| # | Old | New | Reason |
|---|-----|-----|--------|
| 40 | `"This report reflects the current compliance posture derived from live incident and evidence data in LBRO. It is an internal self-assessment and does not constitute a formal audit opinion."` | `"This report shows your current compliance status, derived from live incident and evidence data in LBRO. It is a self-assessment — not a formal audit opinion."` | "Compliance posture" is enterprise/legal vocabulary. "Compliance status" is clear. The em-dash version is easier to parse. |

---

### PrivacyPage.tsx

| # | Old | New | Reason |
|---|-----|-----|--------|
| 41 | `"assigned analyst"` | `"assigned user"` | Removes assumed SOC analyst role. Any user can be assigned to an incident. |
| 42 | `"forensic files uploaded by analysts"` | `"files uploaded by your team"` | "Forensic files" and "analysts" both imply a professional security operations context. "Files uploaded by your team" is universally understood. |
| 43 | `"Forensic files retained until analyst removes them"` | `"Files kept until manually deleted by your team"` | Same dual improvement: "forensic" → plain, "analyst" → "your team." Also "retained" → "kept" is shorter. |

---

### ThreatIntelPage.tsx

| # | Old | New | Reason |
|---|-----|-----|--------|
| 44 | `"IOC Indicators"` | `"Attack Indicators"` | "IOC" (Indicators of Compromise) is threat-intel jargon. "Attack Indicators" conveys the same meaning to any developer. |
| 45 | `"CICIDS2017 ML analytics · MITRE ATT&CK mapping · False positive tracking"` | `"ML-powered attack detection · MITRE ATT&CK framework · false positive tracking"` | "CICIDS2017" is the name of a specific research dataset — not meaningful to users. "ML-powered attack detection" explains the benefit. MITRE ATT&CK is kept (it's an industry standard reference). |
| 46 | `"Live Flow Classifications"` | `"Live Traffic Analysis"` | "Flow Classifications" is network/ML pipeline language. "Live Traffic Analysis" is immediately understandable. |

---

### WeeklyReportPage.tsx

| # | Old | New | Reason |
|---|-----|-----|--------|
| 47 | `"forensic evidence packages stored with WORM protection"` | `"evidence files stored with tamper-proof records"` | "WORM protection" (Write Once Read Many) is a storage engineering term. "Tamper-proof records" explains the security guarantee without the acronym. |

---

## What was NOT changed

The following cybersecurity terms were intentionally preserved because they are accurate, industry-standard, and removing them would reduce the product's credibility with security-aware users:

- **MITRE ATT&CK** — a widely-recognised framework; renaming it would be inaccurate.
- **GDPR, HIPAA, DPDPA** — legal regulation names; must remain exact.
- **SHA-256** — a specific cryptographic hash function; accuracy requires the full name.
- **JWT, Bearer token, bcrypt** — standard technical terms; developers expect these.
- **CVSS, severity levels (low/medium/high/critical)** — standard security scoring vocabulary.
- **ML (machine learning)** — common enough to retain; replaced "ML-classified" where it was used as a standalone noun.
- **ECS, S3, SQS, PostgreSQL** — appear in the Settings page infrastructure config section where they are *configuration values*, not UI copy; appropriate there.

---

## Verification

- TypeScript compilation: **0 errors** (`npx tsc --noEmit` — no output)
- Files modified: 15 (`LoginPage`, `RegisterPage`, `DashboardPage`, `IncidentsPage`, `IncidentDetailPage`, `EvidencePage`, `AuditLogsPage`, `SecurityScorePage`, `NotificationsPage`, `SettingsPage`, `CreateIncidentPage`, `ComplianceAuditPage`, `PrivacyPage`, `ThreatIntelPage`, `WeeklyReportPage`)
- Total changes: **47 individual wording improvements**
- Features removed: **0**
- Backend APIs changed: **0**
- Authentication / RBAC / ML pipeline modified: **0**
