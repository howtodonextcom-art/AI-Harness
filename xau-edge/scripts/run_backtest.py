"""Backtest one baseline on one pre-registered period, judge it, and record the run.

Usage: ``uv run python scripts/run_backtest.py --strategy baseline_a --period development``
The test period needs ``--allow-test`` AND passing development and validation records for the same
parameters. Runs are research runs: no news calendar is available, which the printout states.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from xau_edge.domain.timeframe import Timeframe
from xau_edge.evaluation.periods import period_bounds
from xau_edge.evaluation.runner import STRATEGIES, Frames, run_strategy, strategy_params
from xau_edge.experiments.registry import ExperimentRegistry
from xau_edge.market_data.catalog import DatasetCatalog
from xau_edge.observability import configure_logging
from xau_edge.risk.prop_rules import load_prop_profile

FAMILY = "backtest"


def _latest_passed(registry: ExperimentRegistry, params: dict[str, object], period: str) -> bool:
    """True if the most recent record for these params and period passed its verdict."""
    runs = [r for r in registry.list(FAMILY) if r.params == params and r.period == period]
    return bool(runs) and runs[-1].metrics.get("verdict", {}).get("passed") is True


def _unlocked(registry: ExperimentRegistry, params: dict[str, object]) -> bool:
    """Test is open only if development and validation last passed and test was never run."""
    if any(r.params == params and r.period == "test" for r in registry.list(FAMILY)):
        return False
    return _latest_passed(registry, params, "development") and _latest_passed(
        registry, params, "validation"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", required=True, choices=STRATEGIES)
    parser.add_argument("--period", required=True)
    parser.add_argument("--root", default="data/raw")
    parser.add_argument("--prop", default="configs/prop/ftmo_2step.yaml")
    parser.add_argument("--allow-test", action="store_true")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    configure_logging("WARNING")

    period = period_bounds(args.period, allow_test=args.allow_test)
    registry = ExperimentRegistry("experiments/runs")
    params = strategy_params(args.strategy)
    if args.period == "test" and not _unlocked(registry, params):
        msg = "test period locked: development and validation must both pass for these parameters"
        raise PermissionError(msg)

    catalog = DatasetCatalog(args.root)
    loaded = {tf: catalog.load("XAUUSD", tf) for tf in (Timeframe.M5, Timeframe.M15, Timeframe.H1)}
    frames = Frames(
        loaded[Timeframe.M5].frame, loaded[Timeframe.M15].frame, loaded[Timeframe.H1].frame
    )
    tried = {json_key(r.params) for r in registry.list(FAMILY)} | {json_key(params)}
    run = run_strategy(
        args.strategy,
        frames,
        period,
        load_prop_profile(args.prop),
        variants=len(tried),
        seed=args.seed,
    )

    record = registry.record(
        family=FAMILY,
        name=f"{args.strategy}-{args.period}",
        dataset_ids={tf.value: ld.dataset_id for tf, ld in loaded.items()},
        feature_ids={},
        params=params,
        seeds={"bootstrap": args.seed},
        period=args.period,
        metrics={
            "metrics": asdict(run.metrics),
            "verdict": run.verdict.as_dict(),
            "signals": run.signal_count,
        },
        notes="research run: no news calendar; slippage 3 points assumed; commission 0 unverified",
    )
    out = Path("data/backtests")
    out.mkdir(parents=True, exist_ok=True)
    run.trades.write_parquet(out / f"trades_{args.strategy}_{args.period}.parquet")

    m = run.metrics
    print(
        f"{args.strategy} on {args.period}: {run.signal_count} signals, {m.trade_count} trades "
        f"({run.result.skipped.height} skipped)"
    )
    print(
        f"  net profit {m.net_profit:+.0f} USD ({m.net_return:+.2%}), PF {m.profit_factor}, "
        f"win rate {m.win_rate}, avg R {m.avg_r}, max DD {m.max_drawdown_pct:.2%}"
    )
    print(f"  sharpe {m.sharpe}, sortino {m.sortino}, calmar {m.calmar}, exposure {m.exposure:.1%}")
    pf = run.prop_feasibility
    print(
        f"  prop feasibility ({args.prop}): {len(pf['daily'])} day(s) below the daily floor; "
        f"max-loss floor hit: {pf['max_loss']}"
    )
    print(f"  variants counted: {run.verdict.variants}, alpha {run.verdict.alpha:.4f}")
    for name, c in run.verdict.criteria.items():
        print(f"    {'PASS' if c.passed else 'FAIL'} {name}: {c.value} (threshold {c.threshold})")
    print(f"  EDGE VERDICT: {'PASS' if run.verdict.passed else 'FAIL'}  recorded {record.id}")
    print("  assumptions: no news calendar; slippage 3 points; commission 0 (unverified)")


def json_key(params: dict[str, object]) -> str:
    return json.dumps(params, sort_keys=True)


if __name__ == "__main__":
    main()
