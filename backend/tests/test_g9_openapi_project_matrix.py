"""G9: OpenAPI-derived project-scoped route cross-tenant matrix (evidence artifact)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.main import app

pytest_plugins = ["tests.test_red_team_authorization"]

SCRATCH_MATRIX = (
    Path(__file__).resolve().parents[2].parent / "lbro-run-scratch" / "g9_openapi_matrix.json"
)

FORBIDDEN_CROSS_STATUSES = {200, 201, 204}


def _project_scoped_operations() -> list[tuple[str, str]]:
    spec = app.openapi()
    ops: list[tuple[str, str]] = []
    skip_methods = {"options", "parameters"}
    for path, methods in spec.get("paths", {}).items():
        if "{project_id}" not in path:
            continue
        if "/platform/" in path:
            continue
        for method, detail in methods.items():
            if method in skip_methods:
                continue
            if detail.get("security"):
                ops.append((method.upper(), path))
    return sorted(set(ops))


async def _send(client: AsyncClient, method: str, path: str, headers: dict) -> int:
    kwargs: dict = {"headers": headers}
    if method in ("POST", "PUT", "PATCH"):
        kwargs["json"] = {}
    req = client.build_request(method, path, **kwargs)
    resp = await client.send(req)
    return resp.status_code


@pytest.mark.asyncio
async def test_g9_two_projects_four_roles_openapi_matrix(
    client: AsyncClient,
    owner_a_h: dict,
    viewer_a_h: dict,
    owner_b_h: dict,
    viewer_b_h: dict,
    project_a: dict,
    project_b: dict,
):
    """2 projects × 4 actors: cross-project OpenAPI paths must not succeed."""
    cross_cases = [
        ("owner_b", owner_b_h, "project_a", project_a["id"]),
        ("viewer_b", viewer_b_h, "project_a", project_a["id"]),
        ("owner_a", owner_a_h, "project_b", project_b["id"]),
        ("viewer_a", viewer_a_h, "project_b", project_b["id"]),
    ]
    ops = _project_scoped_operations()
    matrix: list[dict] = []
    violations: list[str] = []

    for actor_name, headers, target_label, pid in cross_cases:
        for method, path_template in ops:
            path = path_template.replace("{project_id}", pid)
            status = await _send(client, method, path, headers)
            matrix.append(
                {
                    "actor": actor_name,
                    "target_project": target_label,
                    "method": method,
                    "path": path,
                    "status": status,
                }
            )
            if status in FORBIDDEN_CROSS_STATUSES:
                violations.append(f"{actor_name} -> {method} {path} -> {status}")

    SCRATCH_MATRIX.parent.mkdir(parents=True, exist_ok=True)
    SCRATCH_MATRIX.write_text(
        json.dumps(
            {
                "operations_count": len(ops),
                "cross_cases": len(cross_cases),
                "rows": matrix,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    assert not violations, "Cross-project IDOR:\n" + "\n".join(violations[:40])


@pytest.mark.asyncio
async def test_g9_owner_a_can_read_own_project(
    client: AsyncClient,
    owner_a_h: dict,
    project_a: dict,
):
    r = await client.get(f"/api/v1/projects/{project_a['id']}", headers=owner_a_h)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_g9_viewer_cannot_regenerate_foreign_project_key(
    client: AsyncClient,
    viewer_a_h: dict,
    project_b: dict,
):
    r = await client.post(
        f"/api/v1/projects/{project_b['id']}/regenerate-key",
        headers=viewer_a_h,
    )
    assert r.status_code in (403, 404)
