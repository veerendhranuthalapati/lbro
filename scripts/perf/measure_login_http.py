#!/usr/bin/env python3
"""HTTP login latency benchmark (median + p95). Run against a live API (e.g. docker compose)."""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request


def percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = min(len(sorted_vals) - 1, int(round(p * (len(sorted_vals) - 1))))
    return sorted_vals[idx]


def post_json(url: str, payload: dict, timeout: float) -> tuple[int, float]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read()
            return resp.status, time.perf_counter() - t0
    except urllib.error.HTTPError as exc:
        exc.read()
        return exc.code, time.perf_counter() - t0


def get(url: str, timeout: float) -> tuple[int, float]:
    t0 = time.perf_counter()
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        resp.read()
        return resp.status, time.perf_counter() - t0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8000")
    parser.add_argument("--email", default="admin@lbro.local")
    parser.add_argument("--password", default="Admin123!")
    parser.add_argument("--runs", type=int, default=25)
    parser.add_argument("--label", default="after")
    args = parser.parse_args()

    login_url = f"{args.base.rstrip('/')}/api/v1/auth/login"
    health_url = f"{args.base.rstrip('/')}/health"

    samples: list[float] = []
    for i in range(args.runs):
        status, elapsed = post_json(
            login_url,
            {"email": args.email, "password": args.password},
            timeout=60.0,
        )
        if status != 200:
            print(f"login failed status={status}", file=sys.stderr)
            return 1
        samples.append(elapsed)
        if i + 1 < args.runs:
            time.sleep(0.4)

    ranked = sorted(samples)
    out = {
        "label": args.label,
        "runs": args.runs,
        "login_median_ms": statistics.median(samples) * 1000,
        "login_p95_ms": percentile(ranked, 0.95) * 1000,
    }

    # Concurrent login + health probes
    import concurrent.futures

    def login_worker() -> None:
        post_json(login_url, {"email": args.email, "password": args.password}, timeout=60.0)

    health_samples: list[float] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
        futures = [pool.submit(login_worker) for _ in range(20)]
        for _ in range(15):
            _, h = get(health_url, timeout=10.0)
            health_samples.append(h)
            time.sleep(0.01)
        concurrent.futures.wait(futures)

    hr = sorted(health_samples)
    out["health_during_20_logins_median_ms"] = statistics.median(health_samples) * 1000
    out["health_during_20_logins_p95_ms"] = percentile(hr, 0.95) * 1000

    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
