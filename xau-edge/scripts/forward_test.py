"""Replay the paper trader over recent bars of the local dataset (or run it on newly fetched bars).

Usage: ``uv run python scripts/forward_test.py --hours 6``

* The loop feeds M5 bars to the paper broker and decides at every M15 close using only data closed
  by then; every refusal reason is counted; nothing real is touched.
* On HISTORICAL bars this is a replay (labelled so), not forward evidence. A forward test is the
  same command run repeatedly on bars that did not exist when the signals were designed (append new
  bars to the raw store, rerun, keep ``data/paper/journal.jsonl``); conclusions need at least
  100 paper trades (`compare_paper_to_backtest`).
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta

from xau_edge.backtest.costs import CostModel
from xau_edge.domain.timeframe import Timeframe
from xau_edge.execution.forward import MIN_TRADES_FOR_CONCLUSION, replay
from xau_edge.execution.paper import PaperExecutionBroker
from xau_edge.execution.safety import ExecutionSafety, assert_live_trading_disabled
from xau_edge.execution.trader import PaperTrader
from xau_edge.experiments.registry import ExperimentRegistry
from xau_edge.market_data.catalog import DatasetCatalog
from xau_edge.observability import configure_logging
from xau_edge.risk.engine import RiskEngine, RiskLimits
from xau_edge.risk.prop_rules import load_prop_profile
from xau_edge.signals.engine import MarketFrames, generate_signal


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="data/raw")
    parser.add_argument("--prop", default="configs/prop/ftmo_2step.yaml")
    parser.add_argument(
        "--hours", type=float, default=6.0, help="window length ending at the last bar"
    )
    parser.add_argument("--journal", default="data/paper/replay-journal.jsonl")
    args = parser.parse_args()
    configure_logging("WARNING")
    assert_live_trading_disabled()

    catalog = DatasetCatalog(args.root)
    frames = MarketFrames(
        *(
            catalog.load("XAUUSD", tf).frame
            for tf in (Timeframe.M5, Timeframe.M15, Timeframe.H1, Timeframe.H4)
        )
    )
    last = frames.m5["timestamp"].max()
    if last is None:
        raise SystemExit("no data")
    if not isinstance(last, datetime):
        raise SystemExit("no data")
    end = last + Timeframe.M5.delta
    start = end - timedelta(hours=args.hours)
    registry = ExperimentRegistry("experiments/runs")
    broker = PaperExecutionBroker(
        100_000.0, costs=CostModel(), journal_path=args.journal, mode="replay"
    )
    trader = PaperTrader(
        broker, RiskEngine(RiskLimits(), load_prop_profile(args.prop)), ExecutionSafety()
    )
    result = replay(frames, trader, lambda at: generate_signal(frames, at, registry), start, end)
    print(f"mode: {result.mode} (historical bars: NOT forward evidence)")
    print(f"window {start.isoformat()} .. {end.isoformat()}")
    print(
        f"decisions {result.decisions}, orders placed {result.accepted}, trades closed {len(result.trades)}"
    )
    for reason, count in sorted(result.refusals.items(), key=lambda kv: -kv[1]):
        print(f"  refused x{count}: {reason}")
    print(f"a paper-vs-backtest conclusion needs {MIN_TRADES_FOR_CONCLUSION}+ paper trades")


if __name__ == "__main__":
    main()
