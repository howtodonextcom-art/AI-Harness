"""Run the pre-specified analogue study on one evaluation period and record it.

Usage: ``uv run python scripts/run_analogue_study.py --period development``
The test period is refused unless ``--allow-test`` is given (single use per finished candidate).
The study frame goes to ``data/patterns/`` and the run to ``experiments/runs/`` (both git-ignored).
"""

from __future__ import annotations

import argparse
import time
from dataclasses import asdict
from pathlib import Path

from xau_edge.domain.timeframe import Timeframe
from xau_edge.evaluation.periods import period_bounds
from xau_edge.evaluation.protocol import FAMILY, evaluate, is_test_period_unlocked, required_alpha
from xau_edge.evaluation.study_stats import analogue_statistics
from xau_edge.experiments.registry import ExperimentRegistry
from xau_edge.market_data.catalog import DatasetCatalog
from xau_edge.observability import configure_logging
from xau_edge.strategies.pattern import PatternConfig, analogue_study


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", required=True)
    parser.add_argument("--timeframe", default="M15")
    parser.add_argument("--root", default="data/raw")
    parser.add_argument("--allow-test", action="store_true")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    configure_logging("WARNING")

    start, end = period_bounds(args.period, allow_test=args.allow_test)
    registry = ExperimentRegistry("experiments/runs")
    config = PatternConfig()
    params = config.model_dump(mode="json")
    if args.period == "test" and not is_test_period_unlocked(registry, params):
        msg = "test period locked: development and validation must both pass for this config"
        raise PermissionError(msg)
    timeframe = Timeframe.parse(args.timeframe)
    loaded = DatasetCatalog(args.root).load("XAUUSD", timeframe)
    began = time.perf_counter()
    study = analogue_study(loaded.frame, timeframe, config, period=(start, end))
    alpha = required_alpha(max(registry.variant_count(FAMILY), 1))
    stats = analogue_statistics(study, seed=args.seed, alpha=alpha)
    passed = evaluate(stats)
    elapsed = time.perf_counter() - began

    out_dir = Path("data/patterns")
    out_dir.mkdir(parents=True, exist_ok=True)
    study.write_parquet(
        out_dir / f"study_{timeframe.value}_{args.period}_{loaded.dataset_id}.parquet"
    )
    record = registry.record(
        family=FAMILY,
        name=f"{timeframe.value}-{args.period}",
        dataset_ids={timeframe.value: loaded.dataset_id},
        feature_ids={},
        params=params,
        seeds={"bootstrap": args.seed},
        period=args.period,
        metrics={**asdict(stats), "alpha": alpha, "passed": passed},
    )
    level = f"{100 * (1 - alpha):.1f}%"
    print(
        f"{args.period}: {study.height} queries ({stats.n} with realised outcome) in {elapsed:.0f}s"
    )
    print(
        f"  total  {stats.total:+.4f} ATR  {level} CI [{stats.total_ci[0]:+.4f}, {stats.total_ci[1]:+.4f}]"
    )
    print(
        f"  timing {stats.timing:+.4f} ATR  {level} CI [{stats.timing_ci[0]:+.4f}, {stats.timing_ci[1]:+.4f}]"
    )
    print(f"  drift {stats.drift:+.4f} ATR; analogues lean long {stats.share_long:.1%}")
    print(f"  pre-registered rule: {'PASS' if passed else 'FAIL'}")
    print(f"  recorded {record.id}; variants in family: {registry.variant_count(FAMILY)}")


if __name__ == "__main__":
    main()
