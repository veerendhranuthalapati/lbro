"""Attack guide coverage and API tests."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.knowledge.loader import load_attack_guides
from app.ml.features import ATTACK_CLASSES


def test_every_attack_class_has_guide():
    bundle = load_attack_guides()
    assert set(bundle.guides.keys()) == set(ATTACK_CLASSES)


@pytest.mark.asyncio
async def test_list_attack_guides_auth(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/knowledge/attacks", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == len(ATTACK_CLASSES)
    assert "disclaimer" in data


@pytest.mark.asyncio
async def test_get_attack_guide_404(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/knowledge/attacks/NotARealClass", headers=auth_headers)
    assert resp.status_code == 404
