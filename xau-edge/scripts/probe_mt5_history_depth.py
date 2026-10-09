"""History depth probe v2: how far back each timeframe and the tick history really go.

Per timeframe it reports the earliest/latest bar returned by ``copy_rates_from_pos`` (the call that
makes the terminal load history up to its "Max bars in chart" limit), whether that limit truncated
the answer, and a range probe in several eras (a window beyond what the terminal holds returns at
most one bar, which is reported as TRUNCATED_BY_TERMINAL, not as "no history"). Ticks: earliest day
found and tick counts in sample windows. Market data only; no returns or prices are analysed.

    uv run --extra mt5 python scripts/probe_mt5_history_depth.py [--write]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_edge.domain.timeframe import Timeframe  # noqa: E402
from xau_edge.market_data.mt5.diagnostics import bar_depth, earliest_tick  # noqa: E402
from xau_edge.market_data.mt5.feed import Mt5Feed  # noqa: E402
from xau_edge.market_data.mt5.runtime import DEFAULT_TERMINAL, open_feed  # noqa: E402

OUT = ROOT / "docs" / "reports" / "mt5-history-depth.json"
ERAS = (2005, 2010, 2015, 2018, 2020, 2022, 2024, 2025, 2026)


def range_probe(feed: Mt5Feed, symbol: str, tf: Timeframe, year: int) -> dict[str, Any]:
    """Bars the terminal returns for a 3-day window (Tuesday-Thursday) in ``year``."""
    start = datetime(year, 3, 1, tzinfo=UTC)
    start += timedelta(days=(1 - start.weekday()) % 7)
    end = start + timedelta(days=3)
    expected = 3 * 24 * 60 // tf.minutes * 4 // 5  # a rough lower bound for a 24x5 market
    try:
        got = feed.bars_range(symbol, tf, start, end, include_forming=True).height
    except RuntimeError as exc:
        return {"year": year, "bars": None, "state": f"ERROR {exc}"}
    if got >= expected // 2:
        state = "OK"
    elif got <= 1:
        state = "TRUNCATED_BY_TERMINAL_OR_NO_HISTORY"
    else:
        state = "PARTIAL"
    return {"year": year, "bars": got, "expected_at_least": expected // 2, "state": state}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terminal-path", default=DEFAULT_TERMINAL)
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    now = datetime.now(UTC)
    with open_feed(args.terminal_path) as feed:
        facts = feed.facts()
        mapping = feed.discover_symbol(args.symbol)
        feed.select(mapping.broker_symbol)
        report: dict[str, Any] = {
            "class": "D (data availability; no market outcome analysed)",
            "probed_at": now.isoformat(),
            "terminal_build": facts.build,
            "terminal_max_bars": facts.max_bars,
            "server": facts.server,
            "broker_symbol": mapping.broker_symbol,
            "timeframes": {},
        }
        for tf in (
            Timeframe.M1,
            Timeframe.M5,
            Timeframe.M15,
            Timeframe.M30,
            Timeframe.H1,
            Timeframe.H4,
        ):
            depth = bar_depth(feed, mapping.broker_symbol, tf, facts.max_bars)
            depth["range_probe"] = [range_probe(feed, mapping.broker_symbol, tf, y) for y in ERAS]
            report["timeframes"][tf.value] = depth
        first = earliest_tick(feed, mapping.broker_symbol, now)
        samples = {}
        for year in (2021, 2022, 2023, 2024, 2025, 2026):
            day = datetime(year, 3, 9, 12, tzinfo=UTC)
            day += timedelta(days=(1 - day.weekday()) % 7)  # a Tuesday: the market is open
            try:
                samples[str(year)] = len(
                    feed.ticks_range(mapping.broker_symbol, day, day + timedelta(minutes=10))
                )
            except RuntimeError:
                samples[str(year)] = None
        report["ticks"] = {
            "earliest_day": None if first is None else first.isoformat(),
            "ten_minute_sample_counts": samples,
        }
    text = json.dumps(report, indent=2, default=str)
    print(text)
    if args.write:
        OUT.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
