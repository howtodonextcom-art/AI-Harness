"""Measure the decision path stage by stage on the live collector files (read-only).

Stages: market loading (ledger tails + live.json), market-state features, decision + trade plan
(entry/SL/TP/RR/lot), JSON view, and the cached no-change step. Prints median / p95 in ms.

Usage: ``uv run python scripts/trade_perf.py [--runs 30]``
"""

from __future__ import annotations

import argparse
import json
import statistics
import tempfile
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from xau_edge.api.trade import build_trade_engine
from xau_edge.strategies.edge_program import SERVER_CLOCK
from xau_edge.trading.baseline import BaselineConfig, DecisionContext, decide
from xau_edge.trading.live_source import news_state
from xau_edge.trading.market_state import build_market_state


def timed(runs: int, fn: Callable[[], object]) -> dict[str, float]:
    samples: list[float] = []
    for _ in range(runs):
        started = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - started) * 1000)
    ordered = sorted(samples)
    return {
        "median_ms": round(statistics.median(samples), 1),
        "p95_ms": round(ordered[int(0.95 * (len(ordered) - 1))], 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=30)
    parser.add_argument("--out", default="data/trade/reports/perf.json")
    args = parser.parse_args()
    engine = build_trade_engine(Path("data/market"), Path(tempfile.mkdtemp()))
    now = datetime.now(UTC)
    snap = engine.source.load(now)
    quote = snap.quote
    state = build_market_state(
        snap.bars,
        now,
        spread_points=None if quote is None else quote.spread_points,
        news_state=news_state(now, None),
        broker_clock=SERVER_CLOCK,
        market_open=snap.market_open,
    )
    if snap.spec is None:
        msg = "no symbol_spec in live.json (collector not running the new code?)"
        raise SystemExit(msg)
    ctx = DecisionContext(
        spec=snap.spec,
        equity=10_000.0,
        market_open=snap.market_open,
        data_ok=snap.usable,
        spec_known=True,
        bid=None if quote is None else quote.bid,
        ask=None if quote is None else quote.ask,
    )
    cfg = BaselineConfig(allow_unknown_news=True)
    engine.step(now)
    report = {
        "runs": args.runs,
        "market_loading": timed(args.runs, lambda: engine.source.load(datetime.now(UTC))),
        "feature_computation": timed(
            args.runs,
            lambda: build_market_state(
                snap.bars,
                now,
                spread_points=None if quote is None else quote.spread_points,
                news_state="UNKNOWN",
                broker_clock=SERVER_CLOCK,
                market_open=snap.market_open,
            ),
        ),
        "decision_and_trade_plan": timed(args.runs, lambda: decide(state, ctx, cfg)),
        "json_view": timed(args.runs, engine.view),
        "step_without_change": timed(args.runs, lambda: engine.step(datetime.now(UTC))),
    }
    total = (
        report["market_loading"]["median_ms"]
        + report["feature_computation"]["median_ms"]
        + report["decision_and_trade_plan"]["median_ms"]
    )
    report["recompute_total_median_ms"] = round(total, 1)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
