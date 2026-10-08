"""Leakage-safe nearest-neighbour search over pattern windows."""

from __future__ import annotations

from itertools import pairwise

import numpy as np
import pytest

from xau_edge.patterns.distances import METHODS, matrix_profile
from xau_edge.patterns.search import PatternIndex, SearchConfig

F = 3


def _values(n: int = 500, seed: int = 1) -> np.ndarray:
    return np.random.default_rng(seed).normal(size=(n, F))


CFG = SearchConfig(window=10, horizon=20, k=5)


def test_search_returns_k_sorted_matches_with_unique_ranks() -> None:
    res = PatternIndex(_values(), CFG).search(query_end=400)
    assert len(res.matches) == 5
    d = [m.distance for m in res.matches]
    assert d == sorted(d)
    assert [m.rank for m in res.matches] == [1, 2, 3, 4, 5]
    assert res.n_candidates > 100
    assert res.best_distance == d[0]


def test_candidates_end_before_the_query_window_minus_the_outcome_horizon() -> None:
    idx = PatternIndex(_values(), CFG)
    q = 300
    ends = idx.candidate_ends(q)
    assert ends.max() == q - CFG.window - CFG.horizon
    assert ends.min() == CFG.window - 1


def test_matches_never_overlap_the_query_or_its_outcome_zone() -> None:
    idx = PatternIndex(_values(), SearchConfig(window=10, horizon=20, k=30, min_separation=1))
    for q in (100, 250, 499):
        for m in idx.search(q).matches:
            assert m.end_index + CFG.horizon < q - CFG.window + 1


def test_the_query_itself_is_never_returned() -> None:
    v = _values()
    for q in (120, 300):
        assert q not in {m.end_index for m in PatternIndex(v, CFG).search(q).matches}


def test_planted_twin_in_the_past_is_found_first_for_every_method() -> None:
    v = _values()
    q = 400
    v[q - 9 : q + 1] = v[100:110]
    for name in METHODS:
        res = PatternIndex(v, SearchConfig(window=10, horizon=20, k=3, method=name)).search(q)
        assert res.matches[0].end_index == 109, name
        assert res.matches[0].distance == pytest.approx(0.0, abs=1e-9), name


def test_twin_planted_inside_the_forbidden_zone_is_ignored() -> None:
    v = _values()
    q = 400
    v[q - 9 : q + 1] = v[100:110]
    v[350:360] = v[100:110]  # ends at 359 > q - window - horizon = 370? no: 359 < 370 allowed
    allowed = PatternIndex(v, CFG).search(q).matches
    assert {109, 359} <= {m.end_index for m in allowed}
    v2 = _values()
    v2[q - 9 : q + 1] = v2[100:110]
    v2[385:395] = v2[100:110]  # ends at 394 > 370: its outcome window overlaps the query pattern
    v2[100:110] = _values(10, seed=99)  # remove the legitimate twin
    got = PatternIndex(v2, CFG).search(q).matches
    assert all(m.end_index <= q - CFG.window - CFG.horizon for m in got)
    assert 394 not in {m.end_index for m in got}


def test_results_do_not_depend_on_anything_after_the_query_bar() -> None:
    v = _values(600)
    q = 380
    base = {
        n: PatternIndex(v, SearchConfig(window=10, horizon=20, k=5, method=n)).search(q)
        for n in METHODS
    }
    garbage = v.copy()
    garbage[q + 1 :] = np.random.default_rng(7).normal(scale=50, size=garbage[q + 1 :].shape)
    garbage[q + 5] = np.nan
    for n, res in base.items():
        other = PatternIndex(garbage, SearchConfig(window=10, horizon=20, k=5, method=n)).search(q)
        assert [(m.end_index, m.distance) for m in other.matches] == [
            (m.end_index, m.distance) for m in res.matches
        ], n
        assert other.n_candidates == res.n_candidates


def test_selected_matches_are_separated() -> None:
    cfg = SearchConfig(window=10, horizon=20, k=8, min_separation=25)
    ends = sorted(m.end_index for m in PatternIndex(_values(), cfg).search(450).matches)
    assert all(b - a >= 25 for a, b in pairwise(ends))


def test_default_separation_is_the_window_length() -> None:
    ends = sorted(m.end_index for m in PatternIndex(_values(), CFG).search(450).matches)
    assert all(b - a >= CFG.window for a, b in pairwise(ends))


def test_incomplete_windows_are_never_candidates() -> None:
    v = _values()
    v[200:215] = np.nan
    res = PatternIndex(v, SearchConfig(window=10, horizon=20, k=50, min_separation=1)).search(450)
    for m in res.matches:
        assert not np.isnan(v[m.end_index - 9 : m.end_index + 1]).any()


def test_query_with_missing_values_is_rejected() -> None:
    v = _values()
    v[395] = np.nan
    with pytest.raises(ValueError, match="query"):
        PatternIndex(v, CFG).search(400)


def test_query_too_early_has_no_candidates() -> None:
    res = PatternIndex(_values(), CFG).search(25)
    assert res.matches == ()
    assert res.n_candidates == 0


def test_deterministic_tie_breaking_prefers_the_earlier_window() -> None:
    v = np.zeros((200, F))
    v[150:160] = 1.0
    v[40:50] = 1.0
    v[80:90] = 1.0
    res = PatternIndex(v, SearchConfig(window=10, horizon=5, k=2, method="euclidean")).search(159)
    assert [m.end_index for m in res.matches] == [49, 89]


def test_every_method_runs_through_the_index() -> None:
    v = _values(300)
    for name in METHODS:
        res = PatternIndex(v, SearchConfig(window=10, horizon=20, k=3, method=name)).search(250)
        assert len(res.matches) == 3


def test_config_validation() -> None:
    with pytest.raises(ValueError, match="method"):
        SearchConfig(method="magic")
    with pytest.raises(ValueError, match="window"):
        SearchConfig(window=1)
    with pytest.raises(ValueError, match="query_end"):
        PatternIndex(_values(50), CFG).search(500)


def test_matrix_profile_finds_a_planted_repeat() -> None:
    rng = np.random.default_rng(5)
    series = rng.normal(size=200).cumsum()
    motif = np.sin(np.linspace(0, 6, 20)) * 5
    series[30:50] = motif + series[30]
    series[120:140] = motif * 2 + series[120]
    profile, index = matrix_profile(series, 20)
    best = int(np.argmin(profile))
    assert best in (30, 120)
    assert index[best] in (30, 120)
    assert profile[best] < 0.5
    assert (profile[~np.isinf(profile)] >= -1e-9).all()


def test_separation_boundary_is_inclusive() -> None:
    v = _values(400, seed=12)
    q = 380
    v[q - 9 : q + 1] = v[100:110]
    v[125:135] = v[100:110]  # second twin 25 bars after the first
    cfg = SearchConfig(window=10, horizon=20, k=2, min_separation=25)
    ends = sorted(m.end_index for m in PatternIndex(v, cfg).search(q).matches)
    assert ends == [109, 134]


def test_ties_are_broken_towards_earlier_windows_even_for_many_candidates() -> None:
    v = np.zeros((400, F))
    v[390:400] = 1.0  # every earlier window is equally far from the query
    res = PatternIndex(v, SearchConfig(window=10, horizon=5, k=3, method="euclidean")).search(399)
    assert [m.end_index for m in res.matches] == [9, 19, 29]


def test_default_separation_equals_window() -> None:
    assert SearchConfig(window=17).separation == 17
    assert SearchConfig(window=17, min_separation=4).separation == 4


def test_a_twin_at_the_last_admissible_end_index_is_matched() -> None:
    v = _values(400, seed=21)
    q = 300
    last = q - CFG.window - CFG.horizon
    v[q - 9 : q + 1] = v[last - 9 : last + 1]
    res = PatternIndex(v, CFG).search(q)
    assert res.matches[0].end_index == last
    assert res.matches[0].distance == pytest.approx(0.0, abs=1e-9)
    one_later = PatternIndex(v, SearchConfig(window=10, horizon=21, k=5)).search(q)
    assert last not in {m.end_index for m in one_later.matches}


def test_infinite_values_in_history_mask_the_window_instead_of_raising() -> None:
    v = _values(300, seed=22)
    v[100, 0] = np.inf
    v[150, 1] = -np.inf
    for name in METHODS:
        res = PatternIndex(
            v, SearchConfig(window=10, horizon=20, k=40, min_separation=1, method=name)
        ).search(250)
        for m in res.matches:
            assert np.isfinite(v[m.end_index - 9 : m.end_index + 1]).all()


def test_k_must_be_positive() -> None:
    with pytest.raises(ValueError, match="k must"):
        PatternIndex(_values(), CFG).search(300, k=0)
    assert len(PatternIndex(_values(), CFG).search(300, k=2).matches) == 2
