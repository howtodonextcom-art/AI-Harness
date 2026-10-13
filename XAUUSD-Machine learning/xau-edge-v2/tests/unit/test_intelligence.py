"""The market-intelligence layer: causal, non-repainting, deterministic, and without authority.

Adversarial intent: every test tries to break one promise (no look-ahead, no repainting, the
control decision untouched, the market reason kept apart from gates and governor, safe on
pathological bars).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.unit.test_core import CTX, SPEC, T0, buy_state, frame
from xau_edge_v2.core import structure as stru
from xau_edge_v2.core.decision import DecisionConfig, DecisionContext, decide
from xau_edge_v2.core.frames import Frame, MultiFrames, to_micros
from xau_edge_v2.core.intelligence import price_action as pa
from xau_edge_v2.core.intelligence import structure_events as se
from xau_edge_v2.core.intelligence import volatility as vol
from xau_edge_v2.core.intelligence.funnel import (
    build_authorization,
    gate_category,
    real_gates,
    ungated_decision,
)
from xau_edge_v2.core.intelligence.observe import IntelMemo, diff, observe
from xau_edge_v2.core.market_state import build_market_state
from xau_edge_v2.domain.contract import Timeframe

CFG = DecisionConfig()


def describe(code: str) -> tuple[str, str | None]:
    return code.lower(), "next " + code.lower()


def bars(rows: list[tuple[float, float, float, float]], tf: Timeframe = Timeframe.M5) -> Frame:
    n = len(rows)
    step = tf.seconds * 1_000_000
    o, h, lo, c = (np.array(col, dtype=np.float64) for col in zip(*rows, strict=True))
    return Frame(
        tf,
        np.arange(n, dtype=np.int64) * step + to_micros(T0),
        o,
        h,
        lo,
        c,
        np.full(n, 100.0),
        np.full(n, 25.0),
    )


BASE = [(100.0, 101.0, 99.0, 100.0)] * 40
"""Forty identical 2-point bars: ATR 2, a flat history to put one special bar after."""


def last_kinds(rows: list[tuple[float, float, float, float]]) -> set[str]:
    f = bars(BASE + rows)
    return {e.kind for e in pa.detect(f, last=1)}


# ---- price action: each description fires on its own bar --------------------------------------
def test_wick_rejection_both_sides() -> None:
    assert "UPPER_WICK_REJECTION" in last_kinds([(100.0, 104.0, 99.9, 100.2)])
    assert "LOWER_WICK_REJECTION" in last_kinds([(100.2, 100.3, 96.0, 100.0)])


def test_a_small_bar_is_not_a_rejection() -> None:
    assert not last_kinds([(100.0, 100.3, 99.95, 100.05)]) & {
        "UPPER_WICK_REJECTION",
        "LOWER_WICK_REJECTION",
    }


def test_engulfing_needs_opposite_colours_and_cover() -> None:
    assert "BULL_ENGULFING" in last_kinds([(102.0, 102.1, 99.9, 100.0), (99.8, 102.6, 99.7, 102.5)])
    assert "BEAR_ENGULFING" in last_kinds([(100.0, 102.1, 99.9, 102.0), (102.2, 102.3, 99.4, 99.5)])
    assert "BULL_ENGULFING" not in last_kinds(
        [(102.0, 102.1, 99.9, 100.0), (100.5, 102.6, 100.4, 101.5)]  # does not cover the body
    )


def test_displacement_inside_outside() -> None:
    assert "BULL_DISPLACEMENT" in last_kinds([(100.0, 104.2, 99.9, 104.0)])
    assert "BEAR_DISPLACEMENT" in last_kinds([(104.0, 104.1, 99.8, 100.0)])
    assert "INSIDE_BAR" in last_kinds([(100.0, 100.8, 99.2, 100.0)])
    assert "OUTSIDE_BAR" in last_kinds([(100.0, 102.0, 98.0, 100.0)])


def test_failed_breakout_is_a_sweep_that_closes_back() -> None:
    assert "FAILED_BREAKOUT_UP" in last_kinds([(100.0, 103.0, 99.8, 100.5)])
    assert "FAILED_BREAKOUT_DOWN" in last_kinds([(100.0, 100.2, 97.0, 99.6)])
    assert "FAILED_BREAKOUT_UP" not in last_kinds([(100.0, 103.0, 99.8, 102.8)])  # closed beyond


@pytest.mark.parametrize("seed", [1, 2, 3, 4])
def test_price_action_never_repaints_and_is_known_at_its_own_close(seed: int) -> None:
    f = frame(Timeframe.M5, 400, seed=seed)
    full = pa.detect(f)
    assert full
    for e in full:
        assert e.known_at_us == int(f.available_us[e.index])  # not earlier than the bar closes
        assert e.known_at_us > e.bar_open_us
    for cut in (120, 250, 333):
        part = pa.detect(f.head(cut))
        assert part == [e for e in full if e.index < cut]


# ---- structure events: knowledge time and parity with the strategy's own swing rule -------------
def test_swing_is_known_only_after_its_right_bars() -> None:
    h = np.array([1, 2, 3, 9, 3, 2, 1, 1, 1, 1, 1, 1], dtype=np.float64)
    f = bars([(x, x + 0.1, x - 0.5, x - 0.2) for x in h], Timeframe.H1)
    s = [x for x in se.swings(f) if x.kind == "HIGH" and x.confirmed]
    assert [x.price for x in s] == [9.1]
    assert s[0].index == 3 and s[0].known_at_us == int(f.available_us[6])


@pytest.mark.parametrize("seed", [3, 5, 8])
def test_confirmed_swings_match_the_strategy_structure(seed: int) -> None:
    f = frame(Timeframe.H1, 500, seed=seed)
    res = stru.analyse_structure(f.high, f.low, f.close)
    items = se.swings(f)
    hi = se.last_swing(items, "HIGH")
    lo = se.last_swing(items, "LOW")
    assert hi is not None and lo is not None
    assert hi.price == res.last_swing_high[-1]
    assert lo.price == res.last_swing_low[-1]


@pytest.mark.parametrize("seed", [3, 9])
def test_swings_and_structure_events_do_not_repaint(seed: int) -> None:
    f = frame(Timeframe.M15, 500, seed=seed)
    full_swings = [s for s in se.swings(f) if s.confirmed]
    full_events = se.structure_events(f)
    assert full_events
    for cut in (200, 321, 440):
        part = f.head(cut)
        assert [s for s in se.swings(part) if s.confirmed] == [
            s for s in full_swings if s.index + stru.SWING_RIGHT <= cut - 1
        ]
        assert se.structure_events(part) == [e for e in full_events if e.index < cut]
        for e in full_events:
            assert e.known_at_us == int(f.available_us[e.index])


def test_a_provisional_swing_is_flagged_and_may_vanish() -> None:
    rows = [(x, x + 0.1, x - 0.5, x - 0.2) for x in [1, 2, 3, 4, 5, 6, 9, 5, 4]]
    f = bars(rows, Timeframe.H1)
    prov = [s for s in se.swings(f) if s.kind == "HIGH" and not s.confirmed]
    assert prov and prov[-1].price == 9.1
    later = bars([*rows, (10.0, 10.5, 9.9, 10.2)], Timeframe.H1)  # a higher high replaces it
    assert not any(s.price == 9.1 and s.confirmed for s in se.swings(later))


# ---- volatility phase ---------------------------------------------------------------------------
def test_compression_expansion_and_box_breakout() -> None:
    wide = [(100.0, 102.0, 98.0, 100.0)] * 80
    tight = [(100.0, 100.3, 99.7, 100.0)] * 20
    v = vol.analyse(bars(wide + tight))
    assert v.phase == "COMPRESSION" and v.box_valid and v.box_breakout == 0
    out = vol.analyse(bars(wide + tight + [(100.0, 101.6, 99.9, 101.5)]))
    assert out.box_breakout == 1 and out.box_known_at_us is not None
    down = vol.analyse(bars(wide + tight + [(100.0, 100.1, 98.4, 98.5)]))
    assert down.box_breakout == -1
    spike = vol.analyse(bars([*wide, (100.0, 108.0, 99.0, 107.0)]))
    assert spike.phase == "EXPANSION"


def test_volatility_unknown_when_history_is_short_or_flat() -> None:
    assert vol.analyse(bars([(100.0, 101.0, 99.0, 100.0)] * 10)).phase == "UNKNOWN"
    flat = bars([(100.0, 100.0, 100.0, 100.0)] * 80)
    assert vol.analyse(flat).phase == "UNKNOWN"  # ATR 0: nothing can be said, and no crash
    assert pa.detect(flat) == []


# ---- the market's reason is kept apart from the gates and the governor --------------------------
def authorize(state, ctx=CTX):  # type: ignore[no-untyped-def]
    decision = decide(state, ctx, CFG)
    return decision, build_authorization(
        state,
        decision,
        ungated_decision(state, ctx, CFG),
        real_gates(state, ctx, CFG),
        describe,
    )


def test_a_hard_gate_no_longer_hides_a_missing_direction() -> None:
    state = buy_state(h1_trend="NEUTRAL", execution_quality="POOR")
    decision, auth = authorize(state)
    assert decision.refusals == ("SPREAD_TOO_WIDE",)  # what V1 / the strategy shows
    assert auth.chain_verdict == "NO_DIRECTION"  # what the market says
    assert [g.code for g in auth.gates] == ["SPREAD_TOO_WIDE"]
    assert auth.funnel[0].status == "FAIL" and auth.funnel[1].status == "NOT_REACHED"
    assert {s.key: s.status for s in auth.funnel}["GATE_COST"] == "FAIL"
    assert "NO_DIRECTION".lower() in auth.explanation


def test_the_governor_is_not_a_market_statement() -> None:
    ctx = replace(CTX, cooldown_active=True)
    decision, auth = authorize(buy_state(), ctx)
    assert decision.action == "WAIT" and decision.refusals == ("COOLDOWN",)
    assert auth.chain_verdict == "CHAIN_OK" and auth.chain_blocker is None
    assert [g.code for g in auth.system_hold] == ["COOLDOWN"] and auth.gates == ()
    assert {s.key: s.status for s in auth.funnel}["GATE_GOVERNOR"] == "FAIL"
    assert all(s.status == "PASS" for s in auth.funnel[:7])


def test_a_valid_buy_has_no_gate_and_no_hold() -> None:
    decision, auth = authorize(buy_state())
    assert decision.action == "BUY"
    assert auth.chain_verdict == "CHAIN_OK" and auth.gates == () and auth.system_hold == ()
    assert auth.candidate_active is False and auth.evidence == "UNVALIDATED"
    assert auth.strategy_version == decision.strategy_version == "1.1.0"


@pytest.mark.parametrize(
    ("change", "step"),
    [
        ({"m15_pullback": "NONE"}, "M15_SETUP"),
        ({"m5_momentum": "FLAT"}, "M5_TRIGGER"),
        ({"m1_micro_state": "QUIET"}, "M1_TIMING"),
        ({"distance_to_resistance": 1.0}, "ROOM"),
        ({"m15_structure": "DOWN"}, "HTF_CONFLICT"),
    ],
)
def test_the_funnel_names_the_first_failing_link(change: dict[str, object], step: str) -> None:
    _, auth = authorize(buy_state(**change))
    failing = [s.key for s in auth.funnel if s.status == "FAIL"]
    assert failing[0] == step
    seen = False
    for s in auth.funnel[:7]:
        if s.key == step:
            seen = True
        elif seen:
            assert s.status == "NOT_REACHED"
        else:
            assert s.status == "PASS"


def test_asking_the_question_does_not_change_the_answer() -> None:
    state = buy_state(h1_trend="NEUTRAL", execution_quality="POOR")
    before = decide(state, CTX, CFG)
    ungated_decision(state, CTX, CFG)
    real_gates(state, CTX, CFG)
    assert decide(state, CTX, CFG) == before


@settings(max_examples=300, deadline=None)
@given(
    h1=st.sampled_from(["BULLISH", "BEARISH", "NEUTRAL"]),
    pullback=st.sampled_from(["PULLBACK_IN_UPTREND", "PULLBACK_IN_DOWNTREND", "NONE"]),
    structure=st.sampled_from(["UP", "DOWN", "RANGE"]),
    mom=st.sampled_from(["UP", "DOWN", "FLAT"]),
    exec_q=st.sampled_from(["GOOD", "POOR"]),
    vol_reg=st.sampled_from(["LOW", "NORMAL", "HIGH"]),
    h4=st.sampled_from(["TREND_UP", "TREND_DOWN", "RANGE", "SHOCK"]),
    cooldown=st.booleans(),
)
def test_authorization_is_consistent_with_the_strategy(  # noqa: PLR0913, PLR0917 - a property over the chain
    h1: str,
    pullback: str,
    structure: str,
    mom: str,
    exec_q: str,
    vol_reg: str,
    h4: str,
    cooldown: bool,
) -> None:
    state = buy_state(
        h1_trend=h1, m15_pullback=pullback, m15_structure=structure, m5_momentum=mom,
        execution_quality=exec_q, volatility_regime=vol_reg, h4_regime=h4,
    )  # fmt: skip
    ctx = replace(CTX, cooldown_active=cooldown)
    decision, auth = authorize(state, ctx)
    clear = auth.chain_verdict == "CHAIN_OK" and not auth.gates and not auth.system_hold
    assert (decision.action in ("BUY", "SELL")) == clear
    if decision.action == "WAIT" and not auth.gates and not auth.system_hold:
        assert auth.chain_verdict == decision.refusals[0]  # no gate: same word as the strategy
    assert all(gate_category(g.code) != "GOVERNOR" for g in auth.gates)
    assert all(gate_category(g.code) == "GOVERNOR" for g in auth.system_hold)


# ---- the engine on real-shaped frames -----------------------------------------------------------
def multi(n: int = 420) -> MultiFrames:
    frames = {
        tf: frame(tf, n, start=T0, seed=i + 1)
        for i, tf in enumerate(
            (Timeframe.M1, Timeframe.M5, Timeframe.M15, Timeframe.H1, Timeframe.H4)
        )
    }
    return MultiFrames(frames)


def run(frames: MultiFrames, ctx: DecisionContext = CTX, *, quote_age: float | None = 1.0):  # type: ignore[no-untyped-def]
    at = T0 + timedelta(days=200)
    state = build_market_state(frames, at, spread_points=25.0, market_open=True)
    decision = decide(state, ctx, CFG)
    auth = build_authorization(
        state, decision, ungated_decision(state, ctx, CFG), real_gates(state, ctx, CFG), describe
    )
    return (
        state,
        decision,
        auth,
        observe(frames, at, state, decision, auth, IntelMemo(), quote_age_s=quote_age),
    )


def test_observe_is_deterministic_and_has_no_authority() -> None:
    frames = multi()
    a = run(frames)[3]
    b = run(frames)[3]
    assert a == b
    assert a.authority == "NONE" and a.descriptive_only is True
    assert {s.key for s in a.scenarios} == {
        "NO_TRADE",
        "CONTINUATION",
        "BREAKOUT",
        "REVERSAL",
        "RANGE",
    }
    assert [t.timeframe for t in a.timeframes] == [
        Timeframe.H4,
        Timeframe.H1,
        Timeframe.M15,
        Timeframe.M5,
        Timeframe.M1,
    ]


def test_every_event_is_known_no_earlier_than_its_bar_closes() -> None:
    intel = run(multi())[3]
    assert intel.events
    for e in intel.events:
        length = timedelta(seconds=e.timeframe.seconds)
        assert e.known_at >= e.bar_open + length


def test_pathological_inputs_fail_safe() -> None:
    n = 80
    gap = frame(Timeframe.H1, n)
    jumped = Frame(
        gap.timeframe, gap.open_us, gap.open, gap.high + 500.0 * (np.arange(n) > 60), gap.low,
        gap.close, gap.tick_volume, gap.spread,
    )  # fmt: skip
    only_h1 = MultiFrames({Timeframe.H1: jumped})
    state = build_market_state(only_h1, T0 + timedelta(days=30), spread_points=None)
    decision = decide(state, CTX, CFG)
    auth = build_authorization(
        state, decision, ungated_decision(state, CTX, CFG), real_gates(state, CTX, CFG), describe
    )
    intel = observe(
        only_h1, T0 + timedelta(days=30), state, decision, auth, IntelMemo(), quote_age_s=None
    )
    assert decision.action != "BUY" and intel.authority == "NONE"
    assert any(not t.available for t in intel.timeframes)  # a missing timeframe is not invented
    empty = observe(MultiFrames({}), T0, state, decision, auth, IntelMemo(), quote_age_s=None)
    assert all(not t.available for t in empty.timeframes) and empty.events == ()


def test_a_shock_or_a_wide_spread_marks_the_market_as_cautious() -> None:
    frames = multi()
    state = build_market_state(frames, T0 + timedelta(days=200), spread_points=25.0)
    poor = replace(state, execution_quality="POOR")
    decision = decide(poor, CTX, CFG)
    auth = build_authorization(
        poor, decision, ungated_decision(poor, CTX, CFG), real_gates(poor, CTX, CFG), describe
    )
    intel = observe(
        frames, T0 + timedelta(days=200), poor, decision, auth, IntelMemo(), quote_age_s=2.0
    )
    no_trade = next(s for s in intel.scenarios if s.key == "NO_TRADE")
    assert no_trade.status == "BLOCKED"


def test_changes_report_what_moved_between_two_evaluations() -> None:
    frames = multi()
    a = run(frames)[3]
    ctx2 = replace(CTX, cooldown_active=True)
    b = run(frames, ctx2)[3]
    moved = diff(a, b)
    assert any(c.kind == "GOVERNOR" and "COOLDOWN" in c.text for c in moved)
    assert diff(a, a) == []


def test_sizing_spec_is_untouched() -> None:
    assert SPEC.point == 0.01  # the shared fixture the control tests rely on
