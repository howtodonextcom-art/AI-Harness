"""Dump the full gate vector of every M5-close decision in a BURNED window (diagnostics only).

Uses the same inputs as the live desk (tail windows, the broker spec, the bar spread as quote) and
the ``BASELINE`` named by ``--version``. Writes JSON lines to ``data/trade/reports/funnel/``.

Usage: ``uv run python scripts/signal_funnel_dump.py --start 2025-11-03 --end 2025-12-01``
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl

from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.ledger import BarLedger
from xau_edge.strategies.edge_program import SERVER_CLOCK
from xau_edge.trading.baseline import BaselineConfig, DecisionContext
from xau_edge.trading.decision_core import SnapshotInputs, evaluate
from xau_edge.trading.frames import MultiTfBars, from_frames
from xau_edge.trading.funnel import gate_vector, raw_features
from xau_edge.trading.live_source import TAILS, spec_from_broker
from xau_edge.trading.sizing import SymbolSpec

BURNED_FROM = datetime(2025, 5, 1, tzinfo=UTC)
BURNED_TO = datetime(2026, 5, 1, tzinfo=UTC)
WARMUP = {
    Timeframe.M1: timedelta(days=4),
    Timeframe.M5: timedelta(days=10),
    Timeframe.M15: timedelta(days=20),
    Timeframe.M30: timedelta(days=30),
    Timeframe.H1: timedelta(days=60),
    Timeframe.H4: timedelta(days=200),
}
EQUITY = 10_000.0


def tail_view(bars: MultiTfBars, at: datetime) -> MultiTfBars:
    closed = bars.truncated(at)
    return MultiTfBars({tf: df.tail(TAILS[tf]) for tf, df in closed.frames.items()})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--root", default="data/market")
    parser.add_argument("--out-dir", default="data/trade/reports/funnel")
    args = parser.parse_args()
    start = datetime.fromisoformat(args.start).replace(tzinfo=UTC)
    end = datetime.fromisoformat(args.end).replace(tzinfo=UTC)
    if start < BURNED_FROM or end > BURNED_TO:
        msg = "refused: window must lie inside the burned period 2025-05-01..2026-04-30"
        raise SystemExit(msg)
    ledger = BarLedger(Path(args.root))
    bars = from_frames(
        {
            tf: ledger.load("XAUUSD", tf, start - w, end + timedelta(days=1))
            for tf, w in WARMUP.items()
        }
    )
    live = json.loads((Path(args.root) / "live.json").read_text(encoding="utf-8"))
    spec = spec_from_broker(live.get("symbol_spec")) or SymbolSpec()
    cfg = BaselineConfig(allow_unknown_news=True)
    m5 = bars.frames[Timeframe.M5]
    rows = m5.filter((pl.col("available_at") >= start) & (pl.col("available_at") < end))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"v1.1_{args.start}_{args.end}.jsonl"
    with target.open("w", encoding="utf-8") as handle:
        for row in rows.iter_rows(named=True):
            at = row["available_at"]
            spread, close = float(row["spread"]), float(row["close"])
            bid, ask = close, close + spread * spec.point
            inputs = SnapshotInputs(
                tail_view(bars, at), at, bid, ask, spread, spec, EQUITY, "UNKNOWN", True, True
            )
            state, signal = evaluate(inputs, cfg, SERVER_CLOCK)
            ctx = DecisionContext(
                spec=spec, equity=EQUITY, market_open=True, data_ok=True, spec_known=True,
                bid=bid, ask=ask,
            )  # fmt: skip
            record = {
                "at": at.isoformat(),
                "decision": signal.decision.value,
                "refusals": [r.value for r in signal.refusal_reasons],
                "gates": gate_vector(state, ctx, cfg),
                "f": raw_features(state),
            }
            handle.write(json.dumps(record) + "\n")
    print(target)


if __name__ == "__main__":
    main()
