"""
ML concurrency benchmark — before vs after asyncio.to_thread fix.
Run: python backend/scripts/ml_benchmark.py
"""
import asyncio, time, httpx

BASE = "http://localhost:8000"
TOKEN = ""  # set via env or hardcode for local testing

async def classify_one(client, i):
    r = await client.post(f"{BASE}/api/v1/ml/classify",
        json={"text": f"Sample incident text number {i}"},
        headers={"Authorization": f"Bearer {TOKEN}"})
    return r.status_code, time.monotonic()

async def run(n=10):
    async with httpx.AsyncClient(timeout=30) as client:
        t0 = time.monotonic()
        results = await asyncio.gather(*[classify_one(client, i) for i in range(n)])
        elapsed = time.monotonic() - t0
    print(f"{n} concurrent requests completed in {elapsed:.2f}s (avg {elapsed/n*1000:.0f}ms each)")
    statuses = [r[0] for r in results]
    print(f"Status codes: {set(statuses)}")

asyncio.run(run(10))
