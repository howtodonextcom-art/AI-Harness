"""Outcome statistics: probabilities with intervals, distribution, expected R, base-rate lift."""

from __future__ import annotations

import numpy as np
import pytest

from xau_edge.outcomes.engine import OutcomeTable
from xau_edge.outcomes.summary import summarise, wilson_interval


def _table(
    direction: list[int],
    fwd_atr: list[float],
    long_r: list[float] | None = None,
    complete: list[bool] | None = None,
) -> OutcomeTable:
    n = len(direction)

    def col(x: list[float]) -> np.ndarray:
        return np.array(x, dtype=float).reshape(n, 1)

    z = np.zeros((n, 1))
    lr = long_r if long_r is not None else [0.0] * n
    return OutcomeTable(
        complete=np.array(complete if complete is not None else [True] * n).reshape(n, 1),
        forward_return=col(fwd_atr) / 100,
        forward_atr=col(fwd_atr),
        direction=np.array(direction, dtype=np.int8).reshape(n, 1),
        max_up_atr=col([abs(x) + 1 for x in fwd_atr]),
        max_down_atr=col([0.5] * n),
        long_barrier=np.zeros((n, 1), dtype=np.int8),
        long_barrier_bars=np.zeros((n, 1), dtype=np.int32),
        long_r=col(lr),
        short_barrier=np.zeros((n, 1), dtype=np.int8),
        short_barrier_bars=np.zeros((n, 1), dtype=np.int32),
        short_r=-col(lr) + z,
    )


def test_probabilities_and_counts() -> None:
    s = summarise(_table([1, 1, 1, -1, 0], [2, 1, 3, -2, 0.1]), 0)
    assert s is not None
    assert s.n == 5
    assert (s.p_up, s.p_down, s.p_neutral) == (0.6, 0.2, 0.2)
    assert s.p_up + s.p_down + s.p_neutral == pytest.approx(1.0)


def test_distribution_statistics_and_excursions() -> None:
    fwd = [-2.0, -1.0, 0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    s = summarise(_table([0] * 9, fwd), 0)
    assert s is not None
    assert s.mean_forward_atr == pytest.approx(np.mean(fwd))
    assert s.median_forward_atr == pytest.approx(2.0)
    assert s.percentiles[50] == pytest.approx(2.0)
    assert s.percentiles[5] == pytest.approx(np.percentile(fwd, 5))
    assert s.percentiles[95] == pytest.approx(np.percentile(fwd, 95))
    assert s.mean_max_down_atr == pytest.approx(0.5)


def test_expected_r_for_both_sides() -> None:
    s = summarise(_table([1, -1, 1, 0], [1, -1, 1, 0], long_r=[2.0, -1.0, 2.0, 0.5]), 0)
    assert s is not None
    assert s.expected_r_long == pytest.approx((2 - 1 + 2 + 0.5) / 4)
    assert s.expected_r_short == pytest.approx(-(2 - 1 + 2 + 0.5) / 4)


def test_incomplete_rows_are_excluded_and_row_selection_works() -> None:
    t = _table([1, -1, 1, 1], [1, -1, 1, 1], complete=[True, True, False, True])
    s = summarise(t, 0)
    assert s is not None
    assert s.n == 3
    sub = summarise(t, 0, rows=np.array([0, 2]))
    assert sub is not None
    assert sub.n == 1  # row 2 is incomplete


def test_no_complete_rows_gives_none() -> None:
    assert summarise(_table([1], [1.0], complete=[False]), 0) is None


def test_wilson_interval_known_values() -> None:
    lo, hi = wilson_interval(50, 100)
    assert lo == pytest.approx(0.4038, abs=1e-3)
    assert hi == pytest.approx(0.5962, abs=1e-3)
    lo0, hi0 = wilson_interval(0, 20)
    assert lo0 == 0.0
    assert 0.1 < hi0 < 0.2
    lo1, hi1 = wilson_interval(20, 20)
    assert hi1 == 1.0
    assert lo1 > 0.8


def test_wilson_interval_narrows_with_more_data() -> None:
    a = wilson_interval(30, 100)
    b = wilson_interval(300, 1000)
    assert (b[1] - b[0]) < (a[1] - a[0])
    with pytest.raises(ValueError, match="n"):
        wilson_interval(1, 0)
    with pytest.raises(ValueError, match="k"):
        wilson_interval(5, 3)


def test_intervals_are_attached_to_probabilities() -> None:
    s = summarise(_table([1] * 30 + [-1] * 70, [1.0] * 100), 0)
    assert s is not None
    lo, hi = s.p_up_ci
    assert lo < s.p_up < hi
    lo, hi = s.p_down_ci
    assert lo < s.p_down < hi
