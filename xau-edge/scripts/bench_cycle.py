"""Benchmark the per-cycle data-load latency of the raw store: fragmented vs compacted vs cached.

    uv run python scripts/bench_cycle.py                      # synthetic store, 30 days of refreshes
    uv run python scripts/bench_cycle.py --refresh-files 480  # 1 week of 24/5 refreshes per timeframe
    uv run python scripts/bench_cycle.py --root data/raw      # copy of a real store (never modified)

A bot cycle loads M5, M15, H1 and H4 through ``DatasetCatalog.load`` (see scripts/demo_trader.py).
Every refresh adds one small Parquet file per timeframe, so the load cost grows with uptime.
Scenarios (milliseconds for the four loads of one cycle, median of --repeats):

* BEFORE      fragmented store, no cache (the behaviour before T3.2)
* CACHED      fragmented store, cache warm (a new DatasetCatalog per cycle, as the bot does)
* COMPACTED   monthly files, no cache (what the first cycle after a change costs)
* AFTER       monthly files, cache warm (steady state)

The benchmark runs on a temporary copy; ``--root`` is only read.
"""

from __future__ import annotations

import argparse
import shutil
import statistics
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl

from xau_edge.domain.bars import BAR_SCHEMA
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.catalog import DatasetCatalog, clear_catalog_cache
from xau_edge.market_data.compact import compact_all
from xau_edge.market_data.store import RawStore

SYMBOL = "XAUUSD"
BASE_BARS = {Timeframe.M5: 100_000, Timeframe.M15: 34_000, Timeframe.H1: 8_500, Timeframe.H4: 2_100}
START = datetime(2025, 1, 6, tzinfo=UTC)


def _bars(tf: Timeframe, first: int, count: int, prices: np.ndarray) -> pl.DataFrame:
    idx = np.arange(first, first + count)
    close = prices[idx]
    open_ = prices[idx - 1]
    return pl.DataFrame(
        {
            "timestamp": [START + int(i) * tf.delta for i in idx],
            "open": open_,
            "high": np.maximum(open_, close) + 0.3,
            "low": np.minimum(open_, close) - 0.3,
            "close": close,
            "tick_volume": 100 + idx % 50,
            "spread": np.full(count, 25),
            "real_volume": np.zeros(count, dtype=np.int64),
        },
        schema=BAR_SCHEMA,
    )


def build_synthetic(root: Path, refresh_files: int) -> None:
    """History plus ``refresh_files`` small overlapping files per timeframe, like the live refresh."""
    rng = np.random.default_rng(7)
    store = RawStore(root)
    for tf, base in BASE_BARS.items():
        prices = 2000 + np.cumsum(rng.normal(0, 0.5, base + refresh_files + 8))
        store.write(
            _bars(tf, 1, base, prices),
            symbol=SYMBOL,
            timeframe=tf,
            source="mt5",
            fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        for k in range(refresh_files):
            last = base + k + 1
            store.write(
                _bars(tf, last - 3, 4, prices),  # three overlapping bars plus one new
                symbol=SYMBOL,
                timeframe=tf,
                source="mt5",
                fetched_at=datetime(2026, 1, 2, tzinfo=UTC) + timedelta(minutes=15 * k),
            )


def cycle_ms(root: Path, *, use_cache: bool, repeats: int) -> float:
    """Median milliseconds to load the four timeframes with a fresh catalog (like one bot cycle)."""
    samples: list[float] = []
    for _ in range(repeats):
        started = time.perf_counter()
        catalog = DatasetCatalog(root)
        for tf in Timeframe:
            catalog.load(SYMBOL, tf, use_cache=use_cache)
        samples.append((time.perf_counter() - started) * 1000)
    return statistics.median(samples)


def count_files(root: Path) -> int:
    return sum(1 for _ in root.glob(f"{SYMBOL}/*/*.parquet"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--root", default=None, help="a real raw store to copy and measure")
    parser.add_argument(
        "--refresh-files", type=int, default=2000, help="synthetic files per timeframe"
    )
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="xau_bench_") as tmp:
        root = Path(tmp) / "raw"
        if args.root:
            shutil.copytree(args.root, root)
            label = f"copy of {args.root}"
        else:
            started = time.perf_counter()
            build_synthetic(root, args.refresh_files)
            label = f"synthetic, {args.refresh_files} refresh files per timeframe"
            print(f"built in {time.perf_counter() - started:.1f}s")
        files_before = count_files(root)
        clear_catalog_cache()
        before = cycle_ms(root, use_cache=False, repeats=args.repeats)
        clear_catalog_cache()
        cycle_ms(root, use_cache=True, repeats=1)  # warm
        cached = cycle_ms(root, use_cache=True, repeats=args.repeats)

        started = time.perf_counter()
        compact_all(root)
        compact_s = time.perf_counter() - started
        files_after = count_files(root)
        clear_catalog_cache()
        compacted = cycle_ms(root, use_cache=False, repeats=args.repeats)
        clear_catalog_cache()
        cycle_ms(root, use_cache=True, repeats=1)
        after = cycle_ms(root, use_cache=True, repeats=args.repeats)

    print(f"\nstore: {label}")
    print(f"files: {files_before} -> {files_after} (compaction took {compact_s:.1f}s)")
    print(f"{'scenario':<12}{'ms per cycle (4 loads)':>26}")
    for name, value in (
        ("BEFORE", before),
        ("CACHED", cached),
        ("COMPACTED", compacted),
        ("AFTER", after),
    ):
        print(f"{name:<12}{value:>26.1f}")
    print(
        f"\nspeed-up BEFORE -> AFTER: {before / after:.0f}x; BEFORE -> COMPACTED: {before / compacted:.1f}x"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
