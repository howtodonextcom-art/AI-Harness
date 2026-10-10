"""Verify the paper desk's state against its journal, and rebuild it from the journal if needed.

Dry-run by default: it prints what differs and changes nothing. ``--apply`` replaces the state
snapshot by the one the journal implies (the old one is kept as ``paper_desk.json.bak-<time>``) and
appends a ``paper.recovered`` journal line. ``--apply`` needs the single-writer lock, so it refuses
while the API (the live desk) is running: stop the stack first (scripts/stop_market_stack.ps1).

Usage: ``uv run python scripts/paper_recover.py [--root data/trade] [--apply]``
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from xau_edge.ops.process_lock import WriterLock, WriterLockError
from xau_edge.trading.paper_desk import DeskConfig
from xau_edge.trading.paper_recovery import recover


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="data/trade")
    parser.add_argument("--capital", type=float, default=DeskConfig().capital)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    root = Path(args.root)
    lock = WriterLock(root / "writer.lock", role="paper-recover")
    if args.apply:
        try:
            lock.acquire()
        except WriterLockError as exc:
            print(f"REFUSED: {exc}. Stop the market stack first.")
            return 2
    try:
        report = recover(root, initial_capital=args.capital, apply=args.apply)
    finally:
        lock.release()
    print(json.dumps(asdict(report), indent=2))
    if report.ok:
        print("OK: the state and the journal agree.")
        return 0
    if not args.apply:
        print("DIFFERENCES FOUND. This was a dry run; re-run with --apply to rebuild the state.")
        return 1
    return 0 if report.applied else 3


if __name__ == "__main__":
    raise SystemExit(main())
