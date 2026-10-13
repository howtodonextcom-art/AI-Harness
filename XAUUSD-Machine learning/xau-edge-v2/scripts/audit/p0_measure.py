"""Read-only latency and resource measurements of the running V2 service (Product Audit P0).

Measures: REST latency (p50/p95/p99) per endpoint, quote age and the propagation delay of a price change
from the MT5 terminal to the V2 API (sampled), WebSocket event cadence / gaps / delivery lag, and the
service's CPU and memory. Nothing is written to the service, the store or the terminal.

    uv run python scripts/audit/p0_measure.py --mt5 mt5_ticks.json --out p0_latency.json
The MT5 sampler is a separate script run by V1's interpreter (it holds the MetaTrader5 package):
    <V1>/.venv/Scripts/python.exe scripts/audit/mt5_tick_sampler.py --seconds 70 --out mt5_ticks.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import websockets

BASE = "http://127.0.0.1:8200"


def get(path: str) -> tuple[float, bytes]:
    t0 = time.perf_counter()
    with urllib.request.urlopen(BASE + path, timeout=10) as r:  # noqa: S310
        body = r.read()
    return (time.perf_counter() - t0) * 1000, body


def pct(x: list[float], q: float) -> float:
    s = sorted(x)
    return round(s[min(len(s) - 1, int(q * len(s)))], 2)


def rest(path: str, n: int) -> dict[str, float | int]:
    ms = []
    size = 0
    for _ in range(n):
        t, b = get(path)
        ms.append(t)
        size = len(b)
        time.sleep(0.05)
    return {"n": n, "p50_ms": pct(ms, 0.5), "p95_ms": pct(ms, 0.95), "p99_ms": pct(ms, 0.99), "max_ms": round(max(ms), 2), "bytes": size}


async def ws_listen(seconds: float) -> dict[str, object]:
    events: list[dict[str, object]] = []
    t_end = time.time() + seconds
    async with websockets.connect("ws://127.0.0.1:8200/ws", origin="http://127.0.0.1:8200") as sock:
        while time.time() < t_end:
            try:
                raw = await asyncio.wait_for(sock.recv(), timeout=10)
            except TimeoutError:
                break
            now = datetime.now(UTC)
            e = json.loads(raw)
            ts = datetime.fromisoformat(e["ts"].replace("Z", "+00:00"))
            events.append({"type": e["type"], "seq": e["seq"], "lag_ms": (now - ts).total_seconds() * 1000, "t": time.time()})
    seqs = [int(e["seq"]) for e in events]  # type: ignore[call-overload]
    gaps = sum(1 for a, b in zip(seqs, seqs[1:], strict=False) if b != a + 1)
    by: dict[str, list[float]] = {}
    for e in events:
        by.setdefault(str(e["type"]), []).append(float(e["t"]))  # type: ignore[arg-type]
    lag = [float(e["lag_ms"]) for e in events]  # type: ignore[arg-type]
    inter = {k: round(statistics.median([b - a for a, b in zip(v, v[1:], strict=False)]), 3) if len(v) > 1 else None for k, v in by.items()}
    return {"events": len(events), "by_type": {k: len(v) for k, v in by.items()}, "seq_gaps": gaps, "median_interarrival_s": inter, "delivery_lag_ms": {"p50": pct(lag, 0.5), "p95": pct(lag, 0.95), "max": round(max(lag), 2)} if lag else None}


def quote_series(seconds: float, hz: float = 8.0) -> list[dict[str, float]]:
    out = []
    t_end = time.time() + seconds
    while time.time() < t_end:
        t0 = time.time()
        _, body = get("/api/v2/market/quote")
        q = json.loads(body)
        out.append({"t": t0, "bid": q["bid"], "ask": q["ask"], "age": q["age_seconds"], "collector_age": q.get("collector_age_seconds") or -1})
        time.sleep(max(0.0, 1 / hz - (time.time() - t0)))
    return out


def propagation(v2: list[dict[str, float]], mt5: list[dict[str, float]]) -> dict[str, object]:
    """For every new (bid, ask) seen in MT5, when did V2 first show the same pair? (sampling resolution ~0.15 s)."""
    first_v2: dict[tuple[float, float], float] = {}
    for s in v2:
        first_v2.setdefault((s["bid"], s["ask"]), s["t"])
    seen: dict[tuple[float, float], float] = {}
    for s in mt5:
        seen.setdefault((s["bid"], s["ask"]), s["t"])
    lags = [first_v2[k] - t for k, t in seen.items() if k in first_v2 and first_v2[k] >= t]
    never = sum(1 for k in seen if k not in first_v2)
    return {"mt5_distinct_quotes": len(seen), "matched_in_v2": len(lags), "never_shown_in_v2": never,
            "lag_s": {"p50": pct(lags, 0.5), "p95": pct(lags, 0.95), "p99": pct(lags, 0.99), "max": round(max(lags), 2)} if lags else None}  # fmt: skip


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mt5", required=True, help="output of mt5_tick_sampler.py (run at the same time)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--seconds", type=float, default=60)
    ap.add_argument("--only-quote", action="store_true")
    a = ap.parse_args()
    out: dict[str, object] = {"taken_at": datetime.now(UTC).isoformat()}
    started = time.time()
    series = quote_series(a.seconds)  # runs concurrently with the MT5 sampler started by the caller
    for _ in range(40):  # wait for the sampler to finish writing (it must be NEWER than this run)
        if Path(a.mt5).exists() and Path(a.mt5).stat().st_mtime > started:
            break
        time.sleep(0.5)
    else:
        Path(a.mt5).unlink(missing_ok=True)
    mt5 = json.loads(Path(a.mt5).read_text(encoding="utf-8")) if Path(a.mt5).exists() else []
    out["quote_age_s"] = {"p50": pct([s["age"] for s in series], 0.5), "p95": pct([s["age"] for s in series], 0.95), "max": round(max(s["age"] for s in series), 2)}
    out["collector_age_s"] = {"p50": pct([s["collector_age"] for s in series], 0.5), "p95": pct([s["collector_age"] for s in series], 0.95)}
    out["propagation_mt5_to_v2"] = propagation(series, mt5) if mt5 else "NOT MEASURED (no MT5 sample file)"
    if a.only_quote:
        Path(a.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
        print(json.dumps(out, indent=1))
        return
    out["rest"] = {p: rest(p, 150) for p in ("/api/v2/state", "/api/v2/market/quote", "/api/v2/market/forming", "/api/v2/health", "/api/v2/market/bars?timeframe=M5&limit=500", "/api/v2/paper/summary")}
    out["websocket"] = asyncio.run(ws_listen(45))
    Path(a.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
