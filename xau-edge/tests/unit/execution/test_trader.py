"""Paper trader: signal -> risk -> safety -> paper broker; WAIT never trades."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tests.unit.signals.test_decision import _inputs
from xau_edge.backtest.costs import CostModel
from xau_edge.execution.paper import MarketBar, PaperExecutionBroker
from xau_edge.execution.safety import ExecutionSafety, assert_live_trading_disabled
from xau_edge.execution.trader import PaperTrader
from xau_edge.risk.engine import RiskEngine, RiskLimits
from xau_edge.risk.prop_rules import load_prop_profile
from xau_edge.signals.decision import decide
from xau_edge.signals.schema import Direction, EvidenceStatus, Signal

PROP = load_prop_profile(Path(__file__).parents[3] / "configs" / "prop" / "ftmo_2step.yaml")
T = datetime(2026, 3, 4, 14, 0, tzinfo=UTC)  # same as the signal fixtures
COSTS = CostModel(slippage_points=3.0, swap_long_points=0.0, swap_short_points=0.0)


def _trader(safety: ExecutionSafety | None = None, journal: Path | None = None) -> PaperTrader:
    broker = PaperExecutionBroker(100_000.0, costs=COSTS, journal_path=journal)
    broker.set_quote(T, bid=2000.0, spread_points=30.0)
    risk = RiskEngine(RiskLimits(), PROP)
    return PaperTrader(broker, risk, safety or ExecutionSafety())


def _buy(**over: object) -> Signal:
    s = decide(_inputs(**over))
    assert s.direction is Direction.BUY
    return s


def test_wait_signals_never_reach_the_broker() -> None:
    trader = _trader()
    wait = decide(_inputs(evidence_status=EvidenceStatus.NONE))
    out = trader.on_signal(wait, T, spread_points=30.0)
    assert not out.accepted
    assert "NO_VALIDATED_EDGE" in out.reasons
    assert trader.broker.get_positions() == []


def test_a_valid_buy_becomes_a_sized_paper_position_with_the_signals_own_levels() -> None:
    trader = _trader()
    signal = _buy()
    out = trader.on_signal(signal, T, spread_points=30.0)
    assert out.accepted
    pos = trader.broker.get_positions()[0]
    assert pos.signal_hash == signal.inputs_hash
    assert pos.stop_loss == signal.stop_loss
    assert pos.take_profit == signal.take_profit_1
    # 0.5% of 100,000 = 500 over a 7.5 stop x 100 oz -> 0.66 lots
    assert out.lots == pytest.approx(0.66)
    assert pos.lots == pytest.approx(0.66)
    assert pos.max_hold_until == T + timedelta(minutes=15 * 20)


def test_the_same_signal_cannot_be_traded_twice() -> None:
    trader = _trader()
    signal = _buy()
    assert trader.on_signal(signal, T, spread_points=30.0).accepted
    again = trader.on_signal(signal, T, spread_points=30.0)
    assert not again.accepted
    assert again.reasons == ("DUPLICATE_SIGNAL",)


def test_an_expired_signal_is_refused() -> None:
    trader = _trader()
    signal = _buy()
    late = T + timedelta(hours=2)
    out = trader.on_signal(signal, late, spread_points=30.0)
    assert out.reasons == ("SIGNAL_EXPIRED",)


def test_the_risk_engine_can_still_refuse_a_valid_signal() -> None:
    trader = _trader()
    out = trader.on_signal(_buy(), T, spread_points=500.0)
    assert not out.accepted
    assert "SPREAD" in out.reasons


def test_safety_limits_refuse_oversized_orders_and_too_many_orders() -> None:
    small = _trader(ExecutionSafety(max_lots=0.1))
    out = small.on_signal(_buy(), T, spread_points=30.0)
    assert "LOTS_ABOVE_MAXIMUM" in out.reasons

    one_a_day = _trader(ExecutionSafety(max_orders_per_day=1))
    first = one_a_day.on_signal(_buy(), T, spread_points=30.0)
    assert first.accepted
    # close it so the risk engine allows another, then a different signal on the same day
    one_a_day.broker.close_position(first.position_id or "", "manual")
    second = one_a_day.on_signal(_buy(price=2001.0), T, spread_points=30.0)
    assert "ORDER_COUNT_EXCEEDED" in second.reasons


def test_symbol_account_and_environment_must_be_confirmed() -> None:
    for safety, reason in (
        (ExecutionSafety(allowed_symbols=("EURUSD",)), "SYMBOL_NOT_WHITELISTED"),
        (ExecutionSafety(account="live-123"), "ACCOUNT_NOT_WHITELISTED"),
        (ExecutionSafety(environment="live"), "ENVIRONMENT_NOT_CONFIRMED"),
    ):
        out = _trader(safety).on_signal(_buy(), T, spread_points=30.0)
        assert reason in out.reasons


def test_dry_run_validates_everything_but_places_nothing() -> None:
    trader = _trader(ExecutionSafety(dry_run=True))
    out = trader.on_signal(_buy(), T, spread_points=30.0)
    assert out.accepted
    assert out.dry_run
    assert out.position_id is None
    assert trader.broker.get_positions() == []


def test_a_tripped_kill_switch_blocks_orders() -> None:
    trader = _trader()
    trader.risk.kill_switch.trip("test")
    out = trader.on_signal(_buy(), T, spread_points=30.0)
    assert not out.accepted
    assert "KILL_SWITCH" in out.reasons


def test_closed_trades_update_the_consecutive_loss_counter_and_block_after_three() -> None:
    trader = _trader()
    now = T
    for i in range(3):
        sig = _buy(price=2000.0 + i, timestamp=now)
        assert trader.on_signal(sig, now, spread_points=30.0).accepted
        # price collapses through the stop on the next bar: a loss
        now += timedelta(minutes=15)
        closed = trader.on_bar(
            MarketBar(now, open=1990.0, high=1990.5, low=1980.0, close=1985.0, spread_points=30.0)
        )
        assert closed
        assert closed[0].net_pnl < 0
        trader.broker.set_quote(now, bid=2000.0 + i + 1, spread_points=30.0)
    fourth = trader.on_signal(_buy(price=2010.0, timestamp=now), now, spread_points=30.0)
    assert not fourth.accepted
    assert "CONSECUTIVE_LOSSES" in fourth.reasons or "DAILY_RISK_BUDGET" in fourth.reasons


def test_live_trading_flag_cannot_be_on() -> None:
    assert_live_trading_disabled()  # default settings: fine


def test_the_execution_package_never_imports_a_broker_api() -> None:
    root = Path(__file__).parents[3] / "src" / "xau_edge" / "execution"
    text = " ".join(p.read_text(encoding="utf-8") for p in root.glob("*.py"))
    for forbidden in ("MetaTrader5", "order_send", "order_check", "positions_close"):
        assert forbidden not in text.replace("MetaTrader5 is", "")
