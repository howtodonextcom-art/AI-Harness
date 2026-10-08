"""Model dataset: scale-free features, forward labels, no look-ahead."""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from tests.conftest import make_bars
from xau_edge.domain.timeframe import Timeframe
from xau_edge.models.dataset import FEATURE_NAMES, WARMUP_ROWS, build_model_data
from xau_edge.outcomes.engine import OutcomeConfig, compute_outcomes


def _bars(n: int = 700, seed: int = 5, scale: float = 1.0) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    close = 2000 + np.cumsum(rng.normal(0, 2, n)) + 20 * np.sin(np.arange(n) / 17)
    open_ = np.concatenate([[2000.0], close[:-1]]) + rng.normal(0, 0.5, n)
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 1, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 1, n))
    return make_bars(n, Timeframe.M15).with_columns(
        pl.Series("open", open_ * scale),
        pl.Series("high", high * scale),
        pl.Series("low", low * scale),
        pl.Series("close", close * scale),
        pl.Series("tick_volume", rng.integers(50, 500, n)),
    )


def test_shapes_names_and_alignment() -> None:
    bars = _bars()
    d = build_model_data(bars, Timeframe.M15, horizon=20)
    assert d.X.shape == (bars.height, len(FEATURE_NAMES))
    assert len(set(FEATURE_NAMES)) == len(FEATURE_NAMES)
    assert d.y.shape == (bars.height,)
    assert d.decision_time.shape == (bars.height,)
    assert d.atr.shape == (bars.height,)
    assert d.regime.shape == (bars.height,)


def test_decision_time_is_the_bar_close() -> None:
    bars = _bars(50)
    d = build_model_data(bars, Timeframe.M15, horizon=5)
    assert d.decision_time[0] - bars["timestamp"][0] == __import__("datetime").timedelta(minutes=15)


def test_labels_match_the_outcome_engine() -> None:
    bars = _bars()
    d = build_model_data(bars, Timeframe.M15, horizon=20, neutral_atr=0.5)
    high, low, close = (bars[k].to_numpy() for k in ("high", "low", "close"))
    table = compute_outcomes(
        high, low, close, d.atr, np.arange(bars.height), OutcomeConfig(horizons=(20,))
    )
    ok = table.complete[:, 0]
    assert (d.y[ok] == table.direction[ok, 0] + 1).all()
    assert (d.y[~ok] == -1).all()
    assert (~ok).sum() >= 20  # the last horizon rows have no label


def test_usable_rows_exclude_warmup_and_unlabelled_rows() -> None:
    d = build_model_data(_bars(), Timeframe.M15, horizon=20)
    assert not d.usable[:WARMUP_ROWS].any()
    assert not d.usable[-20:].any()
    assert d.usable.sum() > 300
    assert (d.y[d.usable] >= 0).all()


def test_features_are_scale_free() -> None:
    a = build_model_data(_bars(), Timeframe.M15, horizon=20)
    b = build_model_data(_bars(scale=3.0), Timeframe.M15, horizon=20)
    np.testing.assert_allclose(a.X, b.X, rtol=1e-6, atol=1e-9, equal_nan=True)
    np.testing.assert_array_equal(a.y, b.y)


def test_features_never_use_future_bars() -> None:
    bars = _bars()
    full = build_model_data(bars, Timeframe.M15, horizon=20)
    part = build_model_data(bars.head(500), Timeframe.M15, horizon=20)
    np.testing.assert_allclose(full.X[:500], part.X, equal_nan=True, rtol=0, atol=0)
    # labels of the last horizon rows of the shortened data are unknown, the rest agree
    np.testing.assert_array_equal(full.y[:480], part.y[:480])


def test_regime_one_hot_and_session_columns_exist() -> None:
    for name in (
        "regime_TREND_UP",
        "regime_SHOCK",
        "session_LONDON",
        "session_OFF_HOURS",
        "hour_sin",
    ):
        assert name in FEATURE_NAMES


def test_horizon_must_be_positive() -> None:
    with pytest.raises(ValueError, match="horizon"):
        build_model_data(_bars(60), Timeframe.M15, horizon=0)
