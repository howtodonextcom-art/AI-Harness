"""Sanity replay of the operational baseline on BURNED development data (never on the holdout).

Purpose: check frequency, payoff shape, cost sensitivity and pathologies of the whole decision
pipeline. It is NOT evidence of an edge and must not be used to tune parameters. Windows at or after
2026-05-01 (the locked holdout) are refused.

    uv run python scripts/trading_baseline_sanity.py --from 2025-09-01 --to 2025-09-15 [--write]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_edge.domain.timeframe import Timeframe  # noqa: E402
from xau_edge.market_data.catalog import DatasetCatalog  # noqa: E402
from xau_edge.market_data.profiles import BrokerProfile  # noqa: E402
from xau_edge.market_data.resampling import resample_bars  # noqa: E402
from xau_edge.trading.baseline import BaselineConfig, DecisionContext  # noqa: E402
from xau_edge.trading.frames import from_frames  # noqa: E402
from xau_edge.trading.position_manager import ManagerConfig  # noqa: E402
from xau_edge.trading.replay import (  # noqa: E402
    CostAssumptions,
    decision_times,
    parity_mismatches,
    run_decisions,
    simulate,
    summarise,
)
from xau_edge.trading.sizing import SymbolSpec  # noqa: E402

LOCK = datetime(2026, 5, 1, tzinfo=UTC)
OUT = ROOT / "docs" / "reports" / "trading-baseline-sanity.json"


def parse(day: str) -> datetime:
    return datetime.fromisoformat(day).replace(tzinfo=UTC)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="start", required=True)
    parser.add_argument("--to", dest="end", required=True)
    parser.add_argument("--parity-sample", type=int, default=40)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    start, end = parse(args.start), parse(args.end)
    if end > LOCK or start >= end:
        sys.exit("refused: the window must end before 2026-05-01 (locked holdout) and be non-empty")
    profile = BrokerProfile.from_yaml(ROOT / "configs" / "brokers" / "ftmo_demo.yaml")
    catalog = DatasetCatalog(ROOT / "data" / "raw")
    frames = {
        tf: catalog.load("XAUUSD", tf).frame.filter(pl.col("timestamp") < end)
        for tf in (Timeframe.M5, Timeframe.M15, Timeframe.H1, Timeframe.H4)
    }
    frames[Timeframe.M30] = resample_bars(
        frames[Timeframe.M15],
        Timeframe.M15,
        Timeframe.M30,
        clock=profile.clock,
        calendar=profile.validation.calendar,
    ).frame
    bars = from_frames(frames)
    ctx = DecisionContext(spec=SymbolSpec(), equity=100_000.0)
    cfg = BaselineConfig()
    times = decision_times(bars, start, end)
    decisions = run_decisions(bars, times, ctx, cfg)
    days = (end - start).total_seconds() / 86400
    counts = Counter(s.decision.value for _, s in decisions)
    refusals = Counter(r.value for _, s in decisions for r in s.refusal_reasons)
    manager = ManagerConfig(max_hold_minutes=180)
    base = simulate(bars, decisions, manager)
    stressed = simulate(
        bars, decisions, manager, costs=CostAssumptions(spread_multiplier=2.0, slippage_points=6.0)
    )
    sample = times[:: max(1, len(times) // max(1, args.parity_sample))][: args.parity_sample]
    mismatches = parity_mismatches(bars, sample, ctx, cfg)
    report = {
        "class": "D (sanity replay on burned development data; not evidence of an edge)",
        "window": [start.isoformat(), end.isoformat()],
        "timeframes_used": [tf.value for tf in bars.available()],
        "m1": "not available in the stored data (state treats M1 as UNKNOWN)",
        "decision_times": len(times),
        "decisions": dict(counts),
        "refusals": dict(refusals.most_common()),
        "trades_base_costs": summarise(base, days),
        "trades_double_costs": summarise(stressed, days),
        "parity_sample": len(sample),
        "parity_mismatches": [t.isoformat() for t in mismatches],
        "config": cfg.model_dump(mode="json"),
    }
    text = json.dumps(report, indent=2, default=str)
    print(text)
    if args.write:
        OUT.write_text(text + "\n", encoding="utf-8")
    return 0 if not mismatches else 3


if __name__ == "__main__":
    raise SystemExit(main())
