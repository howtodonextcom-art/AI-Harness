"""M1 execution intelligence (G10) and the system advice (G9): the state matrix.

The plan used throughout (``buy_state``): price 2000.00, ATR(M15) 2.0, spread 25 points. The
planned BUY at the last M5 close is entry 2000.125, stop 1995.80, target 2008.775, net R:R 1.84; so
the geometry still pays (net R:R >= 1.5) only while the ask stays below roughly 2000.65.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from tests.unit.test_core import CTX, SPEC, T0, buy_state
from xau_edge_v2.core.advice import advise, setup_state, trigger_state
from xau_edge_v2.core.decision import Decision, decide
from xau_edge_v2.core.execution import ExecutionAssessment, assess_execution
from xau_edge_v2.core.frames import Frame, to_micros
from xau_edge_v2.domain.contract import Timeframe

MINUTE = 60 * 1_000_000
ALL = {"TOO_EARLY", "WATCH", "FORMING", "CONFIRMED", "EXECUTION_WINDOW", "TOO_LATE", "INVALIDATED"}


def m1_frame(last: tuple[float, float, float, float], n: int = 30, base: float = 2000.0) -> Frame:
    """A quiet M1 series around ``base`` whose LAST closed candle is (open, high, low, close)."""
    t0 = to_micros(T0)
    o = np.full(n, base)
    h = np.full(n, base + 0.2)
    lo = np.full(n, base - 0.2)
    c = np.full(n, base)
    o[-1], h[-1], lo[-1], c[-1] = last
    return Frame(
        timeframe=Timeframe.M1,
        open_us=t0 + np.arange(n, dtype=np.int64) * MINUTE,
        open=o, high=h, low=lo, close=c,
        tick_volume=np.full(n, 20.0), spread=np.full(n, 25.0),
    )  # fmt: skip


GREEN_STRONG = (2000.0, 2000.45, 1999.95, 2000.35)  # body 80% with, no adverse wick
GREEN_WEAK = (2000.0, 2000.30, 1999.80, 2000.10)  # body 20% with
RED = (2000.1, 2000.15, 1999.80, 1999.90)  # against a BUY
REJECTED = (2000.0, 2000.60, 1999.95, 2000.40)  # strong body but a 50% upper wick would be needed


def assess(  # noqa: PLR0913 - a test scenario builder
    state_changes: dict[str, object] | None = None,
    last: tuple[float, float, float, float] = GREEN_STRONG,
    *,
    ask: float | None = 2000.40,
    bid: float | None = 2000.15,
    m1: Frame | str | None = "default",
    mutate_decision: dict[str, object] | None = None,
) -> tuple[ExecutionAssessment, Decision]:
    state = buy_state(**(state_changes or {}))
    decision = decide(state, CTX)
    if mutate_decision:
        decision = replace(decision, **mutate_decision)
    frame = m1_frame(last) if isinstance(m1, str) else m1
    return assess_execution(decision, state, frame, SPEC, bid=bid, ask=ask), decision


# ---- the seven states ---------------------------------------------------------------------------
def test_execution_window_a_confirmed_clean_candle_while_the_geometry_still_pays() -> None:
    a, _ = assess()
    assert (
        a.applicable and a.state == "EXECUTION_WINDOW" and a.quality == "GOOD" and a.direction == 1
    )
    assert a.net_rr_now is not None and a.net_rr_now >= 1.5
    assert a.planned_entry == pytest.approx(2000.125) and a.planned_stop == pytest.approx(1995.8)
    assert any("xác nhận" in r for r in a.reasons) and a.features["body_dir"] == pytest.approx(0.7)


def test_too_late_when_the_price_ran_and_the_net_rr_fell_below_the_strategy_minimum() -> None:
    a, _ = assess(ask=2001.5)
    assert a.state == "TOO_LATE" and a.quality == "BAD"
    assert a.net_rr_now is not None and a.net_rr_now < 1.5
    assert "R:R ròng hiện tại" in a.reasons[0] and "kế hoạch lúc trigger" in a.reasons[0]
    assert a.features["chase_price"] == pytest.approx(1.375)


def test_too_late_when_the_reward_is_gone() -> None:
    a, _ = assess(ask=2009.0)
    assert (
        a.state == "TOO_LATE" and a.net_rr_now is None and "không còn phần thưởng" in a.reasons[0]
    )


def test_invalidated_when_price_is_at_or_through_the_planned_stop() -> None:
    a, _ = assess(ask=1995.7, bid=1995.5)
    assert a.state == "INVALIDATED" and a.quality == "BAD" and "SL" in a.reasons[0]
    through = m1_frame(
        (1996.5, 1996.6, 1995.0, 1995.5)
    )  # the last closed candle closed below the stop
    b, _ = assess(m1=through, ask=1996.4)
    assert b.state == "INVALIDATED"


def test_too_early_when_the_setup_is_armed_but_m5_has_not_triggered() -> None:
    a, decision = assess({"m5_momentum": "FLAT"})
    assert decision.readiness_level == 3 and a.state == "TOO_EARLY" and a.quality == "CAUTION"
    assert "chưa xác nhận trigger" in a.reasons[0]


def test_watch_when_the_trigger_is_in_but_m1_does_not_move_with_the_trade() -> None:
    a, _ = assess(last=RED, ask=2000.1, bid=1999.9)
    assert a.state == "WATCH" and a.quality == "CAUTION" and a.features["body_dir"] < 0


def test_forming_when_m1_moves_with_the_trade_but_not_enough() -> None:
    a, _ = assess(last=GREEN_WEAK, ask=2000.2)
    assert a.state == "FORMING" and a.quality == "CAUTION"


def test_forming_not_confirmed_when_the_candle_is_rejected_from_above() -> None:
    a, _ = assess(last=(2000.0, 2001.0, 1999.95, 2000.4), ask=2000.4)  # upper wick 57%, body 38%
    assert a.state == "FORMING" and any("bấc ngược" in r for r in a.reasons)
    assert a.features["adverse_wick"] == pytest.approx(0.571, abs=1e-3)


def test_a_failed_upside_breakout_blocks_confirmation_of_a_buy() -> None:
    frame = m1_frame(GREEN_STRONG)
    high = frame.high.copy()
    high[-1] = 2000.9  # poked above the prior 10-bar high (2000.2) ...
    close = frame.close.copy()
    close[-1] = 2000.15  # ... and closed back inside
    opened = frame.open.copy()
    opened[-1] = 2000.0
    failed = Frame(
        frame.timeframe,
        frame.open_us,
        opened,
        high,
        frame.low,
        close,
        frame.tick_volume,
        frame.spread,
    )
    a, _ = assess(m1=failed, ask=2000.2)
    assert a.features["failed_breakout_against"] is True and a.state != "EXECUTION_WINDOW"
    assert any("phá vỡ giả ngược hướng" in r for r in a.reasons) or a.state == "WATCH"


def test_a_clean_candle_with_wide_spread_is_confirmed_but_bad_quality() -> None:
    a, _ = assess({"execution_quality": "POOR", "spread_percentile": 0.95})
    assert (
        a.state == "CONFIRMED" and a.quality == "BAD" and any("spread rộng" in r for r in a.reasons)
    )


def test_every_state_is_in_the_taxonomy_and_quality_is_one_of_three() -> None:
    seen = set()
    for last, ask, changes in [
        (GREEN_STRONG, 2000.4, {}), (GREEN_STRONG, 2001.6, {}), (GREEN_STRONG, 1995.5, {}),
        (RED, 2000.1, {}), (GREEN_WEAK, 2000.2, {}), (GREEN_STRONG, 2000.4, {"m5_momentum": "FLAT"}),
    ]:  # fmt: skip
        a, _ = assess(changes, last, ask=ask)
        assert a.applicable and a.state in ALL and a.quality in ("GOOD", "CAUTION", "BAD")
        seen.add(a.state)
    assert seen == ALL - {"CONFIRMED"}  # CONFIRMED needs a wide spread, shown in the test above


# ---- not applicable -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("changes", "m1", "needle"),
    [
        ({"m15_pullback": "NONE"}, "default", "chưa có setup"),
        ({"h1_trend": "NEUTRAL"}, "default", "chưa có setup"),
        ({"stale_timeframes": ("M1",)}, "default", "thiếu hoặc cũ"),
        ({}, None, "chưa đủ nến M1"),
        ({"atr_m15": None}, "default", "thiếu dữ liệu M5/ATR"),
    ],
)
def test_not_applicable_says_why_and_decides_nothing(
    changes: dict[str, object], m1: object, needle: str
) -> None:
    a, _ = assess(changes, m1=m1 if m1 is None else "default")
    assert a.applicable is False and a.state is None and a.quality is None and needle in a.reason


def test_an_invalid_plan_at_the_trigger_is_not_applicable() -> None:
    a, _ = assess(
        {"distance_to_resistance": 0.2}
    )  # no room: the strategy's own plan is refused (RR)
    assert a.applicable is False and "kế hoạch tại thời điểm trigger không hợp lệ" in a.reason


# ---- M1 cannot decide direction ------------------------------------------------------------------
def test_m1_copies_the_direction_and_never_reverses_it() -> None:
    rng = np.random.default_rng(11)
    for _ in range(300):
        n = 30
        o = 2000 + rng.normal(0, 0.5, n)
        c = 2000 + rng.normal(0, 0.5, n)
        h = np.maximum(o, c) + np.abs(rng.normal(0, 0.3, n))
        lo = np.minimum(o, c) - np.abs(rng.normal(0, 0.3, n))
        frame = Frame(
            Timeframe.M1,
            to_micros(T0) + np.arange(n, dtype=np.int64) * MINUTE,
            o,
            h,
            lo,
            c,
            np.full(n, 9.0),
            np.full(n, 25.0),
        )
        ask = float(2000 + rng.normal(0, 2))
        buy, _ = assess(m1=frame, ask=ask)
        sell_state = {
            "h1_trend": "BEARISH", "h4_regime": "TREND_DOWN", "m15_structure": "DOWN",
            "m15_pullback": "PULLBACK_IN_DOWNTREND", "m5_momentum": "DOWN",
            "distance_to_support": 20.0, "distance_to_resistance": 10.0,
        }  # fmt: skip
        sell, _ = assess(sell_state, m1=frame, bid=ask - 0.25, ask=None)
        if buy.applicable:
            assert buy.direction == 1
        if sell.applicable:
            assert sell.direction == -1


def test_a_bearish_bias_is_assessed_as_a_sell_with_mirrored_geometry() -> None:
    sell_state = {
        "h1_trend": "BEARISH", "h4_regime": "TREND_DOWN", "m15_structure": "DOWN",
        "m15_pullback": "PULLBACK_IN_DOWNTREND", "m5_momentum": "DOWN",
        "distance_to_support": 20.0, "distance_to_resistance": 10.0,
    }  # fmt: skip
    red_strong = (2000.0, 2000.05, 1999.55, 1999.65)
    a, _ = assess(sell_state, red_strong, bid=1999.6, ask=None)
    assert a.direction == -1 and a.planned_stop is not None and a.planned_stop > a.planned_entry  # type: ignore[operator]
    assert a.state == "EXECUTION_WINDOW"


# ---- determinism, locality, no side effects --------------------------------------------------------
def test_the_assessment_is_deterministic_local_and_does_not_touch_its_inputs() -> None:
    frame = m1_frame(GREEN_STRONG)
    before = frame.close.copy()
    a, _ = assess(m1=frame)
    b, _ = assess(m1=frame)
    assert a == b
    np.testing.assert_array_equal(frame.close, before)
    older = frame.close.copy()
    older[:10] += 5.0  # bars older than the window the rules read cannot matter
    moved = Frame(
        frame.timeframe,
        frame.open_us,
        frame.open,
        frame.high,
        frame.low,
        older,
        frame.tick_volume,
        frame.spread,
    )
    c, _ = assess(m1=moved)
    assert (c.state, c.quality, c.features["body_dir"]) == (
        a.state,
        a.quality,
        a.features["body_dir"],
    )


# ---- the system advice ------------------------------------------------------------------------------
def test_a_strategy_candidate_with_a_good_moment_is_a_candidate_for_the_human() -> None:
    a, decision = assess()
    advice = advise(decision, a)
    assert decision.action == "BUY" and advice.recommendation == "BUY_CANDIDATE"
    assert advice.strategy_action == "BUY" and advice.primary_blocker is None
    assert (
        advice.setup_state == "ARMED"
        and advice.trigger_state == "CONFIRMED"
        and advice.bias == "BUY"
    )
    assert "CON NGƯỜI" in advice.reasons[0]


def test_too_late_turns_a_strategy_buy_into_a_wait_without_changing_the_strategy() -> None:
    a, decision = assess(ask=2001.5)
    advice = advise(decision, a)
    assert decision.action == "BUY"  # the strategy still says BUY, untouched
    assert advice.recommendation == "WAIT" and advice.strategy_action == "BUY"
    assert (
        advice.primary_blocker == "M1_TOO_LATE"
        and "chưa phải thời điểm thực thi" in advice.reasons[0]
    )
    assert advice.bias == "BUY"  # M1 never turns the bias into SELL


@pytest.mark.parametrize(
    ("last", "ask", "blocker"),
    [
        (RED, 2000.1, "M1_WATCH"),
        (GREEN_WEAK, 2000.2, "M1_FORMING"),
        (GREEN_STRONG, 1995.5, "M1_INVALIDATED"),
    ],
)
def test_other_m1_states_hold_a_candidate_back(
    last: tuple[float, float, float, float], ask: float, blocker: str
) -> None:
    a, decision = assess(last=last, ask=ask)
    advice = advise(decision, a)
    if decision.action == "BUY":
        assert advice.recommendation == "WAIT" and advice.primary_blocker == blocker
    assert advice.bias in ("BUY", "NEUTRAL") and advice.recommendation != "SELL_CANDIDATE"


def test_a_strategy_wait_stays_wait_and_m1_can_never_create_a_candidate() -> None:
    for changes in ({"m5_momentum": "FLAT"}, {"data_quality": "STALE"}, {"h1_trend": "NEUTRAL"}):
        a, decision = assess(changes)
        advice = advise(decision, a)
        assert decision.action == "WAIT" and advice.recommendation == "WAIT"
        assert advice.primary_blocker == decision.refusals[0]
        assert advice.secondary == decision.refusals[1:]


def test_no_m1_assessment_means_wait_not_a_guess() -> None:
    _, decision = assess()
    for missing in (None, ExecutionAssessment(applicable=False, reason="nến M1 thiếu hoặc cũ")):
        advice = advise(decision, missing)
        assert advice.recommendation == "WAIT" and advice.primary_blocker == "M1_UNKNOWN"


def test_holding_a_paper_position_is_hold_and_a_reversed_h1_is_only_exit_watch() -> None:
    a, decision = assess()
    assert advise(decision, a, held_side="BUY").recommendation == "HOLD"
    bearish = decide(buy_state(h1_trend="BEARISH", h4_regime="TREND_DOWN"), CTX)
    watch = advise(bearish, None, held_side="BUY")
    assert watch.recommendation == "EXIT_WATCH" and "ngược với lệnh PAPER BUY" in watch.reasons[0]
    assert advise(bearish, None, held_side="SELL").recommendation == "HOLD"


def test_setup_and_trigger_states_follow_the_strategy_readiness_exactly() -> None:
    expected = {
        0: ("NONE", "NONE"),
        1: ("NONE", "NONE"),
        2: ("WATCHING", "NONE"),
        3: ("ARMED", "WAITING"),
        4: ("ARMED", "CONFIRMED"),
        6: ("ARMED", "CONFIRMED"),
    }
    for level, (setup, trigger) in expected.items():
        fake = replace(decide(buy_state(), CTX), readiness_level=level)
        assert (setup_state(fake), trigger_state(fake)) == (setup, trigger)
