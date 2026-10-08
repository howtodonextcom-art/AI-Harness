"""Prop-firm Monte Carlo on SYNTHETIC trade lists (sanity of the breach rules only)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import numpy as np
import pytest

from xau_edge.evaluation.prop_mc import (
    RISK_GRID_PCT,
    breach_probabilities,
    daily_blocks,
    prop_monte_carlo,
)

START = datetime(2011, 1, 3, 9, tzinfo=UTC)


def _days(per_day: list[list[float]]) -> tuple[list[float], list[datetime]]:
    r: list[float] = []
    times: list[datetime] = []
    for d, trades in enumerate(per_day):
        for k, value in enumerate(trades):
            r.append(value)
            times.append(START + timedelta(days=d, hours=k))
    return r, times


def test_risk_grid_is_005_to_100_percent() -> None:
    assert RISK_GRID_PCT[0] == 0.05
    assert RISK_GRID_PCT[-1] == 1.0
    assert len(RISK_GRID_PCT) == 20


def test_a_series_without_losses_never_breaches() -> None:
    r, t = _days([[1.0, 0.5]] * 50)
    res = prop_monte_carlo(r, t, n_paths=500)
    assert all(p == 0.0 for probs in res.breach_probability.values() for p in probs.values())
    assert res.max_safe_risk_pct == 1.0
    assert res.override_risk_pct == 0.25


def test_huge_losses_refuse_every_risk_level() -> None:
    r, t = _days([[-100.0]] * 30)
    res = prop_monte_carlo(r, t, n_paths=500)
    assert res.max_safe_risk_pct is None
    assert res.override_risk_pct is None
    assert all(probs[30] == 1.0 for probs in res.breach_probability.values())


def test_the_daily_limit_uses_the_worst_running_loss_inside_the_day() -> None:
    r, t = _days([[-6.0, 6.0]] * 40)  # every day closes flat but dips to -6 R
    res = prop_monte_carlo(r, t, n_paths=300)
    assert res.breach_probability[0.8][90] == 0.0  # 4.8% < 5%
    assert res.breach_probability[0.85][30] == 1.0  # 5.1% >= 5%
    assert res.max_safe_risk_pct == 0.8
    assert res.override_risk_pct == 0.25


def test_trade_order_inside_a_day_follows_exit_time() -> None:
    t0 = datetime(2011, 1, 3, 9, tzinfo=UTC)
    blocks = daily_blocks([-5.0, 3.0], [t0 + timedelta(hours=2), t0])  # +3 exits first
    assert blocks.total_r.tolist() == [-2.0]
    assert blocks.worst_r.tolist() == [-2.0]


def test_days_follow_the_prague_midnight() -> None:
    late = datetime(2011, 1, 10, 22, 30, tzinfo=UTC)  # 23:30 Prague
    later = datetime(2011, 1, 10, 23, 30, tzinfo=UTC)  # 00:30 Prague, next day
    blocks = daily_blocks([1.0, -1.0], [late, later])
    assert blocks.days == (date(2011, 1, 10), date(2011, 1, 11))


def test_listed_flat_days_enter_as_zero_days() -> None:
    blocks = daily_blocks([1.0], [START], all_days=[START.date(), date(2011, 1, 4)])
    assert blocks.total_r.tolist() == [1.0, 0.0]
    assert blocks.worst_r.tolist() == [0.0, 0.0]


def test_the_static_max_loss_floor_by_horizon() -> None:
    r, t = _days([[-2.0]] * 20)  # every day loses 2 R
    blocks = daily_blocks(r, t)
    slow = breach_probabilities(blocks, 0.05, n_paths=200)  # -0.1%/day: floor on day 99
    assert slow == {30: 0.0, 60: 0.0, 90: 0.0}
    mid = breach_probabilities(blocks, 0.1, n_paths=200)  # -0.2%/day: floor on day 50
    assert mid == {30: 0.0, 60: 1.0, 90: 1.0}


def test_results_are_deterministic_for_a_seed() -> None:
    rng = np.random.default_rng(3)
    r, t = _days([list(rng.normal(0.0, 1.5, 3)) for _ in range(60)])
    a = prop_monte_carlo(r, t, n_paths=400, seed=7)
    b = prop_monte_carlo(r, t, n_paths=400, seed=7)
    assert a == b
    probs90 = [a.breach_probability[x][90] for x in RISK_GRID_PCT]
    assert probs90 == sorted(probs90)  # common random numbers: monotone in risk


@pytest.mark.parametrize(
    ("r", "t"),
    [([], []), ([1.0], [datetime(2011, 1, 3)]), ([float("nan")], [START])],  # noqa: DTZ001
)
def test_invalid_input_is_refused(r: list[float], t: list[datetime]) -> None:
    with pytest.raises(ValueError):  # noqa: PT011
        daily_blocks(r, t)
