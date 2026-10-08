"""Edge Program report (T1.5, T1.6): results table, verdict, ledger rule 6 and the prop filter.

Reads the JSON results in ``experiments/edge_program`` and the per-trade files in
``data/backtests/edge_program``; it never runs a backtest and never touches Test-H or the holdout.
The prop Monte Carlo runs on the PESSIMISTIC trades of Dev-H + Val-H of the variant chosen by
ledger rule 6 (and of every variant with a Test-H PASS, if any).

Usage (from ``xau-edge``):
    uv run python scripts/edge_program_report.py
    uv run python scripts/edge_program_report.py --json experiments/edge_program/verdict.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import polars as pl

from xau_edge.evaluation.edge_verdict import (
    StageResult,
    latest,
    load_stage_results,
    program_verdict,
    select_best_pessimistic,
)
from xau_edge.evaluation.prop_mc import HORIZONS, PropMcResult, prop_monte_carlo


def _table(results: list[StageResult]) -> str:
    rows = [
        "| Variant | Period | Trades | Mean net R | Pessimistic mean net R | Stage | Failed criteria |",
        "|---|---|---:|---:|---:|---|---|",
    ]
    for (variant, period), r in sorted(latest(results).items()):
        mean = f"{r.mean_net_r:+.4f}" if r.mean_net_r is not None else "-"
        pess = f"{r.pessimistic_mean_net_r:+.4f}" if r.pessimistic_mean_net_r is not None else "-"
        failed = ", ".join(r.failed_criteria) or "-"
        verdict = "PASS" if r.stage_pass else "FAIL"
        rows.append(
            f"| {variant} | {period} | {r.trades} | {mean} | {pess} | {verdict} | {failed} |"
        )
    return "\n".join(rows)


def _trades(trades_dir: Path, results: list[StageResult], variant: str) -> pl.DataFrame:
    table = latest(results)
    frames = []
    for period in ("dev", "val"):
        stage = table[(variant, period)]
        path = trades_dir / f"trades_{variant}_{period}_pessimistic_{stage.registry_id}.parquet"
        frames.append(pl.read_parquet(path).select("exit_time", "net_r"))
    return pl.concat(frames).sort("exit_time")


def _mc(trades: pl.DataFrame) -> PropMcResult:
    return prop_monte_carlo(trades["net_r"].to_numpy(), trades["exit_time"].to_list())


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--results", default="experiments/edge_program")
    parser.add_argument("--trades", default="data/backtests/edge_program")
    parser.add_argument("--json", default=None, help="also write the summary as JSON")
    args = parser.parse_args()

    results = load_stage_results(args.results)
    verdict = program_verdict(results)
    best = select_best_pessimistic(results)
    print(_table(results))
    print()
    print(
        f"verdict: ({verdict}) " + ("EDGE VALIDATED" if verdict == "A" else "NO EDGE WITHIN BUDGET")
    )
    print(f"rule 6 eligible (>= 100 trades on dev and val): {', '.join(best.eligible) or 'none'}")
    print(f"rule 6 best: {best.variant} score={best.score} positive={best.positive}")

    summary: dict[str, object] = {
        "verdict": verdict,
        "rule6": {
            "variant": best.variant,
            "score_pessimistic_mean_net_r": best.score,
            "positive_in_both": best.positive,
            "eligible": list(best.eligible),
        },
        "stages": len(latest(results)),
    }
    if best.variant is not None:
        mc = _mc(_trades(Path(args.trades), results, best.variant))
        print(
            f"prop MC on {best.variant} (pessimistic, dev+val, {mc.n_days} trade days, "
            f"{mc.n_paths} paths, seed {mc.seed}):"
        )
        for risk in (0.1, 0.25, 0.5, 1.0):
            probs = mc.breach_probability[risk]
            line = ", ".join(f"{h}d={probs[h]:.3f}" for h in HORIZONS)
            print(f"  risk {risk:.2f}%/trade: P(breach) {line}")
        print(f"  max safe risk (P90 <= 5%): {mc.max_safe_risk_pct}")
        print(f"  override risk = min(max safe, 0.25): {mc.override_risk_pct}")
        summary["prop_mc"] = {
            "variant": best.variant,
            "n_days": mc.n_days,
            "n_paths": mc.n_paths,
            "seed": mc.seed,
            "max_safe_risk_pct": mc.max_safe_risk_pct,
            "override_risk_pct": mc.override_risk_pct,
            "breach_probability": {
                str(r): {str(h): p for h, p in v.items()} for r, v in mc.breach_probability.items()
            },
        }
    if args.json:
        Path(args.json).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
