"""LBRO Python SDK.

Lightweight SDK for sending security events to LBRO from Python applications.

Usage:
    from lbro_sdk import LBROClient, SecurityEvent

    client = LBROClient(
        api_key="proj_your_project_api_key",
        base_url="https://your-lbro-instance.example.com",
    )

    client.send_event(
        event_type="auth_failure",
        severity="high",
        source_ip="203.0.113.42",
        message="Failed SSH login attempt",
        payload={"username": "root", "attempts": 5},
    )

    # Batch send
    events = [
        SecurityEvent(event_type="sql_injection", severity="critical",
                      source_ip="192.0.2.1", message="SQL injection in /api/users"),
        SecurityEvent(event_type="xss", severity="medium",
                      source_ip="192.0.2.2", message="XSS in search field"),
    ]
    client.send_events(events)
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request as URLRequest, urlopen

__version__ = "1.0.0"
__all__ = ["LBROClient", "SecurityEvent", "LBROError", "LBROAuthError", "LBROValidationError"]

log = logging.getLogger("lbro_sdk")

# Allowed event types
EVENT_TYPES = {
    "auth_failure", "sql_injection", "xss", "brute_force", "port_scan",
    "suspicious_request", "system_log", "application_log", "nginx_log",
    "apache_log", "firewall_event", "windows_event", "linux_audit", "custom",
}
SEVERITIES = {"critical", "high", "medium", "low", "info"}


class LBROError(Exception):
    """Base LBRO SDK error."""


class LBROAuthError(LBROError):
    """Invalid or expired project API key."""


class LBROValidationError(LBROError):
    """Event validation failed (bad event_type, severity, etc.)."""


@dataclass
class SecurityEvent:
    """A security event to be sent to LBRO.

    Args:
        event_type: One of the allowed event type strings.
        severity: critical / high / medium / low / info.
        source_ip: IP address of the event source.
        source_host: Hostname of the source machine.
        source_application: Application name that generated this event.
        message: Human-readable description of the event.
        event_timestamp: When the event occurred (UTC). Defaults to now.
        payload: Arbitrary JSON-serialisable key-value pairs.
    """
    event_type: str
    severity: str = "medium"
    source_ip: str | None = None
    source_host: str | None = None
    source_application: str | None = None
    message: str | None = None
    event_timestamp: str | None = None  # ISO 8601 UTC
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.event_type not in EVENT_TYPES:
            raise LBROValidationError(
                f"Unknown event_type '{self.event_type}'. Allowed: {sorted(EVENT_TYPES)}"
            )
        if self.severity not in SEVERITIES:
            raise LBROValidationError(
                f"Unknown severity '{self.severity}'. Allowed: {sorted(SEVERITIES)}"
            )
        if self.event_timestamp is None:
            self.event_timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}


class LBROClient:
    """LBRO event ingestion client.

    Args:
        api_key: Project API key (format: proj_<random>).
        base_url: Base URL of your LBRO instance (no trailing slash).
        timeout: HTTP request timeout in seconds. Default: 10.
        max_retries: Number of retries on transient errors. Default: 3.
        retry_delay: Base delay between retries in seconds. Default: 1.
        source_application: Default application name for all events.
        verify_ssl: Whether to verify SSL certificates. Default: True.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "http://localhost:8000",
        timeout: float = 10.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        source_application: str | None = None,
        verify_ssl: bool = True,
    ) -> None:
        if not api_key.startswith("proj_"):
            raise LBROAuthError("LBRO project API keys must start with 'proj_'")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._source_application = source_application
        self._verify_ssl = verify_ssl

    # ── Public methods ──────────────────────────────────────────────────────

    def send_event(
        self,
        event_type: str,
        severity: str = "medium",
        source_ip: str | None = None,
        source_host: str | None = None,
        message: str | None = None,
        payload: dict[str, Any] | None = None,
        event_timestamp: str | None = None,
    ) -> dict:
        """Send a single security event. Returns the LBRO response dict."""
        event = SecurityEvent(
            event_type=event_type,
            severity=severity,
            source_ip=source_ip,
            source_host=source_host,
            source_application=self._source_application,
            message=message,
            event_timestamp=event_timestamp,
            payload=payload or {},
        )
        return self._post("/api/v1/events", event.to_dict())

    def send_events(self, events: list[SecurityEvent]) -> dict:
        """Send a batch of events. Returns summary with accepted/rejected counts."""
        if not events:
            return {"accepted": 0, "rejected": 0, "events": [], "errors": []}
        if len(events) > 1000:
            raise LBROValidationError("Batch size cannot exceed 1000 events")

        # Inject source_application default if not set per event
        dicts = []
        for e in events:
            d = e.to_dict()
            if "source_application" not in d and self._source_application:
                d["source_application"] = self._source_application
            dicts.append(d)

        return self._post("/api/v1/events/batch", {"events": dicts})

    def ping(self) -> bool:
        """Check connectivity to LBRO. Returns True if reachable."""
        try:
            self._get("/health")
            return True
        except Exception:
            return False

    # ── Internal HTTP helpers ───────────────────────────────────────────────

    def _post(self, path: str, body: dict) -> dict:
        return self._request("POST", path, body)

    def _get(self, path: str) -> dict:
        return self._request("GET", path)

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        url = self._base_url + path
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"lbro-python-sdk/{__version__}",
        }

        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                req = URLRequest(url, data=data, headers=headers, method=method)
                with urlopen(req, timeout=self._timeout) as resp:
                    body_bytes = resp.read()
                    return json.loads(body_bytes) if body_bytes else {}

            except HTTPError as exc:
                status = exc.code
                body_text = exc.read().decode("utf-8", errors="replace")
                if status == 401:
                    raise LBROAuthError(f"Invalid project API key: {body_text}") from exc
                if status == 422:
                    raise LBROValidationError(f"Validation error: {body_text}") from exc
                if status >= 500:
                    last_exc = exc
                    if attempt < self._max_retries:
                        delay = self._retry_delay * (2 ** attempt)
                        log.warning("LBRO request failed (HTTP %s), retrying in %.1fs", status, delay)
                        time.sleep(delay)
                        continue
                raise LBROError(f"HTTP {status}: {body_text}") from exc

            except (URLError, OSError) as exc:
                last_exc = exc
                if attempt < self._max_retries:
                    delay = self._retry_delay * (2 ** attempt)
                    log.warning("LBRO network error: %s — retrying in %.1fs", exc, delay)
                    time.sleep(delay)
                    continue

        raise LBROError(f"Request failed after {self._max_retries} retries: {last_exc}") from last_exc
