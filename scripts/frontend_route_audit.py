"""Frontend release audit — SPA routes + API endpoints used by pages."""
from __future__ import annotations

import json
import secrets
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1"
FAILURES: list[str] = []
PASSES: list[str] = []


def req(method: str, path: str, *, token: str | None = None, body: dict | None = None) -> tuple[int, object]:
    headers: dict[str, str] = {}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            raw = resp.read().decode(errors="replace")
            ct = resp.headers.get("Content-Type", "")
            if "json" in ct:
                try:
                    return resp.status, json.loads(raw)
                except json.JSONDecodeError:
                    return resp.status, raw
            return resp.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw


def check(name: str, ok: bool, detail: str = "") -> None:
    line = f"{name}: {'PASS' if ok else 'FAIL'}" + (f" — {detail}" if detail else "")
    (PASSES if ok else FAILURES).append(line)
    print(line)


def spa_route(path: str) -> bool:
    st, body = req("GET", path)
    if st != 200:
        return False
    return isinstance(body, str) and ("<div id=\"root\"" in body or "<!DOCTYPE html" in body)


def main() -> int:
    pw = "AuditTest1!Aa"
    email = f"audit_{secrets.token_hex(4)}@example.com"

    # ── SPA routes (public) ──
    for route in ["/login", "/register", "/forgot-password"]:
        check(f"SPA {route}", spa_route(route))

    # ── Auth flow ──
    st, reg = req("POST", "/api/v1/auth/register", body={
        "email": email,
        "username": f"u_{secrets.token_hex(3)}",
        "password": pw,
        "full_name": "Audit User",
    })
    token = reg.get("access_token") if isinstance(reg, dict) else None
    check("Registration + auto-login token", st in (200, 201) and bool(token), f"status={st}")

    st, login = req("POST", "/api/v1/auth/login", body={"email": email, "password": pw})
    if not token and isinstance(login, dict):
        token = login.get("access_token")
    check("Login", st == 200 and bool(token), f"status={st}")

    st, me = req("GET", "/api/v1/auth/me", token=token)
    user_id = me.get("id") if isinstance(me, dict) else None
    check("Auth /me", st == 200 and bool(user_id), f"status={st}")

    # ── Project ──
    st, proj = req("POST", "/api/v1/projects", token=token, body={
        "name": "Audit Project", "environment": "development",
    })
    pid = proj.get("id") if isinstance(proj, dict) else None
    check("Create project", st in (200, 201) and bool(pid), f"status={st}")

    # ── SPA routes (authenticated shell — nginx serves index.html) ──
    app_routes = [
        "/dashboard", "/incidents", "/evidence", "/notifications", "/settings",
        "/privacy", "/security-overview", "/security-score", "/weekly-report",
        "/compliance", "/compliance/audit", "/infrastructure", "/threat-intel",
        "/ml-insights", "/audit-logs", "/users", "/docs", "/projects",
        f"/projects/{pid}/integrations", f"/projects/{pid}/events",
        f"/projects/{pid}/settings", f"/projects/{pid}",
    ]
    for route in app_routes:
        check(f"SPA {route}", spa_route(route))

    # ── API endpoints used by frontend pages ──
    api_checks = [
        ("GET", f"/api/v1/dashboard/summary?project_id={pid}"),
        ("GET", f"/api/v1/security-score?project_id={pid}"),
        ("GET", f"/api/v1/reports/weekly?project_id={pid}"),
        ("GET", f"/api/v1/incidents?project_id={pid}"),
        ("GET", f"/api/v1/incidents/stats?project_id={pid}"),
        ("GET", f"/api/v1/evidence?project_id={pid}"),
        ("GET", f"/api/v1/compliance/summary?project_id={pid}"),
        ("GET", f"/api/v1/compliance/obligations?project_id={pid}"),
        ("GET", f"/api/v1/ml/stats?project_id={pid}"),
        ("GET", f"/api/v1/ml/metrics?project_id={pid}"),
        ("GET", f"/api/v1/ml/flows?project_id={pid}"),
        ("GET", f"/api/v1/notifications"),
        ("GET", f"/api/v1/projects"),
        ("GET", f"/api/v1/projects/{pid}"),
        ("GET", f"/api/v1/infrastructure?project_id={pid}"),
        ("GET", f"/api/v1/audit-logs"),
        ("GET", f"/api/v1/users"),
    ]
    for method, path in api_checks:
        st, _ = req(method, path, token=token)
        check(f"API {method} {path.split('?')[0]}", st < 400, f"status={st}")

    # ── Create incident for detail page API ──
    st, inc = req("POST", "/api/v1/incidents", token=token, body={
        "title": "Audit incident", "severity": "low", "project_id": pid,
    })
    inc_id = inc.get("id") if isinstance(inc, dict) else None
    if inc_id:
        st, _ = req("GET", f"/api/v1/incidents/{inc_id}", token=token)
        check(f"API GET /api/v1/incidents/{inc_id}", st == 200, f"status={st}")

    # ── Logout ──
    st, _ = req("POST", "/api/v1/auth/logout", token=token)
    check("Logout", st in (200, 204), f"status={st}")

    # ── Redirect routes ──
    st_score, _ = req("GET", "/security-score")
    st_report, _ = req("GET", "/weekly-report")
    check("Legacy /security-score serves SPA", st_score == 200)
    check("Legacy /weekly-report serves SPA", st_report == 200)

    print("\n=== SUMMARY ===")
    print(f"Passed: {len(PASSES)}")
    print(f"Failed: {len(FAILURES)}")
    if FAILURES:
        print("\nFailures:")
        for f in FAILURES:
            print(f"  {f}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
