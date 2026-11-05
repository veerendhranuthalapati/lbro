#!/usr/bin/env python3
"""
Reference LBRO integration tester — car-dealership themed security events.

Copy into your dealership repo as testlbro.py and set:
  LBRO_API_URL=http://localhost:8000/api/v1
  LBRO_PROJECT_API_KEY=proj_...   (from LBRO → Project → Integrations)

Run: python testlbro.py
     python testlbro.py --live   (pause between events so you can watch the UI)
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone

try:
    import httpx
except ImportError:
    print("Install: pip install httpx", file=sys.stderr)
    raise SystemExit(1)

BASE = os.environ.get("LBRO_API_URL", "http://localhost:8000/api/v1").rstrip("/")
KEY = os.environ.get("LBRO_PROJECT_API_KEY", "")

# Simulated attacks against a fictional dealership stack
SCENARIOS = [
    {
        "event_type": "brute_force",
        "severity": "high",
        "source_application": "car-dealership-customer-portal",
        "source_ip": "203.0.113.50",
        "message": "Repeated failed logins on /api/customer/login (dealership portal)",
        "payload": {"endpoint": "/api/customer/login", "fail_count": 120, "dealer_id": "north-lot"},
    },
    {
        "event_type": "sql_injection",
        "severity": "critical",
        "source_application": "car-dealership-inventory-api",
        "source_ip": "198.51.100.22",
        "message": "Suspicious SQL-like input on inventory search",
        "payload": {"query_param": "q", "sample": "' OR 1=1--", "vehicle_vin_search": True},
    },
    {
        "event_type": "port_scan",
        "severity": "medium",
        "source_application": "car-dealership-dmz-firewall",
        "source_ip": "192.0.2.77",
        "message": "Sequential TCP probe across dealer service ports",
        "payload": {"ports_touched": [22, 443, 5432, 8080], "site": "service-bay-network"},
    },
    {
        "event_type": "auth_failure",
        "severity": "high",
        "source_application": "car-dealership-finance-module",
        "source_ip": "203.0.113.91",
        "message": "Invalid API key attempts on finance quote endpoint",
        "payload": {"route": "/api/finance/quote", "role": "anonymous"},
    },
    {
        "event_type": "suspicious_request",
        "severity": "high",
        "source_application": "car-dealership-web",
        "source_ip": "198.51.100.5",
        "message": "Abnormal request rate on vehicle listing scrape pattern",
        "payload": {"user_agent": "bot-scraper/1.0", "listings_per_min": 400},
    },
    {
        "event_type": "custom",
        "severity": "info",
        "source_application": "car-dealership-testlbro",
        "message": "LBRO link check — benign heartbeat from testlbro.py",
        "payload": {"test_run": True},
    },
]


def headers() -> dict[str, str]:
    if not KEY or not KEY.startswith("proj_"):
        print("Set LBRO_PROJECT_API_KEY to your project's proj_* key.", file=sys.stderr)
        raise SystemExit(2)
    return {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}


def post_event(client: httpx.Client, body: dict) -> httpx.Response:
    body.setdefault("event_timestamp", datetime.now(timezone.utc).isoformat())
    return client.post(f"{BASE}/events", json=body, headers=headers())


def list_events(client: httpx.Client, limit: int = 20) -> httpx.Response:
    return client.get(f"{BASE}/events", params={"limit": limit}, headers=headers())


def main() -> None:
    parser = argparse.ArgumentParser(description="Send dealership-themed events to LBRO")
    parser.add_argument("--live", action="store_true", help="Sleep 3s between events for UI watching")
    parser.add_argument("--dry-run", action="store_true", help="Print payloads only")
    args = parser.parse_args()

    print(f"LBRO base: {BASE}")
    if args.dry_run:
        for i, s in enumerate(SCENARIOS, 1):
            print(f"[{i}] {s['event_type']} / {s['severity']}: {s['message']}")
        return

    with httpx.Client(timeout=30.0) as client:
        health = client.get(BASE.replace("/api/v1", "") + "/health/ready")
        print(f"health/ready: {health.status_code}")

        for i, scenario in enumerate(SCENARIOS, 1):
            r = post_event(client, dict(scenario))
            print(f"[{i}/{len(SCENARIOS)}] POST /events -> {r.status_code} {r.text[:200]}")
            if r.status_code not in (200, 202):
                print("  FAIL — check API URL, key, and that LBRO stack is up.", file=sys.stderr)
            if args.live:
                time.sleep(3)

        lr = list_events(client)
        print(f"GET /events -> {lr.status_code}")
        if lr.status_code == 200:
            data = lr.json()
            items = data if isinstance(data, list) else data.get("items", data)
            print(f"  recent events returned: {len(items) if isinstance(items, list) else '?'}")


if __name__ == "__main__":
    main()
