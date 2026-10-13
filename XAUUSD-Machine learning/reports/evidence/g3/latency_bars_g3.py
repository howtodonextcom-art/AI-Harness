"""G3 latency of the history endpoint (V2) next to V1's, same session, same machine.

Samples N requests per case; prints p50/p95/max in ms and payload bytes.
"""
import json
import random
import statistics as st
import time
import urllib.request
from datetime import UTC, datetime, timedelta

V1 = "http://127.0.0.1:8000"
V2 = "http://127.0.0.1:8200"
N = 40
rng = random.Random(7)


def timed(url: str) -> tuple[float, int]:
    t = time.perf_counter()
    body = urllib.request.urlopen(url, timeout=60).read()
    return (time.perf_counter() - t) * 1000, len(body)


def stats(urls: list[str]) -> tuple[float, float, float, int]:
    ts, size = [], 0
    for u in urls:
        ms, size = timed(u)
        ts.append(ms)
    ts.sort()
    return st.median(ts), ts[int(0.95 * len(ts)) - 1], ts[-1], size


oldest = {"M1": "2004-06-11", "M5": "2004-06-11", "M15": "2004-06-11", "H1": "2004-06-11", "H4": "2004-06-11"}


def deep(tf: str) -> str:
    base = datetime(2004, 7, 1, tzinfo=UTC)
    span = (datetime(2026, 9, 1, tzinfo=UTC) - base).days
    d = base + timedelta(days=rng.randrange(span), hours=rng.randrange(24))
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


rows = []
for tf in ("M1", "M15", "H1", "H4"):
    for limit in (400, 5000):
        rows.append((f"V2 latest   {tf:3s} limit {limit}", [f"{V2}/api/v2/market/bars?timeframe={tf}&limit={limit}"] * N))
        rows.append((f"V1 latest   {tf:3s} limit {limit}", [f"{V1}/md/XAUUSD/bars?timeframe={tf}&limit={limit}"] * N))
    rows.append((f"V2 deep page {tf:3s} limit 1000 (random year)", [f"{V2}/api/v2/market/bars?timeframe={tf}&limit=1000&before={deep(tf)}" for _ in range(N)]))
    rows.append((f"V1 deep page {tf:3s} limit 1000 (random year)", [f"{V1}/md/XAUUSD/bars?timeframe={tf}&limit=1000&before={deep(tf)}" for _ in range(N)]))
rows.append(("V2 /api/v2/state", [f"{V2}/api/v2/state"] * N))
rows.append(("V2 /api/v2/health", [f"{V2}/api/v2/health"] * N))
rows.append(("V2 /api/v2/market/quote", [f"{V2}/api/v2/market/quote"] * N))
rows.append(("V1 /md/XAUUSD/quote", [f"{V1}/md/XAUUSD/quote"] * N))
print("case | p50 ms | p95 ms | max ms | bytes")
for name, urls in rows:
    p50, p95, mx, size = stats(urls)
    print(f"{name:48s} {p50:8.1f} {p95:8.1f} {mx:8.1f} {size}")
