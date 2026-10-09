"""Explicit, audited repair of stored bars that the terminal now reports differently.

    uv run --extra mt5 python scripts/repair_changed_bars.py [--hours 24] [--apply]

The normal collector NEVER overwrites a stored bar: a difference becomes a ``BAR_CHANGED`` event. When
such a bar was captured too early (for example while the terminal was still receiving late ticks),
this tool compares exactly those flagged bars with the terminal's current, settled values and, only
with ``--apply``, replaces them. Every replacement is logged as ``BAR_REPAIRED`` with the old and the
new values, and a repaired bar no longer counts as a data-quality problem. Dry run by default.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_edge.domain.timeframe import Timeframe  # noqa: E402
from xau_edge.market_data.ledger import BarLedger  # noqa: E402
from xau_edge.market_data.mt5.runtime import DEFAULT_TERMINAL, open_feed  # noqa: E402

SETTLED = timedelta(minutes=2)


def flagged(ledger: BarLedger, symbol: str, since: datetime) -> dict[str, set[datetime]]:
    """Bars named by a BAR_CHANGED event since ``since`` and not yet repaired."""
    changed: dict[str, set[datetime]] = {}
    repaired: set[tuple[str, str]] = set()
    for event in ledger.events(symbol):
        if event.get("kind") == "BAR_REPAIRED":
            repaired |= {(str(event["timeframe"]), b["timestamp"]) for b in event.get("bars", [])}
    for event in ledger.events(symbol):
        if event.get("kind") != "BAR_CHANGED" or datetime.fromisoformat(event["at"]) < since:
            continue
        for stamp in event.get("timestamps", []):
            if (str(event["timeframe"]), stamp) not in repaired:
                changed.setdefault(str(event["timeframe"]), set()).add(
                    datetime.fromisoformat(stamp)
                )
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terminal-path", default=DEFAULT_TERMINAL)
    parser.add_argument("--root", type=Path, default=ROOT / "data" / "market")
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--hours", type=float, default=24.0)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    now = datetime.now(UTC)
    ledger = BarLedger(args.root)
    todo = flagged(ledger, args.symbol, now - timedelta(hours=args.hours))
    if not todo:
        print("no unrepaired BAR_CHANGED bars in the window")
        return 0
    total = 0
    with open_feed(args.terminal_path) as feed:
        mapping = feed.discover_symbol(args.symbol)
        feed.select(mapping.broker_symbol)
        for name, stamps in sorted(todo.items()):
            tf = Timeframe(name)
            oldest = min(stamps)
            count = int((now - oldest) / tf.delta) + 5
            live = feed.latest_bars(mapping.broker_symbol, tf, min(count, 50_000))
            live = live.filter(
                pl.col("timestamp").is_in(sorted(stamps))
                & (pl.col("timestamp") + pl.duration(minutes=tf.minutes) <= now - SETTLED)
            )
            if not args.apply:
                stored = ledger.load(args.symbol, tf, start=oldest)
                diff = live.join(stored, on="timestamp", suffix="_s").filter(
                    (pl.col("close") != pl.col("close_s"))
                    | (pl.col("tick_volume") != pl.col("tick_volume_s"))
                )
                for row in diff.iter_rows(named=True):
                    print(
                        f"{name} {row['timestamp'].isoformat()}: close {row['close_s']} -> {row['close']},"
                        f" tick_volume {row['tick_volume_s']} -> {row['tick_volume']}"
                    )
                total += diff.height
                continue
            done = ledger.replace_bars(
                args.symbol, tf, live, now=now, reason="repair-early-capture"
            )
            total += len(done)
            print(f"{name}: repaired {len(done)} bar(s)")
    print(
        f"{total} bar(s) {'repaired' if args.apply else 'would be repaired (dry run; add --apply)'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
