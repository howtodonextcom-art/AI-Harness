"""Backfill closed bars from the FTMO MT5 terminal into the local bar ledger (idempotent, resumable).

    uv run --extra mt5 python scripts/backfill_mt5.py [--timeframes M1 M5 ...] [--since 2024-01-01]

Reads as much history as the terminal holds (``copy_rates_from_pos``, at most 99,000 bars per call:
the terminal's "Max bars in chart" must be above that). Only CLOSED bars are stored, stored bars are
never overwritten, and a re-run only adds what is missing. When the terminal holds less than
``--since`` asks for, the shortfall is reported as TRUNCATED_BY_TERMINAL with the owner action.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_edge.domain.timeframe import Timeframe  # noqa: E402
from xau_edge.market_data.ledger import BarLedger  # noqa: E402
from xau_edge.market_data.mt5.feed import MAX_BARS_PER_CALL  # noqa: E402
from xau_edge.market_data.mt5.runtime import DEFAULT_TERMINAL, open_feed  # noqa: E402

DEFAULT_ROOT = ROOT / "data" / "market"
OWNER_ACTION = (
    "raise 'Max bars in chart' (Tools > Options > Charts) in the FTMO MT5 terminal to "
    "Unlimited or >= 10,000,000, restart the terminal, then rerun this backfill"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terminal-path", default=DEFAULT_TERMINAL)
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--timeframes", nargs="+", default=[t.value for t in Timeframe])
    parser.add_argument("--since", default="2004-01-01", help="oldest date wanted (YYYY-MM-DD)")
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()
    wanted = datetime.fromisoformat(args.since).replace(tzinfo=UTC)
    ledger = BarLedger(args.root)
    per_tf: dict[str, Any] = {}
    report: dict[str, Any] = {"since_wanted": wanted.isoformat(), "timeframes": per_tf}
    truncated = False
    with open_feed(args.terminal_path) as feed:
        facts = feed.facts()
        mapping = feed.discover_symbol(args.symbol)
        feed.select(mapping.broker_symbol)
        now = datetime.now(UTC)
        for name in args.timeframes:
            tf = Timeframe(name)
            count = MAX_BARS_PER_CALL
            frame = None
            while count >= 100 and frame is None:
                try:
                    frame = feed.latest_bars(mapping.broker_symbol, tf, count)
                except RuntimeError:
                    count //= 2
            if frame is None:
                per_tf[name] = {"error": "terminal refused every request size"}
                continue
            result = ledger.append_closed(
                mapping.canonical_symbol, tf, frame, now=now, reason="backfill"
            )
            earliest = ledger.earliest(mapping.canonical_symbol, tf)
            short = earliest is not None and earliest > wanted
            truncated = truncated or (short and frame.height >= count - 1)
            per_tf[name] = {
                "fetched": frame.height,
                "new": result.new,
                "duplicates": result.duplicates,
                "changed": result.changed,
                "earliest_stored": None if earliest is None else earliest.isoformat(),
                "state": "TRUNCATED_BY_TERMINAL" if short else "COMPLETE_FOR_REQUEST",
            }
            print(name, per_tf[name])
    report["terminal_max_bars"] = facts.max_bars
    report["owner_action_required"] = OWNER_ACTION if truncated else None
    ledger.log_event(
        mapping.canonical_symbol, "BACKFILL", {"report": report}, now=datetime.now(UTC)
    )
    if args.write_report:
        out = ROOT / "docs" / "reports" / "mt5-backfill.json"
        out.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    if truncated:
        print("OWNER_ACTION_REQUIRED:", OWNER_ACTION)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
