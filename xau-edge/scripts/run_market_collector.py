"""Run the MT5 market collector: quote loop plus closed-bar loop with reconcile and a health file.

    uv run --extra mt5 python scripts/run_market_collector.py [--once] [--quote-interval 1]

Restart-safe: on start (and every 10 minutes) it reconciles the last 200 bars of every timeframe
against the terminal, records gaps/duplicates/changes as events and never overwrites a stored bar.
If the terminal drops, the loop waits and reconnects; the status file then says DISCONNECTED.
Stop with Ctrl+C. Market data only; the feed has no order function and requires a DEMO account.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_edge.market_data.collector import (  # noqa: E402
    CollectorStatus,
    MarketCollector,
    write_status_file,
)
from xau_edge.market_data.ledger import BarLedger  # noqa: E402
from xau_edge.market_data.mt5.runtime import DEFAULT_TERMINAL, open_feed  # noqa: E402
from xau_edge.market_data.validators.market_calendar import MarketCalendar  # noqa: E402

DEFAULT_ROOT = ROOT / "data" / "market"


def _disconnected(path: Path, reason: str) -> None:
    write_status_file(
        path,
        CollectorStatus(
            updated_at=datetime.now(UTC).isoformat(),
            health="DISCONNECTED",
            reasons=[reason],
            market_status="UNKNOWN",
            connected=False,
            demo_account=False,
            server=None,
            broker_symbol="",
            quote=None,
            last_closed={},
            last_bar_age_seconds={},
            stored_rows={},
            stale_timeframes=[],
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terminal-path", default=DEFAULT_TERMINAL)
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--quote-interval", type=float, default=1.0)
    parser.add_argument("--bar-interval", type=float, default=5.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    status_path = args.root / "collector_status.json"
    while True:
        try:
            with open_feed(args.terminal_path) as feed:
                mapping = feed.discover_symbol(args.symbol)
                feed.select(mapping.broker_symbol)
                collector = MarketCollector(
                    feed, BarLedger(args.root), mapping, MarketCalendar(), status_path=status_path
                )
                if args.once:
                    collector.reconcile_all()
                    print(json.dumps(collector.run_once().__dict__, indent=2, default=str))
                    return 0
                collector.run(
                    lambda: False,
                    quote_interval=args.quote_interval,
                    bar_interval=args.bar_interval,
                )
        except KeyboardInterrupt:
            return 0
        except Exception as exc:
            _disconnected(status_path, f"{type(exc).__name__}: {exc}"[:300])
            if args.once:
                print("FAILED:", exc)
                return 2
            time.sleep(5)


if __name__ == "__main__":
    raise SystemExit(main())
