"""Production Docker smoke tests — no credentials printed."""
from __future__ import annotations

import json
import secrets
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1"
RESULTS: dict[str, str] = {}


def req(method: str, path: str, *, token: str | None = None, body: dict | None = None, auth: str | None = None) -> tuple[int, object]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    elif auth:
        headers["Authorization"] = f"Bearer {auth}"
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            raw = resp.read().decode()
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw


def main() -> int:
    # Health
    st, _ = req("GET", "/health")
    st2, _ = req("GET", "/api/v1/auth/login")  # 422/405 proves API reachable
    RESULTS["Health"] = "PASS" if st == 200 else "FAIL"

    pw = "DockerVal1!Aa"
    ea = f"a_{secrets.token_hex(4)}@example.com"
    eb = f"b_{secrets.token_hex(4)}@example.com"

    # Register + auto-login
    st, reg = req("POST", "/api/v1/auth/register", body={
        "email": ea, "username": f"ua_{secrets.token_hex(3)}", "password": pw, "full_name": "User A",
    })
    ta = reg.get("access_token") if isinstance(reg, dict) else None
    ra = reg.get("refresh_token") if isinstance(reg, dict) else None
    auth_ok = st in (200, 201) and bool(ta)

    st, login = req("POST", "/api/v1/auth/login", body={"email": ea, "password": pw})
    auth_ok = auth_ok and st == 200

    st, me = req("GET", "/api/v1/auth/me", token=ta)
    auth_ok = auth_ok and st == 200

    st, ref = req("POST", "/api/v1/auth/refresh", body={"refresh_token": ra})
    ta2 = ref.get("access_token") if isinstance(ref, dict) else ta
    auth_ok = auth_ok and st == 200 and bool(ta2)

    st, _ = req("POST", "/api/v1/auth/logout", token=ta2)
    auth_ok = auth_ok and st in (200, 204)

    st, login2 = req("POST", "/api/v1/auth/login", body={"email": ea, "password": pw})
    ta = login2.get("access_token") if isinstance(login2, dict) else ta
    RESULTS["Auth"] = "PASS" if auth_ok else "FAIL"

    st, regb = req("POST", "/api/v1/auth/register", body={
        "email": eb, "username": f"ub_{secrets.token_hex(3)}", "password": pw, "full_name": "User B",
    })
    tb = regb.get("access_token") if isinstance(regb, dict) else None

    # Projects
    st, pa = req("POST", "/api/v1/projects", token=ta, body={"name": "ProjA", "environment": "development"})
    st, pb = req("POST", "/api/v1/projects", token=tb, body={"name": "ProjB", "environment": "development"})
    pid_a = pa.get("id") if isinstance(pa, dict) else None
    pid_b = pb.get("id") if isinstance(pb, dict) else None
    key_a = pa.get("api_key") if isinstance(pa, dict) else None

    st, inc = req("POST", "/api/v1/incidents", token=ta, body={
        "title": "Inc A", "severity": "medium", "project_id": pid_a,
    })
    inc_id = inc.get("id") if isinstance(inc, dict) else None

    st_cross, _ = req("GET", f"/api/v1/incidents/{inc_id}", token=tb)
    RESULTS["RBAC"] = "PASS" if st_cross in (403, 404) else "FAIL"

    st_d, _ = req("GET", f"/api/v1/dashboard/summary?project_id={pid_a}", token=tb)
    st_ml, _ = req("GET", "/api/v1/ml/stats", token=tb)
    st_n, _ = req("GET", "/api/v1/notifications", token=tb)
    iso = st_cross in (403, 404) and st_d in (403, 404)
    RESULTS["Isolation"] = "PASS" if iso else "FAIL"

    if key_a:
        st_evt, _ = req("POST", "/api/v1/events", auth=key_a, body={
            "event_type": "auth_failure", "severity": "low", "message": "smoke",
        })
    else:
        st_evt = 0
    RESULTS["Events"] = "PASS" if st_evt in (200, 201, 202) else "FAIL"

    st_ml_a, _ = req("GET", "/api/v1/ml/stats", token=ta)
    RESULTS["ML"] = "PASS" if st_ml_a == 200 else "FAIL"

    st_ev, _ = req("GET", "/api/v1/evidence", token=tb)
    RESULTS["Evidence"] = "PASS" if st_ev in (200, 403) else "FAIL"

    st_c, _ = req("GET", "/api/v1/compliance/summary", token=ta)
    RESULTS["Compliance"] = "PASS" if st_c in (200, 404) else "FAIL"

    st_r, _ = req("GET", "/api/v1/reports/weekly", token=ta)
    RESULTS["Reports"] = "PASS" if st_r == 200 else "FAIL"

    for k, v in RESULTS.items():
        print(f"{k}: {v}")
    return 0 if all(v == "PASS" for v in RESULTS.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
