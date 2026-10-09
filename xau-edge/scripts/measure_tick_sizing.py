"""Measure real XAUUSD tick rates and storage cost per session window (Class D, no outcomes).

    uv run --extra mt5 python scripts/measure_tick_sizing.py [--write]

Samples 10-minute windows (quiet Asia, London, London/NY overlap, NY, rollover, a high-volatility
release) on recent trading days, then writes the same ticks as Parquet to measure bytes per tick.
Output feeds the tick storage and retention decision in ``docs/operations/market-data-operations.md``.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_edge.market_data.mt5.runtime import DEFAULT_TERMINAL, open_feed  # noqa: E402

OUT = ROOT / "docs" / "reports" / "mt5-tick-sizing.json"
# (label, UTC hour, minute) on ordinary days; the high-volatility sample is the US payrolls hour.
WINDOWS = (
    ("quiet_asia", 3, 0),
    ("london_open", 7, 30),
    ("london_midday", 10, 30),
    ("overlap_ny_open", 13, 30),
    ("ny_afternoon", 17, 0),
    ("rollover", 21, 30),
)


def recent_weekdays(count: int, now: datetime) -> list[datetime]:
    days: list[datetime] = []
    day = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    while len(days) < count:
        if day.weekday() < 5:
            days.append(day)
        day -= timedelta(days=1)
    return days


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terminal-path", default=DEFAULT_TERMINAL)
    parser.add_argument("--days", type=int, default=3)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    now = datetime.now(UTC)
    samples: list[dict[str, Any]] = []
    total_bytes = total_ticks = 0
    with open_feed(args.terminal_path) as feed:
        mapping = feed.discover_symbol("XAUUSD")
        feed.select(mapping.broker_symbol)
        specials = [
            (f"high_vol_{d.date()}", d.replace(hour=12, minute=25))
            for d in recent_weekdays(10, now)
            if d.weekday() == 4
        ][:1]
        plan = [
            (label, d.replace(hour=h, minute=m))
            for d in recent_weekdays(args.days, now)
            for label, h, m in WINDOWS
        ]
        for label, start in plan + specials:
            frame, truncated = feed.ticks_frame(
                mapping.broker_symbol, start, start + timedelta(minutes=10)
            )
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "t.parquet"
                frame.write_parquet(path, compression="zstd")
                size = path.stat().st_size
            total_bytes += size
            total_ticks += frame.height
            samples.append(
                {
                    "label": label, "start": start.isoformat(), "ticks_10min": frame.height,
                    "ticks_per_second": round(frame.height / 600, 2), "parquet_bytes": size,
                    "bytes_per_tick": round(size / max(1, frame.height), 2), "truncated": truncated,
                }
            )  # fmt: skip
            print(samples[-1])
    plain = [s for s in samples if not s["label"].startswith("high_vol")]
    mean_rate = sum(s["ticks_per_second"] for s in plain) / max(1, len(plain))
    # A trading day is ~22h50m open; the sampled windows are spread over the day, so their mean
    # rate is applied to the open duration (an estimate, bounded by the min/max sample).
    open_seconds = 22.8 * 3600
    ticks_day = mean_rate * open_seconds
    bytes_per_tick = total_bytes / max(1, total_ticks)
    report = {
        "class": "D (storage sizing; no market outcome analysed)",
        "measured_at": now.isoformat(),
        "samples": samples,
        "mean_ticks_per_second_ordinary": round(mean_rate, 2),
        "estimated_ticks_per_day": int(ticks_day),
        "estimated_ticks_per_month_21d": int(ticks_day * 21),
        "parquet_zstd_bytes_per_tick": round(bytes_per_tick, 2),
        "raw_bytes_per_tick_in_memory": 7 * 8,
        "estimated_parquet_mb_per_day": round(ticks_day * bytes_per_tick / 1e6, 1),
        "estimated_parquet_gb_per_year_252d": round(ticks_day * 252 * bytes_per_tick / 1e9, 2),
        "min_sample_ticks_per_second": min(s["ticks_per_second"] for s in plain),
        "max_sample_ticks_per_second": max(s["ticks_per_second"] for s in samples),
    }
    text = json.dumps(report, indent=2)
    print(text.split('"samples"')[0] + "...")
    print(json.dumps({k: v for k, v in report.items() if k != "samples"}, indent=2))
    if args.write:
        OUT.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
