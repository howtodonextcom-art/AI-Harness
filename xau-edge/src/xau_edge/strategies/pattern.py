"""Baseline C: trade only what historical analogues suggest (and the analogue study behind it).

For each query bar the leakage-safe search (ADR-0013) returns the ``k`` most similar earlier
windows; the outcomes that followed them (read only up to ``e + outcome_horizon``, which the
search rule keeps before the query window) give analogue probabilities. The query's own realised
outcome is attached for evaluation ONLY; it is never an input. The signal fires when the analogue
edge ``p_up - p_down`` reaches ``edge_threshold`` (fixed a priori) with at least ``min_matches``
usable analogues.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import polars as pl
from pydantic import BaseModel, ConfigDict, Field, model_validator

from xau_edge.domain.timeframe import Timeframe
from xau_edge.features import indicators as ind
from xau_edge.features.feature_set import check_bars
from xau_edge.outcomes.engine import OutcomeConfig, compute_outcomes
from xau_edge.outcomes.summary import summarise
from xau_edge.patterns.representation import pattern_values, window_validity
from xau_edge.patterns.search import PatternIndex, SearchConfig
from xau_edge.strategies.baselines import signals_from_direction


class PatternConfig(BaseModel):
    """Analogue study and Baseline C parameters (pre-specified in docs/evals/edge-criteria.md)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    window: int = Field(default=30, ge=2)
    horizon_guard: int = Field(default=60, ge=1)
    k: int = Field(default=20, ge=1)
    method: str = "euclidean"
    outcome_horizon: int = Field(default=20, ge=1)
    neutral_threshold_atr: float = Field(default=0.5, ge=0)
    min_matches: int = Field(default=15, ge=1)
    edge_threshold: float = Field(default=0.2, ge=0)
    step: int = Field(default=4, ge=1)
    stop_atr: float = Field(default=1.5, gt=0)
    target_atr: float = Field(default=3.0, gt=0)

    @model_validator(mode="after")
    def _guard_covers_horizon(self) -> PatternConfig:
        if self.outcome_horizon > self.horizon_guard:
            msg = "outcome_horizon must not exceed horizon_guard (the leakage margin)"
            raise ValueError(msg)
        return self


def analogue_study(
    bars: pl.DataFrame,
    timeframe: Timeframe,
    config: PatternConfig,
    *,
    period: tuple[datetime, datetime],
) -> pl.DataFrame:
    """Analogue statistics for every ``step``-th bar with ``period[0] <= timestamp < period[1]``."""
    check_bars(bars)
    values = pattern_values(bars)
    high, low, close = (bars[k].to_numpy() for k in ("high", "low", "close"))
    atr = ind.atr(high, low, close, 14)
    valid = window_validity(values, config.window)
    index = PatternIndex(
        values,
        SearchConfig(
            window=config.window,
            horizon=config.horizon_guard,
            k=config.k,
            method=config.method,
        ),
    )
    outcome_cfg = OutcomeConfig(
        horizons=(config.outcome_horizon,), neutral_threshold_atr=config.neutral_threshold_atr
    )
    ts = bars["timestamp"]
    in_period = ((ts >= period[0]) & (ts < period[1])).to_numpy()
    positions = np.flatnonzero(in_period)
    queries = positions[:: config.step] if positions.size else positions
    # realised outcomes may only use bars inside the period (later bars belong to another period)
    period_end_index = int((ts < period[1]).sum())

    rows: list[dict[str, object]] = []
    for position in queries:
        q = int(position)
        if q < config.window - 1 or not valid[q - config.window + 1]:
            continue
        found = index.search(q)
        if not found.matches:
            continue
        ends = np.array([m.end_index for m in found.matches], dtype=np.intp)
        summary = summarise(compute_outcomes(high, low, close, atr, ends, outcome_cfg), 0)
        if summary is None:
            continue
        realised = compute_outcomes(high, low, close, atr, np.array([q]), outcome_cfg)
        rows.append(
            {
                "timestamp": ts[q],
                "decision_time": bars["timestamp"][q] + timeframe.delta,
                "q_index": q,
                "n_matches": summary.n,
                "p_up": summary.p_up,
                "p_down": summary.p_down,
                "analogue_mean_atr": summary.mean_forward_atr,
                "realized_atr": float(realised.forward_atr[0, 0])
                if realised.complete[0, 0] and q + config.outcome_horizon < period_end_index
                else None,
                "edge": summary.p_up - summary.p_down,
                "atr": float(atr[q]),
                "best_distance": found.best_distance,
                "median_distance": found.median_distance,
            }
        )
    schema: dict[str, pl.DataType | type[pl.DataType]] = {
        "timestamp": pl.Datetime("us", "UTC"),
        "decision_time": pl.Datetime("us", "UTC"),
        "q_index": pl.Int64,
        "n_matches": pl.Int64,
        "p_up": pl.Float64,
        "p_down": pl.Float64,
        "analogue_mean_atr": pl.Float64,
        "realized_atr": pl.Float64,
        "atr": pl.Float64,
        "edge": pl.Float64,
        "best_distance": pl.Float64,
        "median_distance": pl.Float64,
    }
    return pl.DataFrame(rows, schema=schema)


def baseline_c(study: pl.DataFrame, config: PatternConfig | None = None) -> pl.DataFrame:
    """Signals from an analogue study (needs ``n_matches``, ``p_up``, ``p_down``, ``atr``)."""
    cfg = config or PatternConfig()
    edge = (pl.col("p_up") - pl.col("p_down")).round(12)
    enough = pl.col("n_matches") >= cfg.min_matches
    direction = study.select(
        pl.when(enough & (edge >= cfg.edge_threshold))
        .then(1)
        .when(enough & (edge <= -cfg.edge_threshold))
        .then(-1)
        .otherwise(0)
        .alias("d")
    )["d"]
    frame = study.with_columns(
        pl.col("atr").alias("atr_14"), pl.col("decision_time").alias("available_at")
    )
    return signals_from_direction(
        frame,
        direction,
        name="baseline_c",
        stop_atr=cfg.stop_atr,
        target_atr=cfg.target_atr,
        max_hold_bars=cfg.outcome_horizon,
    )
