# Prompt for Cursor agent (car dealership ↔ LBRO)

Copy everything inside the fenced block below into a **new Cursor chat opened in your car dealership project repo** (not in LBRO).

---

```markdown
## Goal

LBRO integration is already linked with a project API key. Create **`testlbro.py`** at the repo root (or `scripts/testlbro.py`) that sends realistic **security events** for our **car dealership** app to LBRO so we can see them live in the LBRO UI (events, incidents, ML classification).

Do **not** commit real API keys. Read the key from environment variables only.

## Environment (required)

Create `.env.example` (not `.env`) with:

```env
LBRO_API_URL=http://localhost:8000/api/v1
LBRO_PROJECT_API_KEY=proj_your_key_here
```

Runtime:

```powershell
$env:LBRO_API_URL="http://localhost:8000/api/v1"
$env:LBRO_PROJECT_API_KEY="proj_..."   # from LBRO UI → Project → Integrations
python testlbro.py --live
```

## LBRO API contract (must follow)

- **Auth:** `Authorization: Bearer <PROJECT_API_KEY>` (key starts with `proj_`)
- **Do not send `project_id`** in body or query — LBRO resolves project from the key
- **Single event:** `POST {LBRO_API_URL}/events` → expect **202**
- **Batch (optional):** `POST {LBRO_API_URL}/events/batch` with `{"events": [...]}`
- **List (verify):** `GET {LBRO_API_URL}/events?limit=20` with same Bearer key
- **Allowed `event_type`:** `auth_failure`, `sql_injection`, `xss`, `brute_force`, `port_scan`, `suspicious_request`, `system_log`, `application_log`, `nginx_log`, `apache_log`, `firewall_event`, `windows_event`, `linux_audit`, `custom`
- **Allowed `severity`:** `critical`, `high`, `medium`, `low`, `info`
- **Body fields:** `event_type`, `severity`, optional `source_ip`, `source_host`, `source_application`, `message`, `event_timestamp` (ISO8601 UTC), `payload` (object)

Use **`httpx`** or **`requests`**. Prefer Python 3.11+.

## Scenarios to implement (car dealership themed)

Implement at least **6** POSTs in one run, with clear console output (`status code` + event id if returned):

1. **brute_force / high** — customer portal login (`source_application`: e.g. `car-dealership-customer-portal`)
2. **sql_injection / critical** — inventory/VIN search API
3. **port_scan / medium** — firewall log from dealer network
4. **auth_failure / high** — finance/quote API
5. **suspicious_request / high** — web tier / listing scrape
6. **custom / info** — benign “link check” heartbeat from `testlbro.py`

Set `source_application` to names that identify our dealership services so they are easy to spot in LBRO.

## CLI flags

- `--live` — sleep **3 seconds** between each POST so a human can watch LBRO UI update
- `--dry-run` — print JSON payloads without calling LBRO
- Default — fire all events quickly, then `GET /events` and print count of recent items

## How the human verifies in LBRO (document in script docstring)

1. LBRO UI logged in → select the **same project** as the API key
2. Open **Events** (or project events stream if available)
3. **High/critical** events may create **incidents** — check Incidents list
4. Optional API docs: `http://localhost:8000/docs` → `POST /api/v1/events`
5. If using Docker: `docker compose logs -f api worker` while running `testlbro.py --live`

## Tests for this repo (minimal)

Add **`tests/test_lbro_integration.py`** (or pytest) that:

- Mocks LBRO HTTP **or** skips unless `LBRO_PROJECT_API_KEY` is set
- Asserts our app's “send to LBRO” helper builds valid payloads (correct headers, no `project_id` in body)
- Does **not** require LBRO running in CI by default (`pytest -m "not lbro"`)

## Reference

If the LBRO monorepo is available locally, mirror behavior from:
`lbro/scripts/testlbro_reference.py`

## Deliverables

1. `testlbro.py` (runnable)
2. `.env.example`
3. Short `LBRO_TESTING.md` with run steps and where to look in LBRO UI
4. Optional pytest file as above

Run `python testlbro.py` once before finishing and paste the terminal output showing **202** responses.
```

---

## Quick manual test (you, right now)

1. LBRO running: `docker compose up -d` in `lbro` **or** API on `:8000`
2. Copy `proj_*` key from **Integrations**
3. From LBRO repo:

```powershell
$env:LBRO_PROJECT_API_KEY="proj_..."
python c:\Users\veere\Desktop\lbro\scripts\testlbro_reference.py --live
```

4. In LBRO UI: same project → **Events** / **Incidents** (refresh or live stream)
