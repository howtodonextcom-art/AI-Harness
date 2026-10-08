"""Run one benchmark model over one evaluation period: probabilities, scores, backtest, verdict."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import polars as pl

from xau_edge.domain.timeframe import Timeframe
from xau_edge.evaluation.runner import Frames, StrategyRun, judge_signals
from xau_edge.models.dataset import ModelData, build_model_data
from xau_edge.models.scoring import ProbabilityReport, score_predictions
from xau_edge.models.signals import ModelSignalConfig, model_signals
from xau_edge.models.walkforward import WalkForwardConfig, walk_forward_predict
from xau_edge.models.zoo import HYPERPARAMETERS, MODELS
from xau_edge.risk.prop_rules import PropProfile

HORIZON = 20
NEUTRAL_ATR = 0.5


@dataclass(frozen=True)
class ModelRun:
    """Predictions, probability scores and the trading evaluation of one model-period."""

    model: str
    predictions: pl.DataFrame
    report: ProbabilityReport | None
    run: StrategyRun | None
    params: dict[str, Any]

    @property
    def passed(self) -> bool:
        """Both the probability scoring and every edge criterion must pass."""
        return (
            self.report is not None
            and self.run is not None
            and self.report.beats_base_rate
            and self.run.verdict.passed
        )


def model_params(model: str, calibration: str) -> dict[str, Any]:
    """Registry identity of a model configuration (everything that defines the variant)."""
    if model not in MODELS:
        msg = f"unknown model {model!r}; choose from {list(MODELS)}"
        raise ValueError(msg)
    return {
        "model": model,
        "calibration": calibration,
        "horizon": HORIZON,
        "neutral_atr": NEUTRAL_ATR,
        "signal": ModelSignalConfig().model_dump(mode="json"),
        "hyperparameters": HYPERPARAMETERS[model],
    }


def run_model(
    model: str,
    frames: Frames,
    period: tuple[datetime, datetime],
    prop: PropProfile,
    *,
    variants: int,
    calibration: str = "sigmoid",
    data: ModelData | None = None,
    seed: int = 7,
    n_resamples: int = 2000,
) -> ModelRun:
    """Walk-forward predict ``period`` with ``model`` and evaluate probabilities and trading."""
    params = model_params(model, calibration)
    d = data or build_model_data(
        frames.m15, Timeframe.M15, horizon=HORIZON, neutral_atr=NEUTRAL_ATR
    )
    cfg = WalkForwardConfig(horizon=HORIZON, calibration=calibration)
    pred = walk_forward_predict(d, MODELS[model], period, cfg)
    if pred.height == 0:
        return ModelRun(model, pred, None, None, params)
    report = score_predictions(pred)
    signals = model_signals(pred, ModelSignalConfig())
    run = judge_signals(
        model,
        signals,
        Timeframe.M15,
        frames,
        period,
        prop,
        params=params,
        variants=variants,
        seed=seed,
        n_resamples=n_resamples,
    )
    return ModelRun(model, pred, report, run, params)
