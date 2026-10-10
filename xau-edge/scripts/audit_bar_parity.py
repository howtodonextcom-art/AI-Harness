"""Independent stored-bars-versus-terminal parity audit (read-only).

    uv run --extra mt5 python scripts/audit_bar_parity.py [--days 14] [--write]

For every timeframe, the CLOSED bars of the last ``--days`` days are fetched with an independent
``copy_rates_range`` call and compared, bar by bar, with the bar ledger (OHLC, tick volume, spread,
real volume, plus bars present on one side only). Every difference is classified and carries its
provenance from the ledger's event log (first seen, last seen, any ``BAR_REPAIRED`` old/new values).
Also checks the ledger for duplicates and bars off their timeframe boundary.

Exit code 0: no UNEXPLAINED difference (identical, or every difference is a documented, audited
revision). Exit code 1: at least one unexplained difference, listed in the output.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_edge.market_data.collector import ALL_TIMEFRAMES  # noqa: E402
from xau_edge.market_data.ledger import BarLedger  # noqa: E402
from xau_edge.market_data.mt5.runtime import DEFAULT_TERMINAL, open_feed  # noqa: E402
from xau_edge.market_data.parity import (  # noqa: E402
    LATE_TICK_VOLUME,
    MISSING_IN_STORE,
    ONLY_IN_STORE,
    PRICE_DIFFERENCE,
    SPREAD_DIFFERENCE,
    UNSETTLED_VOLUME,
    VOLUME_OUT_OF_BOUND,
    BarDifference,
    compare,
)

# the audit vocabulary (what a human reads) for each machine kind
LABEL = {
    LATE_TICK_VOLUME: "LATE TICK",
    UNSETTLED_VOLUME: "FORMING-BAR ERROR",
    VOLUME_OUT_OF_BOUND: "UNKNOWN",
    PRICE_DIFFERENCE: "UNKNOWN",
    SPREAD_DIFFERENCE: "UNKNOWN",
    MISSING_IN_STORE: "REPAIR BUG",
    ONLY_IN_STORE: "BOUNDARY ERROR",
}


def provenance(events: list[dict[str, Any]], tf: str, stamp: datetime) -> dict[str, Any]:
    """first_seen / last_seen as differing, and every audited repair of this bar."""
    iso = stamp.isoformat()
    seen = [
        e["at"]
        for e in events
        if e.get("kind") == "BAR_CHANGED"
        and e.get("timeframe") == tf
        and iso in e.get("timestamps", [])
    ]
    repairs = [
        {"at": e["at"], "reason": e.get("reason"), "old": b["old"], "new": b["new"]}
        for e in events
        if e.get("kind") == "BAR_REPAIRED" and e.get("timeframe") == tf
        for b in e.get("bars", [])
        if b["timestamp"] == iso
    ]
    return {
        "first_seen": min(seen) if seen else None,
        "last_seen": max(seen) if seen else None,
        "audited_repairs": repairs,
    }


def structural(frame: pl.DataFrame, minutes: int) -> dict[str, int]:
    """Duplicates and bars off their timeframe boundary.

    Bars align to BROKER time (UTC+2/+3 with DST), so the check is on the minute inside the hour
    (every timeframe up to H1) and, for H4, on the hour residue: at most two (the two DST states).
    """
    if frame.height == 0:
        return {"rows": 0, "duplicates": 0, "off_boundary": 0}
    ts = frame["timestamp"]
    step = min(minutes, 60)
    off = frame.filter(pl.col("timestamp").dt.minute() % step != 0).height
    if minutes >= 240:
        residues = Counter(h % (minutes // 60) for h in frame["timestamp"].dt.hour().to_list())
        off += sum(n for _, n in residues.most_common()[2:])  # beyond the two DST alignments
    return {"rows": frame.height, "duplicates": frame.height - ts.n_unique(), "off_boundary": off}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terminal-path", default=DEFAULT_TERMINAL)
    parser.add_argument("--root", type=Path, default=ROOT / "data" / "market")
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--days", type=float, default=14.0)
    parser.add_argument("--write", action="store_true", help="write data/market/parity-audit.json")
    args = parser.parse_args()
    now = datetime.now(UTC)
    start = now - timedelta(days=args.days)
    ledger = BarLedger(args.root)
    events = ledger.events(args.symbol)
    report: dict[str, Any] = {
        "generated_at": now.isoformat(),
        "window": {"from": start.isoformat(), "to": now.isoformat()},
        "timeframes": {},
        "differences": [],
    }
    with open_feed(args.terminal_path) as feed:
        mapping = feed.discover_symbol(args.symbol)
        for tf in ALL_TIMEFRAMES:
            terminal = feed.bars_range(mapping.broker_symbol, tf, start, now)
            stored = ledger.load(args.symbol, tf, start=start)
            stored = stored.filter((pl.col("timestamp") + pl.duration(minutes=tf.minutes)) <= now)
            diffs: list[BarDifference] = compare(stored, terminal, tf, now)
            counts = Counter(LABEL[d.kind] for d in diffs)
            report["timeframes"][tf.value] = {
                "compared_terminal": terminal.height,
                "compared_stored": stored.height,
                "identical": terminal.height - len(diffs),
                "differences": len(diffs),
                "by_class": dict(counts),
                "structure": structural(stored, tf.minutes),
            }
            for d in diffs:
                record = d.as_record()
                record["class"] = LABEL[d.kind]
                record["provenance"] = provenance(events, tf.value, d.timestamp)
                record["repairable_by_policy"] = d.kind == LATE_TICK_VOLUME
                report["differences"].append(record)
    open_diffs = report["differences"]
    unexplained = [d for d in open_diffs if not d["repairable_by_policy"]]
    report["summary"] = {
        "differences": len(open_diffs),
        "policy_repairable": len(open_diffs) - len(unexplained),
        "unexplained": len(unexplained),
        "structural_problems": sum(
            t["structure"]["duplicates"] + t["structure"]["off_boundary"]
            for t in report["timeframes"].values()
        ),
    }
    print(json.dumps({k: report[k] for k in ("window", "timeframes", "summary")}, indent=2))
    for d in unexplained[:20]:
        print("UNEXPLAINED", json.dumps(d, default=str))
    if args.write:
        target = args.root / "parity-audit.json"
        target.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print("written", target)
    return 1 if unexplained or report["summary"]["structural_problems"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
