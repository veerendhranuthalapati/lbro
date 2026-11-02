"""Timing-safe login paths and event-loop responsiveness during bcrypt."""
from __future__ import annotations

import asyncio
import statistics
import time

import pytest
from httpx import AsyncClient


def _median_ms(samples: list[float]) -> float:
    return statistics.median(samples) * 1000.0


def _p95_ms(samples: list[float]) -> float:
    if len(samples) < 2:
        return samples[0] * 1000.0
    ranked = sorted(samples)
    idx = min(len(ranked) - 1, int(round(0.95 * (len(ranked) - 1))))
    return ranked[idx] * 1000.0


@pytest.mark.asyncio
async def test_unknown_user_login_timing_similar_to_wrong_password(
    client: AsyncClient, admin_user, db,  # noqa: ARG001
):
    """Both paths run bcrypt (dummy hash vs real hash) — medians must stay close."""
    n = 6
    unknown_samples: list[float] = []
    wrong_pw_samples: list[float] = []

    for i in range(n):
        t0 = time.perf_counter()
        r = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@lbro-test.com", "password": "WrongPass999!"},
        )
        unknown_samples.append(time.perf_counter() - t0)
        assert r.status_code == 401

        # Reset lockout counter so repeated wrong passwords stay on the 401 path.
        admin_user.failed_login_attempts = 0
        admin_user.locked_until = None
        await db.flush()

        t0 = time.perf_counter()
        r = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@lbro-test.com", "password": "WrongPass999!"},
        )
        wrong_pw_samples.append(time.perf_counter() - t0)
        assert r.status_code == 401

    diff_ms = abs(_median_ms(unknown_samples) - _median_ms(wrong_pw_samples))
    assert diff_ms < 250.0, (
        f"median timing delta {diff_ms:.1f}ms "
        f"(unknown median {_median_ms(unknown_samples):.1f}ms, "
        f"wrong-pw median {_median_ms(wrong_pw_samples):.1f}ms)"
    )


@pytest.mark.asyncio
async def test_health_stays_fast_during_concurrent_logins(client: AsyncClient, admin_user):  # noqa: ARG001
    """bcrypt runs in a thread pool — cheap endpoints should not stall for seconds."""
    concurrent = 5

    async def login_once() -> None:
        await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@lbro-test.com", "password": "TestPass123!"},
        )

    async def health_probe() -> float:
        t0 = time.perf_counter()
        r = await client.get("/health")
        assert r.status_code == 200
        return time.perf_counter() - t0

    login_tasks = [asyncio.create_task(login_once()) for _ in range(concurrent)]
    health_samples: list[float] = []
    for _ in range(8):
        health_samples.append(await health_probe())
        await asyncio.sleep(0.02)
    await asyncio.gather(*login_tasks)

    p95 = _p95_ms(health_samples)
    assert p95 < 800.0, f"/health p95 during logins was {p95:.1f}ms"
