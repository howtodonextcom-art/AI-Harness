"""Walk-forward protocol: chronological folds, embargo, calibration split, no leakage."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression

from xau_edge.models.calibration import base_rate_probabilities, log_loss
from xau_edge.models.dataset import ModelData
from xau_edge.models.walkforward import (
    WalkForwardConfig,
    month_folds,
    plan_fold,
    walk_forward_predict,
)

START = datetime(2025, 1, 1, tzinfo=UTC)
H = 10


def _data(n: int = 3000, signal: bool = True, seed: int = 0) -> ModelData:
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, 4))
    if signal:
        score = x[:, 0] + 0.3 * rng.normal(size=n)
        y = np.where(score > 0.5, 2, np.where(score < -0.5, 0, 1)).astype(np.int64)
    else:
        y = rng.integers(0, 3, n).astype(np.int64)
    decision = np.array([START + timedelta(hours=i) for i in range(n)], dtype=object)
    usable = np.ones(n, dtype=bool)
    usable[:20] = False
    y[-H:] = -1
    usable[-H:] = False
    return ModelData(
        X=x,
        y=y,
        usable=usable,
        timestamp=decision,
        decision_time=decision,
        atr=np.ones(n),
        regime=np.array(["RANGE"] * n, dtype=object),
        horizon=H,
    )


CFG = WalkForwardConfig(
    horizon=H, min_train_rows=500, calibration_fraction=0.25, calibration="sigmoid"
)


class _Spy:
    """A model that records what it was fitted on (always predicts the training frequencies)."""

    fits: list[np.ndarray] = []  # noqa: RUF012

    def fit(self, x: np.ndarray, y: np.ndarray) -> _Spy:
        self.freq = np.bincount(y, minlength=3) / len(y)
        _Spy.fits.append(np.asarray(x[:, 0]).copy())
        return self

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        return np.tile(self.freq, (x.shape[0], 1))


def _lr() -> LogisticRegression:
    return LogisticRegression(max_iter=300)


def test_month_folds_cover_the_period_without_gaps_or_overlap() -> None:
    period = (datetime(2025, 1, 15, tzinfo=UTC), datetime(2025, 4, 10, tzinfo=UTC))
    folds = month_folds(period)
    assert folds[0][0] == period[0]
    assert folds[-1][1] == period[1]
    assert all(folds[i][1] == folds[i + 1][0] for i in range(len(folds) - 1))
    assert [f[0].month for f in folds] == [1, 2, 3, 4]
    assert folds[1] == (datetime(2025, 2, 1, tzinfo=UTC), datetime(2025, 3, 1, tzinfo=UTC))


def test_training_rows_end_before_the_first_decision_of_the_fold_minus_the_horizon() -> None:
    d = _data()
    fold = (START + timedelta(hours=2000), START + timedelta(hours=2500))
    plan = plan_fold(d, fold, CFG)
    assert plan is not None
    first = int(plan.test_idx[0])
    assert first == 2000
    assert plan.train_idx.max() + H < first
    assert plan.fit_idx.max() + H < plan.cal_idx.min()  # embargo between fit and calibration
    assert set(plan.fit_idx).isdisjoint(plan.cal_idx)
    assert (np.diff(plan.train_idx) > 0).all()
    assert d.usable[plan.train_idx].all()


def test_folds_with_too_little_history_are_skipped() -> None:
    d = _data()
    early = (START + timedelta(hours=300), START + timedelta(hours=600))
    assert plan_fold(d, early, CFG) is None


def test_predictions_cover_each_test_row_once_and_sum_to_one() -> None:
    d = _data()
    period = (START + timedelta(hours=1500), START + timedelta(hours=2900))
    out = walk_forward_predict(d, _Spy, period, CFG)
    assert out.height == int(d.usable[1500:2900].sum())
    assert out["index"].n_unique() == out.height
    totals = out.select((out["p_down"] + out["p_neutral"] + out["p_up"]).alias("s"))["s"].to_numpy()
    np.testing.assert_allclose(totals, 1.0, atol=1e-9)
    assert (out["decision_time"] >= period[0]).all()
    assert (out["decision_time"] < period[1]).all()


class _IdSpy(_Spy):
    """Records the feature value that encodes each fitted row's index (feature 0 = row index)."""

    seen: list[np.ndarray] = []  # noqa: RUF012

    def fit(self, x: np.ndarray, y: np.ndarray) -> _IdSpy:
        _IdSpy.seen.append(x[:, 0].astype(int).copy())
        self.freq = np.bincount(y, minlength=3) / len(y)
        return self


def test_no_model_ever_sees_rows_at_or_after_its_fold() -> None:
    d = _data()
    d = ModelData(
        np.column_stack([np.arange(d.X.shape[0], dtype=float), d.X[:, 1:]]),
        d.y,
        d.usable,
        d.timestamp,
        d.decision_time,
        d.atr,
        d.regime,
        d.horizon,
    )
    _IdSpy.seen.clear()
    period = (START + timedelta(hours=1500), START + timedelta(hours=2900))
    out = walk_forward_predict(d, _IdSpy, period, CFG)
    folds = sorted(out["fold"].unique().to_list())
    assert len(_IdSpy.seen) == len(folds)
    for fitted, fold_id in zip(_IdSpy.seen, folds, strict=True):
        fold_start = int(out.filter(out["fold"] == fold_id)["index"].to_numpy().min())
        assert (
            fitted.max() + H < fold_start
        )  # label windows of every fitted row end before the fold


def test_future_rows_cannot_change_earlier_predictions() -> None:
    d = _data()
    period = (START + timedelta(hours=1500), START + timedelta(hours=2000))
    base = walk_forward_predict(d, _Spy, period, CFG)
    x2 = d.X.copy()
    y2 = d.y.copy()
    x2[2100:] = 99.0
    y2[2100:] = 0
    changed = ModelData(x2, y2, d.usable, d.timestamp, d.decision_time, d.atr, d.regime, d.horizon)
    other = walk_forward_predict(changed, _Spy, period, CFG)
    assert base["p_up"].to_list() == other["p_up"].to_list()


def test_a_learnable_signal_beats_the_base_rate_out_of_sample() -> None:
    d = _data(4000, signal=True)
    period = (START + timedelta(hours=2500), START + timedelta(hours=3900))
    out = walk_forward_predict(d, _lr, period, CFG)
    p = out.select("p_down", "p_neutral", "p_up").to_numpy()
    y = out["y"].to_numpy()
    base = base_rate_probabilities(d.y[d.usable][:2000], len(y))
    assert log_loss(p, y) < log_loss(base, y) - 0.1


def test_pure_noise_does_not_beat_the_base_rate() -> None:
    d = _data(4000, signal=False)
    period = (START + timedelta(hours=2500), START + timedelta(hours=3900))
    out = walk_forward_predict(d, _lr, period, CFG)
    p = out.select("p_down", "p_neutral", "p_up").to_numpy()
    y = out["y"].to_numpy()
    base = base_rate_probabilities(d.y[d.usable][:2000], len(y))
    assert log_loss(p, y) > log_loss(base, y) - 0.02


def test_config_validation() -> None:
    with pytest.raises(ValueError, match="calibration"):
        WalkForwardConfig(horizon=10, calibration="magic")
    with pytest.raises(ValueError, match="calibration_fraction"):
        WalkForwardConfig(horizon=10, calibration_fraction=0.9)


def _unused(_: Any) -> None:  # keep typing import used
    return None
