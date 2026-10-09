"""Write an immutable, hashed snapshot of the stored closed bars with full provenance.

    uv run python scripts/snapshot_market.py [--timeframes M5 M15 H1 H4] [--out data/market/snapshots]

One parquet per timeframe plus ``manifest.json``: per timeframe the rows, first/last bar, SHA-256 of
the snapshot file and of the ledger it came from, and a ``provenance`` block: source, terminal
build, broker server, broker symbol, UTC creation time, the ledger head hash, the latest closed bar
per timeframe and the latest stored tick. A snapshot is never modified; take a new one instead.
Closed bars only; tick volume only (real volume is not exported as a scientific input).
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
from xau_edge.market_data.tick_ledger import TickLedger  # noqa: E402


def collector_facts(root: Path) -> dict[str, Any]:
    """Server / symbol / build as last reported by the collector (no credentials exist there)."""
    try:
        status = json.loads((root / "collector_status.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {
            "server": None,
            "broker_symbol": None,
            "terminal_build": None,
            "note": "no collector status",
        }
    return {
        "server": status.get("server"),
        "broker_symbol": status.get("broker_symbol"),
        "terminal_build": status.get("terminal_build"),
        "collected_health_at_snapshot": status.get("health"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT / "data" / "market")
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--timeframes", nargs="+", default=[t.value for t in Timeframe])
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    ledger = BarLedger(args.root)
    ticks = TickLedger(args.root)
    created = datetime.now(UTC)
    stamp = created.strftime("%Y%m%dT%H%M%SZ")
    out = (args.out or args.root / "snapshots") / f"{args.symbol}-{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    ledger_manifest = ledger.manifest(args.symbol)["timeframes"]
    per_tf: dict[str, Any] = {}
    latest_bar: dict[str, str] = {}
    for name in args.timeframes:
        frame = ledger.load(args.symbol, Timeframe(name))
        if frame.height == 0:
            continue
        path = out / f"{name}.parquet"
        frame.write_parquet(path)
        last = frame["timestamp"].max()
        latest_bar[name] = last.isoformat() if isinstance(last, datetime) else str(last)
        per_tf[name] = {
            "rows": frame.height,
            "first": frame["timestamp"].min(),
            "last": last,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "ledger_dataset_id": ledger_manifest.get(name, {}).get("dataset_id"),
        }
    head = hashlib.sha256(
        "|".join(f"{k}:{v['ledger_dataset_id']}" for k, v in sorted(per_tf.items())).encode()
    ).hexdigest()
    tick_last = ticks.latest(args.symbol)
    tick_baseline = args.root / args.symbol / "ticks" / "tick-manifest.json"
    try:
        tick_dataset = json.loads(tick_baseline.read_text(encoding="utf-8")).get("dataset_id")
    except (OSError, ValueError):
        tick_dataset = None
    manifest = {
        "symbol": args.symbol,
        "created_at": created.isoformat(),
        "provenance": {
            "source": "FTMO MT5 (first-party terminal; TradingView is not a source)",
            "volume_type": "TICK_VOLUME",
            "created_at_utc": created.isoformat(),
            **collector_facts(args.root),
            "ledger_head_sha256": head,
            "latest_closed_bar_per_timeframe": latest_bar,
            "latest_tick": None if tick_last is None else tick_last.isoformat(),
            "tick_ledger_dataset_id_at_last_verification": tick_dataset,
        },
        "timeframes": per_tf,
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8"
    )
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
