"""Run the MT5 market collector: quotes, closed bars, ticks, reconcile, health file, reconnect.

    uv run --extra mt5 python scripts/run_market_collector.py [--once] [--quote-interval 1]

Restart-safe: every session reconciles the last 200 bars of every timeframe against the terminal
(recording gaps/duplicates/changes as events, never overwriting a stored bar) and ingests ticks
into the tick ledger. If the terminal is missing, starts late, restarts or drops, the status file
says DISCONNECTED and a new session starts automatically after 5 s. Stop with Ctrl+C (or let the
supervisor stop it). Market data only; the feed has no order function and requires a DEMO account.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_edge.market_data.calendars import ftmo_calendar  # noqa: E402
from xau_edge.market_data.collector import MarketCollector, write_status_file  # noqa: E402
from xau_edge.market_data.collector_runner import (  # noqa: E402
    disconnected_status,
    run_with_reconnect,
)
from xau_edge.market_data.ledger import BarLedger  # noqa: E402
from xau_edge.market_data.mt5.feed import Mt5Feed  # noqa: E402
from xau_edge.market_data.mt5.runtime import DEFAULT_TERMINAL, open_feed  # noqa: E402
from xau_edge.market_data.tick_ledger import TickLedger  # noqa: E402

DEFAULT_ROOT = ROOT / "data" / "market"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terminal-path", default=DEFAULT_TERMINAL)
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--quote-interval", type=float, default=1.0)
    parser.add_argument("--bar-interval", type=float, default=5.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    status_path = args.root / "collector_status.json"

    def build(feed: Mt5Feed) -> MarketCollector:
        mapping = feed.discover_symbol(args.symbol)
        feed.select(mapping.broker_symbol)
        return MarketCollector(
            feed,
            BarLedger(args.root),
            mapping,
            ftmo_calendar(),
            status_path=status_path,
            tick_ledger=TickLedger(args.root),
        )

    if args.once:
        try:
            with open_feed(args.terminal_path) as feed:
                collector = build(feed)
                collector.reconcile_all()
                print(json.dumps(collector.run_once().__dict__, indent=2, default=str))
        except Exception as exc:
            write_status_file(
                status_path, disconnected_status(f"{type(exc).__name__}: {exc}"[:300])
            )
            print("FAILED:", exc)
            return 2
        return 0
    try:
        run_with_reconnect(
            lambda: open_feed(args.terminal_path),
            build,
            status_path=status_path,
            quote_interval=args.quote_interval,
            bar_interval=args.bar_interval,
        )
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
