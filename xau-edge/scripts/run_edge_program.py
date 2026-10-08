"""Run Edge Program variants (H01..H06 grid) on Dev-H, Val-H or, once, Test-H.

Usage (from ``xau-edge``):

    uv run python scripts/run_edge_program.py --all --period dev
    uv run python scripts/run_edge_program.py --hypothesis H03 --period val
    uv run python scripts/run_edge_program.py --variant H03-c0.9 --period test --confirm-single-test-run

Frozen rules live in ``src/xau_edge/evaluation/edge_program.py``. Guards: nothing at or after
2025-05-01 is ever read into a period; ``--period test`` needs ``--confirm-single-test-run``, a
recorded stage PASS on dev AND val for every requested variant, and no earlier test record (a
"started" record is written before the test run, so even a crash consumes the single attempt).
The research files must match ``docs/research/edge-program/data-manifest.json`` exactly.
Every run is recorded in the experiment registry and written as a JSON result; per-trade parquet
files (both scenarios) feed the prop Monte Carlo.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from xau_edge.evaluation.edge_program import (
    EDGE_PERIODS,
    check_test_allowed,
    edge_period,
    execute,
    load_research_data,
    manifest_dataset_ids,
)
from xau_edge.experiments.registry import ExperimentRegistry
from xau_edge.market_data.profiles import BrokerProfile
from xau_edge.observability import configure_logging
from xau_edge.risk.prop_rules import load_prop_profile
from xau_edge.strategies.edge_program import SPECS, VARIANTS, Variant, get_variant, variants_of


def _selected(args: argparse.Namespace) -> list[Variant]:
    if args.variant:
        return [get_variant(args.variant)]
    if args.hypothesis:
        return variants_of(args.hypothesis)
    return list(VARIANTS.values())


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--variant", choices=list(VARIANTS))
    which.add_argument("--hypothesis", choices=list(SPECS))
    which.add_argument("--all", action="store_true")
    parser.add_argument("--period", required=True, choices=list(EDGE_PERIODS))
    parser.add_argument("--confirm-single-test-run", action="store_true")
    parser.add_argument("--root", default="data/research_history")
    parser.add_argument("--manifest", default="docs/research/edge-program/data-manifest.json")
    parser.add_argument("--profile", default="configs/brokers/ftmo_demo.yaml")
    parser.add_argument("--prop", default="configs/prop/ftmo_2step.yaml")
    parser.add_argument("--registry", default="experiments/runs")
    parser.add_argument("--out", default="experiments/edge_program")
    parser.add_argument("--trades-out", default="data/backtests/edge_program")
    args = parser.parse_args()
    configure_logging("WARNING")

    variants = _selected(args)
    edge_period(args.period)  # unknown or holdout-touching periods are refused before any I/O
    registry = ExperimentRegistry(args.registry)
    if args.period == "test":
        expected = manifest_dataset_ids(args.manifest)
        for v in variants:  # refuse before reading any market data
            check_test_allowed(
                registry,
                v.variant_id,
                confirmed=args.confirm_single_test_run,
                dataset_ids=expected,
            )

    profile = BrokerProfile.from_yaml(args.profile)
    data = load_research_data(args.root, args.manifest, validation=profile.validation)
    print(f"datasets verified against the manifest: {data.dataset_ids}")
    for tf, issues in data.validation.items():
        listed = ", ".join(f"{i['code']}[{i['severity']}]={i['count']}" for i in issues) or "none"
        print(f"  {tf} validator issues (reported, not repaired): {listed}")

    runs = execute(
        variants,
        args.period,
        data,
        load_prop_profile(args.prop),
        registry,
        out_dir=Path(args.out),
        confirm_single_test_run=args.confirm_single_test_run,
        validation=profile.validation,
        trades_dir=Path(args.trades_out),
    )
    for done in runs:
        run = done.run
        verdict = run.base.verdict
        assert verdict is not None  # noqa: S101 - the base scenario is always judged
        failed = [name for name, c in verdict.criteria.items() if not c.passed]
        print(
            f"{run.variant.variant_id} {args.period}: {run.signal_count} signals, "
            f"{run.base.trades.height} trades, mean net R base {run.base.mean_net_r} / "
            f"pessimistic {run.pessimistic.mean_net_r}; criteria failed: {failed or 'none'}; "
            f"STAGE {'PASS' if run.stage_pass else 'FAIL'}  registry {done.record.id} -> "
            f"{done.result_path}"
        )
    print(
        "assumptions: no news calendar; spread max(recorded, 30) pts; slippage 3/6 pts; "
        "commission 0 (unverified); K = 21, 20,000 resamples, seed 7"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
