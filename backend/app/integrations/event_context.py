"""Extract network and application context from ingested event payloads."""
from __future__ import annotations

from typing import Any

from app.ml.event_mapper import extract_network_features


def _dig(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    for nest in ("network", "endpoint", "flow", "tcp"):
        block = payload.get(nest)
        if isinstance(block, dict):
            for key in keys:
                if key in block and block[key] is not None:
                    return block[key]
    return None


def extract_endpoint_context(payload: dict[str, Any] | None) -> dict[str, Any]:
    """
    Map integration payload shapes to incident network columns.

    Accepts top-level keys or nested ``network`` / ``endpoint`` objects.
    """
    payload = payload or {}
    ctx: dict[str, Any] = {}

    dest_ip = _dig(payload, "destination_ip", "dest_ip", "dst_ip")
    if dest_ip is not None:
        ctx["destination_ip"] = str(dest_ip)

    src_port = _dig(payload, "source_port", "src_port")
    if src_port is not None:
        try:
            ctx["source_port"] = int(src_port)
        except (TypeError, ValueError):
            pass

    dst_port = _dig(payload, "destination_port", "dest_port", "dst_port", "dport")
    if dst_port is not None:
        try:
            ctx["destination_port"] = int(dst_port)
        except (TypeError, ValueError):
            pass

    protocol = _dig(payload, "protocol", "proto")
    if protocol is not None:
        ctx["protocol"] = str(protocol).upper()

    features = extract_network_features(payload)
    if features.get("destination_port") and "destination_port" not in ctx:
        ctx["destination_port"] = int(features["destination_port"])

    if features:
        ctx["network_features"] = features

    return ctx


def build_http_log_excerpt(payload: dict[str, Any] | None) -> str | None:
    """Render a realistic HTTP log snippet when the client sends ``http`` metadata."""
    payload = payload or {}
    http = payload.get("http")
    if not isinstance(http, dict):
        return None

    lines = []
    method = http.get("method", "GET")
    path = http.get("path", "/")
    status = http.get("status_code", http.get("status", "-"))
    ua = http.get("user_agent", "-")
    req_id = http.get("request_id", "-")
    body_sample = http.get("body_sample") or http.get("query_sample") or ""

    lines.append(
        f'{http.get("timestamp", "-")} {http.get("client_ip", "-")} '
        f'"{method} {path} HTTP/1.1" {status} {http.get("bytes", "-")} '
        f'"{ua}" req_id={req_id}'
    )
    if body_sample:
        lines.append(f"  payload_sample: {body_sample[:2000]}")
    if http.get("headers"):
        for k, v in list(http["headers"].items())[:12]:
            lines.append(f"  {k}: {v}")

    return "\n".join(lines) if lines else None


_EVENT_THREAT_HINTS: dict[str, dict[str, Any]] = {
    "brute_force": {
        "mitre_techniques": ["T1110.001"],
        "owasp_category": "A07:2021 – Identification and Authentication Failures",
    },
    "auth_failure": {
        "mitre_techniques": ["T1110"],
        "owasp_category": "A07:2021 – Identification and Authentication Failures",
    },
    "sql_injection": {
        "mitre_techniques": ["T1190", "T1059.007"],
        "owasp_category": "A03:2021 – Injection",
    },
    "xss": {
        "mitre_techniques": ["T1189"],
        "owasp_category": "A03:2021 – Injection",
    },
    "port_scan": {
        "mitre_techniques": ["T1046"],
        "owasp_category": "A05:2021 – Security Misconfiguration",
    },
    "suspicious_request": {
        "mitre_techniques": ["T1071.001"],
        "owasp_category": "A04:2021 – Insecure Design",
    },
}


def extract_integration_context(
    payload: dict[str, Any] | None,
    *,
    event_type: str = "",
    source_ip: str | None = None,
    source_application: str | None = None,
    source_host: str | None = None,
) -> dict[str, Any]:
    """Build UI-facing integration metadata stored on the incident."""
    payload = payload or {}
    ctx: dict[str, Any] = {}

    http = payload.get("http") if isinstance(payload.get("http"), dict) else {}
    geo = payload.get("geo") if isinstance(payload.get("geo"), dict) else {}
    threat = payload.get("threat_intel") if isinstance(payload.get("threat_intel"), dict) else {}
    compliance = payload.get("compliance") if isinstance(payload.get("compliance"), dict) else {}

    ua = http.get("user_agent") or payload.get("user_agent")
    if ua:
        ctx["user_agent"] = str(ua)[:2000]

    app = source_application or payload.get("service") or payload.get("application")
    if app:
        ctx["application"] = str(app)[:255]

    country = geo.get("country_code") or geo.get("country") or payload.get("country")
    if country:
        ctx["country"] = str(country).upper()[:8]
    if geo.get("country_name"):
        ctx["country_name"] = str(geo["country_name"])[:120]
    if geo.get("city"):
        ctx["city"] = str(geo["city"])[:120]
    if geo.get("region"):
        ctx["region"] = str(geo["region"])[:120]

    if source_host:
        ctx["source_host"] = source_host
    if source_ip:
        ctx["source_ip_reported"] = source_ip

    hints = _EVENT_THREAT_HINTS.get(event_type, {})
    ctx["mitre_techniques"] = threat.get("mitre_techniques") or hints.get("mitre_techniques") or []
    ctx["owasp_category"] = threat.get("owasp_category") or hints.get("owasp_category")

    if compliance:
        ctx["compliance"] = compliance

    ctx["dealer_site"] = payload.get("dealer_site")
    ctx["security_event_payload_keys"] = sorted(payload.keys())[:40]

    return ctx


def compliance_from_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Extract incident compliance columns from integration payload."""
    payload = payload or {}
    block = payload.get("compliance") if isinstance(payload.get("compliance"), dict) else {}
    out: dict[str, Any] = {}
    if "personal_data_involved" in block:
        out["personal_data_involved"] = bool(block["personal_data_involved"])
    if "health_data_involved" in block:
        out["health_data_involved"] = bool(block["health_data_involved"])
    jurisdictions = block.get("affected_jurisdictions")
    if isinstance(jurisdictions, list) and jurisdictions:
        out["affected_jurisdictions"] = [str(j) for j in jurisdictions]
    return out
