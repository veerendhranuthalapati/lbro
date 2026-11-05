# Realistic LBRO integration testing

Use **`scripts/realistic_attack_simulator.py`** (not the old metadata-only `testlbro_reference.py`) when validating a linked app such as a car dealership.

## Run (use this — not old `testlbro_reference.py`)

```powershell
# Your public IP as attacker (optional — auto-detected if omitted)
$env:LBRO_ATTACK_SOURCE_IP="YOUR.PUBLIC.IP"
# Where your dealership app actually runs
$env:LBRO_TARGET_IP="192.168.1.50"
$env:LBRO_GEO_COUNTRY="IN"
$env:LBRO_GEO_CITY="Hyderabad"
$env:LBRO_APPLICATION_NAME="my-car-dealership-api"
$env:LBRO_PROJECT_API_KEY="proj_..."

python c:\Users\veere\Desktop\lbro\scripts\realistic_attack_simulator.py --chain --live
```

Apply migration **018_integration_context** if using Postgres (`alembic upgrade head` or compose rebuild).

## What fills the incident overview

| UI field | Source |
|----------|--------|
| Source IP | `source_ip` on event (sim uses your IP) |
| Destination IP / ports / protocol | `payload.network` |
| Country / city | `payload.geo` |
| User Agent | `payload.http.user_agent` |
| Application | `source_application` / `payload.service` |
| MITRE / OWASP | `payload.threat_intel` or auto map from `event_type` |
| Personal data / DPDPA | `payload.compliance` |
| ML confidence | Model when bundle loads + full `network_features`; not the empty-payload 50% path |

Old incidents created with metadata-only POSTs stay sparse — **run a new `--chain` after upgrading**.

## What you should see

| Layer | Content |
|--------|---------|
| **Events (live SSE)** | Source IP, dest port, ML source, feature coverage |
| **GET /api/v1/events/{id}** | Full `payload` (HTTP excerpt, `network`, 77 flow features) |
| **Incidents** | `destination_ip`, ports, `network_features` on Raw Event tab |
| **Evidence** | Auto files: `ingestion-event-*.json`, `http-access-*.log`, `network-flow-*.json` |
| **ML confidence** | Varies with model + flow shape when bundle loads; not the empty-payload 50% heuristic |

## Payload contract (from your app or the simulator)

```json
{
  "event_type": "sql_injection",
  "severity": "critical",
  "source_ip": "198.51.100.44",
  "source_application": "car-dealership-north-lot",
  "message": "...",
  "payload": {
    "network": {
      "destination_ip": "10.20.5.12",
      "source_port": 45123,
      "destination_port": 443,
      "protocol": "TCP"
    },
    "http": {
      "method": "GET",
      "path": "/api/v1/inventory/search",
      "query_sample": "..."
    },
    "network_features": { "... all CICIDS2017 feature names ...": 0.0 }
  }
}
```

Generate vectors in Python: `from app.integrations.flow_profiles import build_dealership_scenario`.

## Disable auto evidence (optional)

Set `EVENT_INGESTION_CAPTURE_EVIDENCE=false` in API env.
