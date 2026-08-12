"""Generate Python SDK example archives for project integration."""
from __future__ import annotations

import io
import zipfile


def build_python_sdk_zip(base_url: str, project_name: str) -> bytes:
    """Return a zip containing a minimal Python SDK (no real API key embedded)."""
    base_url = base_url.rstrip("/")
    readme = f"""# LBRO Python SDK — {project_name}

Connect your application to LBRO for security event monitoring.

## Setup

1. Copy `.env.example` to `.env`
2. Set `LBRO_API_KEY` to your project API key (shown once at generation)
3. Install dependencies: `pip install -r requirements.txt`
4. Run the example: `python example.py`

## API contract

- `POST {{base_url}}/api/v1/events` — single event (Bearer proj_* key)
- `POST {{base_url}}/api/v1/events/batch` — up to 1000 events

The project is resolved from the API key. Never send project_id in the body.
""".replace("{base_url}", base_url)

    requirements = "requests>=2.31.0\n"

    env_example = f"""LBRO_BASE_URL={base_url}
LBRO_API_KEY=YOUR_PROJECT_API_KEY
"""

    client_py = '''"""Minimal LBRO HTTP client for security event ingestion."""
from __future__ import annotations

import os
from typing import Any

import requests


class LBROClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = (base_url or os.environ["LBRO_BASE_URL"]).rstrip("/")
        self.api_key = api_key or os.environ["LBRO_API_KEY"]
        self.timeout = timeout
        if not self.api_key or self.api_key == "YOUR_PROJECT_API_KEY":
            raise ValueError("Set LBRO_API_KEY to your project API key")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def send_event(
        self,
        event_type: str,
        severity: str = "medium",
        message: str | None = None,
        source_ip: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """POST /api/v1/events — project resolved from API key."""
        body: dict[str, Any] = {
            "event_type": event_type,
            "severity": severity,
        }
        if message is not None:
            body["message"] = message
        if source_ip is not None:
            body["source_ip"] = source_ip
        if payload:
            body["payload"] = payload
        resp = requests.post(
            f"{self.base_url}/api/v1/events",
            json=body,
            headers=self._headers(),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def send_events_batch(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        """POST /api/v1/events/batch"""
        resp = requests.post(
            f"{self.base_url}/api/v1/events/batch",
            json={"events": events},
            headers=self._headers(),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()
'''

    example_py = '''"""Send a sample security event to LBRO."""
from lbro_client import LBROClient


def main() -> None:
    client = LBROClient()
    result = client.send_event(
        event_type="auth_failure",
        severity="high",
        message="Failed login attempt from unknown IP",
        source_ip="203.0.113.42",
        payload={"username": "admin", "attempts": 3},
    )
    print("Event accepted:", result.get("id"), result.get("processing_status"))


if __name__ == "__main__":
    main()
'''

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        prefix = "lbro-sdk/"
        zf.writestr(f"{prefix}README.md", readme)
        zf.writestr(f"{prefix}requirements.txt", requirements)
        zf.writestr(f"{prefix}.env.example", env_example)
        zf.writestr(f"{prefix}lbro_client.py", client_py)
        zf.writestr(f"{prefix}example.py", example_py)
    return buf.getvalue()
