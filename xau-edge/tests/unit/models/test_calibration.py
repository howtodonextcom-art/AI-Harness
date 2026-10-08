"""Probability scoring and calibration (brief section 20)."""

from __future__ import annotations

import numpy as np
import pytest

from xau_edge.models.calibration import (
    OvRCalibrator,
    base_rate_probabilities,
    expected_calibration_error,
    log_loss,
    multiclass_brier,
    reliability_curve,
)


def test_brier_and_log_loss_hand_values() -> None:
    p = np.array([[0.7, 0.2, 0.1], [0.1, 0.1, 0.8]])
    y = np.array([0, 2])
    assert multiclass_brier(p, y) == pytest.approx(
        ((0.3**2 + 0.2**2 + 0.1**2) + (0.1**2 + 0.1**2 + 0.2**2)) / 2
    )
    assert log_loss(p, y) == pytest.approx(-(np.log(0.7) + np.log(0.8)) / 2)


def test_perfect_and_worst_predictions() -> None:
    y = np.array([0, 1, 2])
    perfect = np.eye(3)
    assert multiclass_brier(perfect, y) == pytest.approx(0.0)
    assert log_loss(perfect, y) == pytest.approx(0.0, abs=1e-9)
    assert multiclass_brier(np.eye(3)[::-1], y) > 1.0
    assert np.isfinite(log_loss(np.eye(3)[::-1], y))  # clipped, not infinite


def test_uniform_probabilities_score_ln3_and_two_thirds() -> None:
    p = np.full((30, 3), 1 / 3)
    y = np.arange(30) % 3
    assert log_loss(p, y) == pytest.approx(np.log(3))
    assert multiclass_brier(p, y) == pytest.approx(2 / 3)


def test_reliability_curve_and_ece_hand_values() -> None:
    p = np.array([0.1] * 10 + [0.9] * 10)
    hit = np.array([0] * 9 + [1] + [1] * 9 + [0], dtype=float)  # 10% and 90% observed
    curve = reliability_curve(p, hit, bins=10)
    assert [round(c.mean_predicted, 2) for c in curve] == [0.1, 0.9]
    assert [round(c.observed_rate, 2) for c in curve] == [0.1, 0.9]
    assert expected_calibration_error(p, hit, bins=10) == pytest.approx(0.0, abs=1e-9)
    overconfident = np.array([0.9] * 20)
    outcomes = np.array([1] * 10 + [0] * 10, dtype=float)
    assert expected_calibration_error(overconfident, outcomes, bins=10) == pytest.approx(0.4)


def test_base_rate_probabilities_use_training_frequencies() -> None:
    y_train = np.array([0, 0, 1, 2, 2, 2, 2, 2])
    p = base_rate_probabilities(y_train, 5)
    assert p.shape == (5, 3)
    np.testing.assert_allclose(p[0], [2 / 8, 1 / 8, 5 / 8])


def _overconfident(n: int = 4000, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    true_p = rng.dirichlet([2.0, 2.0, 2.0], n)
    y = np.array([rng.choice(3, p=row) for row in true_p])
    sharpened = true_p**2.5
    return sharpened / sharpened.sum(axis=1, keepdims=True), y


@pytest.mark.parametrize("method", ["sigmoid", "isotonic"])
def test_calibration_reduces_log_loss_and_ece_of_overconfident_probabilities(method: str) -> None:
    p, y = _overconfident()
    cal = OvRCalibrator(method).fit(p[:2000], y[:2000])
    out = cal.transform(p[2000:])
    assert out.shape == (2000, 3)
    np.testing.assert_allclose(out.sum(axis=1), 1.0, atol=1e-9)
    assert log_loss(out, y[2000:]) < log_loss(p[2000:], y[2000:])
    before = expected_calibration_error(p[2000:, 2], (y[2000:] == 2).astype(float))
    after = expected_calibration_error(out[:, 2], (y[2000:] == 2).astype(float))
    assert after < before


def test_calibrator_is_identity_like_for_already_calibrated_input() -> None:
    rng = np.random.default_rng(1)
    p = rng.dirichlet([3, 3, 3], 3000)
    y = np.array([rng.choice(3, p=row) for row in p])
    out = OvRCalibrator("sigmoid").fit(p, y).transform(p)
    assert log_loss(out, y) <= log_loss(p, y) + 0.01


def test_transform_before_fit_and_bad_inputs_are_rejected() -> None:
    with pytest.raises(RuntimeError, match="fit"):
        OvRCalibrator("sigmoid").transform(np.full((2, 3), 1 / 3))
    with pytest.raises(ValueError, match="method"):
        OvRCalibrator("magic")
    with pytest.raises(ValueError, match="shape"):
        multiclass_brier(np.ones((3, 2)), np.zeros(3, dtype=int))
    with pytest.raises(ValueError, match="rows"):
        log_loss(np.full((3, 3), 1 / 3), np.zeros(2, dtype=int))
    with pytest.raises(ValueError, match="finite"):
        log_loss(np.array([[np.nan, 0.5, 0.5]]), np.array([0]))


def test_a_class_never_seen_in_calibration_data_gets_a_floor_probability() -> None:
    p = np.full((200, 3), 1 / 3)
    y = np.array([0, 1] * 100)  # class 2 never occurs
    out = OvRCalibrator("isotonic").fit(p, y).transform(p)
    assert np.isfinite(out).all()
    assert out[:, 2].max() < 0.2
