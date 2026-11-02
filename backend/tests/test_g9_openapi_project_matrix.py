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
MUTATING = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def project_scoped_operations() -> list[tuple[str, str]]:
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
    if method in MUTATING:
        kwargs["json"] = {}
    req = client.build_request(method, path, **kwargs)
    resp = await client.send(req)
    return resp.status_code


@pytest.mark.asyncio
async def test_g9_openapi_project_scoped_operation_count(capsys):
    ops = project_scoped_operations()
    print(f"G9_OPENAPI_PROJECT_SCOPED_OPS={len(ops)}")
    assert len(ops) >= 1


@pytest.mark.asyncio
async def test_g9_two_projects_four_roles_openapi_matrix(
    client: AsyncClient,
    owner_a_h: dict,
    viewer_a_h: dict,
    owner_b_h: dict,
    viewer_b_h: dict,
    super_admin_h: dict,
    auth_headers: dict,
    project_a: dict,
    project_b: dict,
):
    """Cross-project: all OpenAPI project-scoped operations."""
    cross_cases = [
        ("owner_b", owner_b_h, "project_a", project_a["id"]),
        ("viewer_b", viewer_b_h, "project_a", project_a["id"]),
        ("owner_a", owner_a_h, "project_b", project_b["id"]),
        ("viewer_a", viewer_a_h, "project_b", project_b["id"]),
    ]
    ops = project_scoped_operations()
    matrix: list[dict] = []
    violations: list[str] = []

    for actor_name, headers, target_label, pid in cross_cases:
        for method, path_template in ops:
            path = path_template.replace("{project_id}", pid)
            status = await _send(client, method, path, headers)
            matrix.append(
                {
                    "kind": "cross_tenant",
                    "actor": actor_name,
                    "target_project": target_label,
                    "method": method,
                    "path": path,
                    "status": status,
                }
            )
            if status in FORBIDDEN_CROSS_STATUSES:
                violations.append(f"{actor_name} -> {method} {path} -> {status}")

    cross_rows = len(matrix)
    cross_coverage = cross_rows / (len(ops) * len(cross_cases)) if ops else 0.0

    mutating_ops = [o for o in ops if o[0] in MUTATING]
    role_matrix: list[dict] = []

    async def _record_role(actor: str, headers: dict) -> None:
        for method, path_template in mutating_ops:
            path = path_template.replace("{project_id}", project_a["id"])
            status = await _send(client, method, path, headers)
            role_matrix.append({"actor": actor, "method": method, "path": path, "status": status})

    await _record_role("viewer", viewer_a_h)
    for method, path_template in mutating_ops:
        path = path_template.replace("{project_id}", project_a["id"])
        st_viewer = next(r["status"] for r in role_matrix if r["actor"] == "viewer" and r["path"] == path)
        assert st_viewer in (403, 404, 405, 422), f"viewer must not mutate: {method} {path} -> {st_viewer}"

    await _record_role("project_admin_analyst", owner_a_h)
    await _record_role("platform_admin", auth_headers)
    await _record_role("super_admin", super_admin_h)

    SCRATCH_MATRIX.parent.mkdir(parents=True, exist_ok=True)
    SCRATCH_MATRIX.write_text(
        json.dumps(
            {
                "operations_count": len(ops),
                "mutating_operations_count": len(mutating_ops),
                "cross_tenant_rows": cross_rows,
                "cross_tenant_coverage_ratio": cross_coverage,
                "in_project_role_rows": len(role_matrix),
                "rows": matrix,
                "role_matrix": role_matrix,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    assert cross_coverage == 1.0
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
