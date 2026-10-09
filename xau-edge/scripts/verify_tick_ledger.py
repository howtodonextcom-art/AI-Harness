"""Verify the tick ledger: hashes, order, duplicates, crossed quotes, partition containment.

    uv run python scripts/verify_tick_ledger.py [--save-manifest] [--days 30]

Exit 0 only when clean. ``--save-manifest`` stores the day-file hashes as the baseline; later runs
fail when a historical day changed or disappeared (the newest day may grow).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_edge.market_data.tick_ledger import TickLedger  # noqa: E402
from xau_edge.market_data.verification import load_manifest, verify_ticks  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT / "data" / "market")
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--days", type=int, default=None, help="only the newest N days")
    parser.add_argument("--save-manifest", action="store_true")
    args = parser.parse_args()
    ledger = TickLedger(args.root)
    baseline = args.root / args.symbol / "ticks" / "tick-manifest.json"
    report = verify_ticks(
        ledger, args.symbol, saved_manifest=load_manifest(baseline), max_days=args.days
    )
    print(json.dumps(report, indent=2, default=str))
    if args.save_manifest and report["ok"]:
        baseline.write_text(
            json.dumps(ledger.manifest(args.symbol), indent=2, default=str), encoding="utf-8"
        )
        print("manifest saved:", baseline)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
