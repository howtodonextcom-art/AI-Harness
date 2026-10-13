"""Statistics of the pre-specified analogue study (docs/evals/edge-criteria.md)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import polars as pl

from xau_edge.evaluation.bootstrap import block_bootstrap_ci


@dataclass(frozen=True)
class AnalogueStatistics:
    """Total and timing skill of the analogue direction, with day-block bootstrap intervals."""

    n: int
    total: float
    total_ci: tuple[float, float]
    timing: float
    timing_ci: tuple[float, float]
    drift: float
    share_long: float


def analogue_statistics(
    study: pl.DataFrame, *, seed: int = 7, n_resamples: int = 2000, alpha: float = 0.05
) -> AnalogueStatistics:
    """Evaluate ``sign(analogue_mean_atr) * realized_atr`` and its drift-free timing component."""
    usable = study.drop_nulls(["realized_atr", "analogue_mean_atr"])
    if usable.height == 0:
        msg = "no usable rows: every query lacks a realised outcome"
        raise ValueError(msg)
    sign = np.sign(usable["analogue_mean_atr"].to_numpy())
    realised = usable["realized_atr"].to_numpy()
    days = usable["timestamp"].dt.date().to_numpy()
    total_values = sign * realised
    timing_values = (sign - sign.mean()) * realised
    return AnalogueStatistics(
        n=int(usable.height),
        total=float(total_values.mean()),
        total_ci=block_bootstrap_ci(
            total_values, days, seed=seed, n_resamples=n_resamples, alpha=alpha
        ),
        timing=float(timing_values.mean()),
        timing_ci=block_bootstrap_ci(
            timing_values, days, seed=seed, n_resamples=n_resamples, alpha=alpha
        ),
        drift=float(realised.mean()),
        share_long=float((sign > 0).mean()),
    )
