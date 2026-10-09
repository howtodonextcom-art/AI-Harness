"""Backfill raw ticks from the FTMO MT5 terminal into the tick ledger (chunked, resumable).

    uv run --extra mt5 python scripts/backfill_mt5_ticks.py --from 2026-09-01 [--to 2026-10-09]

Newest chunks first, in windows of ``--chunk-hours`` (default 6, split in half whenever the
terminal's per-call cap is hit, never one giant request). Windows already covered in the ledger are
skipped, so an interrupted run resumes where it stopped and a re-run adds nothing. Coverage is
recorded only for completely fetched windows. Writes ``docs/reports/mt5-tick-backfill.json`` with
``--write-report``.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_edge.market_data.mt5.runtime import DEFAULT_TERMINAL, open_feed  # noqa: E402
from xau_edge.market_data.tick_collection import FetchStats, fetch_window  # noqa: E402
from xau_edge.market_data.tick_ledger import TickLedger  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terminal-path", default=DEFAULT_TERMINAL)
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--root", type=Path, default=ROOT / "data" / "market")
    parser.add_argument("--from", dest="start", required=True, help="YYYY-MM-DD (UTC)")
    parser.add_argument(
        "--to", dest="end", default=None, help="YYYY-MM-DD (UTC), default: now - 10 s"
    )
    parser.add_argument("--chunk-hours", type=float, default=6.0)
    parser.add_argument("--pause", type=float, default=0.05, help="seconds between calls")
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()
    start = datetime.fromisoformat(args.start).replace(tzinfo=UTC)
    end = (
        datetime.fromisoformat(args.end).replace(tzinfo=UTC)
        if args.end
        else (datetime.now(UTC) - timedelta(seconds=10)).replace(microsecond=0)
    )
    ledger = TickLedger(args.root)
    stats = FetchStats()
    errors: list[str] = []
    chunk = timedelta(hours=args.chunk_hours)
    began = time.monotonic()
    with open_feed(args.terminal_path) as feed:
        mapping = feed.discover_symbol(args.symbol)
        feed.select(mapping.broker_symbol)
        todo = ledger.uncovered(mapping.canonical_symbol, start, end)
        for gap_start, gap_end in reversed(todo):  # newest first
            cursor = gap_end
            while cursor > gap_start:
                lo = max(gap_start, cursor - chunk)
                try:
                    fetch_window(
                        feed,
                        ledger,
                        symbol=mapping.canonical_symbol,
                        broker_symbol=mapping.broker_symbol,
                        start=lo,
                        end=cursor,
                        stats=stats,
                    )
                except RuntimeError as exc:
                    errors.append(f"{lo.isoformat()}: {exc}"[:200])
                cursor = lo
                time.sleep(args.pause)
    covered = ledger.coverage(mapping.canonical_symbol)
    report = {
        "requested": [start.isoformat(), end.isoformat()],
        "elapsed_seconds": round(time.monotonic() - began, 1),
        **asdict(stats),
        "errors": errors,
        "earliest_tick": ledger.earliest(mapping.canonical_symbol),
        "latest_tick": ledger.latest(mapping.canonical_symbol),
        "coverage_windows": len(covered),
        "still_uncovered": [
            [a.isoformat(), b.isoformat()]
            for a, b in ledger.uncovered(mapping.canonical_symbol, start, end)
        ][:20],
    }
    text = json.dumps(report, indent=2, default=str)
    print(text)
    if args.write_report:
        (ROOT / "docs" / "reports" / "mt5-tick-backfill.json").write_text(
            text + "\n", encoding="utf-8"
        )
    return 0 if not errors and not stats.unsplittable else 1


if __name__ == "__main__":
    raise SystemExit(main())
