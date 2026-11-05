"""
Realistic CICIDS-style flow vectors for integration testing.

Vectors are built from bundle training medians with archetype-specific shaping
and per-run jitter — not a single hardcoded confidence path.

Environment (real-world addressing):
  LBRO_ATTACK_SOURCE_IP  — attacker IP shown in LBRO (default: your public IP via ipify)
  LBRO_TARGET_IP         — your dealership/app server IP (default: 127.0.0.1)
  LBRO_DEALER_SITE       — site slug (north-lot)
  LBRO_APPLICATION_NAME  — shown under Application in incident overview
  LBRO_GEO_COUNTRY       — ISO country code (default IN)
  LBRO_GEO_CITY          — optional city label
  LBRO_USER_AGENT        — optional UA string for HTTP attacks
"""
from __future__ import annotations

import json
import os
import random
import socket
from pathlib import Path
from typing import Any

from app.config import settings
from app.ml.features import CICIDS2017_FEATURES

_ARCHETYPE_SHAPES: dict[str, dict[str, float]] = {
    "port_scan": {
        "destination_port": 22.0,
        "flow_duration": 1200.0,
        "total_fwd_packets": 45.0,
        "total_bwd_packets": 2.0,
        "syn_flag_count": 800.0,
        "flow_packets_per_sec": 120.0,
        "flow_bytes_per_sec": 8000.0,
    },
    "web_brute_force": {
        "destination_port": 443.0,
        "flow_duration": 85000.0,
        "total_fwd_packets": 220.0,
        "total_bwd_packets": 180.0,
        "syn_flag_count": 12.0,
        "ack_flag_count": 400.0,
        "flow_packets_per_sec": 35.0,
        "flow_bytes_per_sec": 42000.0,
    },
    "sql_injection": {
        "destination_port": 443.0,
        "flow_duration": 4200.0,
        "total_fwd_packets": 18.0,
        "total_bwd_packets": 14.0,
        "flow_packets_per_sec": 8.5,
        "flow_bytes_per_sec": 12000.0,
        "fwd_packet_length_mean": 512.0,
    },
    "ddos": {
        "destination_port": 80.0,
        "flow_duration": 500.0,
        "total_fwd_packets": 5000.0,
        "total_bwd_packets": 10.0,
        "syn_flag_count": 4500.0,
        "flow_packets_per_sec": 15000.0,
        "flow_bytes_per_sec": 900000.0,
    },
    "data_exfil": {
        "destination_port": 443.0,
        "flow_duration": 600000.0,
        "total_fwd_packets": 40.0,
        "total_bwd_packets": 900.0,
        "flow_bytes_per_sec": 250000.0,
        "total_length_bwd_packets": 5000000.0,
    },
}

_EVENT_TO_ARCHETYPE: dict[str, str] = {
    "port_scan": "port_scan",
    "firewall_event": "port_scan",
    "brute_force": "web_brute_force",
    "auth_failure": "web_brute_force",
    "nginx_log": "web_brute_force",
    "apache_log": "web_brute_force",
    "sql_injection": "sql_injection",
    "xss": "sql_injection",
    "suspicious_request": "sql_injection",
}


def _load_medians() -> dict[str, float]:
    path = Path(settings.ML_MODEL_BUNDLE_DIR) / "preprocessing.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        raw = data.get("medians") or {}
        return {k: float(v) for k, v in raw.items() if k in CICIDS2017_FEATURES}
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return {}


def _jitter(base: float, rng: random.Random, spread: float = 0.35) -> float:
    if base <= 0:
        return abs(rng.uniform(0.001, max(0.01, spread)))
    factor = 1.0 + rng.uniform(-spread, spread)
    return max(0.0, base * factor)


def resolve_attack_topology() -> dict[str, Any]:
    """Resolve real-ish source/target addressing from env or local discovery."""
    source = os.environ.get("LBRO_ATTACK_SOURCE_IP", "").strip()
    if not source:
        try:
            import httpx

            source = httpx.get("https://api.ipify.org", timeout=4.0).text.strip()
        except Exception:
            try:
                probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                probe.connect(("8.8.8.8", 80))
                source = probe.getsockname()[0]
                probe.close()
            except Exception:
                source = "127.0.0.1"

    target = os.environ.get("LBRO_TARGET_IP", "").strip() or os.environ.get(
        "LBRO_TARGET_HOST", "127.0.0.1"
    ).strip()

    dealer_site = os.environ.get("LBRO_DEALER_SITE", "north-lot")
    application = os.environ.get("LBRO_APPLICATION_NAME", f"car-dealership-{dealer_site}")

    geo: dict[str, str] = {
        "country_code": os.environ.get("LBRO_GEO_COUNTRY", "IN").upper(),
        "country_name": os.environ.get("LBRO_GEO_COUNTRY_NAME", "India"),
    }
    if os.environ.get("LBRO_GEO_CITY"):
        geo["city"] = os.environ["LBRO_GEO_CITY"]
    if os.environ.get("LBRO_GEO_REGION"):
        geo["region"] = os.environ["LBRO_GEO_REGION"]

    hostname = os.environ.get("LBRO_ATTACK_HOSTNAME") or socket.gethostname()

    default_ua = (
        os.environ.get("LBRO_USER_AGENT")
        or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )

    return {
        "source_ip": source,
        "target_ip": target,
        "dealer_site": dealer_site,
        "application": application,
        "geo": geo,
        "user_agent": default_ua,
        "source_host": hostname,
    }


def build_flow_vector(
    archetype: str,
    *,
    seed: int | None = None,
) -> dict[str, float]:
    """Return a full 77-feature dict with realistic variance for the archetype."""
    rng = random.Random(seed)
    medians = _load_medians()
    shape = _ARCHETYPE_SHAPES.get(archetype, _ARCHETYPE_SHAPES["web_brute_force"])

    out: dict[str, float] = {}
    for name in CICIDS2017_FEATURES:
        if name in shape:
            out[name] = _jitter(shape[name], rng, spread=0.25)
        elif name in medians:
            out[name] = _jitter(medians[name], rng, spread=0.4)
        else:
            out[name] = rng.uniform(0.01, 2.0)

    # Avoid uniform vectors (OOD / capped confidence in classifier).
    out["destination_port"] = float(shape.get("destination_port", out.get("destination_port", 443)))
    return out


def build_dealership_scenario(
    event_type: str,
    *,
    seed: int | None = None,
    dealer_site: str = "north-lot",
) -> dict[str, Any]:
    """
    Build a complete event ``payload`` for POST /api/v1/events.

    Includes application context, HTTP excerpt metadata, and ``network_features``.
    """
    topo = resolve_attack_topology()
    archetype = _EVENT_TO_ARCHETYPE.get(event_type, "web_brute_force")
    flows = build_flow_vector(archetype, seed=seed)
    dst_port = int(flows.get("destination_port", 443))
    req_tag = seed if seed is not None else rng_id()
    src_port = 40000 + (req_tag % 20000)
    source_ip = topo["source_ip"]
    target_ip = topo["target_ip"]
    ua = topo["user_agent"]

    scenarios: dict[str, dict[str, Any]] = {
        "sql_injection": {
            "severity": "critical",
            "message": f"SQLi on inventory API from {source_ip} → {target_ip}",
            "http": {
                "method": "GET",
                "path": "/api/v1/inventory/search",
                "query_sample": "vin=1' UNION SELECT username,password FROM staff--",
                "status_code": 403,
                "user_agent": ua,
                "client_ip": source_ip,
                "request_id": f"req-{req_tag}",
            },
            "compliance": {
                "personal_data_involved": True,
                "affected_jurisdictions": [topo["geo"].get("country_code", "IN")],
            },
        },
        "brute_force": {
            "severity": "high",
            "message": f"Credential stuffing from {source_ip} against customer portal ({target_ip})",
            "http": {
                "method": "POST",
                "path": "/api/customer/login",
                "body_sample": '{"email":"***","password":"***"} x847',
                "status_code": 401,
                "user_agent": ua,
                "client_ip": source_ip,
                "request_id": f"req-{req_tag}",
            },
            "compliance": {
                "personal_data_involved": True,
                "affected_jurisdictions": [topo["geo"].get("country_code", "IN")],
            },
        },
        "port_scan": {
            "severity": "high",
            "message": f"SYN scan from {source_ip} targeting dealer VLAN host {target_ip}",
            "http": None,
        },
    }

    meta = scenarios.get(
        event_type,
        {
            "severity": "high",
            "message": f"{event_type.replace('_', ' ')} from {source_ip} → {target_ip}",
            "http": {
                "method": "GET",
                "path": "/api/finance/quote",
                "status_code": 429,
                "user_agent": ua,
                "client_ip": source_ip,
                "request_id": f"req-{req_tag}",
            },
        },
    )

    payload: dict[str, Any] = {
        "dealer_site": topo["dealer_site"],
        "service": topo["application"],
        "geo": topo["geo"],
        "network": {
            "destination_ip": target_ip,
            "source_port": src_port,
            "destination_port": dst_port,
            "protocol": "TCP",
        },
        "network_features": flows,
        "telemetry": {
            "sensor": "dealership-edge-ids",
            "capture_method": "netflow+vpc_flow_logs",
            "scenario_archetype": archetype,
            "attacker_ip": source_ip,
            "target_ip": target_ip,
        },
    }
    if meta.get("compliance"):
        payload["compliance"] = meta["compliance"]
    if meta.get("http"):
        payload["http"] = meta["http"]

    return {
        "event_type": event_type,
        "severity": meta["severity"],
        "source_ip": source_ip,
        "source_host": topo["source_host"],
        "source_application": topo["application"],
        "message": meta["message"],
        "payload": payload,
    }


def rng_id() -> int:
    return random.randint(100000, 999999)


def dealership_attack_sequence(*, base_seed: int = 42) -> list[dict[str, Any]]:
    """Ordered multi-stage attack chain for end-to-end demos."""
    topo = resolve_attack_topology()
    site = topo["dealer_site"]
    types = ["port_scan", "brute_force", "sql_injection", "suspicious_request"]
    return [
        build_dealership_scenario(t, seed=base_seed + i, dealer_site=site)
        for i, t in enumerate(types)
    ]
