"""Write an immutable, hashed snapshot of the stored closed bars (for research, backtests, audits).

    uv run python scripts/snapshot_market.py [--timeframes M5 M15 H1 H4] [--out data/market/snapshots]

The snapshot is one parquet per timeframe plus ``manifest.json`` (row counts, first/last bar and
SHA-256). A snapshot is never modified; take a new one instead. Closed bars only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_edge.domain.timeframe import Timeframe  # noqa: E402
from xau_edge.market_data.ledger import BarLedger  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT / "data" / "market")
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--timeframes", nargs="+", default=[t.value for t in Timeframe])
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    ledger = BarLedger(args.root)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = (args.out or args.root / "snapshots") / f"{args.symbol}-{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    per_tf: dict[str, Any] = {}
    manifest: dict[str, Any] = {"symbol": args.symbol, "created_at": stamp, "timeframes": per_tf}
    for name in args.timeframes:
        frame = ledger.load(args.symbol, Timeframe(name))
        if frame.height == 0:
            continue
        path = out / f"{name}.parquet"
        frame.write_parquet(path)
        per_tf[name] = {
            "rows": frame.height,
            "first": frame["timestamp"].min(),
            "last": frame["timestamp"].max(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    text = json.dumps(manifest, indent=2, default=str) + "\n"
    (out / "manifest.json").write_text(text, encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
