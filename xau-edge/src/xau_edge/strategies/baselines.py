"""Transparent baseline strategies (brief section 17). They only emit signals; entries, fills,
costs and exits are the backtest's job.

All parameters are fixed a priori (docs/evals/edge-criteria.md) and are not to be tuned on the
evaluation periods. A signal row means: at ``decision_time`` (the close of bar ``timestamp``)
the strategy wants to enter ``direction`` at the next bar's open with a stop ``stop_atr`` x ATR and
a target ``target_atr`` x ATR away, and give up after ``max_hold_bars``.

* A: H1 structure trend, M15 RSI pullback, M5 break of structure in the trend direction.
* B: EMA 9 > 20 > 50 stack with RSI 14 in the momentum band, on the first bar the state appears.
* C (pattern similarity only) lives in ``strategies/pattern.py``.
"""

from __future__ import annotations

from typing import Final

import polars as pl
from pydantic import BaseModel, ConfigDict, Field

from xau_edge.strategies.context import align_to

SIGNAL_COLUMNS: Final = (
    "timestamp",
    "decision_time",
    "direction",
    "atr",
    "stop_atr",
    "target_atr",
    "max_hold_bars",
    "strategy",
)


class BaselineAConfig(BaseModel):
    """Baseline A parameters."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rsi_long_max: float = 45.0
    rsi_short_min: float = 55.0
    stop_atr: float = Field(default=1.5, gt=0)
    target_atr: float = Field(default=3.0, gt=0)
    max_hold_bars: int = Field(default=48, ge=1)
    cooldown_bars: int = Field(default=12, ge=0)


class BaselineBConfig(BaseModel):
    """Baseline B parameters."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rsi_long_band: tuple[float, float] = (50.0, 70.0)
    rsi_short_band: tuple[float, float] = (30.0, 50.0)
    stop_atr: float = Field(default=1.5, gt=0)
    target_atr: float = Field(default=3.0, gt=0)
    max_hold_bars: int = Field(default=48, ge=1)


def signals_from_direction(
    frame: pl.DataFrame,
    direction: pl.Series,
    *,
    name: str,
    stop_atr: float,
    target_atr: float,
    max_hold_bars: int,
    cooldown_bars: int = 0,
) -> pl.DataFrame:
    """Turn a per-row direction series (-1, 0, 1) into signal rows, applying a cooldown."""
    rows = frame.select("timestamp", "available_at", "atr_14").with_columns(
        direction.alias("direction"), pl.int_range(pl.len()).alias("_i")
    )
    candidates = rows.filter((pl.col("direction") != 0) & pl.col("atr_14").is_not_null())
    keep: list[int] = []
    last = -(10**9)
    for i in candidates["_i"].to_list():
        if i - last >= max(cooldown_bars, 1):
            keep.append(i)
            last = i
    picked = candidates.filter(pl.col("_i").is_in(keep))
    return picked.select(
        pl.col("timestamp"),
        pl.col("available_at").alias("decision_time"),
        pl.col("direction").cast(pl.Int8),
        pl.col("atr_14").alias("atr"),
        pl.lit(stop_atr).alias("stop_atr"),
        pl.lit(target_atr).alias("target_atr"),
        pl.lit(max_hold_bars, dtype=pl.Int32).alias("max_hold_bars"),
        pl.lit(name).alias("strategy"),
    )


def baseline_a(
    m5: pl.DataFrame,
    m15: pl.DataFrame,
    h1: pl.DataFrame,
    config: BaselineAConfig | None = None,
) -> pl.DataFrame:
    """Baseline A on M5: needs bos, choch, atr_14 (M5), rsi_14 (M15) and trend (H1)."""
    cfg = config or BaselineAConfig()
    joined = align_to(m5, m15, ["rsi_14"], prefix="m15_")
    joined = align_to(joined, h1, ["trend"], prefix="h1_")
    break_up = (pl.col("bos") == 1) | (pl.col("choch") == 1)
    break_down = (pl.col("bos") == -1) | (pl.col("choch") == -1)
    long_ok = (pl.col("h1_trend") == 1) & (pl.col("m15_rsi_14") <= cfg.rsi_long_max) & break_up
    short_ok = (pl.col("h1_trend") == -1) & (pl.col("m15_rsi_14") >= cfg.rsi_short_min) & break_down
    direction = joined.select(
        pl.when(long_ok).then(1).when(short_ok).then(-1).otherwise(0).alias("d")
    )["d"]
    return signals_from_direction(
        joined,
        direction,
        name="baseline_a",
        stop_atr=cfg.stop_atr,
        target_atr=cfg.target_atr,
        max_hold_bars=cfg.max_hold_bars,
        cooldown_bars=cfg.cooldown_bars,
    )


def baseline_b(frame: pl.DataFrame, config: BaselineBConfig | None = None) -> pl.DataFrame:
    """Baseline B on one timeframe. Needs ``ema_9, ema_20, ema_50, rsi_14, atr_14``."""
    cfg = config or BaselineBConfig()
    up_stack = (pl.col("ema_9") > pl.col("ema_20")) & (pl.col("ema_20") > pl.col("ema_50"))
    down_stack = (pl.col("ema_9") < pl.col("ema_20")) & (pl.col("ema_20") < pl.col("ema_50"))
    rsi = pl.col("rsi_14")
    long_now = up_stack & rsi.is_between(*cfg.rsi_long_band)
    short_now = down_stack & rsi.is_between(*cfg.rsi_short_band)
    state = frame.select(
        pl.when(long_now.fill_null(value=False))
        .then(1)
        .when(short_now.fill_null(value=False))
        .then(-1)
        .otherwise(0)
        .alias("state")
    )["state"]
    fresh = state.ne(state.shift(1, fill_value=0)) & state.ne(0)
    direction = pl.select(pl.when(fresh).then(state).otherwise(0).alias("d"))["d"]
    return signals_from_direction(
        frame,
        direction,
        name="baseline_b",
        stop_atr=cfg.stop_atr,
        target_atr=cfg.target_atr,
        max_hold_bars=cfg.max_hold_bars,
    )
