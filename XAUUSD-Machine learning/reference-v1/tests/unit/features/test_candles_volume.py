"""Candle geometry and volume features: hand values, degenerate bars, causality."""

from __future__ import annotations

import numpy as np
import pytest

from xau_edge.features.candles import candle_geometry
from xau_edge.features.volume import volume_change, volume_zscore


def test_bullish_candle_hand_values() -> None:
    g = candle_geometry(
        np.array([10.0]), np.array([14.0]), np.array([9.0]), np.array([13.0]), np.array([2.0])
    )
    assert g.body_size[0] == pytest.approx(3.0)
    assert g.upper_wick[0] == pytest.approx(1.0)
    assert g.lower_wick[0] == pytest.approx(1.0)
    assert g.body_to_range[0] == pytest.approx(3.0 / 5.0)
    assert g.body_to_atr[0] == pytest.approx(1.5)
    assert g.upper_wick_to_atr[0] == pytest.approx(0.5)
    assert g.lower_wick_to_atr[0] == pytest.approx(0.5)
    assert g.range_to_atr[0] == pytest.approx(2.5)


def test_bearish_candle_wicks_use_max_and_min_of_open_close() -> None:
    g = candle_geometry(
        np.array([13.0]), np.array([14.0]), np.array([9.0]), np.array([10.0]), np.array([1.0])
    )
    assert g.upper_wick[0] == pytest.approx(1.0)
    assert g.lower_wick[0] == pytest.approx(1.0)
    assert g.body_size[0] == pytest.approx(3.0)


def test_zero_range_and_unavailable_atr_give_nan_ratios() -> None:
    flat = np.array([5.0, 5.0])
    g = candle_geometry(flat, flat, flat, flat, np.array([np.nan, 0.0]))
    assert np.isnan(g.body_to_range).all()
    assert np.isnan(g.body_to_atr).all()
    assert np.isnan(g.range_to_atr).all()
    assert g.body_size.tolist() == [0.0, 0.0]


def test_geometry_rejects_inconsistent_bars() -> None:
    with pytest.raises(ValueError, match="high"):
        candle_geometry(
            np.array([10.0]), np.array([9.0]), np.array([9.5]), np.array([10.0]), np.array([1.0])
        )
    with pytest.raises(ValueError, match="length"):
        candle_geometry(np.ones(2), np.ones(2), np.ones(2), np.ones(2), np.ones(3))


def test_geometry_is_row_local_so_it_cannot_look_ahead() -> None:
    rng = np.random.default_rng(1)
    o = 100 + rng.normal(size=50)
    c = o + rng.normal(size=50)
    h = np.maximum(o, c) + abs(rng.normal(size=50))
    lo = np.minimum(o, c) - abs(rng.normal(size=50))
    atr = np.full(50, 1.5)
    full = candle_geometry(o, h, lo, c, atr)
    part = candle_geometry(o[:20], h[:20], lo[:20], c[:20], atr[:20])
    for f, p in zip(full, part, strict=True):
        np.testing.assert_array_equal(f[:20], p)


def test_volume_zscore_hand_values_and_warmup() -> None:
    v = np.array([1.0, 2.0, 3.0, 4.0, 10.0])
    z = volume_zscore(v, 3)
    assert np.isnan(z[:2]).all()
    window = v[2:5]
    assert z[4] == pytest.approx((10.0 - window.mean()) / window.std(ddof=1))


def test_volume_zscore_constant_window_is_nan() -> None:
    assert np.isnan(volume_zscore(np.full(10, 7.0), 4)[-1])


def test_volume_zscore_window_must_be_at_least_two() -> None:
    with pytest.raises(ValueError, match="window"):
        volume_zscore(np.arange(5.0), 1)


def test_volume_change_hand_values() -> None:
    out = volume_change(np.array([100.0, 150.0, 0.0, 10.0]))
    assert np.isnan(out[0])
    assert out[1] == pytest.approx(0.5)
    assert out[2] == pytest.approx(-1.0)
    assert np.isnan(out[3])  # previous volume is zero


def test_volume_features_do_not_repaint() -> None:
    v = np.random.default_rng(3).integers(50, 500, 80).astype(float)
    np.testing.assert_array_equal(volume_zscore(v, 10)[:50], volume_zscore(v[:50], 10))
    np.testing.assert_array_equal(volume_change(v)[:50], volume_change(v[:50]))


def test_volume_rejects_negative_values() -> None:
    with pytest.raises(ValueError, match="negative"):
        volume_zscore(np.array([1.0, -1.0, 2.0]), 2)
    with pytest.raises(ValueError, match="negative"):
        volume_change(np.array([1.0, -1.0]))
