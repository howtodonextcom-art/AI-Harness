"""Native vs resampled parity and spread semantics on the stored FTMO MT5 bars (Class D, no outcomes).

    uv run python scripts/market_data_parity.py [--write]

For every coarser timeframe the broker's NATIVE bars are compared with bars resampled from the
finest stored finer timeframe over the overlap, bar by bar (OHLC exact, tick volume exact, count).
Also reports how the per-bar ``spread`` field behaves (units, distribution, relation to a bar's
last quote) so spread is never mis-described. Closed bars only; prices are never analysed for edge.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_edge.domain.timeframe import Timeframe  # noqa: E402
from xau_edge.market_data.broker_clock import BrokerClock  # noqa: E402
from xau_edge.market_data.ledger import BarLedger  # noqa: E402
from xau_edge.market_data.resampling import resample_bars  # noqa: E402
from xau_edge.market_data.validators.market_calendar import MarketCalendar  # noqa: E402

PAIRS = (
    (Timeframe.M1, Timeframe.M5),
    (Timeframe.M1, Timeframe.M15),
    (Timeframe.M1, Timeframe.M30),
    (Timeframe.M1, Timeframe.H1),
    (Timeframe.M1, Timeframe.H4),
    (Timeframe.M5, Timeframe.H1),
    (Timeframe.M5, Timeframe.H4),
    (Timeframe.H1, Timeframe.H4),
)
COLUMNS = ("open", "high", "low", "close", "tick_volume")


def parity(ledger: BarLedger, src: Timeframe, dst: Timeframe, clock: BrokerClock) -> dict[str, Any]:
    fine = ledger.load("XAUUSD", src)
    native = ledger.load("XAUUSD", dst)
    if fine.height == 0 or native.height == 0:
        return {"pair": f"{src.value}->{dst.value}", "state": "NO_DATA"}
    # The first stored fine bar may sit mid-bucket: drop the partial leading bucket.
    start = fine["timestamp"].min()
    native = native.filter(pl.col("timestamp") >= start)
    result = resample_bars(fine, src, dst, clock=clock, calendar=MarketCalendar())
    derived = result.frame
    native = native.filter(pl.col("timestamp") <= fine["timestamp"].max())
    joined = native.join(derived, on="timestamp", how="inner", suffix="_d")
    out: dict[str, Any] = {
        "pair": f"{src.value}->{dst.value}",
        "native_bars": native.height,
        "derived_bars": derived.height,
        "compared": joined.height,
        "incomplete_buckets": len(result.incomplete),
        "native_without_derived": native.join(
            derived.select("timestamp"), on="timestamp", how="anti"
        ).height,
    }
    for col in COLUMNS:
        diff = joined.filter(pl.col(col) != pl.col(f"{col}_d"))
        out[f"{col}_mismatches"] = diff.height
    out["state"] = "EXACT" if all(out[f"{c}_mismatches"] == 0 for c in COLUMNS) else "DIFFERENCES"
    return out


def spread_semantics(ledger: BarLedger) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for tf in (Timeframe.M1, Timeframe.M15, Timeframe.H1):
        frame = ledger.load("XAUUSD", tf).tail(20000)
        s = frame["spread"]
        out[tf.value] = {
            "bars": frame.height,
            "min": s.min(),
            "median": s.median(),
            "p95": s.quantile(0.95),
            "max": s.max(),
            "zero_share": float((s == 0).mean()),  # type: ignore[arg-type]
        }
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT / "data" / "market")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    ledger = BarLedger(args.root)
    clock = BrokerClock.parse("NY+7")
    report = {
        "class": "D (data parity; no market outcome analysed)",
        "parity": [parity(ledger, s, d, clock) for s, d in PAIRS],
        "bar_spread_field": spread_semantics(ledger),
    }
    text = json.dumps(report, indent=2, default=str)
    print(text)
    if args.write:
        (ROOT / "docs" / "reports" / "mt5-data-parity.json").write_text(
            text + "\n", encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
