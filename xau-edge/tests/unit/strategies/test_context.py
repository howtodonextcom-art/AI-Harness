"""build_context joins features and structure on the same rows without look-ahead."""

from __future__ import annotations

import numpy as np
import polars as pl

from tests.conftest import make_bars
from xau_edge.domain.timeframe import Timeframe
from xau_edge.strategies.context import build_context


def _bars(n: int = 400) -> pl.DataFrame:
    rng = np.random.default_rng(2)
    close = 2000 + np.cumsum(rng.normal(0, 2, n))
    open_ = np.concatenate([[2000.0], close[:-1]])
    return make_bars(n, Timeframe.M15).with_columns(
        pl.Series("open", open_),
        pl.Series("high", np.maximum(open_, close) + 1.0),
        pl.Series("low", np.minimum(open_, close) - 1.0),
        pl.Series("close", close),
    )


def test_context_has_features_structure_and_close_on_the_same_rows() -> None:
    bars = _bars()
    ctx = build_context(bars, Timeframe.M15)
    assert ctx.height == bars.height
    assert ctx["timestamp"].equals(bars["timestamp"])
    for col in ("rsi_14", "ema_50", "atr_14", "trend", "bos", "choch", "regime", "close"):
        assert col in ctx.columns, col
    assert ctx.columns.count("timestamp") == 1
    assert ctx.columns.count("available_at") == 1


def test_context_never_repaints() -> None:
    bars = _bars()
    full = build_context(bars, Timeframe.M15)
    assert full.head(250).equals(build_context(bars.head(250), Timeframe.M15))
