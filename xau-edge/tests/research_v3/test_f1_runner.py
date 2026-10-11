from datetime import UTC, date, datetime
from typing import Any

import numpy as np
import pytest

from xau_edge.research_v3 import f1
from xau_edge.research_v3.data import ProtectedDataError, load_bars
from xau_edge.research_v3.execution import GROSS, M1, Fill, Scenario, rollovers, simulate
from xau_edge.research_v3.stats import block_bootstrap_means, mean_without_top, stage1_gate

MIN_US = 60_000_000


def _series(n: int, seed: int = 1) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    u = rng.normal(0, 1e-3, n)
    y = 0.3 * u + rng.normal(0, 1e-3, n)
    return y, u


def test_rolling_z_matches_the_least_squares_oracle() -> None:
    y, u = _series(1200)
    z = f1.rolling_z(y, u, chunk=97)
    assert np.isnan(z[: f1.LOOKBACK]).all()
    for i in range(f1.LOOKBACK, 1200, 37):
        assert z[i] == pytest.approx(f1.reference_z(y, u, i), rel=1e-9, abs=1e-12)


def test_z_at_t_does_not_depend_on_any_later_row() -> None:
    y, u = _series(900, seed=2)
    z = f1.rolling_z(y, u)
    y2, u2 = y.copy(), u.copy()
    y2[701:] += 5.0
    u2[701:] -= 3.0
    z2 = f1.rolling_z(y2, u2)
    np.testing.assert_array_equal(z[:701], z2[:701])


def _m1(rows: list[tuple[float, float, float, float]]) -> M1:
    t = np.arange(len(rows), dtype=np.int64) * MIN_US
    a = np.array(rows, dtype=np.float64)
    return M1(t=t, o=a[:, 0], h=a[:, 1], low=a[:, 2], spread=a[:, 3])


FLAT = [(100.0, 100.0, 100.0, 20.0)] * 10
SC = Scenario("t", 1.0, 0.0)


def _sim(m: M1, x: int, direction: int, target: float | None, sc: Scenario) -> Fill:
    f = simulate(m, 0, x, direction, 1.0, 1.0, target, sc)
    assert f is not None
    return f


def _us(y: int, mo: int, d: int, h: int, mi: int = 0) -> int:
    return int(datetime(y, mo, d, h, mi, tzinfo=UTC).timestamp() * 1e6)


def test_one_spread_per_round_trip_on_the_crossing_side() -> None:
    m = _m1(FLAT)
    long_ = simulate(m, 0, 5, 1, 1.0, 1.0, 2.0, SC)
    short = simulate(m, 0, 5, -1, 1.0, 1.0, 2.0, SC)
    gross = simulate(m, 0, 5, 1, 1.0, 1.0, 2.0, GROSS)
    assert long_ is not None and short is not None and gross is not None
    assert long_.reason == short.reason == "TIME_EXIT"
    assert long_.r == pytest.approx(-0.20)
    assert short.r == pytest.approx(-0.20)
    assert gross.r == 0.0


def test_stop_first_when_both_barriers_are_inside_one_bar() -> None:
    rows = [(100.0, 100.0, 100.0, 0.0), (100.0, 103.0, 98.0, 0.0), *FLAT]
    f = _sim(_m1(rows), 8, 1, 2.0, GROSS)
    assert (f.reason, f.r, f.exit_i) == ("STOP_LOSS", -1.0, 1)


def test_a_gap_through_the_stop_fills_at_the_open_and_a_gap_through_the_target_does_not_gift() -> (
    None
):
    gap_down = [(100.0, 100.0, 100.0, 0.0), (97.0, 97.5, 96.0, 0.0), *FLAT]
    assert _sim(_m1(gap_down), 8, 1, 2.0, GROSS).r == -3.0
    gap_up = [(100.0, 100.0, 100.0, 0.0), (105.0, 106.0, 104.0, 0.0), *FLAT]
    assert _sim(_m1(gap_up), 8, 1, 2.0, GROSS).r == 2.0


def test_short_barriers_trigger_on_the_ask() -> None:
    rows = [(100.0, 100.0, 100.0, 50.0), (100.0, 100.6, 99.9, 50.0), *FLAT]
    assert _sim(_m1(rows), 8, -1, None, SC).reason == "STOP_LOSS"


def test_simulator_matches_the_walking_oracle_on_random_paths() -> None:
    rng = np.random.default_rng(3)
    for case in range(200):
        n = 60
        c = 100 + np.cumsum(rng.normal(0, 0.4, n))
        o = np.concatenate([[100.0], c[:-1]]) + rng.normal(0, 0.05, n)
        h = np.maximum(o, c) + rng.random(n) * 0.5
        lo = np.minimum(o, c) - rng.random(n) * 0.5
        sp = rng.integers(10, 60, n).astype(float)
        m = M1(t=np.arange(n, dtype=np.int64) * MIN_US, o=o, h=h, low=lo, spread=sp)
        bars = [(int(m.t[i]), o[i], h[i], lo[i], sp[i]) for i in range(n)]
        d = 1 if case % 2 else -1
        a = 0.5 + rng.random()
        sc = Scenario("b", 1.6, 3.0)
        got = simulate(m, 2, 50, d, a, a, 2 * a, sc)
        ref = f1.reference_trade(bars, int(m.t[2]), int(m.t[50]), d, a, 1.6, 3.0)
        assert got is not None and ref is not None
        ex, reason, r = ref
        assert (int(m.t[got.exit_i]), got.reason) == (ex, reason)
        assert got.r == pytest.approx(r, abs=1e-12)


def test_loader_refuses_protected_months() -> None:
    with pytest.raises(ProtectedDataError):
        load_bars("XAUUSD", "H1", date(2021, 12, 1), date(2022, 1, 1))


def test_rollovers_count_weekday_2100_utc_instants() -> None:
    assert rollovers(_us(2015, 3, 2, 20), _us(2015, 3, 2, 22)) == 1
    assert rollovers(_us(2015, 3, 6, 20), _us(2015, 3, 9, 22)) == 2
    assert rollovers(_us(2015, 3, 4, 20), _us(2015, 3, 4, 22), triple_wednesday=True) == 3
    assert rollovers(_us(2015, 3, 2, 21), _us(2015, 3, 2, 21, 30)) == 0


def test_rollover_is_1700_new_york_in_summer_and_winter() -> None:
    assert rollovers(_us(2015, 7, 1, 20, 30), _us(2015, 7, 1, 21, 30)) == 1
    assert rollovers(_us(2015, 1, 7, 20, 30), _us(2015, 1, 7, 21, 30)) == 0
    assert rollovers(_us(2015, 1, 7, 21, 30), _us(2015, 1, 7, 22, 30)) == 1


def test_reopen_hour_uses_the_first_m1_bar_inside_the_hour() -> None:
    hour = 10 * f1.HOUR_US
    t = np.array([hour - MIN_US, hour + 5 * MIN_US, hour + 6 * MIN_US], dtype=np.int64)
    assert f1.first_in_hour(t, hour) == (1, True)
    assert f1.first_in_hour(t, hour + f1.HOUR_US)[1] is False


def test_missing_timeout_hour_drops_only_trades_that_reach_it() -> None:
    flat = _m1(FLAT)
    assert simulate(flat, 0, 5, 1, 1.0, 1.0, 2.0, GROSS, x_exists=False) is None
    hit = _m1([(100.0, 100.0, 100.0, 0.0), (100.0, 100.0, 98.0, 0.0), *FLAT])
    f = simulate(hit, 0, 5, 1, 1.0, 1.0, 2.0, GROSS, x_exists=False)
    assert f is not None and f.reason == "STOP_LOSS"


def test_bootstrap_blocks_span_the_trading_calendar() -> None:
    from xau_edge.research_v3.stats import weekday_calendar  # noqa: PLC0415

    cal = weekday_calendar(4, 400)
    assert ((cal + 3) % 7 < 5).all()
    days = cal[::2]
    v = np.where(np.arange(days.size) % 3 == 0, 1.0, -0.4)
    assert block_bootstrap_means(v, days, resamples=50, calendar=cal).shape == (50,)
    with pytest.raises(ValueError, match="missing from the trading calendar"):
        block_bootstrap_means(v, days + 1, resamples=5, calendar=cal)


def test_trading_day_puts_the_sunday_session_on_monday() -> None:
    sunday_eve = int(datetime(2015, 3, 1, 23, 30, tzinfo=UTC).timestamp() * 1e6)
    assert (f1.trading_day(sunday_eve) + 3) % 7 == 0


def test_gate_needs_every_condition() -> None:
    ok: dict[str, Any] = {
        "n": 1200,
        "n_min": 1000,
        "p": 0.01,
        "alpha": 0.0333,
        "mean_base": 0.12,
        "mean_pess": 0.02,
        "years_positive": 6,
        "mean_without_top1pct": 0.05,
        "placebo_pct": 97.0,
    }
    assert stage1_gate(**ok)["verdict"] == "PASS"
    for k, bad in [
        ("p", 0.04),
        ("mean_base", 0.09),
        ("mean_pess", 0.0),
        ("years_positive", 4),
        ("mean_without_top1pct", -0.01),
        ("placebo_pct", 94.9),
        ("n", 999),
    ]:
        assert stage1_gate(**(ok | {k: bad}))["verdict"] == "FAIL"


def test_bootstrap_is_deterministic_and_centred() -> None:
    rng = np.random.default_rng(4)
    v = rng.normal(0.2, 1.0, 3000)
    days = np.repeat(np.arange(1000), 3)
    a = block_bootstrap_means(v, days, resamples=400)
    b = block_bootstrap_means(v, days, resamples=400)
    np.testing.assert_array_equal(a, b)
    assert abs(a.mean() - v.mean()) < 0.02
    assert mean_without_top(np.arange(100.0)) == pytest.approx(np.arange(99.0).mean())
