"""The V0 models and baselines (frozen hyper-parameters; nothing here is ever tuned).

``HarRidge`` is standardised ridge regression with the intercept unpenalised (identical to
scikit-learn's ``StandardScaler + Ridge(alpha=10)``, verified in the tests), written in NumPy so the
default model has no heavy dependency and its coefficients can be exported as a small JSON.
``LightGbm`` imports LightGBM lazily: it is a challenger used by the offline trainer only.
"""

from __future__ import annotations

from typing import Any, Protocol

import numpy as np
from numpy.typing import NDArray

Floats = NDArray[np.float64]
RIDGE_ALPHA = 10.0
LGBM_PARAMS: dict[str, Any] = {
    "n_estimators": 200,
    "num_leaves": 8,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "min_child_samples": 50,
    "random_state": 7,
    "n_jobs": 1,
    "verbose": -1,
}
ATR_FEATURE = 0  # lATR14
ATR_BUCKETS = 5


class Model(Protocol):
    def fit(self, x: Floats, y: Floats, aux: Floats | None = None) -> Model: ...
    def predict(self, x: Floats, aux: Floats | None = None) -> Floats: ...


class MeanExpanding:
    """``mean_expanding``: the mean of the training label."""

    def fit(self, x: Floats, y: Floats, aux: Floats | None = None) -> MeanExpanding:
        self.mean = float(y.mean())
        return self

    def predict(self, x: Floats, aux: Floats | None = None) -> Floats:
        return np.full(x.shape[0], self.mean)


class Atr14OneFeature:
    """``atr14_one_feature``: OLS of the label on lATR14 only, refit per fold."""

    def fit(self, x: Floats, y: Floats, aux: Floats | None = None) -> Atr14OneFeature:
        a = np.column_stack([np.ones(x.shape[0]), x[:, ATR_FEATURE]])
        self.coef: Floats = np.linalg.lstsq(a, y, rcond=None)[0]
        return self

    def predict(self, x: Floats, aux: Floats | None = None) -> Floats:
        return np.asarray(self.coef[0] + self.coef[1] * x[:, ATR_FEATURE], dtype=np.float64)


class RuleStateAtrPercentile:
    """``rule_state_atr_percentile``: label mean by 5 buckets of the 250-bar ATR14 percentile.

    ``aux`` is the percentile (in [0, 1]) of the current ATR14 among its last 250 values.
    """

    def fit(self, x: Floats, y: Floats, aux: Floats | None = None) -> RuleStateAtrPercentile:
        if aux is None:
            msg = "the ATR percentile is required"
            raise ValueError(msg)
        bucket = self._bucket(aux)
        overall = float(y.mean())
        self.means = np.array(
            [
                float(y[bucket == b].mean()) if (bucket == b).any() else overall
                for b in range(ATR_BUCKETS)
            ]
        )
        return self

    @staticmethod
    def _bucket(pct: Floats) -> NDArray[np.int64]:
        return np.minimum((pct * ATR_BUCKETS).astype(np.int64), ATR_BUCKETS - 1)

    def predict(self, x: Floats, aux: Floats | None = None) -> Floats:
        if aux is None:
            msg = "the ATR percentile is required"
            raise ValueError(msg)
        return self.means[self._bucket(aux)]


class HarRidge:
    """``har_ridge`` (the V0 default): standardise, then ridge with alpha 10, intercept unpenalised."""

    def __init__(self, alpha: float = RIDGE_ALPHA) -> None:
        self.alpha = alpha

    def fit(self, x: Floats, y: Floats, aux: Floats | None = None) -> HarRidge:
        self.mean = x.mean(axis=0)
        scale = x.std(axis=0)
        self.scale = np.where(scale > 0, scale, 1.0)
        z = (x - self.mean) / self.scale
        self.intercept = float(y.mean())
        yc = y - self.intercept
        gram = z.T @ z + self.alpha * np.eye(z.shape[1])
        self.coef = np.linalg.solve(gram, z.T @ yc)
        return self

    def predict(self, x: Floats, aux: Floats | None = None) -> Floats:
        return ((x - self.mean) / self.scale) @ self.coef + self.intercept

    def export(self) -> dict[str, list[float] | float]:
        """Everything needed to serve the model (small JSON; no pickles)."""
        return {
            "alpha": self.alpha,
            "mean": self.mean.tolist(),
            "scale": self.scale.tolist(),
            "coef": self.coef.tolist(),
            "intercept": self.intercept,
        }


class LightGbm:
    """``lightgbm_regressor`` (the challenger): frozen parameters, single thread, seed 7."""

    def fit(self, x: Floats, y: Floats, aux: Floats | None = None) -> LightGbm:
        import lightgbm as lgb  # noqa: PLC0415 - optional offline dependency

        self.model = lgb.LGBMRegressor(**LGBM_PARAMS).fit(x, y)
        return self

    def predict(self, x: Floats, aux: Floats | None = None) -> Floats:
        return np.asarray(self.model.predict(x), dtype=np.float64)


BASELINES: dict[str, type] = {
    "mean_expanding": MeanExpanding,
    "atr14_one_feature": Atr14OneFeature,
    "rule_state_atr_percentile": RuleStateAtrPercentile,
}
CANDIDATES: dict[str, type] = {"har_ridge": HarRidge, "lightgbm_regressor": LightGbm}


def atr_percentile(x: Floats, window: int = 250) -> Floats:
    """Percent rank of lATR14 among its last ``window`` values (current included); NaN until full."""
    v = x[:, ATR_FEATURE]
    out = np.full(v.size, np.nan)
    from numpy.lib.stride_tricks import sliding_window_view  # noqa: PLC0415

    ok = np.isfinite(v)
    # a window is valid only when every value in it is finite
    if v.size >= window:
        view = sliding_window_view(v, window)
        full = np.isfinite(view).all(axis=1)
        pct = (view <= view[:, -1:]).mean(axis=1)
        out[window - 1 :] = np.where(full, pct, np.nan)
    out[~ok] = np.nan
    return out
