"""Pre-registered periods and the analogue-study statistics."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import numpy as np
import polars as pl
import pytest

from xau_edge.evaluation.periods import PERIODS, period_bounds
from xau_edge.evaluation.study_stats import analogue_statistics


def test_periods_are_contiguous_chronological_and_match_the_criteria_document() -> None:
    dev, val, test = (PERIODS[n] for n in ("development", "validation", "test"))
    assert dev[1] == val[0]
    assert val[1] == test[0]
    assert dev[0] == datetime(2025, 5, 1, tzinfo=UTC)
    assert val[0] == datetime(2026, 1, 1, tzinfo=UTC)
    assert test[0] == datetime(2026, 5, 1, tzinfo=UTC)
    assert dev[0] < dev[1] <= val[1] <= test[1]


def test_unknown_period_is_rejected_and_test_requires_explicit_permission() -> None:
    with pytest.raises(ValueError, match="period"):
        period_bounds("holdout")
    with pytest.raises(PermissionError, match="test"):
        period_bounds("test")
    assert period_bounds("test", allow_test=True) == PERIODS["test"]


def _study(analogue: Sequence[float], realised: Sequence[float | None]) -> pl.DataFrame:
    n = len(analogue)
    base = datetime(2026, 1, 1, tzinfo=UTC)
    ts = [base + timedelta(hours=6 * i) for i in range(n)]
    return pl.DataFrame(
        {
            "timestamp": pl.Series(ts, dtype=pl.Datetime("us", "UTC")),
            "analogue_mean_atr": analogue,
            "realized_atr": pl.Series(realised, dtype=pl.Float64),
        }
    )


def test_total_and_timing_hand_values() -> None:
    study = _study([1.0, -1.0, 1.0, -1.0], [2.0, -1.0, 0.0, 1.0])
    s = analogue_statistics(study, seed=1, n_resamples=200)
    # signs +,-,+,-  -> signed = 2, 1, 0, -1  -> mean 0.5 ; mean(sign)=0 so timing == total
    assert s.n == 4
    assert s.total == pytest.approx(0.5)
    assert s.timing == pytest.approx(0.5)
    assert s.drift == pytest.approx(0.5)  # mean realised move
    assert s.share_long == pytest.approx(0.5)


def test_timing_removes_the_always_long_component() -> None:
    n = 40
    realised = [1.0] * n  # a pure drift market
    study = _study([1.0] * n, realised)
    s = analogue_statistics(study, seed=1, n_resamples=200)
    assert s.total == pytest.approx(1.0)  # looks like skill ...
    assert s.timing == pytest.approx(0.0)  # ... but it is only drift


def test_rows_without_a_realised_outcome_are_dropped() -> None:
    study = _study([1.0, 1.0, -1.0], [1.0, None, -1.0])
    s = analogue_statistics(study, seed=1, n_resamples=100)
    assert s.n == 2


def test_intervals_reflect_dependence_by_day() -> None:
    rng = np.random.default_rng(1)
    n = 200
    study = _study(list(rng.choice([-1.0, 1.0], n)), list(rng.normal(0, 1, n)))
    s = analogue_statistics(study, seed=1, n_resamples=300)
    assert s.total_ci[0] < s.total < s.total_ci[1]
    assert s.timing_ci[0] < s.timing < s.timing_ci[1]


def test_empty_study_is_rejected() -> None:
    with pytest.raises(ValueError, match="no usable"):
        analogue_statistics(_study([], []))
