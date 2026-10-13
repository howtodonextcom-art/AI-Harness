"""Out-of-sample probability scoring against the no-skill base rate."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import polars as pl
from numpy.typing import NDArray

from xau_edge.models.calibration import (
    expected_calibration_error,
    log_loss,
    multiclass_brier,
)


@dataclass(frozen=True)
class ProbabilityReport:
    """Scores of a prediction frame; ``base_*`` is the training-frequency forecast."""

    n: int
    brier: float
    log_loss: float
    base_brier: float
    base_log_loss: float
    raw_brier: float | None
    raw_log_loss: float | None
    ece_per_class: tuple[float, float, float]

    @property
    def beats_base_rate(self) -> bool:
        """True only if BOTH Brier score and log loss are better than the base rate."""
        return self.brier < self.base_brier and self.log_loss < self.base_log_loss

    def as_dict(self) -> dict[str, Any]:
        """JSON-safe form for the experiment registry."""
        out = asdict(self)
        out["ece_per_class"] = list(self.ece_per_class)
        out["beats_base_rate"] = self.beats_base_rate
        return out


def score_predictions(
    pred: pl.DataFrame, *, base_rates: NDArray[np.float64] | None = None
) -> ProbabilityReport:
    """Brier, log loss, per-class calibration error, and the base-rate comparison.

    The no-skill forecast is the per-row ``base_*`` columns written by the walk-forward (class
    frequencies of that fold's own fit labels) unless ``base_rates`` is given explicitly.
    """
    if pred.height == 0:
        msg = "no predictions to score"
        raise ValueError(msg)
    p = pred.select("p_down", "p_neutral", "p_up").to_numpy()
    y = pred["y"].to_numpy().astype(np.int64)
    if base_rates is not None:
        base = np.tile(base_rates, (len(y), 1))
    elif {"base_down", "base_neutral", "base_up"} <= set(pred.columns):
        base = pred.select("base_down", "base_neutral", "base_up").to_numpy()
    else:
        msg = "pass base_rates or include base_* columns"
        raise ValueError(msg)
    raw = None
    if {"p_raw_down", "p_raw_neutral", "p_raw_up"} <= set(pred.columns):
        raw = pred.select("p_raw_down", "p_raw_neutral", "p_raw_up").to_numpy()
    ece = tuple(expected_calibration_error(p[:, k], (y == k).astype(float)) for k in range(3))
    return ProbabilityReport(
        n=len(y),
        brier=multiclass_brier(p, y),
        log_loss=log_loss(p, y),
        base_brier=multiclass_brier(base, y),
        base_log_loss=log_loss(base, y),
        raw_brier=None if raw is None else multiclass_brier(raw, y),
        raw_log_loss=None if raw is None else log_loss(raw, y),
        ece_per_class=(ece[0], ece[1], ece[2]),
    )
