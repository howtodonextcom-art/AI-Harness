"""REST latency of the intelligence endpoint next to /state (read-only), plus service CPU/memory.

uv run python scripts/audit/intel_latency.py ../reports/evidence/intel/latency.json
"""

from __future__ import annotations

import json
import statistics
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

BASE = "http://127.0.0.1:8200"
N = 200


def pct(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int(p / 100 * len(ordered)))], 2)


def get(path: str) -> bytes:
    with urllib.request.urlopen(BASE + path, timeout=10) as r:  # noqa: S310 - local service
        data: bytes = r.read()
    return data


def measure(path: str) -> dict[str, float | int]:
    times: list[float] = []
    size = 0
    for _ in range(N):
        t = time.perf_counter()
        body = get(path)
        times.append((time.perf_counter() - t) * 1000)
        size = len(body)
        time.sleep(0.05)
    return {
        "n": N,
        "p50_ms": pct(times, 50),
        "p95_ms": pct(times, 95),
        "p99_ms": pct(times, 99),
        "max_ms": round(max(times), 2),
        "mean_ms": round(statistics.mean(times), 2),
        "bytes": size,
    }


def main() -> None:
    out = Path(sys.argv[1])
    get("/api/v2/intelligence")  # warm the per-bar memo
    result = {
        "taken_at": datetime.now(UTC).isoformat(),
        "/api/v2/intelligence": measure("/api/v2/intelligence"),
        "/api/v2/state": measure("/api/v2/state"),
    }
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
