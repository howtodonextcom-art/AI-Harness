"""Soak test of the RUNNING service: latency, errors, socket gaps, memory trend, engine health.

    uv run python scripts/soak.py --minutes 15 [--url http://127.0.0.1:8200] [--out result.json]

It only reads (GET) and listens to the socket; it never opens or closes a paper position. Memory is
the resident set of the process listening on the service port, sampled every 15 s; the report gives
the least-squares slope per hour so a slow leak is visible, not just a final number.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import threading
import time
import urllib.request
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

import psutil

PATHS = (
    "/api/v2/health",
    "/api/v2/state",
    "/api/v2/paper/summary",
    "/api/v2/forward/summary",
    "/api/v2/model",
    "/api/v2/market/bars?timeframe=M15&limit=500",
    "/api/v2/market/quote",
)


def listening_process(port: int) -> psutil.Process:
    for conn in psutil.net_connections(kind="tcp"):
        if conn.status == psutil.CONN_LISTEN and conn.laddr.port == port and conn.pid:
            return psutil.Process(conn.pid)
    msg = f"nothing listens on port {port}"
    raise SystemExit(msg)


def get(url: str) -> tuple[int, float, bytes]:
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=20) as r:  # noqa: S310 - the local service
            body = r.read()
            return r.status, (time.perf_counter() - started) * 1000, body
    except Exception:
        return 0, (time.perf_counter() - started) * 1000, b""


def socket_listener(url: str, stop: threading.Event, stats: dict[str, object]) -> None:
    import websockets  # noqa: PLC0415

    async def run() -> None:
        last = None
        types: dict[str, int] = defaultdict(int)
        gaps = 0
        async with websockets.connect(url.replace("http", "ws") + "/ws") as ws:
            while not stop.is_set():
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=2)
                except TimeoutError:
                    continue
                event = json.loads(raw)
                types[event["type"]] += 1
                if last is not None and event["seq"] != last + 1:
                    gaps += 1
                last = event["seq"]
        stats.update(events=sum(types.values()), by_type=dict(types), seq_gaps=gaps)

    try:
        asyncio.run(run())
    except Exception as exc:
        stats["error"] = f"{type(exc).__name__}: {exc}"


def slope_per_hour(samples: list[tuple[float, float]]) -> float:
    if len(samples) < 3:
        return 0.0
    xs, ys = [s[0] for s in samples], [s[1] for s in samples]
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    den = sum((x - mx) ** 2 for x in xs)
    return (
        0.0
        if den == 0
        else sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / den * 3600
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=15)
    ap.add_argument("--url", default="http://127.0.0.1:8200")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    port = urlparse(args.url).port or 80
    proc = listening_process(port)
    stop = threading.Event()
    sock: dict[str, object] = {}
    thread = threading.Thread(target=socket_listener, args=(args.url, stop, sock), daemon=True)
    thread.start()
    latencies: dict[str, list[float]] = defaultdict(list)
    errors: dict[str, int] = defaultdict(int)
    rss: list[tuple[float, float]] = []
    cpu: list[float] = []
    t0 = time.time()
    end = t0 + args.minutes * 60
    next_sample = t0
    proc.cpu_percent(None)
    health_first: dict[str, object] = {}
    while time.time() < end:
        for path in PATHS:
            status, ms, body = get(args.url + path)
            latencies[path.split("?")[0]].append(ms)
            if status != 200:
                errors[path] += 1
            elif path.endswith("/health") and not health_first:
                health_first = json.loads(body)
        if time.time() >= next_sample:
            rss.append((time.time() - t0, proc.memory_info().rss / 1e6))
            cpu.append(proc.cpu_percent(None))
            next_sample += 15
        time.sleep(2)
    stop.set()
    thread.join(timeout=10)
    _, _, last = get(args.url + "/api/v2/health")
    health = json.loads(last) if last else {}
    paper_db = next((p for p in Path("data").glob("paper.sqlite3")), None)
    report = {
        "minutes": args.minutes,
        "pid": proc.pid,
        "requests": sum(len(v) for v in latencies.values()),
        "errors": dict(errors),
        "latency_ms": {
            k: {
                "n": len(v),
                "p50": round(statistics.median(v), 1),
                "p95": round(sorted(v)[max(int(len(v) * 0.95) - 1, 0)], 1),
                "max": round(max(v), 1),
            }
            for k, v in latencies.items()
        },
        "rss_mb": {
            "start": round(rss[0][1], 1) if rss else None,
            "end": round(rss[-1][1], 1) if rss else None,
            "min": round(min(r[1] for r in rss), 1) if rss else None,
            "max": round(max(r[1] for r in rss), 1) if rss else None,
            "slope_mb_per_hour": round(slope_per_hour(rss), 2),
            "samples": len(rss),
        },
        "cpu_percent_mean": round(statistics.fmean(cpu[1:]), 2) if len(cpu) > 1 else None,
        "threads": proc.num_threads(),
        "socket": sock,
        "health": {
            "status": health.get("status"),
            "checks": {c["id"]: [c["state"], c["detail"]] for c in health.get("checks", [])},
        },
        "paper_db_bytes": paper_db.stat().st_size if paper_db else None,
    }
    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
