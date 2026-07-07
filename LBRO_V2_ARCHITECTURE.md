# LBRO v2 — Real-Time Log Ingestion Architecture Plan

**Document type:** Technical implementation plan  
**Target version:** 2.0 (next release)  
**Audience:** Engineers implementing the v2 log ingestion pipeline  
**Status:** Design-only — nothing is implemented  
**Constraint:** Must not break existing v1 architecture  

---

## 1. Executive Summary

LBRO v1 is a reactive incident management platform: humans or applications manually create incidents via the web UI or API. The ML classifier runs on already-created incidents.

**v2 makes LBRO proactive.** A lightweight log agent running alongside any application captures security-relevant events, ships them to a new LBRO ingestion API, and the backend automatically classifies, filters, and converts threats into incidents — all without human involvement in the detection loop. Humans remain in the loop for containment decisions, compliance approval, and dispatch.

The target pipeline is:

```
Application
    ↓
Log Agent            (new — lightweight process on the app host)
    ↓
LBRO API             (new ingest endpoint on existing FastAPI server)
    ↓
Queue                (new SQS_LOG_QUEUE_URL — separate from existing incident queue)
    ↓
ML Classification    (existing AttackClassifier — no changes)
    ↓
Incident Creation    (existing IncidentService.create() — no changes)
    ↓
Evidence Storage     (existing EvidenceService — minor extension)
    ↓
Compliance Engine    (existing ComplianceService — no changes)
    ↓
Dashboard            (existing frontend — new ingestion status widget)
```

Every node below the queue is fully implemented in v1 and **requires no changes** to support v2 ingestion. The entire new build is confined to: the log agent binary, the ingest API endpoint, the new SQS queue, and the new log worker.

---

## 2. Current Architecture (v1 baseline)

```
┌────────────────────────────────────────────────────────────┐
│  Frontend (React/Vite :3000)                               │
│  ← POST /api/v1/incidents (human-created)                  │
└──────────────────┬─────────────────────────────────────────┘
                   │
┌──────────────────▼─────────────────────────────────────────┐
│  FastAPI :8000                                             │
│                                                            │
│  POST /incidents → IncidentService.create()                │
│      → classifier.predict()          [ML, sync]            │
│      → ComplianceService             [obligations]         │
│      → NotificationService           [drafts]              │
│      → sqs_service.enqueue_incident  [async reclassify]    │
└──────────┬─────────────────────────────────────────────────┘
           │
    ┌──────▼──────┐         ┌─────────────────────┐
    │  PostgreSQL  │         │  SQS (LocalStack)    │
    │  :5432       │         │  • incident_queue    │
    └─────────────┘         │  • notification_queue│
                            └──────────┬───────────┘
                                       │
                            ┌──────────▼───────────┐
                            │  Background Worker    │
                            │  • incident_worker    │
                            │  • notification_worker│
                            └──────────────────────┘
```

---

## 3. v2 Target Architecture

```
  [ Your Application ]
         │
         │  CICFlowMeter / eBPF / log tail
         ▼
  ┌─────────────┐
  │  LBRO Agent │  (new — Go or Python binary, runs on app host)
  │  v0.1.0     │  polls log files / syslog / HTTP hooks
  └──────┬──────┘
         │  POST /api/v1/ingest/events  (X-API-Key: lbro-agent-xxx)
         │  Batch of LogEvent objects, max 1000/batch
         ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  FastAPI :8000                                              │
  │                                                             │
  │  POST /api/v1/ingest/events   ← NEW                        │
  │      → validate batch (schema + rate limit)                 │
  │      → write ingestion_batches record                       │
  │      → sqs_service.enqueue_log_batch(batch)   ← NEW call   │
  │      → return IngestResponse (accepted/rejected count)      │
  │                                                             │
  │  GET  /api/v1/ingest/status   ← NEW                        │
  │  POST /api/v1/agent/register  ← NEW                        │
  │  GET  /api/v1/agent/config    ← NEW                        │
  │                                                             │
  │  [All existing endpoints unchanged]                         │
  └──────────────────────────────┬──────────────────────────────┘
                                 │
          ┌──────────────────────▼───────────────────────┐
          │  PostgreSQL :5432                            │
          │  + log_agents table       (NEW)              │
          │  + ingestion_batches table (NEW)             │
          │  + ingestion_metrics table (NEW)             │
          │  + incidents.source_type   (NEW column)      │
          │  + incidents.agent_id      (NEW column)      │
          │  [All existing tables unchanged]             │
          └──────────────────────────────────────────────┘
                                 │
          ┌──────────────────────▼───────────────────────┐
          │  SQS                                         │
          │  • lbro-incident-queue  (existing)           │
          │  • lbro-notification-queue  (existing)       │
          │  • lbro-log-queue       (NEW)                │
          └──────────────────────┬───────────────────────┘
                                 │
          ┌──────────────────────▼───────────────────────┐
          │  Background Worker                           │
          │  • incident_worker.py    (existing)          │
          │  • notification_worker.py (existing)         │
          │  • log_worker.py         (NEW)               │
          └──────────────────────┬───────────────────────┘
                                 │
          ┌──────────────────────▼───────────────────────┐
          │  Existing pipeline (unchanged)               │
          │  classifier.predict()                        │
          │  IncidentService.create()                    │
          │  ComplianceService.generate_obligations()    │
          │  NotificationService.generate_for_incident() │
          │  EvidenceService (optional raw log storage)  │
          └──────────────────────────────────────────────┘
```

---

## 4. Existing Reusable Components

Everything below can be used as-is in v2. No modifications required.

| Component | File | How v2 Uses It |
|---|---|---|
| `AttackClassifier.predict(features)` | `backend/app/ml/classifier.py` | Log worker calls this with features extracted from each log event |
| `IncidentService.create(data, user)` | `backend/app/services/incident_service.py` | Log worker calls this for every event whose confidence > threshold |
| `ComplianceService.generate_obligations()` | `backend/app/services/compliance_service.py` | Fires automatically from `IncidentService.create()` when data flags are set |
| `NotificationService.generate_for_incident()` | `backend/app/services/notification_service.py` | Same — fires automatically |
| `EvidenceService` | `backend/app/services/evidence_service.py` | Log worker can store the raw log line as evidence for the created incident |
| `AuditService` | `backend/app/services/audit_service.py` | Log worker logs all incident-creation events |
| `SQSService.receive_messages()` / `.delete_message()` | `backend/app/services/sqs_service.py` | Log worker uses same polling pattern as existing workers |
| `AsyncSessionLocal` | `backend/app/database.py` | Log worker uses same database session factory |
| `require_permission()` dependency | `backend/app/dependencies.py` | Ingest endpoint uses existing API-key auth path |
| `RateLimitMiddleware` | `backend/app/middleware/rate_limit.py` | Ingest endpoint protected by existing middleware (needs per-agent limit added) |
| `SecurityHeadersMiddleware` | `backend/app/middleware/security_headers.py` | Applies to all endpoints including ingest |
| `api_key` column on `users` table | `backend/app/models/user.py` | Agent authenticates via `X-API-Key` — already supported in `get_current_active_user` |
| `poll_queue()` in workers/main.py | `backend/app/workers/main.py` | Log worker is a third poll loop added to the same `asyncio.gather()` |
| CICIDS2017 feature list (80 features) | `backend/app/ml/features.py` | Defines the feature contract the log agent must compute |
| `IncidentCreate` schema | `backend/app/schemas/incident.py` | Log worker constructs this schema object when creating incidents |
| `HEURISTIC_FALLBACK` in classifier | `backend/app/ml/classifier.py` | Handles events with partial features when full CICIDS2017 extraction is not available |

---

## 5. Missing APIs

### 5a. `POST /api/v1/ingest/events`

The primary new endpoint. Accepts a batch of log events from the log agent.

**Authentication:** `X-API-Key` header with an agent-specific API key. Uses the existing `get_current_active_user` dependency which already supports API key auth. The agent user account must have `incident:create` permission (analyst role or a new `agent` role).

**Request body:** `EventBatch` (see section 6)  
**Response:** `IngestResponse`  
**Rate limit:** 100 batches per agent per minute (separate from the per-IP user limit)  
**Max payload:** 5 MB  

**Logic:**
1. Validate `EventBatch` schema (Pydantic)
2. Check `ingestion_batches` for duplicate `batch_id` — return 200 if already processed (idempotent)
3. Write `ingestion_batches` record with `status = "pending"`
4. Call `sqs_service.enqueue_log_batch(batch.model_dump())` — new SQS method
5. Return `IngestResponse(accepted=len(events), rejected=0, batch_id=batch.batch_id)`

**New router file:** `backend/app/routers/ingest.py`  
**Router prefix:** `/ingest`  
**Mount in:** `backend/app/main.py` alongside existing routers

---

### 5b. `GET /api/v1/ingest/status`

Returns current ingestion health for the dashboard.

**Authentication:** Bearer token, permission `dashboard:read`  
**Response:**
```json
{
  "connected_agents": 3,
  "events_last_hour": 14203,
  "incidents_created_last_hour": 7,
  "queue_depth": 42,
  "last_batch_received": "2026-07-05T14:23:11Z",
  "processing_lag_seconds": 4.2
}
```

Sourced from `ingestion_metrics` table + SQS `GetQueueAttributes` call.

---

### 5c. `POST /api/v1/agent/register`

Registers a new log agent instance. Returns a one-time API key for the agent.

**Authentication:** Bearer token, permission `user:manage` (admin only)  
**Request body:** `AgentRegisterRequest`  
**Response:** `AgentResponse` including the plaintext API key (shown once, stored as hash)  
**Side effects:** Creates a `log_agents` record + a system user account linked to it

**New router file:** `backend/app/routers/agent.py`

---

### 5d. `GET /api/v1/agent/config`

Returns the current ingestion configuration for the calling agent. The agent polls this on startup and every 5 minutes to pick up config changes without restart.

**Authentication:** `X-API-Key` (agent key)  
**Response:** `AgentConfig`

---

### 5e. `GET /api/v1/agents`

Lists all registered agents with health status. Admin-only.

**Authentication:** Bearer token, permission `user:manage`

---

## 6. Required Schemas

New Pydantic schemas in `backend/app/schemas/ingest.py`:

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class NetworkFeaturesPartial(BaseModel):
    """CICIDS2017 features — all optional for partial extraction mode."""
    flow_duration: Optional[float] = None
    total_fwd_packets: Optional[int] = None
    total_bwd_packets: Optional[int] = None
    flow_bytes_per_sec: Optional[float] = None
    flow_packets_per_sec: Optional[float] = None
    syn_flag_count: Optional[int] = None
    ack_flag_count: Optional[int] = None
    psh_flag_count: Optional[int] = None
    rst_flag_count: Optional[int] = None
    fin_flag_count: Optional[int] = None
    destination_port: Optional[int] = None
    init_win_bytes_forward: Optional[int] = None
    init_win_bytes_backward: Optional[int] = None
    # ... remaining 67 CICIDS2017 features, all Optional[float]


class LogEvent(BaseModel):
    """A single security-relevant event from the log agent."""
    timestamp: datetime
    source_type: str  # "nginx", "syslog", "app-json", "cloudflare", "aws-waf"
    source_ip: Optional[str] = None
    destination_ip: Optional[str] = None
    destination_port: Optional[int] = None
    protocol: Optional[str] = None
    raw_log: Optional[str] = Field(None, max_length=8192)
    structured: Optional[dict] = None  # Pre-parsed fields from the agent
    network_features: Optional[NetworkFeaturesPartial] = None  # Pre-computed features
    # Data sensitivity hints (drives compliance engine)
    personal_data_involved: bool = False
    health_data_involved: bool = False
    affected_jurisdictions: list[str] = []


class EventBatch(BaseModel):
    """Batch of events from a single agent."""
    batch_id: str = Field(..., max_length=64)  # Agent-generated UUID for idempotency
    agent_id: str
    agent_version: str = Field(..., max_length=32)
    hostname: str = Field(..., max_length=255)
    events: list[LogEvent] = Field(..., max_length=1000)


class IngestResponse(BaseModel):
    accepted: int
    rejected: int
    batch_id: str
    queued: bool  # False if processed synchronously


class AgentRegisterRequest(BaseModel):
    name: str = Field(..., max_length=255)
    hostname: str = Field(..., max_length=500)
    source_types: list[str]  # ["nginx", "syslog"]
    agent_version: str


class AgentResponse(BaseModel):
    id: str
    name: str
    hostname: str
    api_key: Optional[str] = None  # Only returned on registration
    is_active: bool
    last_seen: Optional[datetime]
    created_at: datetime


class AgentConfig(BaseModel):
    poll_interval_seconds: int = 30
    max_batch_size: int = 500
    sampling_rate: float = 1.0
    incident_auto_create_threshold: float = 0.70
    min_severity_to_create: str = "low"  # Ignore BENIGN + info
    log_sources: list[dict]


class IngestionStatus(BaseModel):
    connected_agents: int
    events_last_hour: int
    incidents_created_last_hour: int
    queue_depth: int
    last_batch_received: Optional[datetime]
    processing_lag_seconds: float
```

**Existing schema change** — `backend/app/schemas/incident.py`, `IncidentCreate` does not need changes. The log worker constructs it using the existing schema.

**TypeScript types** — `frontend/src/types/index.ts` needs corresponding interfaces for `AgentResponse`, `IngestionStatus`.

---

## 7. Required Worker Changes

### 7a. New file: `backend/app/workers/log_worker.py`

This is the core new component. Structure mirrors the existing `incident_worker.py`.

```python
"""Log ingestion worker — feature extraction, ML classification, incident creation."""

async def process_log_batch(body: dict) -> None:
    """Entry point from SQS poll loop."""
    batch = EventBatch(**body)
    
    # Idempotency: skip if already processed
    if await _batch_already_processed(batch.batch_id):
        return
    
    await _mark_batch_processing(batch.batch_id)
    
    incidents_created = 0
    for event in batch.events:
        incident = await _process_single_event(event, batch)
        if incident:
            incidents_created += 1
    
    await _mark_batch_done(batch.batch_id, incidents_created)


async def _process_single_event(event: LogEvent, batch: EventBatch) -> Incident | None:
    """
    1. Extract CICIDS2017 features from the event (or use pre-computed)
    2. Run ML classifier
    3. If threat detected above threshold: create incident
    4. Optionally store raw log as evidence
    """
    features = _extract_features(event)
    
    if not features:
        return None  # Cannot classify without any features
    
    prediction = classifier.predict(features)
    
    # Skip benign traffic and low-confidence predictions
    if (
        prediction["attack_category"] == "BENIGN"
        or prediction["confidence"] < settings.INCIDENT_AUTO_CREATE_THRESHOLD
    ):
        return None
    
    async with AsyncSessionLocal() as db:
        # Use the system agent user as the creator
        system_user = await _get_agent_system_user(db, batch.agent_id)
        
        incident_data = IncidentCreate(
            title=f"[Agent] {prediction['attack_category']} detected on {event.hostname}",
            description=(
                f"Automatically detected by LBRO agent on {batch.hostname}. "
                f"Source: {event.source_type}. Raw: {event.raw_log or 'N/A'}"
            ),
            severity=prediction["severity"],
            source_ip=event.source_ip,
            destination_ip=event.destination_ip,
            destination_port=event.destination_port,
            protocol=event.protocol,
            network_features=features,  # Store the features used for classification
            personal_data_involved=event.personal_data_involved,
            health_data_involved=event.health_data_involved,
            affected_jurisdictions=event.affected_jurisdictions,
        )
        
        svc = IncidentService(db)
        incident = await svc.create(incident_data, system_user)
        
        # Set agent metadata on the incident (new columns)
        incident.source_type = event.source_type
        incident.agent_id = batch.agent_id
        incident.raw_log = event.raw_log
        incident.batch_id = batch.batch_id
        
        # Optionally store raw log as evidence (skip for high-volume scenarios)
        if event.raw_log and settings.STORE_RAW_LOG_AS_EVIDENCE:
            await _store_log_evidence(db, incident, event, system_user)
        
        await db.commit()
        return incident


def _extract_features(event: LogEvent) -> dict | None:
    """
    Bridge between raw log events and CICIDS2017 feature format.
    
    Two modes:
    a) Pre-computed: agent already computed features → use directly
    b) Approximate: extract coarse features from structured log fields
    
    Approximate mode limitations: HTTP access logs don't contain packet-level
    timing statistics. We can approximate some features (destination_port,
    flow_packets_per_sec from request rate, syn_flag_count from connection counts)
    but most features will be 0. The heuristic fallback in the classifier handles
    this gracefully.
    """
    if event.network_features:
        # Pre-computed by agent (CICFlowMeter or eBPF) — use directly
        return event.network_features.model_dump(exclude_none=False)
    
    if event.structured:
        # Approximate from structured fields
        return _approximate_features(event)
    
    return None  # Cannot extract any features


def _approximate_features(event: LogEvent) -> dict:
    """
    Builds a partial CICIDS2017 feature vector from HTTP log fields.
    Most features will be 0; the classifier heuristic handles this.
    """
    s = event.structured or {}
    return {
        "destination_port": event.destination_port or s.get("port", 0),
        "flow_packets_per_sec": s.get("requests_per_sec", 0),
        "syn_flag_count": s.get("connection_count", 0),
        # All other features default to 0
        **{f: 0 for f in CICIDS2017_FEATURES 
           if f not in ("destination_port", "flow_packets_per_sec", "syn_flag_count")},
    }
```

### 7b. `backend/app/workers/main.py` — add third poll loop

```python
# Add after existing queue tasks:
from app.workers.log_worker import process_log_batch

if settings.SQS_LOG_QUEUE_URL:
    tasks.append(poll_queue(settings.SQS_LOG_QUEUE_URL, process_log_batch))
```

This is the **only change to `main.py`**. The existing incident and notification loops are untouched.

### 7c. `backend/app/services/sqs_service.py` — add new enqueue method

```python
def enqueue_log_batch(self, batch: dict) -> str:
    """Send a log event batch to the log queue."""
    return self.send_message(settings.SQS_LOG_QUEUE_URL, batch)
```

One new method. Existing methods unchanged.

---

## 8. Required Database Changes

All changes are additive. No existing columns or tables are modified. One new column per existing table.

### 8a. New table: `log_agents`

Tracks registered log agent instances.

```sql
CREATE TABLE log_agents (
    id            UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    name          VARCHAR(255) NOT NULL,
    hostname      VARCHAR(500),
    agent_version VARCHAR(50),
    source_types  JSONB,                     -- ["nginx", "syslog"]
    api_key_hash  VARCHAR(128) UNIQUE NOT NULL,
    user_id       UUID REFERENCES users(id) ON DELETE SET NULL,  -- linked system user
    last_seen     TIMESTAMPTZ,
    is_active     BOOLEAN      DEFAULT true,
    config        JSONB,                     -- AgentConfig JSON blob
    metadata      JSONB,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_log_agents_api_key_hash ON log_agents(api_key_hash);
CREATE INDEX idx_log_agents_is_active    ON log_agents(is_active);
```

### 8b. New table: `ingestion_batches`

Idempotency tracking. Prevents duplicate incident creation if the agent retries a batch.

```sql
CREATE TABLE ingestion_batches (
    id               UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    batch_id         VARCHAR(64)  UNIQUE NOT NULL,
    agent_id         UUID REFERENCES log_agents(id) ON DELETE SET NULL,
    event_count      INTEGER      NOT NULL DEFAULT 0,
    accepted_count   INTEGER      NOT NULL DEFAULT 0,
    rejected_count   INTEGER      NOT NULL DEFAULT 0,
    incidents_created INTEGER     NOT NULL DEFAULT 0,
    status           VARCHAR(50)  NOT NULL DEFAULT 'pending',
                                  -- pending | processing | done | failed
    error_message    TEXT,
    processed_at     TIMESTAMPTZ,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ingestion_batches_batch_id  ON ingestion_batches(batch_id);
CREATE INDEX idx_ingestion_batches_agent_id  ON ingestion_batches(agent_id);
CREATE INDEX idx_ingestion_batches_created_at ON ingestion_batches(created_at);
```

### 8c. New table: `ingestion_metrics`

Aggregated per-minute counters for the dashboard status endpoint. Written by the log worker after each batch.

```sql
CREATE TABLE ingestion_metrics (
    id                UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id          UUID REFERENCES log_agents(id) ON DELETE CASCADE,
    window_start      TIMESTAMPTZ NOT NULL,   -- truncated to the minute
    events_received   INTEGER     NOT NULL DEFAULT 0,
    events_classified INTEGER     NOT NULL DEFAULT 0,
    incidents_created INTEGER     NOT NULL DEFAULT 0,
    threats_detected  INTEGER     NOT NULL DEFAULT 0,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (agent_id, window_start)           -- upsert target
);

CREATE INDEX idx_ingestion_metrics_agent_window ON ingestion_metrics(agent_id, window_start);
CREATE INDEX idx_ingestion_metrics_window ON ingestion_metrics(window_start);
```

### 8d. New columns on `incidents`

```sql
ALTER TABLE incidents
    ADD COLUMN source_type VARCHAR(50),         -- 'manual' | 'agent' | 'cloudflare' | 'aws-waf'
    ADD COLUMN agent_id    UUID REFERENCES log_agents(id) ON DELETE SET NULL,
    ADD COLUMN raw_log     TEXT,                -- raw log line that triggered this incident
    ADD COLUMN batch_id    VARCHAR(64);         -- links to ingestion_batches.batch_id

CREATE INDEX idx_incidents_source_type ON incidents(source_type);
CREATE INDEX idx_incidents_agent_id    ON incidents(agent_id);
```

Existing rows get `source_type = 'manual'` via the migration's data backfill:
```sql
UPDATE incidents SET source_type = 'manual' WHERE source_type IS NULL;
```

### 8e. New Alembic migration: `007_log_ingestion.py`

New migration in `backend/app/migrations/versions/007_log_ingestion.py`. Creates all four changes above in a single reversible migration. Downgrade drops the new tables and columns.

---

## 9. New Configuration Settings

New entries for `backend/app/config.py` (all additive — no existing settings changed):

```python
# ── Log Ingestion ─────────────────────────────────────────────────────────
SQS_LOG_QUEUE_URL: str = ""              # New SQS queue for raw log batches
MAX_EVENTS_PER_BATCH: int = 1000        # Reject batches larger than this
MAX_BATCH_PAYLOAD_KB: int = 5120        # Reject payloads > 5 MB
LOG_AGENT_RATE_LIMIT_PER_MINUTE: int = 100  # Per-agent-key rate limit
INCIDENT_AUTO_CREATE_THRESHOLD: float = 0.70  # Min confidence to auto-create incident
STORE_RAW_LOG_AS_EVIDENCE: bool = False  # Store raw log lines as evidence (expensive)
AGENT_CONFIG_POLL_INTERVAL: int = 300   # How often agents re-fetch config (seconds)
```

---

## 10. Infrastructure Changes

### 10a. New SQS Queue: `lbro-log-queue`

Different from the existing `lbro-incident-queue` because log batches:
- Arrive at much higher volume than manual incidents
- Process faster (no email sending)
- Need a separate DLQ threshold

```hcl
# terraform/modules/sqs/log_queue.tf
resource "aws_sqs_queue" "log_queue" {
  name                       = "${var.project_name}-log-queue"
  visibility_timeout_seconds = 60       # Shorter than incident queue (300s)
  message_retention_seconds  = 86400    # 1 day (batches are transient)
  receive_wait_time_seconds  = 20       # Long polling

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.log_dlq.arn
    maxReceiveCount     = 3
  })
}

resource "aws_sqs_queue" "log_dlq" {
  name                      = "${var.project_name}-log-dlq"
  message_retention_seconds = 604800    # 7 days for investigation
}
```

### 10b. New ECS Task: Log Worker

The log worker can run as a separate ECS Fargate task (same image as the existing worker, different command) or as an additional process in the existing worker task. Recommended: separate task for independent scaling.

```hcl
# Additional task definition for the log worker
# Same Docker image as the existing worker
# CMD: ["python", "-m", "app.workers.main", "--only-queue", "log"]
```

### 10c. IAM Policy Updates

The existing task role needs `sqs:SendMessage` / `sqs:ReceiveMessage` / `sqs:DeleteMessage` on the new log queue ARN. This is an additive change to the existing IAM policy.

### 10d. Redis (Recommended for v2)

With the agent introducing potentially high-volume ingest traffic, the in-memory rate limiter becomes a blocker for multi-replica API deployments. The existing `REDIS_URL` setting is already in `config.py` but unused. v2 should activate it:

```python
# middleware/rate_limit.py — replace defaultdict with Redis
# Use redis-py async client with INCR + EXPIRE
```

This unblocks horizontal API scaling under agent load.

### 10e. LocalStack init script update

`scripts/localstack-init.sh` — add queue creation for the new log queue:

```bash
awslocal sqs create-queue --queue-name lbro-log-queue
awslocal sqs create-queue --queue-name lbro-log-dlq
```

---

## 11. Log Agent Specification

The log agent is a **new separate binary** — not part of the FastAPI backend. It is out of scope for v2 implementation but the API contract must accommodate it.

### Minimum Viable Agent (MVP)

Language: **Python** (faster to build, matches the rest of LBRO's stack)  
Deployment: `pip install lbro-agent` or Docker sidecar  
Config file: `lbro-agent.yaml`

```yaml
# lbro-agent.yaml
api_url: https://lbro.your-org.com
api_key: lbro-agent-xxxxxxxxxxxx
hostname: web-prod-01

sources:
  - type: file
    path: /var/log/nginx/access.log
    format: nginx-combined
  - type: file
    path: /var/log/auth.log
    format: syslog

batch:
  max_events: 500
  max_interval_seconds: 30
  max_payload_kb: 2048

spool_dir: /tmp/lbro-agent-spool   # Local disk buffer for retry
```

### Agent Internal Flow

```
[Log Source]
    ↓  tail -F / inotify
[Parser]         ← Converts raw line to LogEvent.structured
    ↓
[Feature Extractor]  ← Computes partial CICIDS2017 features
    ↓
[Batcher]        ← Accumulates up to max_events or max_interval
    ↓
[Shipper]        ← POST /api/v1/ingest/events
    ↓ (on failure)
[Disk Spooler]   ← Write failed batch to spool_dir, retry with backoff
```

### Supported Log Formats (MVP)

- **nginx combined** — extracts: source IP, destination port (from request), request method, status code, bytes, referrer
- **syslog auth.log** — extracts: source IP, failed/success auth events, brute-force detection from rapid failures
- **JSON application log** — pass-through of structured fields

### Feature Extraction Modes

| Mode | Agent Requirement | Feature Quality | When to Use |
|---|---|---|---|
| Full CICIDS2017 | CICFlowMeter or eBPF on agent host | High (all 80 features) | Network-level monitoring |
| Partial HTTP | Any HTTP access log | Low (5–10 features) | Application-level only |
| Zero (raw only) | Log tail only | None (heuristic classifier) | Minimum viable setup |

---

## 12. Frontend Changes Required

### 12a. New API functions in `frontend/src/api/client.ts`

```typescript
// Ingestion status
export const ingestApi = {
  status: (): Promise<IngestionStatus> =>
    apiClient.get<IngestionStatus>('/api/v1/ingest/status').then(r => r.data),
}

// Agent management
export const agentApi = {
  list: (): Promise<AgentResponse[]> =>
    apiClient.get<AgentResponse[]>('/api/v1/agents').then(r => r.data),
  register: (data: AgentRegisterRequest): Promise<AgentResponse> =>
    apiClient.post<AgentResponse>('/api/v1/agent/register', data).then(r => r.data),
}
```

### 12b. New TypeScript types in `frontend/src/types/index.ts`

```typescript
export interface IngestionStatus {
  connected_agents: number
  events_last_hour: number
  incidents_created_last_hour: number
  queue_depth: number
  last_batch_received: string | null
  processing_lag_seconds: number
}

export interface AgentResponse {
  id: string
  name: string
  hostname: string
  is_active: boolean
  last_seen: string | null
  created_at: string
  api_key?: string  // Only present on registration response
}
```

### 12c. Dashboard widget — Ingestion Status

A new `StatCard` on `DashboardPage.tsx` showing:
- Connected agents count (from `ingest.status()`)
- Events/hour
- Auto-created incidents in last hour

This is additive — no existing dashboard cards are removed.

### 12d. New page: `AgentsPage.tsx`

Route: `/agents`  
Permission: `user:manage` (admin only)

Shows a table of registered agents, their last-seen timestamp, status (active/inactive), and source types. Includes a "Register New Agent" form that calls `POST /api/v1/agent/register` and displays the one-time API key.

### 12e. MSW mock handlers

New file: `frontend/src/mocks/handlers/ingest.ts`  
New file: `frontend/src/mocks/handlers/agents.ts`

Both return realistic mock data so the frontend works in mock mode without a backend.

### 12f. Sidebar entry

In `frontend/src/components/layout/Sidebar.tsx`, add an "Agents" link gated by `useCan(Permission.MANAGE_USERS)`. This matches the existing pattern for admin-only links.

---

## 13. RBAC Changes

The log agent authenticates using a service account. Two options:

**Option A (recommended): Reuse analyst role**  
Register the agent as a standard user with `role = "analyst"`. It already has `incident:create` permission. Simple, no schema changes.

**Option B: New `agent` role**  
Add a fourth role with only the permissions needed for ingestion: `incident:create`, `evidence:upload`. More restrictive but adds complexity.

Recommendation: **Option A** for v2. If multi-tenancy or fine-grained agent permissions become a requirement, introduce Option B in v3.

---

## 14. New Permissions Required

No new `Permission` enum values are needed for v2. The ingest endpoints use:

| Endpoint | Permission | Notes |
|---|---|---|
| `POST /api/v1/ingest/events` | `incident:create` | Agent's analyst account |
| `GET /api/v1/ingest/status` | `dashboard:read` | All authenticated users |
| `POST /api/v1/agent/register` | `user:manage` | Admin only |
| `GET /api/v1/agents` | `user:manage` | Admin only |
| `GET /api/v1/agent/config` | None (API key auth) | Agent's own config |

---

## 15. Implementation Order

This is a phased plan. Each phase is independently deployable and testable without breaking existing functionality.

### Phase 1 — Database (Week 1)

1. Write Alembic migration `007_log_ingestion.py`
2. Test migration up/down in dev
3. Add new columns to `Incident` SQLAlchemy model
4. Add `LogAgent` and `IngestionBatch` models to `backend/app/models/`
5. Export from `models/__init__.py`

No API changes in this phase. Existing endpoints continue working.

---

### Phase 2 — Ingest API (Week 1–2)

1. Write `backend/app/schemas/ingest.py` (all schemas in section 6)
2. Write `backend/app/routers/ingest.py` (ingest + agent endpoints)
3. Write `backend/app/routers/agent.py`
4. Mount both routers in `main.py`
5. Add `SQS_LOG_QUEUE_URL` and new settings to `config.py`
6. Add `enqueue_log_batch()` to `sqs_service.py`
7. Write tests: `backend/tests/test_ingest.py`

At end of Phase 2: the ingest endpoint accepts batches, validates them, and enqueues to SQS (or logs a warning if `SQS_LOG_QUEUE_URL` is not set).

---

### Phase 3 — Log Worker (Week 2–3)

1. Write `backend/app/workers/log_worker.py`
2. Write feature extractor: `backend/app/ml/feature_extractor.py`
3. Update `workers/main.py` to add log queue poll loop
4. Add log queue to LocalStack init script
5. Write tests: `backend/tests/test_log_worker.py`
6. Test end-to-end: `POST /api/v1/ingest/events` → SQS → log worker → incident created

---

### Phase 4 — Frontend (Week 3)

1. Add new TypeScript types to `types/index.ts`
2. Add `ingestApi` and `agentApi` to `api/client.ts`
3. Add ingestion status widget to `DashboardPage.tsx`
4. Write `AgentsPage.tsx`
5. Add `/agents` route to `AppRouter.tsx`
6. Add sidebar entry
7. Write MSW mock handlers for new endpoints
8. Run `npx tsc --noEmit` → 0 errors

---

### Phase 5 — Infrastructure (Week 4)

1. Add Terraform resources for `lbro-log-queue` and `lbro-log-dlq`
2. Update IAM policies
3. Add log worker ECS task definition
4. Add new env vars to ECS task definition
5. Activate Redis rate limiter (replaces in-memory for multi-replica safety)
6. Update GitHub Actions CI to test new endpoints

---

### Phase 6 — Log Agent MVP (Week 4–6, separate repo)

1. Scaffold `lbro-agent` Python package
2. Implement nginx access log parser
3. Implement syslog/auth.log parser
4. Implement batch shipper with disk spool
5. Write Docker image: `ghcr.io/lbro/agent:latest`
6. Write `docker-compose.example.yml` snippet for sidecar deployment
7. Write agent documentation

---

## 16. What Does NOT Change

The following are explicitly unchanged. No modifications required.

| Component | Reason |
|---|---|
| `ml/classifier.py` | Log worker calls the same `predict()` interface |
| `ml/features.py` | Same CICIDS2017 feature list — no new features |
| `services/incident_service.py` | Log worker calls `create()` exactly as the API router does |
| `services/compliance_service.py` | Auto-fires from `IncidentService.create()` |
| `services/notification_service.py` | Auto-fires from `IncidentService.create()` |
| `services/evidence_service.py` | Log worker calls existing upload method |
| `workers/incident_worker.py` | Unchanged — continues to handle manual re-classification |
| `workers/notification_worker.py` | Unchanged |
| `core/rbac.py` | No new permissions needed for Phase 1–4 |
| `models/incident.py` | Only new columns added; existing columns and relationships unchanged |
| All existing API endpoints | Zero changes to existing routes |
| All existing frontend pages | New pages added; existing pages unchanged |
| All existing database tables | New tables and columns added; no existing schema modified |
| Authentication flow | Agent uses existing X-API-Key mechanism |
| Compliance engine | Auto-triggers from incident creation — no changes |
| PDF reports | Reports gain a new "Agent-created incidents" section in v2 (minor addition) |

---

## 17. Known Risks and Open Questions

**Feature quality in approximate mode**  
Raw HTTP logs yield at best 5–10 of the 80 CICIDS2017 features. The heuristic classifier handles this gracefully (confidence = 0.65, always flagged for review), but threat detection quality will be lower than with a full CICFlowMeter agent. This is documented and expected for the MVP.

**Incident volume explosion**  
A busy production server generates thousands of HTTP requests per minute. Even with sampling (default 1.0 → should be 0.01 or lower for high-traffic apps), the agent could create hundreds of incidents per hour. The `INCIDENT_AUTO_CREATE_THRESHOLD` (default 0.70) and `min_severity_to_create` (default "low") settings are the primary controls. A deduplication window (suppress duplicate source IPs within N minutes) should be added to the log worker before production use.

**Idempotency at scale**  
The `ingestion_batches` table check is a `SELECT` before each insert. Under high concurrency (many agents), this can race. The `UNIQUE (batch_id)` constraint is the safety net — duplicate inserts will raise an integrity error that the worker catches and ignores.

**Agent API key rotation**  
No rotation flow is designed. An agent with a compromised key requires admin to delete and re-register the agent. A key rotation endpoint (`POST /api/v1/agents/{id}/rotate-key`) should be part of Phase 2.

**Evidence storage at agent scale**  
`STORE_RAW_LOG_AS_EVIDENCE = False` by default. If enabled, every auto-created incident generates a PostgreSQL blob with the raw log line. At 100 incidents/hour this is manageable; at 10,000/hour it will impact PostgreSQL performance. S3 migration (already designed in the schema via `s3_key` columns) becomes urgent at that scale.

**ML model staleness**  
The CICIDS2017 model was trained on 2017 data. Real production logs from 2026 may exhibit attack patterns the model has never seen, resulting in `BENIGN` classifications for genuine threats. The `needs_analyst_review` flag and the heuristic fallback confidence (0.65) ensure these are surfaced for human review. Online learning (v3 roadmap) addresses this structurally.

---

## 18. Summary Table

| Item | Status | Phase |
|---|---|---|
| `log_agents` table | Missing | 1 |
| `ingestion_batches` table | Missing | 1 |
| `ingestion_metrics` table | Missing | 1 |
| `incidents.source_type` / `agent_id` / `raw_log` columns | Missing | 1 |
| Alembic migration 007 | Missing | 1 |
| `schemas/ingest.py` | Missing | 2 |
| `routers/ingest.py` | Missing | 2 |
| `routers/agent.py` | Missing | 2 |
| `sqs_service.enqueue_log_batch()` | Missing | 2 |
| `config.py` — new log ingestion settings | Missing | 2 |
| `workers/log_worker.py` | Missing | 3 |
| `ml/feature_extractor.py` | Missing | 3 |
| `workers/main.py` — add log queue poll | Minor change | 3 |
| `frontend/src/types/index.ts` — new types | Missing | 4 |
| `frontend/src/api/client.ts` — ingestApi/agentApi | Missing | 4 |
| `DashboardPage.tsx` — ingestion widget | Missing | 4 |
| `AgentsPage.tsx` | Missing | 4 |
| `AppRouter.tsx` — /agents route | Missing | 4 |
| `Sidebar.tsx` — agents link | Missing | 4 |
| MSW handlers for ingest + agents | Missing | 4 |
| Terraform: `lbro-log-queue` | Missing | 5 |
| Terraform: log worker ECS task | Missing | 5 |
| Redis rate limiter activation | Missing | 5 |
| LocalStack init: log queue | Missing | 5 |
| LBRO Agent binary (separate repo) | Missing | 6 |
| Agent documentation | Missing | 6 |
| `AttackClassifier.predict()` | **Reusable as-is** | — |
| `IncidentService.create()` | **Reusable as-is** | — |
| `ComplianceService` | **Reusable as-is** | — |
| `NotificationService` | **Reusable as-is** | — |
| `EvidenceService` | **Reusable as-is** | — |
| `SQSService` | **Reusable as-is** | — |
| `incident_worker.py` | **Reusable as-is** | — |
| `notification_worker.py` | **Reusable as-is** | — |
| `workers/main.py` poll_queue() | **Reusable as-is** | — |
| All existing API endpoints | **Unchanged** | — |
| All existing frontend pages | **Unchanged** | — |

---

*LBRO v2 Architecture Plan — prepared July 2026*  
*Document owner: Engineering Lead*  
*Review before Phase 1 implementation*
