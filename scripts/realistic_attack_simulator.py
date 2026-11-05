#!/usr/bin/env python3
"""
Realistic multi-stage dealership attack simulation for LBRO integration testing.

Uses backend flow profiles (CICIDS-shaped vectors + HTTP context), not flat
metadata-only payloads. Each high/critical event should produce:
  - Model or coverage-aware ML scores (not the empty-payload 50% heuristic)
  - Incidents with ports, destination IP, network_features
  - Evidence vault files (JSON snapshot, HTTP log, flow JSON)

Usage (from repo root):
  set LBRO_PROJECT_API_KEY=proj_...
  python scripts/realistic_attack_simulator.py --live
  python scripts/realistic_attack_simulator.py --chain --seed 42
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

try:
    import httpx
except ImportError:
    print("pip install httpx", file=sys.stderr)
    raise SystemExit(1)

from app.integrations.flow_profiles import build_dealership_scenario, dealership_attack_sequence, resolve_attack_topology

BASE = os.environ.get("LBRO_API_URL", "http://localhost:8000/api/v1").rstrip("/")
KEY = os.environ.get("LBRO_PROJECT_API_KEY", "")


def headers() -> dict[str, str]:
    if not KEY.startswith("proj_"):
        print("Set LBRO_PROJECT_API_KEY=proj_...", file=sys.stderr)
        raise SystemExit(2)
    return {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}


def post_event(client: httpx.Client, body: dict) -> httpx.Response:
    body = dict(body)
    body.setdefault("event_timestamp", datetime.now(timezone.utc).isoformat())
    return client.post(f"{BASE}/events", json=body, headers=headers())


def main() -> None:
    parser = argparse.ArgumentParser(description="Realistic LBRO integration attack sim")
    parser.add_argument("--live", action="store_true", help="Pause 4s between events")
    parser.add_argument("--chain", action="store_true", help="Run port scan → brute → SQLi chain")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for flow vectors")
    args = parser.parse_args()

    if args.chain:
        scenarios = dealership_attack_sequence(base_seed=args.seed)
    else:
        scenarios = [
            build_dealership_scenario("port_scan", seed=args.seed),
            build_dealership_scenario("brute_force", seed=args.seed + 1),
            build_dealership_scenario("sql_injection", seed=args.seed + 2),
            build_dealership_scenario("suspicious_request", seed=args.seed + 3),
        ]

    print(f"Target: {BASE}")
    topo = resolve_attack_topology()
    print(f"Topology: attacker={topo['source_ip']} → target={topo['target_ip']} app={topo['application']}")
    with httpx.Client(timeout=60.0) as client:
        ready_url = BASE.replace("/api/v1", "") + "/health/ready"
        print(f"health: {client.get(ready_url).status_code}")

        for i, scenario in enumerate(scenarios, 1):
            r = post_event(client, scenario)
            preview = r.text[:300]
            print(f"[{i}/{len(scenarios)}] {scenario['event_type']} -> {r.status_code} {preview}")
            if r.status_code in (200, 202):
                data = r.json()
                cov = data.get("ml_feature_coverage")
                src = data.get("ml_source")
                conf = data.get("ml_confidence")
                print(
                    f"     ML: source={src} confidence={conf} coverage={cov} "
                    f"incident={data.get('incident_id')}"
                )
            if args.live:
                time.sleep(4)

        lr = client.get(f"{BASE}/events", params={"limit": 10}, headers=headers())
        print(f"list events: {lr.status_code} total={lr.json().get('total')}")


if __name__ == "__main__":
    main()
