"""Verify the bar ledger: readability, schema, order, uniqueness, OHLC sanity, immutability, coverage.

    uv run python scripts/verify_market_ledger.py [--save-manifest]

Exit 0 only when every timeframe is clean. ``--save-manifest`` stores the current file hashes as the
baseline; later runs fail if a historical month file changed or disappeared.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_edge.market_data.calendars import ftmo_calendar  # noqa: E402
from xau_edge.market_data.ledger import BarLedger  # noqa: E402
from xau_edge.market_data.verification import load_manifest, verify_bars  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT / "data" / "market")
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--save-manifest", action="store_true")
    args = parser.parse_args()
    ledger = BarLedger(args.root)
    baseline = args.root / args.symbol / "bar-manifest.json"
    report = verify_bars(
        ledger, args.symbol, ftmo_calendar(), saved_manifest=load_manifest(baseline)
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
