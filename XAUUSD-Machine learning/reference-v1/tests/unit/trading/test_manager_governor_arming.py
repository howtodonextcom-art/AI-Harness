from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from xau_edge.config import Settings
from xau_edge.trading.arming import (
    ArmState,
    clear_marker,
    effective_state,
    read_marker,
    write_marker,
)
from xau_edge.trading.governor import GovernorConfig, TradeGovernor
from xau_edge.trading.position_manager import (
    ManagerConfig,
    ManagerContext,
    PositionState,
    SlStage,
    TrailModel,
    apply,
    evaluate,
)
from xau_edge.trading.schema import Refusal

T0 = datetime(2026, 3, 3, 10, 0, tzinfo=UTC)


def long_pos(**over: object) -> PositionState:
    base = {
        "ticket": "t1",
        "direction": 1,
        "lots": 0.2,
        "entry": 2000.0,
        "initial_sl": 1995.0,
        "sl": 1995.0,
        "tp": 2010.0,
        "opened_at": T0,
    }
    base.update(over)
    return PositionState(**base)  # type: ignore[arg-type]


def ctx(now: datetime = T0 + timedelta(minutes=10), **over: object) -> ManagerContext:
    base: dict[str, object] = {
        "now": now,
        "bar_high": 2002.0,
        "bar_low": 1998.0,
        "last_price": 2001.0,
        "atr": 2.0,
    }
    base.update(over)
    return ManagerContext(**base)  # type: ignore[arg-type]


OFF = ManagerConfig()

# -- automatic exits -----------------------------------------------------------------------


def test_stop_loss_and_take_profit_close_with_their_reason() -> None:
    assert evaluate(long_pos(), ctx(bar_low=1994.0), OFF).reason == "STOP_LOSS"
    assert evaluate(long_pos(), ctx(bar_high=2011.0), OFF).reason == "TAKE_PROFIT"
    short = long_pos(direction=-1, initial_sl=2005.0, sl=2005.0, tp=1990.0)
    assert evaluate(short, ctx(bar_high=2006.0), OFF).reason == "STOP_LOSS"
    assert evaluate(short, ctx(bar_low=1989.0), OFF).reason == "TAKE_PROFIT"


def test_when_both_levels_are_reached_in_one_bar_the_stop_wins() -> None:
    action = evaluate(long_pos(), ctx(bar_low=1994.0, bar_high=2011.0), OFF)
    assert action.kind == "CLOSE"
    assert action.reason == "STOP_LOSS"


def test_time_expiry_forced_flat_and_invalidation() -> None:
    cfg = ManagerConfig(max_hold_minutes=60)
    assert evaluate(long_pos(), ctx(T0 + timedelta(minutes=61)), cfg).reason == "TIME_EXPIRY"
    assert evaluate(long_pos(), ctx(T0 + timedelta(minutes=59)), cfg).kind == "HOLD"
    flat = ctx(must_flat_by=T0 + timedelta(minutes=5))
    assert evaluate(long_pos(), flat, cfg).reason == "FORCED_FLAT"
    assert evaluate(long_pos(), ctx(invalidated=True), cfg).reason == "INVALIDATION"
    keep = ManagerConfig(close_on_invalidation=False)
    assert evaluate(long_pos(), ctx(invalidated=True), keep).kind == "HOLD"


def test_opposite_signal_and_spread_emergency_follow_the_policy() -> None:
    assert evaluate(long_pos(), ctx(opposite_signal=True), OFF).kind == "HOLD"
    on = ManagerConfig(close_on_opposite_signal=True, spread_emergency_points=150.0)
    assert evaluate(long_pos(), ctx(opposite_signal=True), on).reason == "OPPOSITE_SIGNAL"
    assert evaluate(long_pos(), ctx(spread_points=200.0), on).reason == "SPREAD_EMERGENCY"
    assert evaluate(long_pos(), ctx(spread_points=200.0), OFF).kind == "HOLD"


def test_emergencies_beat_everything_and_have_a_priority() -> None:
    c = ctx(kill_switch=True, daily_loss_guard=True, equity_floor_hit=True, bar_high=2011.0)
    assert evaluate(long_pos(), c, OFF).reason == "KILL_SWITCH"
    assert evaluate(long_pos(), ctx(daily_loss_guard=True, equity_floor_hit=True), OFF).reason == (
        "DAILY_LOSS_GUARD"
    )
    assert evaluate(long_pos(), ctx(equity_floor_hit=True), OFF).reason == "EQUITY_FLOOR"


# -- break-even and trailing ---------------------------------------------------------------


def test_break_even_is_off_by_default_and_moves_the_stop_once_enabled() -> None:
    reached = ctx(bar_high=2005.5, bar_low=2003.0, last_price=2005.0)  # +1.1 R (risk is 5.0)
    assert evaluate(long_pos(), reached, OFF).kind == "HOLD"
    on = ManagerConfig(break_even_enabled=True)
    action = evaluate(long_pos(), reached, on)
    assert action.kind == "MODIFY_SL"
    assert action.stage is SlStage.BREAK_EVEN
    assert action.new_sl == pytest.approx(2000.25)  # entry + 0.05 R buffer
    moved = apply(long_pos(), action)
    assert moved.sl == pytest.approx(2000.25)
    assert moved.stage is SlStage.BREAK_EVEN
    assert evaluate(moved, reached, on).kind == "HOLD"  # only once
    below = ctx(bar_high=2004.0)
    assert evaluate(long_pos(), below, on).kind == "HOLD"  # +0.8 R is not enough


def test_trailing_distinguishes_the_three_stops_and_never_starts_early() -> None:
    cfg = ManagerConfig(break_even_enabled=True, trail_model=TrailModel.ATR, trail_atr_k=2.0)
    early = ctx(bar_high=2005.5, bar_low=2003.0, last_price=2005.0)
    assert evaluate(long_pos(), early, cfg).stage is SlStage.BREAK_EVEN
    late = ctx(
        bar_high=2008.0, bar_low=2006.0, last_price=2007.0, atr=2.0
    )  # +1.6 R: trailing may start
    action = evaluate(long_pos(), late, cfg)
    assert action.stage is SlStage.TRAILING
    assert action.new_sl == pytest.approx(2003.0)  # 2007 - 2*2
    trailed = apply(long_pos(), action)
    lower = ctx(bar_high=2008.0, bar_low=2003.5, last_price=2004.0, atr=2.0)
    assert evaluate(trailed, lower, cfg).kind == "HOLD"  # a lower candidate never loosens it


def test_swing_and_chandelier_trailing() -> None:
    swing = ManagerConfig(trail_model=TrailModel.SWING)
    c = ctx(bar_high=2008.0, last_price=2007.0, swing_low=2002.0)
    assert evaluate(long_pos(), c, swing).new_sl == pytest.approx(2002.0)
    chand = ManagerConfig(trail_model=TrailModel.CHANDELIER, trail_atr_k=2.5)
    c2 = ctx(bar_high=2008.0, last_price=2007.0, atr=2.0, highest_since_entry=2008.0)
    assert evaluate(long_pos(), c2, chand).new_sl == pytest.approx(2003.0)
    missing = ctx(bar_high=2008.0, last_price=2007.0, atr=None)
    assert evaluate(long_pos(), missing, ManagerConfig(trail_model=TrailModel.ATR)).kind == "HOLD"


def test_the_short_side_mirrors_break_even_and_trailing() -> None:
    short = long_pos(direction=-1, initial_sl=2005.0, sl=2005.0, tp=1990.0)
    cfg = ManagerConfig(break_even_enabled=True, trail_model=TrailModel.ATR)
    c = ctx(bar_low=1993.0, bar_high=1996.0, last_price=1994.0, atr=2.0)  # +1.4 R
    action = evaluate(short, c, cfg)
    assert action.kind == "MODIFY_SL"
    assert action.new_sl is not None
    assert action.new_sl < 2005.0


@given(
    st.lists(
        st.tuples(
            st.floats(1990, 2015),
            st.floats(0.1, 6.0),
            st.floats(0.5, 4.0),
        ),
        min_size=1,
        max_size=40,
    )
)
@settings(max_examples=80, deadline=None)
def test_the_stop_never_moves_the_wrong_way_whatever_the_market_does(
    path: list[tuple[float, float, float]],
) -> None:
    cfg = ManagerConfig(
        break_even_enabled=True, trail_model=TrailModel.ATR, max_hold_minutes=10_000
    )
    pos = long_pos(tp=3000.0)
    now = T0
    for price, spread, atr in path:
        now += timedelta(minutes=1)
        c = ctx(
            now,
            bar_high=price + spread,
            bar_low=price - spread,
            last_price=price,
            atr=atr,
            highest_since_entry=price + spread,
        )
        action = evaluate(pos, c, cfg)
        if action.kind == "CLOSE":
            break
        new = apply(pos, action)
        assert new.sl >= pos.sl  # long: never loosened
        assert new.initial_sl == pos.initial_sl
        pos = new


def test_apply_ignores_a_modification_that_would_loosen_the_stop() -> None:
    from xau_edge.trading.position_manager import Action  # noqa: PLC0415

    pos = long_pos(sl=1998.0)
    assert apply(pos, Action("MODIFY_SL", "bad", new_sl=1990.0)).sl == 1998.0
    assert apply(pos, Action("CLOSE", "x")).sl == 1998.0


# -- governor ------------------------------------------------------------------------------


def check(
    g: TradeGovernor, now: datetime, equity: float = 100_000.0, risk: float = 0.25
) -> list[Refusal]:
    return g.check(now, "LONDON", risk, day_start_equity=100_000.0, equity=equity)


def test_an_empty_governor_allows_and_open_position_and_risk_limits_apply() -> None:
    g = TradeGovernor()
    assert check(g, T0) == []
    g.record_open("a", T0, "LONDON", 0.25)
    assert Refusal.RISK_LIMIT in check(g, T0 + timedelta(minutes=1))  # one position at a time
    g2 = TradeGovernor(GovernorConfig(max_open_positions=5, max_total_risk_pct=0.5))
    g2.record_open("a", T0, "LONDON", 0.3)
    assert Refusal.RISK_LIMIT in check(g2, T0 + timedelta(hours=2), risk=0.3)


def test_frequency_limits_per_hour_session_and_day() -> None:
    cfg = GovernorConfig(
        max_open_positions=9, max_total_risk_pct=9.0, max_trades_per_hour=2,
        max_trades_per_session=3, max_trades_per_day=4, cooldown_after_loss_minutes=0,
    )  # fmt: skip
    g = TradeGovernor(cfg)
    g.record_open("1", T0, "LONDON", 0.2)
    g.record_open("2", T0 + timedelta(minutes=10), "LONDON", 0.2)
    assert Refusal.DAILY_LIMIT in check(g, T0 + timedelta(minutes=20))  # 2 in the last hour
    assert check(g, T0 + timedelta(hours=2)) == []
    g.record_open("3", T0 + timedelta(hours=2), "LONDON", 0.2)
    assert Refusal.DAILY_LIMIT in check(g, T0 + timedelta(hours=4))  # 3 in the session
    g.record_open("4", T0 + timedelta(hours=5), "NEW_YORK", 0.2)
    assert Refusal.DAILY_LIMIT in g.check(
        T0 + timedelta(hours=8), "NEW_YORK", 0.2, day_start_equity=1e5, equity=1e5
    )  # 4 today
    next_day = T0 + timedelta(days=1, hours=1)
    assert g.check(next_day, "LONDON", 0.2, day_start_equity=1e5, equity=1e5) == []


def test_cooldown_after_a_loss_and_after_a_streak() -> None:
    g = TradeGovernor(
        GovernorConfig(max_open_positions=9, max_total_risk_pct=9.0, max_trades_per_hour=9)
    )
    g.record_open("1", T0, "LONDON", 0.2)
    g.record_close("1", T0 + timedelta(minutes=10), -50.0)
    assert Refusal.COOLDOWN in check(g, T0 + timedelta(minutes=20))
    assert Refusal.COOLDOWN not in check(g, T0 + timedelta(minutes=45))
    for i in (2, 3):
        g.record_open(str(i), T0 + timedelta(hours=i), "LONDON", 0.2)
        g.record_close(str(i), T0 + timedelta(hours=i, minutes=5), -40.0)
    assert g.loss_streak() == 3
    assert Refusal.COOLDOWN in check(g, T0 + timedelta(hours=3, minutes=200))  # long cooldown
    g.record_open("9", T0 + timedelta(hours=9), "LONDON", 0.2)
    g.record_close("9", T0 + timedelta(hours=9, minutes=5), 80.0)
    assert g.loss_streak() == 0


def test_the_daily_loss_guard_counts_floating_loss_and_has_a_flatten_floor() -> None:
    g = TradeGovernor(GovernorConfig(daily_loss_stop_pct=2.0, daily_loss_flatten_pct=3.5))
    assert check(g, T0, equity=99_000.0) == []  # -1 %
    assert Refusal.DAILY_LIMIT in check(g, T0, equity=97_900.0)  # -2.1 %
    assert not g.flatten_required(100_000.0, 97_900.0)
    assert g.flatten_required(100_000.0, 96_000.0)  # -4 %
    assert g.daily_loss_pct(100_000.0, 105_000.0) == 0.0
    assert g.daily_loss_pct(0.0, 5.0) == 0.0


# -- arming --------------------------------------------------------------------------------


def make_settings(**over: object) -> Settings:
    return Settings(_env_file=None, **over)  # type: ignore[arg-type]


def test_the_default_is_disarmed_and_dry_run_never_arms(tmp_path: Path) -> None:
    now = T0
    assert effective_state(make_settings(), None, now) is ArmState.DISARMED
    assert effective_state(make_settings(enable_demo_trading=True), None, now) is ArmState.DRY_RUN


def test_demo_armed_needs_the_settings_and_an_unexpired_marker(tmp_path: Path) -> None:
    armed = make_settings(
        enable_demo_trading=True,
        demo_dry_run=False,
        demo_allowed_accounts="123",
        demo_magic=777,
        demo_initial_capital=100_000.0,
    )
    path = tmp_path / "armed.json"
    assert effective_state(armed, None, T0) is ArmState.DRY_RUN
    marker = write_marker(path, "operator", T0, hours=2)
    assert effective_state(armed, marker, T0 + timedelta(hours=1)) is ArmState.DEMO_ARMED
    assert effective_state(armed, marker, T0 + timedelta(hours=3)) is ArmState.DRY_RUN  # expired
    assert effective_state(armed, marker, T0 - timedelta(minutes=1)) is ArmState.DRY_RUN
    assert effective_state(make_settings(), marker, T0 + timedelta(hours=1)) is ArmState.DISARMED
    clear_marker(path)
    assert read_marker(path) is None


def test_a_broken_or_forged_marker_never_arms(tmp_path: Path) -> None:
    path = tmp_path / "armed.json"
    path.write_text("{not json", encoding="utf-8")
    assert read_marker(path) is None
    path.write_text(
        '{"armed_at": "2026-03-03T10:00:00", "armed_until": "2026-03-03T11:00:00",'
        ' "operator": "x"}',
        encoding="utf-8",
    )
    assert read_marker(path) is None  # naive time stamps are refused
    path.write_text(
        '{"armed_at": "2026-03-03T10:00:00+00:00", "armed_until": "2026-03-03T09:00:00+00:00",'
        ' "operator": "x"}',
        encoding="utf-8",
    )
    assert read_marker(path) is None  # ends before it starts
    with pytest.raises(ValueError, match="arming window"):
        write_marker(path, "x", T0, hours=48)
    with pytest.raises(ValueError, match="arming window"):
        write_marker(path, "x", T0, hours=0)
