"""Structure + regime as a frame aligned to the bar index, with the same timing as features."""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import polars as pl
import pytest

from tests.conftest import make_bars
from xau_edge.domain.timeframe import Timeframe
from xau_edge.structure.frame import structure_frame
from xau_edge.structure.swings import StructureConfig, analyse_structure


def _walk(n: int = 900, timeframe: Timeframe = Timeframe.M15) -> pl.DataFrame:
    rng = np.random.default_rng(21)
    close = 2000 + np.cumsum(rng.normal(0, 2, n))
    open_ = np.concatenate([[2000.0], close[:-1]])
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 1, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 1, n))
    return make_bars(n, timeframe).with_columns(
        pl.Series("open", open_),
        pl.Series("high", high),
        pl.Series("low", low),
        pl.Series("close", close),
    )


def test_columns_and_alignment() -> None:
    bars = _walk()
    out = structure_frame(bars, Timeframe.M15)
    assert out.height == bars.height
    assert out["timestamp"].equals(bars["timestamp"])
    assert (out["available_at"] - out["timestamp"]).unique().to_list() == [timedelta(minutes=15)]
    assert {
        "swing_high",
        "swing_low",
        "high_label",
        "low_label",
        "trend",
        "bos",
        "choch",
        "support",
        "resistance",
        "dist_support_atr",
        "dist_resistance_atr",
        "regime",
    } <= set(out.columns)


def test_matches_the_array_level_analysis() -> None:
    bars = _walk()
    cfg = StructureConfig(left=3, right=3)
    out = structure_frame(bars, Timeframe.M15, structure=cfg)
    raw = analyse_structure(bars["high"], bars["low"], bars["close"], cfg)
    assert out["trend"].to_numpy().tolist() == raw.trend.tolist()
    np.testing.assert_array_equal(
        out["swing_high"].fill_null(np.nan).to_numpy(), raw.last_swing_high
    )


def test_frame_never_repaints() -> None:
    bars = _walk()
    full = structure_frame(bars, Timeframe.M15)
    for cut in (300, 650):
        assert full.head(cut).equals(structure_frame(bars.head(cut), Timeframe.M15))


def test_regime_is_null_during_warmup_and_valid_afterwards() -> None:
    out = structure_frame(_walk(), Timeframe.M15)
    assert out["regime"].head(100).null_count() == 100
    assert out["regime"].tail(300).null_count() == 0
    assert set(out["regime"].drop_nulls().unique()) <= {
        "TREND_UP",
        "TREND_DOWN",
        "RANGE",
        "HIGH_VOLATILITY",
        "LOW_VOLATILITY",
        "SHOCK",
    }


def test_distances_are_atr_normalised_and_signed_by_side() -> None:
    out = structure_frame(_walk(), Timeframe.M15).drop_nulls(["dist_support_atr"])
    assert (out["dist_support_atr"] > 0).all()
    res = structure_frame(_walk(), Timeframe.M15).drop_nulls(["dist_resistance_atr"])
    assert (res["dist_resistance_atr"] > 0).all()


def test_rejects_unsorted_bars() -> None:
    with pytest.raises(ValueError, match="sorted"):
        structure_frame(_walk(50).reverse(), Timeframe.M15)
