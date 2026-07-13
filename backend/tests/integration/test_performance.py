"""
Performance test suite — LBRO
Covers: bulk incident creation (100 items), paginated listing, response time bounds.
"""
from __future__ import annotations

import time

import pytest
from httpx import AsyncClient


class TestBulkOperations:
    async def test_create_100_incidents_all_succeed(
        self, client: AsyncClient, alice_h: dict, portfolio_project: dict
    ):
        created_ids = []
        for i in range(100):
            resp = await client.post("/api/v1/incidents", json={
                "title": f"Bulk Incident {i + 1:03d} — Automated Scan Result",
                "severity": ["critical", "high", "medium", "low", "info"][i % 5],
                "attack_category": ["malware", "phishing", "injection", "reconnaissance", "dos"][i % 5],
                "project_id": portfolio_project["id"],
            }, headers=alice_h)
            assert resp.status_code == 201, f"Incident {i} failed: {resp.text}"
            created_ids.append(resp.json()["id"])

        assert len(created_ids) == 100

    async def test_paginated_listing_returns_correct_pages(
        self, client: AsyncClient, alice_h: dict, portfolio_project: dict
    ):
        # Create 30 incidents
        for i in range(30):
            await client.post("/api/v1/incidents", json={
                "title": f"Page Test Incident {i + 1:03d}",
                "severity": "medium",
                "project_id": portfolio_project["id"],
            }, headers=alice_h)

        # Page 1
        r1 = await client.get(
            "/api/v1/incidents",
            params={"project_id": portfolio_project["id"], "page": 1, "page_size": 10},
            headers=alice_h,
        )
        assert r1.status_code == 200
        body1 = r1.json()
        assert len(body1["items"]) == 10
        assert body1["total"] >= 30

        # Page 2
        r2 = await client.get(
            "/api/v1/incidents",
            params={"project_id": portfolio_project["id"], "page": 2, "page_size": 10},
            headers=alice_h,
        )
        assert r2.status_code == 200
        body2 = r2.json()
        assert len(body2["items"]) == 10

        # Pages must not overlap
        ids1 = {i["id"] for i in body1["items"]}
        ids2 = {i["id"] for i in body2["items"]}
        assert ids1.isdisjoint(ids2)

    async def test_list_100_incidents_completes_within_10_seconds(
        self, client: AsyncClient, alice_h: dict, portfolio_project: dict
    ):
        # Create 100 incidents
        for i in range(100):
            await client.post("/api/v1/incidents", json={
                "title": f"Perf Incident {i + 1:03d}",
                "severity": "low",
                "project_id": portfolio_project["id"],
            }, headers=alice_h)

        start = time.monotonic()
        resp = await client.get(
            "/api/v1/incidents",
            params={"project_id": portfolio_project["id"], "page_size": 100},
            headers=alice_h,
        )
        elapsed = time.monotonic() - start

        assert resp.status_code == 200
        assert resp.json()["total"] >= 100
        assert elapsed < 10.0, f"Listing 100 incidents took {elapsed:.2f}s (limit: 10s)"

    async def test_page_size_max_100_enforced(
        self, client: AsyncClient, alice_h: dict
    ):
        resp = await client.get(
            "/api/v1/incidents",
            params={"page_size": 101},  # exceeds max of 100
            headers=alice_h,
        )
        assert resp.status_code == 422

    async def test_page_size_zero_rejected(self, client: AsyncClient, alice_h: dict):
        resp = await client.get(
            "/api/v1/incidents",
            params={"page_size": 0},  # below min of 1
            headers=alice_h,
        )
        assert resp.status_code == 422

    async def test_incident_stats_returns_fast(
        self, client: AsyncClient, alice_h: dict, portfolio_project: dict
    ):
        # Seed some incidents
        for i in range(10):
            await client.post("/api/v1/incidents", json={
                "title": f"Stats Test Incident {i + 1}",
                "severity": "high",
                "project_id": portfolio_project["id"],
            }, headers=alice_h)

        start = time.monotonic()
        resp = await client.get(
            "/api/v1/incidents/stats",
            params={"project_id": portfolio_project["id"]},
            headers=alice_h,
        )
        elapsed = time.monotonic() - start

        assert resp.status_code == 200
        assert elapsed < 5.0, f"Stats endpoint took {elapsed:.2f}s"
