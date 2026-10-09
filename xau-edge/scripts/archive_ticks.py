"""Tick retention: move (or delete) whole old tick day files. Explicit, dry-run by default.

    uv run python scripts/archive_ticks.py --before 2023-01-01 --archive-root D:\\xau-archive [--apply]

Nothing in the platform runs this on a timer: the default policy is to KEEP every tick (the ledger is
about 0.3 GB per year). Use it only when disk budget demands it. With ``--archive-root`` each day file
is copied, hash-verified and only then removed from the live ledger; without it the files are deleted
(``--delete-without-archive`` is required to say so out loud). Coverage windows are kept, so the gap
stays visible instead of looking like missing data.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_edge.market_data.tick_ledger import TickLedger  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT / "data" / "market")
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument(
        "--before", required=True, help="day files older than this UTC date (YYYY-MM-DD)"
    )
    parser.add_argument("--archive-root", type=Path, default=None)
    parser.add_argument("--delete-without-archive", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    ledger = TickLedger(args.root)
    old = [d for d in ledger.days(args.symbol) if d < args.before]
    print(f"{len(old)} day files older than {args.before} (of {len(ledger.days(args.symbol))})")
    if not args.apply:
        print("dry run: nothing changed (add --apply)")
        return 0
    if args.archive_root is None and not args.delete_without_archive:
        print("refusing: pass --archive-root, or --delete-without-archive to delete for good")
        return 2
    moved = ledger.archive_before(args.symbol, args.before, args.archive_root)
    print(f"{'archived' if args.archive_root else 'deleted'} {len(moved)} day files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
