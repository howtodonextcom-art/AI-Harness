"""Evaluate the four benchmark models on one pre-registered period and record every run.

Usage: ``uv run python scripts/run_models.py --period development``
The test period needs ``--allow-test`` and a passing, latest development AND validation record for
the same model configuration. ``--save-artifacts`` additionally trains each model on all labels
known before the test period and stores a versioned artifact (NOT an approval: see its metrics).
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from xau_edge.domain.timeframe import Timeframe
from xau_edge.evaluation.model_runner import (
    HORIZON,
    NEUTRAL_ATR,
    ModelRun,
    model_params,
    run_model,
)
from xau_edge.evaluation.periods import PERIODS, period_bounds
from xau_edge.evaluation.runner import Frames
from xau_edge.experiments.registry import ExperimentRegistry, current_code_version
from xau_edge.market_data.catalog import DatasetCatalog
from xau_edge.models.artifact import ModelArtifact, save_artifact
from xau_edge.models.calibration import OvRCalibrator
from xau_edge.models.dataset import MODEL_FEATURE_VERSION, ModelData, build_model_data
from xau_edge.models.walkforward import WalkForwardConfig, plan_fold
from xau_edge.models.zoo import HYPERPARAMETERS, MODELS
from xau_edge.observability import configure_logging
from xau_edge.risk.prop_rules import load_prop_profile

FAMILY = "model"


def _key(params: dict[str, object]) -> str:
    return json.dumps(params, sort_keys=True)


def _latest_passed(
    registry: ExperimentRegistry, params: dict[str, object], period: str, ids: dict[str, str]
) -> bool:
    """Latest record for these params and period passed on the SAME datasets."""
    runs = [
        r
        for r in registry.list(FAMILY)
        if r.params == params and r.period == period and r.dataset_ids == ids
    ]
    return bool(runs) and runs[-1].metrics.get("passed") is True


def _unlocked(registry: ExperimentRegistry, params: dict[str, object], ids: dict[str, str]) -> bool:
    if any(r.params == params and r.period == "test" for r in registry.list(FAMILY)):
        return False
    return _latest_passed(registry, params, "development", ids) and _latest_passed(
        registry, params, "validation", ids
    )


def _print(run: ModelRun, variants: int) -> None:
    if run.report is None or run.run is None:
        print(f"  {run.model}: no folds had enough history")
        return
    r, m = run.report, run.run.metrics
    print(
        f"  {run.model}: n={r.n} logloss {r.log_loss:.4f} (base {r.base_log_loss:.4f}) "
        f"brier {r.brier:.4f} (base {r.base_brier:.4f}) beats base: {r.beats_base_rate}"
    )
    print(
        f"     trades {m.trade_count}, net {m.net_return:+.2%}, PF {m.profit_factor}, "
        f"avg R {m.avg_r}, max DD {m.max_drawdown_pct:.2%}; edge criteria passed "
        f"{sum(c.passed for c in run.run.verdict.criteria.values())}/7 -> "
        f"{'PASS' if run.passed else 'FAIL'}  (variants {variants})"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", required=True)
    parser.add_argument("--models", nargs="*", default=list(MODELS))
    parser.add_argument("--calibration", default="sigmoid")
    parser.add_argument("--root", default="data/raw")
    parser.add_argument("--prop", default="configs/prop/ftmo_2step.yaml")
    parser.add_argument("--allow-test", action="store_true")
    parser.add_argument("--save-artifacts", action="store_true")
    args = parser.parse_args()
    configure_logging("WARNING")

    period = period_bounds(args.period, allow_test=args.allow_test)
    registry = ExperimentRegistry("experiments/runs")
    catalog = DatasetCatalog(args.root)
    loaded = {tf: catalog.load("XAUUSD", tf) for tf in (Timeframe.M5, Timeframe.M15, Timeframe.H1)}
    frames = Frames(
        loaded[Timeframe.M5].frame, loaded[Timeframe.M15].frame, loaded[Timeframe.H1].frame
    )
    data = build_model_data(frames.m15, Timeframe.M15, horizon=HORIZON, neutral_atr=NEUTRAL_ATR)
    prop = load_prop_profile(args.prop)
    ids = {tf.value: ld.dataset_id for tf, ld in loaded.items()}

    # K counts every variant tried across the backtest and model families
    tried = {_key(r.params) for fam in ("backtest", FAMILY) for r in registry.list(fam)}
    for name in args.models:
        tried.add(_key(model_params(name, args.calibration)))
    variants = len(tried)

    print(f"models on {args.period} (K={variants}):")
    for name in args.models:
        params = model_params(name, args.calibration)
        if args.period == "test" and not _unlocked(registry, params, ids):
            msg = f"test period locked for {name}: development and validation must both pass"
            raise PermissionError(msg)
        run = run_model(
            name, frames, period, prop, variants=variants, calibration=args.calibration, data=data
        )
        _print(run, variants)
        metrics: dict[str, object] = {"passed": run.passed}
        if run.report is not None and run.run is not None:
            metrics.update(
                probability=run.report.as_dict(),
                verdict=run.run.verdict.as_dict(),
                trades=run.run.metrics.trade_count,
                net_return=run.run.metrics.net_return,
            )
        registry.record(
            family=FAMILY,
            name=f"{name}-{args.period}",
            dataset_ids=ids,
            feature_ids={"model_features": MODEL_FEATURE_VERSION},
            params=params,
            seeds={"model": 7, "bootstrap": 7},
            period=args.period,
            metrics=metrics,
            notes="research run: no news calendar; slippage 3 points; commission 0 unverified",
        )
        out = Path("data/backtests")
        out.mkdir(parents=True, exist_ok=True)
        if run.predictions.height:
            run.predictions.write_parquet(out / f"pred_{name}_{args.period}.parquet")

    if args.save_artifacts:
        _save_artifacts(args.models, data, registry, args.calibration)


def _save_artifacts(
    models: list[str], data: ModelData, registry: ExperimentRegistry, calibration: str
) -> None:
    """Fit each model (and its calibrator) on labels known before the test period and store it."""
    cfg = WalkForwardConfig(horizon=data.horizon, calibration=calibration)
    cutoff = PERIODS["test"][0]
    plan = plan_fold(data, (cutoff, cutoff.replace(year=cutoff.year + 1)), cfg)
    if plan is None:
        msg = "not enough history before the test period to fit artifacts"
        raise RuntimeError(msg)
    commit, _ = current_code_version()
    stamp = datetime.now(UTC)
    for name in models:
        model = MODELS[name]().fit(data.X[plan.fit_idx], data.y[plan.fit_idx])
        calibrator = None
        if calibration != "none":
            raw = model.predict_proba(data.X[plan.cal_idx])
            calibrator = OvRCalibrator(calibration).fit(raw, data.y[plan.cal_idx])
        records = [r for r in registry.list(FAMILY) if r.params == model_params(name, calibration)]
        latest = {r.period: r.metrics.get("passed") for r in records}
        art = ModelArtifact(
            name=name,
            version=f"{MODEL_FEATURE_VERSION}-{stamp:%Y%m%dT%H%M%S}",
            training_period=(
                str(data.decision_time[plan.fit_idx[0]]),
                str(
                    data.decision_time[plan.cal_idx[-1] if plan.cal_idx.size else plan.fit_idx[-1]]
                ),
            ),
            feature_version=MODEL_FEATURE_VERSION,
            hyperparameters=HYPERPARAMETERS[name],
            metrics={"approved": False, "passed_by_period": latest, "calibration": calibration},
            trained_at=stamp.isoformat(),
            git_commit=commit,
        )
        folder = save_artifact("models", art, {"model": model, "calibrator": calibrator})
        print(f"  artifact {folder} (approved: False)")


if __name__ == "__main__":
    main()
