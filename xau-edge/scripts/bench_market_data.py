"""Measure the real cost of the market data path (no guessing): API latency and MT5 call rate.

    uv run python scripts/bench_market_data.py [--mt5] [--write]

* API: every ``/md/*`` endpoint against the real ledgers (in-process, so it measures our work, not
  the network): wall time per request (median / p95 of 20) and CPU seconds per request.
* ``--mt5``: runs the collector loop for 20 s against the live terminal with a counting proxy and
  reports MT5 calls per second by function, i.e. what the UI polling and the collector cost the
  terminal. The browser polls the API, never MT5; the API never opens an MT5 connection.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from xau_edge.api.market_data import add_market_data_routes  # noqa: E402

OUT = ROOT / "docs" / "reports" / "mt5-performance.json"


def timed(http: TestClient, url: str, runs: int = 20) -> dict[str, Any]:
    wall: list[float] = []
    cpu: list[float] = []
    size = 0
    for _ in range(runs):
        w0, c0 = time.perf_counter(), time.process_time()
        response = http.get(url)
        wall.append((time.perf_counter() - w0) * 1000)
        cpu.append((time.process_time() - c0) * 1000)
        size = len(response.content)
        if response.status_code != 200:
            raise RuntimeError(f"{url}: HTTP {response.status_code}")
    wall.sort()
    return {
        "url": url, "median_ms": round(statistics.median(wall), 1), "p95_ms": round(wall[int(runs * 0.95) - 1], 1),
        "cpu_ms_median": round(statistics.median(cpu), 1), "bytes": size,
    }  # fmt: skip


class CountingClient:
    """Counts every MT5 function the collector calls (market-data functions only exist here)."""

    def __init__(self, inner: Any, counter: Counter[str]) -> None:
        self._inner = inner
        self._counter = counter

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._inner, name)
        if not callable(attr):
            return attr

        def wrapped(*args: Any, **kwargs: Any) -> Any:
            self._counter[name] += 1
            return attr(*args, **kwargs)

        return wrapped


def mt5_rate(seconds: float = 20.0) -> dict[str, Any]:
    from xau_edge.market_data.calendars import ftmo_calendar  # noqa: PLC0415
    from xau_edge.market_data.collector import MarketCollector  # noqa: PLC0415
    from xau_edge.market_data.ledger import BarLedger  # noqa: PLC0415
    from xau_edge.market_data.mt5.runtime import DEFAULT_TERMINAL, open_feed  # noqa: PLC0415
    from xau_edge.market_data.tick_ledger import TickLedger  # noqa: PLC0415

    counter: Counter[str] = Counter()
    deadline = time.monotonic() + seconds
    with open_feed(DEFAULT_TERMINAL) as feed:
        mapping = feed.discover_symbol("XAUUSD")
        feed.select(mapping.broker_symbol)
        feed._client = CountingClient(feed._client, counter)  # type: ignore[assignment]
        root = ROOT / "data" / "bench"
        collector = MarketCollector(
            feed, BarLedger(root), mapping, ftmo_calendar(),
            status_path=root / "collector_status.json", tick_ledger=TickLedger(root),
        )  # fmt: skip
        warm0 = time.process_time()
        collector.reconcile_all()  # run() repeats this once at start-up; it is not steady state
        warmup = time.process_time() - warm0
        cpu0 = time.process_time()
        collector.run(lambda: time.monotonic() > deadline, quote_interval=1.0, bar_interval=5.0)
        cpu = max(0.0, time.process_time() - cpu0 - warmup)
    return {
        "seconds": seconds,
        "mt5_calls_per_second": {k: round(v / seconds, 2) for k, v in sorted(counter.items())},
        "total_calls_per_second": round(sum(counter.values()) / seconds, 2),
        "collector_steady_state_cpu_percent_of_one_core": round(100 * cpu / seconds, 1),
        "startup_reconcile_cpu_seconds": round(warmup, 2),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT / "data" / "market")
    parser.add_argument("--mt5", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    app = FastAPI()
    add_market_data_routes(app, args.root)
    http = TestClient(app)
    urls = [
        "/md/status", "/md/XAUUSD/quote", "/md/XAUUSD/matrix", "/md/XAUUSD/quality",
        "/md/XAUUSD/bars?timeframe=M1&limit=500&include_forming=true",
        "/md/XAUUSD/bars?timeframe=M1&limit=5000&include_forming=true",
        "/md/XAUUSD/bars?timeframe=M15&limit=500&include_forming=true",
        "/md/XAUUSD/bars?timeframe=H4&limit=5000",
        "/md/XAUUSD/ticks?limit=200",
    ]  # fmt: skip
    report: dict[str, Any] = {"api": [timed(http, u) for u in urls]}
    for row in report["api"]:
        print(row)
    if args.mt5:
        report["mt5"] = mt5_rate()
        print(report["mt5"])
    if args.write:
        OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
