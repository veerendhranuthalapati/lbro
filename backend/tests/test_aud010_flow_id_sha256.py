"""AUD-010: ML demo flow export uses SHA-256 fingerprint, not MD5."""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_ml_flow_id_is_sha256_prefix(client: AsyncClient, auth_headers: dict, db):
    from app.models.incident import Incident

    iid = uuid.uuid4()
    inc = Incident(
        id=iid,
        title="Flow ID Audit",
        status="new",
        severity="high",
        attack_category="DDoS",
        confidence_score=0.91,
        detected_at=datetime.now(timezone.utc),
        network_features={"total_fwd_packets": 10},
    )
    db.add(inc)
    await db.commit()
    expected = hashlib.sha256(str(iid).encode()).hexdigest()[:12]

    flows = await client.get("/api/v1/ml/flows", params={"limit": 20}, headers=auth_headers)
    assert flows.status_code == 200
    items = flows.json()
    assert isinstance(items, list)
    match = [f for f in items if f.get("flow_id") == expected]
    assert match, f"expected flow_id {expected} in /ml/flows"


def test_aud010_ml_router_source_uses_sha256_not_md5():
    from pathlib import Path

    text = Path(__file__).resolve().parents[1].joinpath("app/routers/ml.py").read_text(encoding="utf-8")
    assert "hashlib.md5" not in text
    assert "hashlib.sha256" in text
