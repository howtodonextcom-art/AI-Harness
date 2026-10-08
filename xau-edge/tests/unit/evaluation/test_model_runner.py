"""Model runner end to end on synthetic frames (code paths only; no market meaning)."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from tests.conftest import MONDAY, make_bars
from xau_edge.domain.timeframe import Timeframe
from xau_edge.evaluation.model_runner import HORIZON, ModelRun, model_params, run_model
from xau_edge.evaluation.runner import Frames
from xau_edge.models.dataset import build_model_data
from xau_edge.risk.prop_rules import load_prop_profile

PROP = load_prop_profile(Path(__file__).parents[3] / "configs" / "prop" / "ftmo_2step.yaml")


def _walk(n: int, tf: Timeframe, seed: int) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    step = 1.0 * (tf.minutes / 5) ** 0.5
    close = (
        2000 + np.cumsum(rng.normal(0, step, n)) + 8 * np.sin(np.arange(n) * 5 / tf.minutes / 40)
    )
    open_ = np.concatenate([[2000.0], close[:-1]])
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.4, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.4, n))
    return make_bars(n, tf).with_columns(
        pl.Series("open", open_),
        pl.Series("high", high),
        pl.Series("low", low),
        pl.Series("close", close),
        pl.Series("tick_volume", rng.integers(50, 500, n)),
    )


@pytest.fixture(scope="module")
def frames() -> Frames:
    return Frames(
        m5=_walk(20_000, Timeframe.M5, 1),
        m15=_walk(6_500, Timeframe.M15, 2),
        h1=_walk(1_700, Timeframe.H1, 3),
    )


def test_model_params_identify_the_variant_and_reject_unknown_models() -> None:
    a = model_params("logistic", "sigmoid")
    assert a["model"] == "logistic"
    assert a["horizon"] == HORIZON
    assert a != model_params("logistic", "isotonic")
    assert a != model_params("xgboost", "sigmoid")
    with pytest.raises(ValueError, match="logistic"):
        model_params("magic", "sigmoid")


def test_run_model_returns_probabilities_scores_and_a_trading_verdict(frames: Frames) -> None:
    last = frames.m15["timestamp"][-1]
    period = (last - timedelta(days=15), last)
    data = build_model_data(frames.m15, Timeframe.M15, horizon=HORIZON)
    run = run_model("logistic", frames, period, PROP, variants=4, data=data, n_resamples=100)
    assert isinstance(run, ModelRun)
    assert run.predictions.height > 500
    assert run.report is not None
    assert run.report.n == run.predictions.height
    assert run.run is not None
    assert run.run.verdict.variants == 4
    # the prediction frame only contains decisions inside the period
    assert (run.predictions["decision_time"] >= period[0]).all()
    assert (run.predictions["decision_time"] < period[1]).all()
    assert run.passed == (run.report.beats_base_rate and run.run.verdict.passed)


def test_a_period_without_enough_history_returns_an_empty_run(frames: Frames) -> None:
    early = (MONDAY, MONDAY + timedelta(days=10))
    run = run_model("logistic", frames, early, PROP, variants=1, n_resamples=50)
    assert run.predictions.height == 0
    assert run.report is None
    assert run.run is None
    assert not run.passed
