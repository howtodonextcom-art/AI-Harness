"""Pattern representation: ATR-normalised, scale-free, causal, with explicit validity."""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from tests.conftest import make_bars
from xau_edge.domain.timeframe import Timeframe
from xau_edge.features import indicators as ind
from xau_edge.patterns.representation import (
    PATTERN_COLUMNS,
    pattern_frame,
    pattern_values,
    window_validity,
    window_view,
)


def _walk(n: int = 300) -> pl.DataFrame:
    rng = np.random.default_rng(31)
    close = 2000 + np.cumsum(rng.normal(0, 2, n))
    open_ = np.concatenate([[2000.0], close[:-1]]) + rng.normal(
        0, 0.8, n
    )  # gaps: open != prev close
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 1, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 1, n))
    return make_bars(n, Timeframe.M15).with_columns(
        pl.Series("open", open_),
        pl.Series("high", high),
        pl.Series("low", low),
        pl.Series("close", close),
        pl.Series("tick_volume", rng.integers(50, 500, n)),
    )


def test_columns_follow_the_brief() -> None:
    assert PATTERN_COLUMNS == (
        "ret_atr",
        "body_atr",
        "upper_wick_atr",
        "lower_wick_atr",
        "range_atr",
        "volume_z",
    )
    frame = pattern_frame(_walk(), Timeframe.M15)
    assert frame.columns == ["timestamp", "available_at", *PATTERN_COLUMNS]


def test_values_match_hand_computation_on_every_bar() -> None:
    bars = _walk()
    atr = ind.atr(bars["high"].to_numpy(), bars["low"].to_numpy(), bars["close"].to_numpy(), 14)
    v = pattern_values(bars, atr_period=14, volume_window=20)
    o, h, lo, c = (bars[k].to_numpy() for k in ("open", "high", "low", "close"))
    rows = np.arange(20, bars.height)
    np.testing.assert_allclose(v[rows, 0], (c[rows] - c[rows - 1]) / atr[rows])
    np.testing.assert_allclose(v[rows, 1], (c[rows] - o[rows]) / atr[rows])
    np.testing.assert_allclose(v[rows, 2], (h[rows] - np.maximum(o, c)[rows]) / atr[rows])
    np.testing.assert_allclose(v[rows, 3], (np.minimum(o, c)[rows] - lo[rows]) / atr[rows])
    np.testing.assert_allclose(v[rows, 4], (h[rows] - lo[rows]) / atr[rows])
    assert (c < o).any()
    assert (c > o).any()


def test_warmup_is_nan_and_validity_masks_incomplete_windows() -> None:
    v = pattern_values(_walk(), atr_period=14, volume_window=20)
    assert np.isnan(v[:14]).any(axis=1).all()
    assert not np.isnan(v[40:]).any()
    valid = window_validity(v, 30)
    assert not valid[:11].any()  # windows ending before the first complete bar
    assert valid[-1]
    assert valid.size == v.shape[0] - 30 + 1


def test_a_single_missing_row_invalidates_every_window_containing_it() -> None:
    v = np.ones((10, 2))
    v[4, 1] = np.nan
    valid = window_validity(v, 3)
    assert valid.tolist() == [True, True, False, False, False, True, True, True]


def test_representation_is_scale_and_offset_free() -> None:
    bars = _walk()
    scaled = bars.with_columns((pl.col(c) * 3.0 + 500.0) for c in ("open", "high", "low", "close"))
    a = pattern_values(bars, atr_period=14, volume_window=20)
    b = pattern_values(scaled, atr_period=14, volume_window=20)
    np.testing.assert_allclose(a, b, equal_nan=True, rtol=1e-9, atol=1e-9)


def test_representation_is_causal() -> None:
    bars = _walk()
    full = pattern_values(bars, atr_period=14, volume_window=20)
    part = pattern_values(bars.head(200), atr_period=14, volume_window=20)
    np.testing.assert_array_equal(full[:200], part)


def test_window_view_shape_and_content_without_copy() -> None:
    v = np.arange(24, dtype=float).reshape(8, 3)
    view = window_view(v, 4)
    assert view.shape == (5, 4, 3)
    np.testing.assert_array_equal(view[2], v[2:6])
    assert np.shares_memory(view, v)


def test_window_view_rejects_bad_sizes() -> None:
    with pytest.raises(ValueError, match="window"):
        window_view(np.zeros((5, 2)), 0)
    assert window_view(np.zeros((3, 2)), 5).shape[0] == 0
