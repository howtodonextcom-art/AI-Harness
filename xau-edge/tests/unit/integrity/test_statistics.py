from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from xau_edge.integrity.attribution import attribute
from xau_edge.integrity.dependence import (
    DEPENDENCE_SENSITIVE,
    block_bootstrap_ci,
    dependence_report,
    dependence_sensitivity,
    effective_n,
    overlap_ratio,
    stationary_bootstrap_ci,
)
from xau_edge.integrity.intrabar import (
    INTRABAR_ROBUST,
    INTRABAR_SENSITIVE,
    classify_bar,
    intrabar_report,
)
from xau_edge.integrity.placebo import (
    block_permutation_placebo,
    flip_placebo,
    random_pool_placebo,
    run_placebo,
    shift_placebo,
)
from xau_edge.integrity.power2 import (
    planted_edge_table,
    power_report,
    rejection_rate,
    simulate_sample,
)


def _rng(seed: int = 7) -> np.random.Generator:
    return np.random.default_rng(seed)


# -- dependence ----------------------------------------------------------------------------


def test_independent_samples_keep_almost_all_their_effective_n() -> None:
    values, days = simulate_sample(_rng(), effect=0.0, scenario="independent")
    assert effective_n(values, days) > 0.85 * len(values)


def test_clustered_samples_lose_effective_n() -> None:
    values, days = simulate_sample(_rng(), effect=0.0, scenario="clustered", rho=0.5)
    assert effective_n(values, days) < 0.7 * len(values)


def test_overlapping_samples_lose_effective_n() -> None:
    values, days = simulate_sample(_rng(), effect=0.0, scenario="overlapping", hold=6)
    assert effective_n(values, days) < 0.7 * len(values)


@given(st.lists(st.floats(-5, 5), min_size=4, max_size=60), st.integers(1, 6))
@settings(max_examples=60, deadline=None)
def test_effective_n_is_never_above_raw_n(values: list[float], per_day: int) -> None:
    arr = np.asarray(values)
    days = (np.arange(len(arr)) // per_day).astype(np.int64)
    assert 0 < effective_n(arr, days) <= len(arr) + 1e-9


def test_overlap_ratio_counts_overlapping_windows() -> None:
    entry = np.array([0, 5, 20], dtype=np.int64)
    exit_ = np.array([10, 15, 25], dtype=np.int64)
    assert overlap_ratio(entry, exit_) == pytest.approx(2 / 3)
    assert overlap_ratio(np.array([0, 10]), np.array([5, 15])) == 0.0
    with pytest.raises(ValueError, match="exits before"):
        overlap_ratio(np.array([5, 9]), np.array([1, 12]))


def test_dependence_report_counts_days_and_weeks() -> None:
    values = np.arange(14, dtype=np.float64)
    days = np.arange(14, dtype=np.int64)
    rep = dependence_report(values, days)
    assert (rep.raw_n, rep.unique_days, rep.unique_weeks) == (14, 14, 2)


def test_bootstrap_is_deterministic_and_seed_sensitive() -> None:
    values, days = simulate_sample(_rng(), effect=0.1, scenario="independent", days=60)
    a = block_bootstrap_ci(values, days, 2, seed=3, draws=300)
    assert a == block_bootstrap_ci(values, days, 2, seed=3, draws=300)
    assert a != block_bootstrap_ci(values, days, 2, seed=4, draws=300)
    assert a[0] < values.mean() < a[1]
    s = stationary_bootstrap_ci(values, mean_block=4, seed=3, draws=200)
    assert s == stationary_bootstrap_ci(values, mean_block=4, seed=3, draws=200)


def test_serial_dependence_across_days_can_flip_the_verdict() -> None:
    """Day effects that persist for weeks: 1-day blocks look precise, 5-day blocks do not."""
    flagged = 0
    for seed in range(40):
        rng = _rng(seed)
        day_effect = np.zeros(300)
        for i in range(1, 300):
            day_effect[i] = 0.95 * day_effect[i - 1] + 0.3 * rng.standard_normal()
        values = day_effect + 0.35
        days = np.arange(300, dtype=np.int64)
        rep = dependence_sensitivity(values, days, seed=1, include_stationary=False)
        flagged += rep.status == DEPENDENCE_SENSITIVE
    assert flagged >= 1


def test_sensitivity_is_unknown_for_a_tiny_sample() -> None:
    rep = dependence_sensitivity(np.ones(3), np.arange(3, dtype=np.int64), seed=1)
    assert rep.status == "UNKNOWN"


def test_non_finite_input_is_refused() -> None:
    with pytest.raises(ValueError, match="finite"):
        effective_n(np.array([1.0, np.nan]), np.array([0, 1], dtype=np.int64))


# -- power ---------------------------------------------------------------------------------


def test_adequately_powered_needs_effective_n() -> None:
    assert power_report(raw_n=5000, effective_n=None, k=21).adequately_powered is None
    big = power_report(raw_n=5000, effective_n=4000, k=21)
    assert big.adequately_powered is True
    small = power_report(raw_n=5000, effective_n=300, k=21)
    assert small.adequately_powered is False
    assert small.mde_effective is not None
    assert small.mde_effective > small.mde_raw
    assert (
        small.required_effective_n_for_target["0.10R"]
        > small.required_effective_n_for_target["0.20R"]
    )


def test_the_null_effect_is_not_rejected_more_often_than_alpha_by_much() -> None:
    for scenario in ("independent", "clustered"):
        assert rejection_rate(effect=0.0, scenario=scenario, k=1, sims=300, seed=2) <= 0.10


def test_power_grows_with_the_planted_effect() -> None:
    low = rejection_rate(effect=0.05, scenario="independent", k=21, sims=200, seed=5)
    high = rejection_rate(effect=0.20, scenario="independent", k=21, sims=200, seed=5)
    assert high > low
    assert high > 0.5


def test_planted_edge_table_has_every_effect_and_scenario() -> None:
    table = planted_edge_table(k=21, sims=60, seed=1)
    assert set(table) == {"0.00R", "0.05R", "0.10R", "0.20R"}
    assert set(table["0.10R"]) == {"independent", "clustered", "overlapping"}


# -- placebo -------------------------------------------------------------------------------


def test_placebo_is_deterministic_and_places_the_real_value() -> None:
    pool = _rng(1).standard_normal(500)
    draw = random_pool_placebo(pool, 50)
    a = run_placebo(2.0, draw, n=200, seed=9)
    b = run_placebo(2.0, draw, n=200, seed=9)
    assert a == b
    assert a.empirical_percentile == 1.0
    assert a.p99 >= a.p95 >= a.median
    assert run_placebo(-2.0, draw, n=200, seed=9).empirical_percentile == 0.0


def test_placebo_needs_enough_draws() -> None:
    with pytest.raises(ValueError, match="at least"):
        run_placebo(0.0, lambda rng: float(rng.random()), n=10, seed=1)


def test_shift_flip_and_permutation_placebos() -> None:
    out = np.array([1.0, -1.0, 2.0, -2.0, 3.0, -3.0])
    dirs = np.ones(6)
    assert shift_placebo(out, dirs, 1) == pytest.approx(np.mean([1.0, -1.0, 2.0, -2.0, 3.0]))
    with pytest.raises(ValueError, match="shift"):
        shift_placebo(out, dirs, 0)
    assert flip_placebo(np.array([1.0, 2.0])) == -1.5
    perm = block_permutation_placebo(out, dirs, 2)
    assert perm(_rng(1)) == pytest.approx(out.mean())  # mean is invariant to permutation


# -- attribution ---------------------------------------------------------------------------


def test_direction_edge_is_found_when_the_strategy_picks_the_right_side() -> None:
    rng = _rng(3)
    n = 400
    move = rng.standard_normal(n)
    long_r, short_r = move, -move
    direction = np.where(move > 0, 1.0, -1.0).astype(np.float64)  # an oracle
    days = np.arange(n, dtype=np.int64)
    att = attribute(long_r=long_r, short_r=short_r, direction=direction, day_ids=days)
    assert att.direction_edge > 0.5
    assert att.observed_mean_r > 0
    assert abs(att.drift_exposure) < 0.2
    by = {c.name: c for c in att.counterfactuals}
    assert by["B random direction (expected)"].ci_low > 0
    assert by["E opposite direction"].incremental_r > 0


def test_a_random_direction_has_no_direction_edge() -> None:
    rng = _rng(4)
    n = 2000
    move = rng.standard_normal(n)
    direction = rng.choice([-1.0, 1.0], size=n).astype(np.float64)
    days = np.arange(n, dtype=np.int64)
    att = attribute(long_r=move, short_r=-move, direction=direction, day_ids=days)
    by = {c.name: c for c in att.counterfactuals}
    assert (
        by["B random direction (expected)"].ci_low < 0 < by["B random direction (expected)"].ci_high
    )


def test_pure_drift_shows_up_as_drift_not_direction() -> None:
    n = 500
    long_r = np.full(n, 0.3) + _rng(5).standard_normal(n) * 0.1
    short_r = -long_r
    att = attribute(
        long_r=long_r, short_r=short_r, direction=np.ones(n), day_ids=np.arange(n, dtype=np.int64)
    )
    assert att.drift_exposure == pytest.approx(0.3, abs=0.02)


def test_attribution_rejects_bad_inputs() -> None:
    with pytest.raises(ValueError, match="same length"):
        attribute(long_r=np.ones(3), short_r=np.ones(2), direction=np.ones(3), day_ids=np.arange(3))
    with pytest.raises(ValueError, match="\\+1 or -1"):
        attribute(
            long_r=np.ones(3), short_r=np.ones(3), direction=np.zeros(3), day_ids=np.arange(3)
        )


# -- intrabar ------------------------------------------------------------------------------


def test_a_bar_touching_both_levels_is_ambiguous() -> None:
    assert classify_bar(high=11, low=9, take_profit=10.5, stop_loss=9.5, long=True) == "AMBIGUOUS"
    assert classify_bar(high=11, low=10, take_profit=10.5, stop_loss=9.5, long=True) == "TP"
    assert classify_bar(high=10, low=9, take_profit=10.5, stop_loss=9.5, long=True) == "SL"
    assert classify_bar(high=10, low=9.8, take_profit=10.5, stop_loss=9.5, long=True) == "NONE"
    assert classify_bar(high=11, low=9, take_profit=9.5, stop_loss=10.5, long=False) == "AMBIGUOUS"


def test_a_conclusion_that_flips_between_bounds_is_intrabar_sensitive() -> None:
    pess = np.array([-1.0, -1.0, 1.0, 1.0, -1.0])
    opt = np.array([2.0, -1.0, 1.0, 1.0, 2.0])
    amb = np.array([True, False, False, False, True])
    rep = intrabar_report(pess, opt, amb)
    assert rep.status == INTRABAR_SENSITIVE
    assert rep.ambiguous_count == 2
    assert rep.pessimistic_mean_r < 0 < rep.optimistic_mean_r
    assert "lower-timeframe" in rep.recommendation


def test_few_ambiguous_bars_with_a_stable_sign_are_robust() -> None:
    pess = np.full(100, 0.2)
    opt = pess.copy()
    amb = np.zeros(100, dtype=bool)
    assert intrabar_report(pess, opt, amb).status == INTRABAR_ROBUST


def test_optimistic_cannot_be_worse_than_pessimistic() -> None:
    with pytest.raises(ValueError, match="optimistic"):
        intrabar_report(np.array([1.0]), np.array([0.0]), np.array([True]))
