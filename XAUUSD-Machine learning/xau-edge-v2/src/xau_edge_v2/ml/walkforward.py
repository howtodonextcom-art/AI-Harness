"""Chronological walk-forward (expanding window, one fold per calendar year) with an embargo.

For test year ``Y`` the training rows are those whose decision time precedes the first test row by
at least ``EMBARGO`` bars (24 label bars + 1), so no training label overlaps a test feature. The
80% interval comes from the out-of-fold residuals of a model refit on the first 75% of the training
rows and scored on the last 25% (the calibration window, itself separated from the fit rows by the
embargo); the model that predicts the test rows is fit on all training rows. Nothing is shuffled and
nothing is tuned.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from xau_edge_v2.ml.models import BASELINES, CANDIDATES, Model

Floats = NDArray[np.float64]
EMBARGO = 25
MIN_TRAIN_ROWS = 3000
CAL_SHARE = 0.25
INTERVAL_LEVEL = 0.8
INTERVAL_MODELS = ("har_ridge", "lightgbm_regressor")


@dataclass
class WalkForward:
    """Predictions per model over all rows (NaN outside the test folds) + interval bounds."""

    preds: dict[str, Floats]
    lower: dict[str, Floats]
    upper: dict[str, Floats]
    folds: list[dict[str, int]] = field(default_factory=list)


def years_of(open_s: NDArray[np.int64]) -> NDArray[np.int64]:
    return open_s.astype("datetime64[s]").astype("datetime64[Y]").astype(np.int64) + 1970


def walk_forward(
    x: Floats,
    y: Floats,
    aux: Floats,
    ok: NDArray[np.bool_],
    years: NDArray[np.int64],
    test_years: list[int],
    *,
    models: dict[str, type] | None = None,
    min_train_rows: int = MIN_TRAIN_ROWS,
) -> WalkForward:
    chosen = models if models is not None else {**BASELINES, **CANDIDATES}
    n = x.shape[0]
    out = WalkForward(
        preds={k: np.full(n, np.nan) for k in chosen},
        lower={k: np.full(n, np.nan) for k in chosen if k in INTERVAL_MODELS},
        upper={k: np.full(n, np.nan) for k in chosen if k in INTERVAL_MODELS},
    )
    idx = np.arange(n)
    for year in test_years:
        test = np.flatnonzero(ok & (years == year))
        if test.size == 0:
            continue
        train = np.flatnonzero(ok & (idx <= test[0] - EMBARGO))
        if train.size < min_train_rows:
            continue
        cal_start = int(train.size * (1 - CAL_SHARE))
        cal = train[cal_start:]
        fit = train[:cal_start]
        fit = fit[fit <= cal[0] - EMBARGO]
        out.folds.append(
            {
                "year": year,
                "train": int(train.size),
                "fit": int(fit.size),
                "cal": int(cal.size),
                "test": int(test.size),
            }
        )
        for name, cls in chosen.items():
            model: Model = cls().fit(x[train], y[train], aux[train])
            out.preds[name][test] = model.predict(x[test], aux[test])
            if name in out.lower:
                half: Model = cls().fit(x[fit], y[fit], aux[fit])
                resid = y[cal] - half.predict(x[cal], aux[cal])
                lo_q, hi_q = np.quantile(
                    resid, [(1 - INTERVAL_LEVEL) / 2, 1 - (1 - INTERVAL_LEVEL) / 2]
                )
                out.lower[name][test] = out.preds[name][test] + lo_q
                out.upper[name][test] = out.preds[name][test] + hi_q
    return out
