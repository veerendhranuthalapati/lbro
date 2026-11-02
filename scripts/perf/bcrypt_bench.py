"""Single bcrypt verify timing on this machine (passlib default rounds)."""
from __future__ import annotations

import statistics
import time

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
hashed = pwd_context.hash("BenchPassword123!")
samples: list[float] = []
for _ in range(25):
    t0 = time.perf_counter()
    pwd_context.verify("BenchPassword123!", hashed)
    samples.append(time.perf_counter() - t0)

ranked = sorted(samples)
p95 = ranked[int(round(0.95 * (len(ranked) - 1)))]
print(
    {
        "bcrypt_verify_median_ms": statistics.median(samples) * 1000,
        "bcrypt_verify_p95_ms": p95 * 1000,
        "rounds": pwd_context.handler().rounds,
    }
)
