"""Stage B rules (research/backtest.py) and the statistics (research/stats.py)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from xau_edge_v2.research.backtest import (
    POINT,
    M1Series,
    episodes,
    r_net,
    resolve,
    run_variant,
    us,
)
from xau_edge_v2.research.stats import (
    Bound,
    block_bootstrap,
    classify,
    drawdown_r,
    n_required,
    safety_caps_hold,
    worst_month_r,
)

ROOT = Path(__file__).resolve().parents[2]
SPEC = json.loads((ROOT / "docs" / "research" / "cand_v2_spec.json").read_text(encoding="utf-8"))
T0 = datetime(2018, 3, 5, 10, 0, tzinfo=UTC)  # a Monday
MIN = 60 * 1_000_000
Bar = tuple[float, float, float, float]


def series(bars: list[Bar], *, start: datetime = T0, spread: float = 20.0) -> M1Series:
    n = len(bars)
    o, h, lo, c = (np.array(col, dtype=float) for col in zip(*bars, strict=True))
    return M1Series(
        open_us=us(start) + np.arange(n, dtype=np.int64) * MIN,
        open=o,
        high=h,
        low=lo,
        close=c,
        spread=np.full(n, spread),
    )


def flat(n: int, p: float = 2000.0) -> list[Bar]:
    return [(p, p + 0.1, p - 0.1, p)] * n


STOP, TARGET, QUOTE = 1995.8, 2008.7, 2000.1


def test_buy_target_fills_exactly_and_charges_only_the_entry_slippage() -> None:
    m1 = series([*flat(5), (2000.0, 2009.0, 1999.9, 2008.0)])
    res = resolve("BUY", STOP, TARGET, us(T0), m1)
    assert res is not None
    assert res.reason == "TAKE_PROFIT"
    assert res.exit_price == TARGET
    price, _, _ = r_net("BUY", QUOTE + 3 * POINT, res.exit_price, 0, QUOTE - STOP)
    assert price == pytest.approx((TARGET - QUOTE - 0.03) / (QUOTE - STOP))


def test_buy_stop_fills_with_adverse_slippage() -> None:
    m1 = series([*flat(3), (2000.0, 2000.1, 1995.0, 1996.0)])
    res = resolve("BUY", STOP, TARGET, us(T0), m1)
    assert res is not None
    assert res.reason == "STOP_LOSS"
    assert res.exit_price == pytest.approx(STOP - 0.03)
    price, _, _ = r_net("BUY", QUOTE + 0.03, res.exit_price, 0, QUOTE - STOP)
    assert price == pytest.approx(-1 - 0.06 / (QUOTE - STOP))  # a loss pays two slippages, once


def test_a_bar_that_reaches_both_levels_is_a_stop_and_flagged() -> None:
    m1 = series([*flat(2), (2000.0, 2010.0, 1994.0, 2000.0)])
    res = resolve("BUY", STOP, TARGET, us(T0), m1)
    assert res is not None
    assert res.reason == "STOP_LOSS"
    assert res.ambiguous


def test_sell_levels_are_hit_through_the_ask() -> None:
    # SELL entry 1999.9, stop 2004.2, target 1991.3; the exit side is the ask (bar + spread 0.20)
    stop, target = 2004.2, 1991.3
    m1 = series(
        [*flat(2), (2000.0, 2004.05, 1999.9, 2003.0)], spread=20.0
    )  # 2004.05 + 0.20 >= stop
    res = resolve("SELL", stop, target, us(T0), m1)
    assert res is not None
    assert res.reason == "STOP_LOSS"
    assert res.exit_price == pytest.approx(stop + 0.03)
    m2 = series(
        [*flat(2), (2000.0, 2000.1, 1991.05, 1992.0)], spread=20.0
    )  # 1991.05 + 0.20 <= target
    res2 = resolve("SELL", stop, target, us(T0), m2)
    assert res2 is not None
    assert res2.reason == "TAKE_PROFIT"
    m3 = series([*flat(2), (2000.0, 2000.1, 1991.15, 1992.0)], spread=20.0)  # 1991.35 > target
    res3 = resolve("SELL", stop, target, us(T0), m3)
    assert res3 is not None
    assert res3.reason == "HORIZON"


def test_bars_before_the_fill_minute_are_never_used() -> None:
    m1 = series([(2000.0, 2010.0, 1999.0, 2009.0), *flat(5)])  # the target bar is first
    res = resolve("BUY", STOP, TARGET, us(T0) + MIN, m1)  # filled one minute later
    assert res is not None
    assert res.reason == "HORIZON"


def test_a_gap_through_the_stop_is_flagged_but_the_desk_rule_still_fills_at_the_stop() -> None:
    m1 = series([*flat(2), (1990.0, 1991.0, 1989.0, 1990.0)])
    res = resolve("BUY", STOP, TARGET, us(T0), m1)
    assert res is not None
    assert res.gap
    assert res.exit_price == pytest.approx(STOP - 0.03)


def test_no_later_bar_means_no_trade() -> None:
    assert resolve("BUY", STOP, TARGET, us(T0) + 10 * MIN, series(flat(3))) is None


def test_swap_is_charged_per_rollover_night_and_is_part_of_r() -> None:
    price, swap, total = r_net("BUY", 2000.0, 2000.0, 2, 4.3)
    assert price == 0
    assert swap == pytest.approx(-76.05 * 2 * POINT / 4.3)
    assert total == swap


def test_episode_grouping() -> None:
    t = [T0 + timedelta(minutes=5 * i) for i in (0, 1, 2, 30, 31)]
    sides = ["BUY", "BUY", "SELL", "BUY", "BUY"]
    # the BUY at +150 minutes is more than 60 minutes after the previous BUY (+5): a new episode
    assert episodes(list(zip(t, sides, strict=True))) == [1, 1, 2, 3, 3]


def signal(
    at: datetime, side: str = "BUY", entry: float = QUOTE, sl: float = STOP, tp: float = TARGET
) -> dict[str, Any]:
    return {
        "ts": at, "side": side, "entry": entry, "sl": sl, "tp": tp, "net_rr": 1.8,
        "session": "LONDON", "bid": entry - 0.2, "ask": entry, "cost_r": None,
    }  # fmt: skip


def test_one_trade_per_episode_at_its_first_signal() -> None:
    m1 = series(flat(600))
    sigs = [signal(T0 + timedelta(minutes=5 * i)) for i in range(4)]  # one episode
    trades, c = run_variant("V", sigs, m1)
    assert (c.episodes, c.attempted, c.executed) == (1, 1, 1)
    assert trades[0].opened_at == T0
    assert trades[0].reason == "HORIZON"


def test_governor_refuses_a_second_open_position_and_the_cooldown_after_a_loss() -> None:
    m1 = series([*flat(70), (2000.0, 2000.1, 1990.0, 1991.0), *flat(600)])
    first = signal(T0)  # stopped at minute 70
    second = signal(
        T0 + timedelta(minutes=10), side="SELL", entry=1999.9, sl=2004.2, tp=1991.3
    )  # position open
    third = signal(
        T0 + timedelta(minutes=75)
    )  # a new episode, inside the 30-minute cooldown after the loss
    fourth = signal(T0 + timedelta(minutes=150))  # cooldown over
    trades, c = run_variant("V", [first, second, third, fourth], m1)
    assert [t.opened_at for t in trades] == [T0, T0 + timedelta(minutes=150)]
    assert c.refused.get("RISK_LIMIT", 0) >= 1
    assert c.refused.get("COOLDOWN", 0) >= 1


# ---- statistics ----
def test_the_power_table_in_the_spec_is_the_formula() -> None:
    assert SPEC["statistics"]["power"]["table"] == {
        "delta_0.30R": n_required(0.30),
        "delta_0.20R": n_required(0.20),
        "delta_0.15R": n_required(0.15),
        "delta_0.10R": n_required(0.10),
    }


def test_bootstrap_is_deterministic_and_resamples_whole_months() -> None:
    x = [1.0, -1.0, 2.0, -1.0] * 15
    m = [f"2018-{(i // 5) % 12 + 1:02d}" for i in range(len(x))]
    a, b = block_bootstrap(x, m, b=500), block_bootstrap(x, m, b=500)
    assert a == b
    assert a.lower < a.mean < a.upper
    assert (a.n, a.months) == (60, 12)


def test_statuses_follow_the_spec() -> None:
    assert (
        classify(Bound(0.5, 0.2, 0.8, 20, 10))[0] == "INCONCLUSIVE"
    )  # below N_min whatever the estimate
    assert classify(Bound(-0.5, -0.9, -0.1, 80, 20))[0] == "REFUTED_HARM"
    assert (
        classify(Bound(0.4, 0.1, 0.7, 80, 20))[0] == "INCONCLUSIVE"
    )  # positive but N < N_req(0.20R)
    assert classify(Bound(0.4, 0.1, 0.7, 700, 40))[0] == "SUPPORTED"
    assert classify(Bound(0.0, -0.3, 0.3, 700, 40))[0] == "INCONCLUSIVE"


def test_drawdown_and_worst_month_and_caps() -> None:
    assert drawdown_r([1, 1, -2, -3, 4]) == 5.0
    assert drawdown_r([]) == 0.0
    assert worst_month_r([1, -3, -2, 5], ["a", "a", "b", "b"]) == -2.0
    ok, mdd, worst = safety_caps_hold([-1.0] * 9, ["2018-01"] * 9)
    assert not ok
    assert (mdd, worst) == (9.0, -9.0)
    assert safety_caps_hold([-1.0, 2.0, -1.0], ["2018-01"] * 3)[0]
