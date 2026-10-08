"""Statistical leakage checks for pattern search (brief sections 15 and 26).

Three contaminations are tested on many random queries rather than one hand case:

* future leakage: results must not change when every bar after the query is replaced;
* overlap leakage: a match's outcome window must end before the query window starts;
* self-match: the query window and anything overlapping it never appears among matches.
"""

from __future__ import annotations

import numpy as np
import pytest

from xau_edge.patterns.distances import METHODS
from xau_edge.patterns.search import PatternIndex, SearchConfig

W, H = 12, 25


def _walk_values(seed: int, n: int = 700) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(size=(n, 4)) + np.sin(np.arange(n) / 9.0)[:, None]


@pytest.mark.parametrize("method", sorted(METHODS))
def test_future_replacement_never_changes_results(method: str) -> None:
    cfg = SearchConfig(window=W, horizon=H, k=6, method=method)
    for seed in range(4):
        v = _walk_values(seed)
        for q in np.random.default_rng(seed).integers(150, 600, size=4):
            base = PatternIndex(v, cfg).search(int(q))
            future = v.copy()
            future[q + 1 :] = np.random.default_rng(seed + 99).normal(
                scale=30, size=future[q + 1 :].shape
            )
            other = PatternIndex(future, cfg).search(int(q))
            assert [(m.end_index, m.distance) for m in base.matches] == [
                (m.end_index, m.distance) for m in other.matches
            ], (method, seed, int(q))


@pytest.mark.parametrize("method", sorted(METHODS))
def test_no_match_overlaps_the_query_window_or_has_an_outcome_that_does(method: str) -> None:
    cfg = SearchConfig(window=W, horizon=H, k=40, min_separation=1, method=method)
    v = _walk_values(11)
    for q in range(120, 690, 37):
        for m in PatternIndex(v, cfg).search(q).matches:
            assert m.end_index != q
            assert m.end_index + H < q - W + 1, f"outcome window of {m.end_index} touches query {q}"


def test_a_future_copy_of_the_query_is_not_a_match() -> None:
    v = _walk_values(5)
    q = 300
    v[500 - W + 1 : 501] = v[q - W + 1 : q + 1]  # perfect twin placed in the future
    res = PatternIndex(v, SearchConfig(window=W, horizon=H, k=10)).search(q)
    assert 500 not in {m.end_index for m in res.matches}
    assert all(m.distance > 1e-6 for m in res.matches)


def test_a_copy_inside_the_outcome_overlap_zone_is_not_a_match() -> None:
    v = _walk_values(6)
    q = 400
    zone_end = q - 3  # overlaps the query window itself
    v[zone_end - W + 1 : zone_end + 1] = v[q - W + 1 : q + 1]
    res = PatternIndex(v, SearchConfig(window=W, horizon=H, k=10, min_separation=1)).search(q)
    assert zone_end not in {m.end_index for m in res.matches}
    near = q - W - H + 1  # first forbidden end index
    assert all(m.end_index < near for m in res.matches)
