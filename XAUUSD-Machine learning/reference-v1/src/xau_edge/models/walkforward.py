"""Walk-forward prediction: expanding window, monthly folds, embargo, held-out calibration.

For a fold starting at row ``f`` the training rows are the usable rows with index
``<= f - horizon - 1``
(their labels, which look ``horizon`` bars ahead, are fully known before the fold's first decision).
The most recent ``calibration_fraction`` of those rows are held out to calibrate the probabilities,
with another ``horizon``-bar embargo between the fit rows and the calibration rows. Nothing at or
after the fold start is ever used to fit or calibrate anything.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

import numpy as np
import polars as pl
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field, field_validator

from xau_edge.models.calibration import N_CLASSES, OvRCalibrator
from xau_edge.models.dataset import ModelData


class Classifier(Protocol):
    """The slice of the scikit-learn estimator API used here."""

    def fit(self, x: NDArray[np.float64], y: NDArray[np.int64]) -> Any:
        """Fit on features and labels."""
        ...

    def predict_proba(self, x: NDArray[np.float64]) -> NDArray[np.float64]:
        """Class probabilities."""
        ...


class WalkForwardConfig(BaseModel):
    """Protocol parameters."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    horizon: int = Field(ge=1)
    min_train_rows: int = Field(default=3000, ge=10)
    calibration_fraction: float = Field(default=0.25, gt=0, le=0.5)
    calibration: str = "sigmoid"

    @field_validator("calibration")
    @classmethod
    def _known(cls, value: str) -> str:
        if value not in ("none", "sigmoid", "isotonic"):
            msg = f"unknown calibration {value!r}; use none, sigmoid or isotonic"
            raise ValueError(msg)
        return value


@dataclass(frozen=True)
class FoldPlan:
    """Row indices used by one fold."""

    test_idx: NDArray[np.intp]
    train_idx: NDArray[np.intp]
    fit_idx: NDArray[np.intp]
    cal_idx: NDArray[np.intp]


def month_folds(period: tuple[datetime, datetime]) -> list[tuple[datetime, datetime]]:
    """Calendar-month folds clipped to ``period`` (contiguous, no overlap)."""
    start, end = period
    folds: list[tuple[datetime, datetime]] = []
    cursor = start
    while cursor < end:
        nxt = datetime(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1, tzinfo=UTC)
        folds.append((cursor, min(nxt, end)))
        cursor = nxt
    return folds


def plan_fold(
    data: ModelData, fold: tuple[datetime, datetime], cfg: WalkForwardConfig
) -> FoldPlan | None:
    """Choose test, fit and calibration rows for ``fold`` (``None`` if history is insufficient)."""
    a, b = fold
    times = data.decision_time
    in_fold = np.array([a <= t < b for t in times], dtype=bool)
    test_idx = np.flatnonzero(in_fold & data.usable)
    if test_idx.size == 0:
        return None
    first = int(test_idx[0])
    train_idx = np.flatnonzero(data.usable & (np.arange(len(times)) <= first - cfg.horizon - 1))
    if train_idx.size < cfg.min_train_rows:
        return None
    if cfg.calibration == "none":
        return FoldPlan(test_idx, train_idx, train_idx, np.empty(0, dtype=np.intp))
    n_cal = max(int(train_idx.size * cfg.calibration_fraction), 1)
    cal_idx = train_idx[-n_cal:]
    fit_idx = train_idx[train_idx <= int(cal_idx[0]) - cfg.horizon - 1]
    if fit_idx.size < cfg.min_train_rows // 2:
        return None
    return FoldPlan(test_idx, train_idx, fit_idx, cal_idx)


def _proba(model: Classifier, x: NDArray[np.float64]) -> NDArray[np.float64]:
    raw = np.asarray(model.predict_proba(x), dtype=np.float64)
    classes = getattr(model, "classes_", None)
    if classes is None or len(classes) == N_CLASSES:
        return raw
    out = np.zeros((raw.shape[0], N_CLASSES))
    out[:, np.asarray(classes, dtype=int)] = raw
    return out


def walk_forward_predict(
    data: ModelData,
    make_model: Callable[[], Classifier],
    period: tuple[datetime, datetime],
    cfg: WalkForwardConfig,
) -> pl.DataFrame:
    """Out-of-sample class probabilities for every usable row of ``period``."""
    frames: list[pl.DataFrame] = []
    for fold_id, fold in enumerate(month_folds(period)):
        plan = plan_fold(data, fold, cfg)
        if plan is None:
            continue
        model = make_model()
        model.fit(data.X[plan.fit_idx], data.y[plan.fit_idx])
        raw = _proba(model, data.X[plan.test_idx])
        probs = raw
        if cfg.calibration != "none":
            cal_raw = _proba(model, data.X[plan.cal_idx])
            calibrator = OvRCalibrator(cfg.calibration).fit(cal_raw, data.y[plan.cal_idx])
            probs = calibrator.transform(raw)
        idx = plan.test_idx
        base = np.bincount(data.y[plan.fit_idx], minlength=N_CLASSES) / plan.fit_idx.size
        frames.append(
            pl.DataFrame(
                {
                    "timestamp": pl.Series(
                        data.timestamp[idx].tolist(), dtype=pl.Datetime("us", "UTC")
                    ),
                    "decision_time": pl.Series(
                        data.decision_time[idx].tolist(), dtype=pl.Datetime("us", "UTC")
                    ),
                    "index": idx.astype(np.int64),
                    "fold": np.full(idx.size, fold_id, dtype=np.int64),
                    "y": data.y[idx],
                    "p_down": probs[:, 0],
                    "p_neutral": probs[:, 1],
                    "p_up": probs[:, 2],
                    "base_down": np.full(idx.size, base[0]),
                    "base_neutral": np.full(idx.size, base[1]),
                    "base_up": np.full(idx.size, base[2]),
                    "p_raw_down": raw[:, 0],
                    "p_raw_neutral": raw[:, 1],
                    "p_raw_up": raw[:, 2],
                    "atr": data.atr[idx],
                    "regime": pl.Series(data.regime[idx].tolist(), dtype=pl.String),
                    "n_train": np.full(idx.size, plan.fit_idx.size, dtype=np.int64),
                }
            )
        )
    if not frames:
        return pl.DataFrame()
    return pl.concat(frames)
