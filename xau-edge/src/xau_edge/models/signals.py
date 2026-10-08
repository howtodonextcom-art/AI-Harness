"""Turn calibrated class probabilities into trade signals (or nothing).

A signal needs BOTH a clear probability edge over the opposite direction and a minimum probability
for the chosen direction; otherwise the answer is WAIT (no row). The label column is never read.
"""

from __future__ import annotations

import polars as pl
from pydantic import BaseModel, ConfigDict, Field

from xau_edge.strategies.baselines import SIGNAL_COLUMNS, signals_from_direction


class ModelSignalConfig(BaseModel):
    """Decision thresholds (fixed a priori, not tuned on evaluation data)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    edge_threshold: float = Field(default=0.15, ge=0)
    min_probability: float = Field(default=0.40, ge=0, le=1)
    stop_atr: float = Field(default=1.5, gt=0)
    target_atr: float = Field(default=3.0, gt=0)
    outcome_horizon: int = Field(default=20, ge=1)


def model_signals(pred: pl.DataFrame, config: ModelSignalConfig | None = None) -> pl.DataFrame:
    """Signals for the rows of a walk-forward prediction frame."""
    cfg = config or ModelSignalConfig()
    if pred.height == 0:
        return pl.DataFrame(schema=dict.fromkeys(SIGNAL_COLUMNS, pl.Null))
    edge = (pl.col("p_up") - pl.col("p_down")).round(12)
    long_ok = (edge >= cfg.edge_threshold) & (pl.col("p_up").round(12) >= cfg.min_probability)
    short_ok = (edge <= -cfg.edge_threshold) & (pl.col("p_down").round(12) >= cfg.min_probability)
    direction = pred.select(
        pl.when(long_ok).then(1).when(short_ok).then(-1).otherwise(0).alias("d")
    )["d"]
    frame = pred.select(
        pl.col("timestamp"),
        pl.col("decision_time").alias("available_at"),
        pl.col("atr").alias("atr_14"),
        pl.col("regime"),
    )
    return signals_from_direction(
        frame,
        direction,
        name="model",
        stop_atr=cfg.stop_atr,
        target_atr=cfg.target_atr,
        max_hold_bars=cfg.outcome_horizon,
    )
