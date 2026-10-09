from __future__ import annotations

import numpy as np
import pytest

from xau_edge.integrity.cost_distribution import by_bucket, ev_scenarios, summarise
from xau_edge.integrity.forward_power import (
    CONSISTENT,
    INCONCLUSIVE,
    INCONSISTENT,
    LEGACY_MIN_TRADES,
    power_at,
    readiness,
    required_effective_n,
)
from xau_edge.integrity.structure_breaks import (
    ERA_DEPENDENT,
    ERA_STABLE,
    UNKNOWN,
    cusum_break,
    era_report,
)

# -- forward readiness ---------------------------------------------------------------------


def ready(**over: float) -> object:
    base: dict[str, float] = {
        "raw_n": 400,
        "effective_n": 400,
        "calendar_days": 200,
        "regimes_seen": 3,
        "observed_mean": 0.12,
        "observed_sd": 1.3,
        "expected_lower_bound": 0.02,
        "target_effect": 0.10,
        "expected_sd": 1.3,
    }
    base.update(over)
    return readiness(**base)  # type: ignore[arg-type]


def test_required_effective_n_matches_the_textbook_formula() -> None:
    assert required_effective_n(0.10, 1.3, 0.8, 0.05) == 1045  # ((1.645 + 0.842) * 1.3 / 0.1) ** 2
    assert required_effective_n(0.05, 1.3, 0.8, 0.05) > 4 * 1000


def test_hundred_raw_trades_never_conclude_anything() -> None:
    r = ready(raw_n=LEGACY_MIN_TRADES, effective_n=40)
    assert r.conclusion == INCONCLUSIVE  # type: ignore[attr-defined]
    assert r.legacy_reference_trades == LEGACY_MIN_TRADES  # type: ignore[attr-defined]
    assert any("effective N" in x for x in r.reasons)  # type: ignore[attr-defined]


def test_raw_n_is_irrelevant_when_effective_n_is_small() -> None:
    r = ready(raw_n=5000, effective_n=100)
    assert r.conclusion == INCONCLUSIVE  # type: ignore[attr-defined]


def test_calendar_and_regime_requirements_also_block_a_conclusion() -> None:
    assert ready(effective_n=2000, calendar_days=30).conclusion == INCONCLUSIVE  # type: ignore[attr-defined]
    assert ready(effective_n=2000, regimes_seen=1).conclusion == INCONCLUSIVE  # type: ignore[attr-defined]


def test_enough_evidence_gives_consistent_or_inconsistent() -> None:
    assert ready(effective_n=2000).conclusion == CONSISTENT  # type: ignore[attr-defined]
    bad = ready(effective_n=2000, observed_mean=-0.2, expected_lower_bound=0.05)
    assert bad.conclusion == INCONSISTENT  # type: ignore[attr-defined]


def test_power_grows_with_effective_n() -> None:
    assert (
        power_at(100, 0.1, 1.3, 0.05)
        < power_at(1200, 0.1, 1.3, 0.05)
        < power_at(5000, 0.1, 1.3, 0.05)
    )
    assert power_at(0, 0.1, 1.3, 0.05) == 0.0
    with pytest.raises(ValueError, match="invalid"):
        required_effective_n(0, 1.3, 0.8, 0.05)


# -- costs ---------------------------------------------------------------------------------


def test_summary_is_none_without_observations() -> None:
    assert summarise("x", np.array([])) is None
    s = summarise("london", np.linspace(0.0, 1.0, 101))
    assert s is not None
    assert s.median == pytest.approx(0.5)
    assert s.p99 == pytest.approx(0.99)


def test_buckets_are_summarised_separately() -> None:
    costs = np.array([0.1, 0.1, 0.1, 0.9, 0.9, 0.9])
    out = by_bucket(costs, ["asia"] * 3 + ["news"] * 3)
    assert out["asia"].median == pytest.approx(0.1)
    assert out["news"].median == pytest.approx(0.9)
    with pytest.raises(ValueError, match="same length"):
        by_bucket(costs, ["a"])


def test_a_candidate_that_only_works_at_median_cost_does_not_pass_the_tail() -> None:
    rng = np.random.default_rng(0)
    gross = rng.normal(0.10, 1.0, 2000)
    cost = np.concatenate([np.full(1900, 0.03), np.full(100, 0.80)])  # a fat right tail
    out = ev_scenarios(gross, cost, seed=4, draws=300)
    assert out.base > 0
    assert out.tail < out.stress <= out.base
    assert not out.passes_tail
    assert out == ev_scenarios(gross, cost, seed=4, draws=300)
    assert out.mc_p05 <= out.mc_median <= out.mc_p95


def test_ev_needs_data() -> None:
    with pytest.raises(ValueError, match="required"):
        ev_scenarios(np.array([]), np.array([0.1]), seed=1)


# -- eras and breaks -----------------------------------------------------------------------


def test_an_edge_that_exists_in_only_one_era_is_flagged() -> None:
    rng = np.random.default_rng(2)
    a = rng.normal(0.25, 1.0, 300)
    b = rng.normal(-0.15, 1.0, 300)
    rep = era_report(np.concatenate([a, b]), ["pre2021"] * 300 + ["post2021"] * 300)
    assert rep.status == ERA_DEPENDENT


def test_an_effect_present_in_every_era_is_stable() -> None:
    rng = np.random.default_rng(3)
    v = rng.normal(0.2, 1.0, 900)
    rep = era_report(v, ["a"] * 300 + ["b"] * 300 + ["c"] * 300)
    assert rep.status == ERA_STABLE


def test_one_era_carrying_the_profit_is_flagged() -> None:
    rng = np.random.default_rng(4)
    v = np.concatenate([rng.normal(0.5, 1.0, 300), rng.normal(0.02, 1.0, 300)])
    rep = era_report(v, ["a"] * 300 + ["b"] * 300)
    assert rep.status == ERA_DEPENDENT


def test_too_few_trades_per_era_is_unknown() -> None:
    assert era_report(np.ones(10), ["a"] * 5 + ["b"] * 5).status == UNKNOWN
    assert era_report(np.array([]), []).status == UNKNOWN


def test_a_mean_shift_is_found_and_noise_is_not() -> None:
    rng = np.random.default_rng(5)
    shifted = np.concatenate([rng.normal(0, 1, 200), rng.normal(1, 1, 200)])
    hit = cusum_break(shifted, seed=1, draws=200)
    assert hit["position"] is not None
    assert abs(int(hit["position"]) - 200) <= 25
    assert float(hit["p_value"]) < 0.05  # type: ignore[arg-type]
    noise = rng.normal(0, 1, 400)
    assert float(cusum_break(noise, seed=1, draws=200)["p_value"]) > 0.05  # type: ignore[arg-type]
    assert cusum_break(np.ones(10), seed=1)["position"] is None
