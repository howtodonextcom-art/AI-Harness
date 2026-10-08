"""The four benchmark models: shapes, determinism, missing-value handling."""

from __future__ import annotations

import numpy as np
import pytest

from xau_edge.models.zoo import HYPERPARAMETERS, MODELS


def _xy(n: int = 600, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, 6))
    score = x[:, 0] - 0.5 * x[:, 1] + 0.3 * rng.normal(size=n)
    y = np.where(score > 0.4, 2, np.where(score < -0.4, 0, 1)).astype(np.int64)
    return x, y


def test_the_four_models_from_the_brief_in_order() -> None:
    assert list(MODELS) == ["logistic", "random_forest", "xgboost", "lightgbm"]
    assert set(HYPERPARAMETERS) == set(MODELS)


@pytest.mark.parametrize("name", list(MODELS))
def test_probabilities_have_three_columns_and_sum_to_one(name: str) -> None:
    x, y = _xy()
    model = MODELS[name]().fit(x[:500], y[:500])
    p = model.predict_proba(x[500:])
    assert p.shape == (100, 3)
    np.testing.assert_allclose(p.sum(axis=1), 1.0, atol=1e-6)
    assert (p >= 0).all()


@pytest.mark.parametrize("name", list(MODELS))
def test_fitting_twice_gives_identical_predictions(name: str) -> None:
    x, y = _xy()
    a = MODELS[name]().fit(x[:500], y[:500]).predict_proba(x[500:])
    b = MODELS[name]().fit(x[:500], y[:500]).predict_proba(x[500:])
    np.testing.assert_allclose(a, b, atol=1e-9)


@pytest.mark.parametrize("name", list(MODELS))
def test_models_learn_a_planted_signal(name: str) -> None:
    x, y = _xy(1500)
    p = MODELS[name]().fit(x[:1200], y[:1200]).predict_proba(x[1200:])
    accuracy = (p.argmax(axis=1) == y[1200:]).mean()
    assert accuracy > 0.55  # chance is about 0.4 with these class frequencies


@pytest.mark.parametrize("name", list(MODELS))
def test_missing_values_are_handled(name: str) -> None:
    x, y = _xy()
    holes = x.copy()
    holes[::7, 2] = np.nan
    holes[:30, 3] = np.nan
    model = MODELS[name]().fit(holes[:500], y[:500])
    p = model.predict_proba(holes[500:])
    assert np.isfinite(p).all()


@pytest.mark.parametrize("name", list(MODELS))
def test_an_all_missing_feature_does_not_break_fitting(name: str) -> None:
    x, y = _xy()
    x[:, 5] = np.nan
    p = MODELS[name]().fit(x[:500], y[:500]).predict_proba(x[500:])
    assert np.isfinite(p).all()
