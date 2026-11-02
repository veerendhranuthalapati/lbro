"""Readiness endpoint tests."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_readiness_includes_database(client: AsyncClient):
    resp = await client.get("/health/ready")
    data = resp.json()
    assert "checks" in data
    assert data["checks"]["database"] == "ok"
    assert resp.status_code in (200, 503)
