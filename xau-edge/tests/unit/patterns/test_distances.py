"""Similarity measures: unified interface, hand values, metric properties, agreement with loops."""

from __future__ import annotations

import numpy as np
import pytest

from xau_edge.patterns.distances import (
    METHODS,
    cosine_distance,
    dtw_distance,
    euclidean_distance,
    mass_distance_profile,
    pearson_distance,
    znorm_path_distance,
)

W, F = 12, 3


def _data(n: int = 40, seed: int = 1) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    return rng.normal(size=(W, F)), rng.normal(size=(n, W, F))


def test_registry_exposes_every_method_from_the_brief() -> None:
    assert set(METHODS) == {"pearson", "euclidean", "cosine", "dtw", "znorm_path"}
    q, c = _data()
    for name, fn in METHODS.items():
        d = fn(q, c)
        assert d.shape == (c.shape[0],), name
        assert np.isfinite(d).all(), name
        assert (d >= -1e-12).all(), name


def test_identical_window_has_zero_distance_for_every_method() -> None:
    q, c = _data()
    c[7] = q
    for name, fn in METHODS.items():
        d = fn(q, c)
        assert d[7] == pytest.approx(0.0, abs=1e-9), name
        assert d.argmin() == 7, name


def test_euclidean_hand_value_and_loop_agreement() -> None:
    q = np.zeros((2, 2))
    c = np.array([[[3.0, 0.0], [0.0, 4.0]]])
    assert euclidean_distance(q, c)[0] == pytest.approx(5.0)
    q, cs = _data()
    loop = [np.sqrt(((cs[i] - q) ** 2).sum()) for i in range(cs.shape[0])]
    np.testing.assert_allclose(euclidean_distance(q, cs), loop)


def test_cosine_hand_values() -> None:
    q = np.array([[1.0, 0.0]])
    c = np.array([[[1.0, 0.0]], [[0.0, 1.0]], [[-1.0, 0.0]], [[5.0, 0.0]]])
    np.testing.assert_allclose(cosine_distance(q, c), [0.0, 1.0, 2.0, 0.0], atol=1e-12)


def test_cosine_of_zero_vector_is_defined_as_maximal_distance_one() -> None:
    q = np.ones((2, 2))
    c = np.zeros((1, 2, 2))
    assert cosine_distance(q, c)[0] == pytest.approx(1.0)


def test_pearson_is_invariant_to_offset_and_positive_scale_but_not_to_sign() -> None:
    q, cs = _data()
    shifted = cs[0] * 4.0 + 7.0
    d = pearson_distance(q, np.stack([cs[0], shifted, -cs[0]]))
    assert d[0] == pytest.approx(d[1])
    assert d[2] == pytest.approx(2.0 - d[0])


def test_pearson_constant_window_is_maximally_distant() -> None:
    q, _ = _data()
    flat = np.full((1, W, F), 3.0)
    assert pearson_distance(q, flat)[0] == pytest.approx(1.0)


def test_dtw_is_never_larger_than_euclidean_and_equals_it_with_zero_band() -> None:
    q, cs = _data()
    e = euclidean_distance(q, cs)
    assert (dtw_distance(q, cs) <= e + 1e-9).all()
    np.testing.assert_allclose(dtw_distance(q, cs, radius=0), e, atol=1e-9)


def test_dtw_matches_a_plain_python_dynamic_program() -> None:
    q, cs = _data(n=5, seed=9)

    def reference(a: np.ndarray, b: np.ndarray, radius: int | None) -> float:
        n = a.shape[0]
        acc = np.full((n + 1, n + 1), np.inf)
        acc[0, 0] = 0.0
        for i in range(1, n + 1):
            for j in range(1, n + 1):
                if radius is not None and abs(i - j) > radius:
                    continue
                cost = float(((a[i - 1] - b[j - 1]) ** 2).sum())
                acc[i, j] = cost + min(acc[i - 1, j], acc[i, j - 1], acc[i - 1, j - 1])
        return float(np.sqrt(acc[n, n]))

    for radius in (None, 2):
        expected = [reference(q, cs[i], radius) for i in range(cs.shape[0])]
        np.testing.assert_allclose(dtw_distance(q, cs, radius=radius), expected, atol=1e-9)


def test_dtw_absorbs_a_time_shift_that_euclidean_penalises() -> None:
    base = np.sin(np.linspace(0, 3, W))[:, None]
    shifted = np.roll(base, 1, axis=0)
    shifted[0] = base[0]
    assert dtw_distance(base, shifted[None])[0] < euclidean_distance(base, shifted[None])[0]


def test_znorm_path_ignores_offset_and_scale_of_the_cumulative_path() -> None:
    q, cs = _data()
    other = cs[0].copy()
    other[:, 0] = other[:, 0] * 5.0
    a = znorm_path_distance(q, np.stack([cs[0], other]))
    assert a[0] == pytest.approx(a[1])


def test_mass_equals_direct_znormalised_euclidean_distance() -> None:
    rng = np.random.default_rng(3)
    series = np.cumsum(rng.normal(size=300))
    m = 20
    query = series[100:120]
    profile = mass_distance_profile(query, series)
    assert profile.shape == (series.size - m + 1,)
    direct = np.empty_like(profile)
    qn = (query - query.mean()) / query.std()
    for i in range(profile.size):
        w = series[i : i + m]
        direct[i] = np.sqrt(((qn - (w - w.mean()) / w.std()) ** 2).sum())
    np.testing.assert_allclose(profile, direct, atol=1e-6)
    assert profile[100] == pytest.approx(0.0, abs=1e-6)


def test_mass_constant_windows_have_defined_distances() -> None:
    series = np.concatenate([np.zeros(30), np.cumsum(np.ones(30))])
    query = series[40:50]  # a ramp
    profile = mass_distance_profile(query, series)
    assert profile[0] == pytest.approx(np.sqrt(10))  # constant window vs ramp
    assert mass_distance_profile(np.ones(10), series)[0] == pytest.approx(
        0.0
    )  # constant vs constant
    assert mass_distance_profile(np.ones(10), series)[40] == pytest.approx(np.sqrt(10))


def test_distance_inputs_are_validated() -> None:
    q, cs = _data()
    with pytest.raises(ValueError, match="shape"):
        euclidean_distance(q[:5], cs)
    bad = cs.copy()
    bad[0, 0, 0] = np.nan
    with pytest.raises(ValueError, match="finite"):
        euclidean_distance(q, bad)
    with pytest.raises(ValueError, match="radius"):
        dtw_distance(q, cs, radius=-1)


def test_mass_is_accurate_at_large_price_levels() -> None:
    rng = np.random.default_rng(8)
    series = 1e9 + np.cumsum(rng.normal(size=200))
    profile = mass_distance_profile(series[50:70], series)
    assert profile[50] == pytest.approx(0.0, abs=1e-3)
    assert profile.min() >= 0


def test_pearson_works_at_tiny_scales() -> None:
    q, cs = _data()
    tiny = pearson_distance(q * 1e-9, cs * 1e-9)
    np.testing.assert_allclose(tiny, pearson_distance(q, cs), atol=1e-6)
