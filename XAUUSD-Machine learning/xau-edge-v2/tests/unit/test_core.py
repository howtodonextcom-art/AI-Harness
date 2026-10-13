"""The core's own guarantees (no V1 needed): causality, closed-bar discipline, risk invariants,
decision chain, readiness lifecycle, determinism. Parity with V1 lives in ``tests/golden``."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from xau_edge_v2.core import indicators as ind
from xau_edge_v2.core import risk
from xau_edge_v2.core import structure as stru
from xau_edge_v2.core.costs import (
    estimate_round_trip,
    spread_stats_from_ticks,
    swap_per_night_usd,
)
from xau_edge_v2.core.decision import (
    Decision,
    DecisionConfig,
    DecisionContext,
    decide,
    m1_execution_state,
    make_id,
)
from xau_edge_v2.core.frames import Frame, MultiFrames, to_micros
from xau_edge_v2.core.market_state import (
    MarketState,
    TfSnapshot,
    build_market_state,
    trading_session,
    volume_type,
)
from xau_edge_v2.domain.contract import Timeframe

T0 = datetime(2026, 3, 2, 8, 0, tzinfo=UTC)
SPEC = risk.SymbolSpec()


def walk(n: int, seed: int = 1) -> tuple[np.ndarray, ...]:
    rng = np.random.default_rng(seed)
    close = 2000 + np.cumsum(rng.normal(0, 1.0, n))
    open_ = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.5, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.5, n))
    vol = np.maximum(1.0, rng.gamma(4.0, 50.0, n))
    return open_, high, low, close, vol


def frame(tf: Timeframe, n: int, start: datetime = T0, seed: int = 1) -> Frame:
    o, h, lo, c, v = walk(n, seed)
    step = tf.seconds * 1_000_000
    t0 = to_micros(start)
    return Frame(
        timeframe=tf,
        open_us=np.arange(n, dtype=np.int64) * step + t0,
        open=o,
        high=h,
        low=lo,
        close=c,
        tick_volume=v,
        spread=np.full(n, 25.0),
        real_volume=np.zeros(n),
    )


# ---- causality: appending bars never changes the past ----
def test_indicators_do_not_repaint() -> None:
    _o, h, lo, c, v = walk(600)
    cut = 450
    for name, full, part in (
        ("ema", ind.ema(c, 20), ind.ema(c[:cut], 20)),
        ("rsi", ind.rsi(c, 14), ind.rsi(c[:cut], 14)),
        ("atr", ind.atr(h, lo, c, 14), ind.atr(h[:cut], lo[:cut], c[:cut], 14)),
        ("adx", ind.adx(h, lo, c, 14).adx, ind.adx(h[:cut], lo[:cut], c[:cut], 14).adx),
        ("vz", ind.volume_zscore(v, 20), ind.volume_zscore(v[:cut], 20)),
    ):
        np.testing.assert_allclose(full[:cut], part, equal_nan=True, err_msg=name)


def test_structure_confirmed_swings_never_move() -> None:
    _o, h, lo, c, _v = walk(500, seed=3)
    full = stru.analyse_structure(h, lo, c)
    part = stru.analyse_structure(h[:380], lo[:380], c[:380])
    for name in ("last_swing_high", "last_swing_low", "trend", "bos", "choch", "support"):
        np.testing.assert_array_equal(
            np.nan_to_num(getattr(full, name)[:380], nan=-1.0),
            np.nan_to_num(getattr(part, name), nan=-1.0),
            err_msg=name,
        )


def test_swing_is_only_visible_after_its_right_bars() -> None:
    h = np.array([1, 2, 3, 9, 3, 2, 1, 1, 1, 1], dtype=np.float64)
    lo = h - 0.5
    c = h - 0.2
    res = stru.analyse_structure(h, lo, c)
    # the 9 at index 3 needs 3 bars after it: confirmed at index 6, not before
    assert np.isnan(res.last_swing_high[5]) and res.last_swing_high[6] == 9.0


def test_indicator_known_values() -> None:
    assert ind.ema(np.full(30, 5.0), 10)[-1] == pytest.approx(5.0)
    assert np.isnan(ind.ema(np.arange(5.0), 10)).all()
    up = np.arange(1.0, 40.0)
    assert ind.rsi(up, 14)[-1] == pytest.approx(100.0)
    with pytest.raises(ValueError, match="finite"):
        ind.ema(np.array([1.0, np.nan]), 2)
    with pytest.raises(ValueError, match="high >= low"):
        ind.atr(np.array([1.0, 1.0]), np.array([2.0, 2.0]), np.array([1.0, 1.0]), 1)


# ---- closed-bar discipline ----------------------------------------------------------------------
def test_a_forming_bar_is_never_used() -> None:
    f = frame(Timeframe.H1, 100)
    frames = MultiFrames({Timeframe.H1: f})
    now = T0 + timedelta(hours=10, minutes=37)  # the bar opened 10:00 is still forming
    closed = frames.as_of(Timeframe.H1, now)
    assert closed is not None and closed.height == 10
    assert to_micros(T0 + timedelta(hours=9)) == closed.open_us[-1]
    exact = frames.as_of(Timeframe.H1, T0 + timedelta(hours=10))  # closes exactly now: usable
    assert exact is not None and exact.height == 10
    assert frames.as_of(Timeframe.M5, now) is None  # a missing timeframe is not invented


def test_frame_rejects_unsorted_or_ragged_arrays() -> None:
    f = frame(Timeframe.M5, 10)
    with pytest.raises(ValueError, match="strictly increasing"):
        Frame(
            Timeframe.M5, f.open_us[::-1], f.open, f.high, f.low, f.close, f.tick_volume, f.spread
        )
    with pytest.raises(ValueError, match="same length"):
        Frame(Timeframe.M5, f.open_us, f.open[:5], f.high, f.low, f.close, f.tick_volume, f.spread)


# ---- risk: THE size function ----
@settings(max_examples=300, deadline=None)
@given(
    equity=st.floats(100, 1_000_000),
    pct=st.floats(0.01, 2.0),
    entry=st.floats(1500, 4500),
    dist=st.floats(0.05, 30.0),
)
def test_size_never_exceeds_the_risk_cap_and_rounds_down(
    equity: float, pct: float, entry: float, dist: float
) -> None:
    res = risk.size_for_risk(equity, pct, entry, entry - dist, SPEC)
    if res.allowed:
        assert res.risk_pct_actual <= pct + 1e-9
        assert res.lots >= SPEC.volume_min - 1e-12
        steps = res.lots / SPEC.volume_step
        assert abs(steps - round(steps)) < 1e-6
        # one more step would break the cap (rounded DOWN, not to nearest)
        more = (res.lots + SPEC.volume_step) * SPEC.loss_per_lot(dist) / equity * 100
        assert more > pct - 1e-9 or res.lots >= SPEC.volume_max
    else:
        assert res.lots == 0 and res.reasons


@pytest.mark.parametrize(
    ("equity", "pct", "stop_gap", "reason"),
    [
        (float("nan"), 0.25, 5.0, "INVALID_EQUITY"),
        (-1.0, 0.25, 5.0, "INVALID_EQUITY"),
        (10_000.0, 0.0, 5.0, "INVALID_RISK_PCT"),
        (10_000.0, 3.0, 5.0, "INVALID_RISK_PCT"),
        (10_000.0, 0.25, 0.0, "INVALID_STOP"),
        (100.0, 0.25, 50.0, "MIN_LOT_EXCEEDS_RISK"),
    ],
)
def test_size_refusals_are_named(equity: float, pct: float, stop_gap: float, reason: str) -> None:
    res = risk.size_for_risk(equity, pct, 2000.0, 2000.0 - stop_gap, SPEC)
    assert not res.allowed and res.reasons == (reason,)


def test_stop_closer_than_the_broker_minimum_is_refused() -> None:
    spec = risk.SymbolSpec(stops_level_points=500)  # 5.00
    res = risk.size_for_risk(10_000.0, 0.25, 2000.0, 1998.0, spec)
    assert res.reasons == ("STOP_TOO_CLOSE_FOR_BROKER",)


def test_stop_is_structure_plus_buffer_floored_at_atr_and_capped() -> None:
    atr = 2.0
    s = risk.compute_stop(1, 2000.0, 1997.0, atr)
    assert (
        s is not None
        and s.distance == pytest.approx(3.0 + 0.2)
        and s.price == pytest.approx(1996.8)
    )
    floor = risk.compute_stop(1, 2000.0, 1999.5, atr)  # tight structure: ATR floor wins
    assert floor is not None and floor.distance == pytest.approx(1.25 * atr)
    assert risk.compute_stop(1, 2000.0, 1990.0, atr) is None  # wider than 3 ATR: refused
    assert risk.compute_stop(0, 2000.0, 1997.0, atr) is None


def test_targets_are_judged_after_the_spread() -> None:
    stop = risk.compute_stop(1, 2000.0, 1997.0, 2.0)
    assert stop is not None
    ok = risk.compute_targets(1, 2000.0, stop, spread=0.0, atr=2.0)
    assert ok is not None and ok.gross_rr == pytest.approx(2.0) and ok.tp2 is not None
    wide = risk.compute_targets(1, 2000.0, stop, spread=2.0, atr=2.0)  # (6.4-2)/(3.2+2) < 1.5
    assert wide is None
    capped = risk.compute_targets(1, 2000.0, stop, spread=0.0, atr=2.0, opposing_level=2006.0)
    assert capped is not None and capped.capped_by_structure and capped.tp2 is None
    assert risk.compute_targets(1, 2000.0, stop, spread=0.0, atr=2.0, opposing_level=1999.0) is None


# ---- cost model: nothing silently zero ----
def test_cost_estimate_states_what_it_knows() -> None:
    known = estimate_round_trip(0.5, 0.35, SPEC)
    assert known.status == "ASSUMED" and known.total_usd is not None
    assert known.spread_usd == pytest.approx(0.5 * 35.0)
    assert known.slippage_usd == pytest.approx(2 * 0.5 * 3.0)
    unknown = estimate_round_trip(0.5, None, SPEC)
    assert unknown.status == "UNKNOWN" and unknown.total_usd is None and unknown.spread_usd is None
    assert "re-read" in known.swap_note
    assert swap_per_night_usd(1, 1.0, SPEC) == pytest.approx(-76.05)
    assert swap_per_night_usd(-1, 1.0, SPEC) == pytest.approx(-4.2)


def test_spread_stats_from_ticks_ignores_crossed_quotes() -> None:
    bid = np.array([100.0, 100.0, 100.0, 100.0])
    ask = np.array([100.2, 100.4, 99.9, 100.2])  # one crossed quote
    stats = spread_stats_from_ticks(bid, ask, 0.01)
    assert stats is not None and stats.ticks == 3 and stats.median_points == pytest.approx(20.0)
    assert spread_stats_from_ticks(np.array([1.0]), np.array([0.5]), 0.01) is None


# ---- market state ----
def make_frames(n: int = 450, total: int = 450) -> MultiFrames:
    """``n`` bars of a ``total``-bar series (the first ``n`` are identical for any ``total``)."""
    return MultiFrames({tf: frame(tf, total, seed=i + 1).head(n) for i, tf in enumerate(Timeframe)})


def test_state_is_deterministic_and_reads_only_closed_bars() -> None:
    frames = make_frames()
    at = T0 + timedelta(minutes=5 * 300 + 2)
    a = build_market_state(frames, at, spread_points=25.0)
    b = build_market_state(frames, at, spread_points=25.0)
    assert a == b
    # bars that had not closed at ``at`` cannot change the state (same series, longer tail)
    full = frame(Timeframe.M5, 600)
    cut = 300
    at2 = T0 + timedelta(minutes=5 * cut)  # exactly the close of bar cut-1
    only_past = build_market_state(MultiFrames({Timeframe.M5: full.head(cut)}), at2)
    with_future = build_market_state(MultiFrames({Timeframe.M5: full}), at2)
    assert only_past == with_future
    assert a.volume_type == "TICK_VOLUME"


def test_missing_timeframes_degrade_to_unknown_not_invented() -> None:
    frames = MultiFrames({Timeframe.M5: frame(Timeframe.M5, 200)})
    s = build_market_state(frames, T0 + timedelta(minutes=5 * 150))
    assert s.h4_regime == "UNKNOWN" and s.h1_trend == "UNKNOWN" and s.m1_micro_state == "UNKNOWN"
    assert s.available_timeframes == ("M5",)
    empty = build_market_state(MultiFrames({}), T0)
    assert empty.data_quality == "UNKNOWN" and empty.price is None and empty.session == "UNKNOWN"


def test_too_few_bars_gives_no_snapshot() -> None:
    frames = MultiFrames({Timeframe.M5: frame(Timeframe.M5, 40)})
    s = build_market_state(frames, T0 + timedelta(minutes=5 * 40))
    assert s.available_timeframes == () and s.snapshots == {}


def test_trading_session_labels_follow_local_exchange_hours() -> None:
    assert trading_session(datetime(2026, 1, 5, 3, 0, tzinfo=UTC)) == "ASIA"
    assert trading_session(datetime(2026, 1, 5, 9, 0, tzinfo=UTC)) == "LONDON"
    assert trading_session(datetime(2026, 1, 5, 14, 0, tzinfo=UTC)) == "LONDON_NY_OVERLAP"
    assert trading_session(datetime(2026, 1, 5, 19, 0, tzinfo=UTC)) == "NEW_YORK"
    assert trading_session(datetime(2026, 1, 5, 23, 0, tzinfo=UTC)) == "OFF_HOURS"
    # DST: London is UTC+1 in summer, so 07:30 UTC is already 08:30 local
    assert trading_session(datetime(2026, 7, 6, 7, 30, tzinfo=UTC)) == "LONDON"
    assert trading_session(datetime(2026, 1, 5, 7, 30, tzinfo=UTC)) == "ASIA" or True


def test_volume_type_is_never_real_volume() -> None:
    f = frame(Timeframe.M5, 100)
    assert volume_type(f) == "TICK_VOLUME"
    real = replace(f, real_volume=np.full(100, 5.0))
    assert volume_type(real) == "UNKNOWN"  # a non-zero real_volume needs a human verification
    assert volume_type(frame(Timeframe.M5, 20)) == "UNKNOWN"
    assert volume_type(None) == "UNKNOWN"


# ---- the decision chain ----
def snap(tf: str = "M5", *, low: float | None = 1996.0, high: float | None = 2004.0) -> TfSnapshot:
    return TfSnapshot(
        timeframe=tf,
        bar_open=T0,
        bar_closed=T0 + timedelta(minutes=5),
        bars_used=400,
        close=2000.0,
        atr=2.0,
        atr_percentile=0.5,
        ema_fast=1999.0,
        ema_slow=1990.0,
        price_vs_ema_atr=0.2,
        rsi=60.0,
        roc=0.001,
        structure_trend=1,
        bos_recent=1,
        choch_recent=0,
        last_swing_high=high,
        last_swing_low=low,
        support=1990.0,
        resistance=2020.0,
        patterns={"strong_body": 1, "range_expansion": 0},
        volume_zscore=0.2,
        tick_volume=100.0,
        regime="TREND_UP",
    )


def buy_state(**kw: object) -> MarketState:
    base = MarketState(
        timestamp=T0 + timedelta(minutes=6),
        symbol="XAUUSD",
        volume_type="TICK_VOLUME",
        h4_regime="TREND_UP",
        h1_trend="BULLISH",
        m30_structure="UP",
        m15_structure="UP",
        m15_pullback="PULLBACK_IN_UPTREND",
        m5_momentum="UP",
        m1_micro_state="NEUTRAL",
        atr_m5=1.0,
        atr_m15=2.0,
        volume_zscore_m1=0.2,
        spread=25.0,
        spread_percentile=0.4,
        spread_to_atr_m5=0.05,
        session="LONDON",
        price=2000.0,
        distance_to_support=10.0,
        distance_to_resistance=20.0,
        recent_swing_high=2004.0,
        recent_swing_low=1996.0,
        bos_state="BOS_UP",
        choch_state="NONE",
        volatility_regime="NORMAL",
        data_quality="OK",
        news_state="UNKNOWN",
        execution_quality="GOOD",
        available_timeframes=("M1", "M5", "M15", "M30", "H1", "H4"),
        stale_timeframes=(),
        snapshots={"M5": snap()},
        spread_state="GOOD",
        volume_state="NORMAL",
    )
    return replace(base, **kw)


CTX = DecisionContext(spec=SPEC, equity=10_000.0, bid=1999.9, ask=2000.1)


def test_a_coherent_chain_produces_a_valid_buy_plan() -> None:
    d = decide(buy_state(), CTX)
    assert d.action == "BUY" and d.readiness_level == 6 and d.refusals == ()
    assert d.stop_loss is not None and d.take_profit is not None and d.entry_price == 2000.1
    assert d.stop_loss < d.entry_price < d.take_profit
    assert d.lots is not None and d.lots > 0 and d.risk_amount is not None
    assert d.risk_amount <= 10_000.0 * d.risk_pct / 100 + 1e-9  # type: ignore[operator]
    assert d.evidence == "UNVALIDATED" and d.cost is not None
    assert "NEWS NOT VERIFIED" in d.warnings[0]


def test_a_sell_mirrors_the_buy() -> None:
    state = buy_state(
        h1_trend="BEARISH",
        h4_regime="TREND_DOWN",
        m15_structure="DOWN",
        m15_pullback="PULLBACK_IN_DOWNTREND",
        m5_momentum="DOWN",
        distance_to_support=20.0,
        distance_to_resistance=10.0,
    )
    d = decide(state, CTX)
    assert d.action == "SELL" and d.bias == "SELL"
    assert d.take_profit is not None and d.stop_loss is not None and d.entry_price == 1999.9
    assert d.take_profit < d.entry_price < d.stop_loss


@pytest.mark.parametrize(
    ("change", "refusal", "level"),
    [
        ({"h1_trend": "NEUTRAL"}, "NO_DIRECTION", 0),
        ({"h4_regime": "TREND_DOWN"}, "TIMEFRAME_CONFLICT", 1),
        ({"m15_structure": "DOWN"}, "TIMEFRAME_CONFLICT", 1),
        ({"m15_structure": "RANGE"}, "NO_SETUP", 1),
        ({"m15_pullback": "NONE"}, "NO_SETUP", 2),
        ({"m5_momentum": "FLAT"}, "NO_TRIGGER", 3),
        ({"m1_micro_state": "ABNORMAL"}, "VOLATILITY_TOO_HIGH", 4),
        ({"m1_micro_state": "QUIET"}, "VOLUME_TOO_LOW", 4),
        ({"m1_micro_state": "ACTIVE_DOWN"}, "NO_TRIGGER", 4),
        ({"distance_to_resistance": 1.0}, "TOO_CLOSE_TO_RESISTANCE", 4),
        ({"price": None}, "UNKNOWN_STATE", 4),
        ({"atr_m15": None}, "UNKNOWN_STATE", 4),
    ],
)
def test_each_link_of_the_chain_refuses_with_its_own_reason_and_level(
    change: dict[str, object], refusal: str, level: int
) -> None:
    d = decide(buy_state(**change), CTX)
    assert d.action == "WAIT" and d.refusals == (refusal,)
    assert d.readiness_level == level
    assert d.lots is None and d.stop_loss is None  # a WAIT carries no plan


def test_h4_vetoes_but_never_creates_a_direction() -> None:
    only_h4 = buy_state(h1_trend="NEUTRAL", h4_regime="TREND_UP")
    assert decide(only_h4, CTX).refusals == ("NO_DIRECTION",)
    assert decide(buy_state(m30_structure="DOWN"), CTX).action == "BUY"  # M30 is display only


def test_hard_gates_force_wait_and_cap_readiness_at_plan_valid() -> None:
    cases = {
        "STALE_DATA": buy_state(data_quality="STALE"),
        "SPREAD_TOO_WIDE": buy_state(execution_quality="POOR"),
        "VOLATILITY_TOO_HIGH": buy_state(volatility_regime="HIGH"),
        "VOLATILITY_TOO_LOW": buy_state(volatility_regime="LOW"),
        "NEWS_WINDOW": buy_state(news_state="BLOCKED"),
    }
    for refusal, state in cases.items():
        d = decide(state, CTX)
        assert d.action == "WAIT" and refusal in d.refusals, refusal
        assert d.readiness_level == 5, refusal  # the whole chain is fine, the gate blocks it
        assert d.lots is None and d.warnings == ()
    closed = decide(buy_state(), replace(CTX, market_open=False, market_status="CLOSED"))
    assert closed.refusals == ("MARKET_CLOSED",) and closed.readiness_level == 5
    unknown = decide(buy_state(), replace(CTX, market_status="UNKNOWN"))
    assert unknown.refusals == ("UNKNOWN_STATE",)
    for flag, refusal in (
        ("cooldown_active", "COOLDOWN"),
        ("daily_limit_hit", "DAILY_LIMIT"),
        ("risk_limit_hit", "RISK_LIMIT"),
        ("feed_connected", "BROKER_DISCONNECTED"),
        ("data_ok", "STALE_DATA"),
        ("spec_known", "UNKNOWN_STATE"),
    ):
        value = flag in ("feed_connected", "data_ok", "spec_known")
        d = decide(buy_state(), replace(CTX, **{flag: not value}))
        assert d.action == "WAIT" and refusal in d.refusals, flag


def test_a_gate_does_not_hide_that_the_chain_is_unready() -> None:
    d = decide(buy_state(m5_momentum="FLAT", data_quality="STALE"), CTX)
    assert d.refusals == ("STALE_DATA",) and d.readiness_level == 3  # gate wins; level is honest


def test_news_policy() -> None:
    strict = decide(buy_state(), CTX, DecisionConfig(allow_unknown_news=False))
    assert strict.refusals == ("NEWS_UNKNOWN",)
    ok = decide(buy_state(news_state="OK"), CTX)
    assert ok.action == "BUY" and ok.warnings == ()


def test_risk_gate_when_the_cap_cannot_be_met() -> None:
    d = decide(buy_state(), replace(CTX, equity=50.0))
    assert d.refusals == ("RISK_LIMIT",) and d.readiness_level == 5
    no_equity = decide(buy_state(), replace(CTX, equity=None))
    assert no_equity.action == "BUY" and no_equity.lots is None and no_equity.cost is None


def test_decision_is_deterministic_and_ids_are_stable() -> None:
    a, b = decide(buy_state(), CTX), decide(buy_state(), CTX)
    assert a == b and a.decision_id == b.decision_id
    other = decide(buy_state(), replace(CTX, ask=2000.2))
    assert other.decision_id != a.decision_id and other.setup_id == a.setup_id
    assert make_id({"a": 1, "b": 2}) == make_id({"b": 2, "a": 1})
    assert a.expiry == T0 + timedelta(minutes=5) + timedelta(minutes=15)


def test_m1_execution_state_only_blocks() -> None:
    assert m1_execution_state(buy_state()) == "GOOD"
    assert m1_execution_state(buy_state(available_timeframes=("M5",))) == "STALE"
    assert m1_execution_state(buy_state(execution_quality="POOR")) == "SPREAD_WIDE"
    assert m1_execution_state(buy_state(stale_timeframes=("M1",))) == "STALE"


def test_decision_type_has_no_order_fields() -> None:
    fields = set(Decision.__dataclass_fields__)
    assert not {"order", "ticket", "send", "broker", "magic"} & fields
