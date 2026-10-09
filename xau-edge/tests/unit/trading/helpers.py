"""Synthetic data and states for the trading-core tests (no network, no broker, deterministic)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import polars as pl

from xau_edge.domain.timeframe import Timeframe
from xau_edge.trading.frames import MultiTfBars, from_frames
from xau_edge.trading.market_state import MarketState, TfSnapshot
from xau_edge.trading.sizing import SymbolSpec

T0 = datetime(2026, 3, 2, 0, 0, tzinfo=UTC)  # a Monday
SPEC = SymbolSpec()


def m1_series(
    minutes: int, *, seed: int = 1, drift: float = 0.0, vol: float = 0.25
) -> pl.DataFrame:
    """Continuous M1 bars (UTC, no calendar gaps) with a random walk plus a per-minute drift."""
    rng = np.random.default_rng(seed)
    steps = rng.normal(drift, vol, minutes)
    close = 2000.0 + np.cumsum(steps)
    open_ = np.concatenate([[2000.0], close[:-1]])
    high = np.maximum(open_, close) + np.abs(rng.normal(0, vol / 2, minutes))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, vol / 2, minutes))
    stamps = [T0 + timedelta(minutes=i) for i in range(minutes)]
    return pl.DataFrame(
        {
            "timestamp": pl.Series(stamps, dtype=pl.Datetime("us", "UTC")),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "tick_volume": rng.integers(50, 400, minutes),
            "spread": np.full(minutes, 25, dtype=np.int64),
            "real_volume": np.zeros(minutes, dtype=np.int64),
        }
    )


def resample(m1: pl.DataFrame, minutes: int) -> pl.DataFrame:
    """UTC-aligned OHLC aggregation (test-only; production uses the broker-clock resampler)."""
    return (
        m1.group_by_dynamic("timestamp", every=f"{minutes}m", closed="left", label="left")
        .agg(
            pl.col("open").first(),
            pl.col("high").max(),
            pl.col("low").min(),
            pl.col("close").last(),
            pl.col("tick_volume").sum(),
            pl.col("spread").last(),
            pl.col("real_volume").sum(),
        )
        .sort("timestamp")
    )


def multi_tf(minutes: int = 60 * 24 * 12, **kwargs: Any) -> MultiTfBars:
    """M1..H4 frames from one synthetic M1 series (the last bucket of each frame is partial)."""
    m1 = m1_series(minutes, **kwargs)
    frames = {Timeframe.M1: m1}
    for tf in (Timeframe.M5, Timeframe.M15, Timeframe.M30, Timeframe.H1, Timeframe.H4):
        frames[tf] = resample(m1, tf.minutes)
    return from_frames(frames)


def aligned_state(**over: Any) -> MarketState:
    """A bullish, fully aligned, healthy state that yields a BUY (override fields to break it)."""
    base: dict[str, Any] = {
        "timestamp": T0 + timedelta(days=3, hours=10),
        "symbol": "XAUUSD",
        "volume_type": "TICK_VOLUME",
        "h4_regime": "TREND_UP",
        "h1_trend": "BULLISH",
        "m30_structure": "UP",
        "m15_structure": "UP",
        "m15_pullback": "PULLBACK_IN_UPTREND",
        "m5_momentum": "UP",
        "m1_micro_state": "ACTIVE_UP",
        "atr_m1": 0.5,
        "atr_m5": 1.2,
        "atr_m15": 2.0,
        "atr_h1": 5.0,
        "tick_volume_m1": 200.0,
        "volume_zscore_m1": 0.8,
        "volume_ratio_m1_m5": 0.3,
        "spread": 25.0,
        "spread_percentile": 0.4,
        "spread_to_atr_m5": 0.2 * 0.01 / 1.2 * 100 * 0.0 + 0.05,
        "session": "LONDON",
        "price": 2000.0,
        "distance_to_recent_high": 8.0,
        "distance_to_recent_low": 3.0,
        "distance_to_support": 3.0,
        "distance_to_resistance": 20.0,
        "recent_swing_high": 2008.0,
        "recent_swing_low": 1997.0,
        "bos_state": "BOS_UP",
        "choch_state": "NONE",
        "volatility_regime": "NORMAL",
        "data_quality": "OK",
        "news_state": "CLEAR",
        "execution_quality": "GOOD",
        "available_timeframes": ("M1", "M5", "M15", "M30", "H1", "H4"),
        "stale_timeframes": (),
        "snapshots": {},
    }
    base.update(over)
    return MarketState(**base)


def snap(timeframe: str = "M5", **over: Any) -> TfSnapshot:
    """A minimal TfSnapshot (override swing levels etc.)."""
    base: dict[str, Any] = {
        "timeframe": timeframe,
        "bar_open": T0,
        "bar_closed": T0 + timedelta(minutes=5),
        "bars_used": 300,
        "close": 2000.0,
        "atr": 1.2,
        "atr_percentile": 0.5,
        "ema_fast": 1999.5,
        "ema_slow": 1995.0,
        "ema_slope_atr": 0.1,
        "price_vs_ema_atr": 0.4,
        "adx": 28.0,
        "plus_di": 25.0,
        "minus_di": 15.0,
        "rsi": 58.0,
        "roc": 0.001,
        "structure_trend": 1,
        "bos_recent": 1,
        "choch_recent": 0,
        "last_swing_high": 2008.0,
        "last_swing_low": 1997.0,
        "support": 1997.0,
        "resistance": 2020.0,
        "range_percentile": 0.6,
        "patterns": {},
        "volume_zscore": 0.5,
        "volume_percentile": 0.6,
        "volume_ratio": 1.1,
        "volume_acceleration": 0.2,
        "tick_volume": 200.0,
        "regime": "TREND_UP",
    }
    base.update(over)
    return TfSnapshot(**base)
