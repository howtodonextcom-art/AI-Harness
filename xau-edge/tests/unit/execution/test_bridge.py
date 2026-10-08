"""Signal bridge: every dangerous case is refused, and only an accepted signal changes state."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from tests.unit.execution.test_trader import _trader
from tests.unit.signals.test_decision import _inputs
from xau_edge.execution.bridge import BridgeResult, SignalBridge
from xau_edge.execution.safety import ExecutionSafety
from xau_edge.execution.state import ExecutionState, PersistentKillSwitch
from xau_edge.risk.engine import AccountState, RiskEngine, RiskLimits
from xau_edge.risk.prop_rules import load_prop_profile
from xau_edge.signals.decision import decide
from xau_edge.signals.schema import Direction, EvidenceStatus, Signal

PROP = load_prop_profile(Path(__file__).parents[3] / "configs" / "prop" / "ftmo_2step.yaml")
T = datetime(2026, 3, 4, 14, 0, tzinfo=UTC)


def _account(**over: Any) -> AccountState:
    base: dict[str, Any] = {
        "timestamp": T,
        "initial_capital": 100_000.0,
        "balance": 100_000.0,
        "equity": 100_000.0,
        "day_start_balance": 100_000.0,
        "highest_eod_balance": 100_000.0,
        "open_positions": 0,
        "open_lots": 0.0,
        "risk_taken_today": 0.0,
        "consecutive_losses": 0,
    }
    base.update(over)
    return AccountState(**base)


def _bridge(
    folder: Path,
    *,
    safety: ExecutionSafety | None = None,
    magic: int | None = 7,
    dry_run: bool = True,
) -> SignalBridge:
    state = ExecutionState(folder / "s.sqlite")
    risk = RiskEngine(RiskLimits(), PROP, kill_switch=PersistentKillSwitch(state))
    return SignalBridge(state, risk, safety or ExecutionSafety(), magic=magic, dry_run=dry_run)


def _buy(**over: Any) -> Signal:
    s = decide(_inputs(**over))
    assert s.direction is Direction.BUY
    return s


def _offer(
    bridge: SignalBridge,
    signal: Signal,
    now: datetime = T,
    account: AccountState | None = None,
) -> BridgeResult:
    return bridge.process(signal, now, account=account or _account(), spread_points=30.0)


def _untouched(bridge: SignalBridge, signal: Signal) -> None:
    assert not bridge.state.is_seen(signal.inputs_hash)
    assert bridge.state.last_decision_bar() is None


def test_a_valid_buy_becomes_a_deterministic_intent_and_is_marked_as_seen(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)
    signal = _buy()
    result = _offer(bridge, signal)
    assert result.accepted
    assert result.reasons == ()
    intent = result.intent
    assert intent is not None
    assert intent.signal_hash == signal.inputs_hash
    assert intent.dry_run is True
    assert intent.magic == 7
    assert intent.lots == pytest.approx(0.66)  # sized by the risk engine, not the bridge
    assert bridge.state.is_seen(signal.inputs_hash)
    assert bridge.state.last_decision_bar() == signal.timestamp
    other = tmp_path / "other"
    other.mkdir()
    assert _offer(_bridge(other), _buy()).intent == intent  # same inputs, same intent


def test_wait_is_rejected_and_nothing_is_recorded(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)
    wait = decide(_inputs(evidence_status=EvidenceStatus.NONE))
    result = _offer(bridge, wait)
    assert not result.accepted
    assert result.intent is None
    assert "NO_VALIDATED_EDGE" in result.reasons
    _untouched(bridge, wait)


def test_news_unknown_is_rejected(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)
    wait = decide(_inputs(news_blocked=None))
    result = _offer(bridge, wait)
    assert not result.accepted
    assert "NEWS_UNKNOWN" in result.reasons
    _untouched(bridge, wait)


def test_news_risk_is_rejected(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)
    wait = decide(_inputs(news_blocked=True))
    assert "NEWS_RISK" in _offer(bridge, wait).reasons


def test_an_open_evidence_gate_is_re_checked_even_on_a_tampered_signal(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)
    signal = _buy()
    object.__setattr__(signal, "evidence_status", EvidenceStatus.NONE)
    assert _offer(bridge, signal).reasons == ("NO_VALIDATED_EDGE",)
    signal = _buy()
    object.__setattr__(signal, "inputs_hash", "")
    assert _offer(bridge, signal).reasons == ("SIGNAL_NO_HASH",)
    _untouched(bridge, signal)


@pytest.mark.parametrize("field", ["stop_loss", "take_profit_1", "entry_zone"])
def test_missing_levels_are_rejected(tmp_path: Path, field: str) -> None:
    bridge = _bridge(tmp_path)
    signal = _buy()
    object.__setattr__(signal, field, None)
    assert _offer(bridge, signal).reasons == ("SIGNAL_INCOMPLETE",)
    _untouched(bridge, signal)


def test_inconsistent_or_non_finite_levels_are_rejected(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)
    signal = _buy()
    object.__setattr__(signal, "stop_loss", 2010.0)
    assert _offer(bridge, signal).reasons == ("SIGNAL_LEVELS_INVALID",)
    signal = _buy()
    object.__setattr__(signal, "stop_loss", float("nan"))
    assert _offer(bridge, signal).reasons == ("SIGNAL_LEVELS_INVALID",)
    _untouched(bridge, signal)


def test_expired_and_stale_and_future_decisions_are_rejected(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)
    signal = _buy()
    assert _offer(bridge, signal, T + timedelta(hours=2)).reasons == ("SIGNAL_EXPIRED",)
    assert _offer(bridge, signal, T + timedelta(minutes=45)).reasons == ("DECISION_STALE",)
    assert _offer(bridge, signal, T - timedelta(minutes=1)).reasons == ("DECISION_STALE",)
    no_expiry = _buy()
    object.__setattr__(no_expiry, "signal_expiry", None)
    assert _offer(bridge, no_expiry).reasons == ("SIGNAL_NO_EXPIRY",)
    _untouched(bridge, signal)


def test_a_duplicate_signal_is_rejected_after_the_first_even_after_restart(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)
    assert _offer(bridge, _buy()).accepted
    assert _offer(bridge, _buy()).reasons == ("DUPLICATE_SIGNAL",)
    restarted = _bridge(tmp_path)  # same state file
    assert _offer(restarted, _buy()).reasons == ("DUPLICATE_SIGNAL",)


def test_a_second_different_signal_on_the_same_decision_bar_is_rejected(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)
    assert _offer(bridge, _buy()).accepted
    other = _buy(price=2000.4)
    assert other.inputs_hash != _buy().inputs_hash
    assert _offer(bridge, other).reasons == ("DUPLICATE_DECISION_BAR",)
    assert not bridge.state.is_seen(other.inputs_hash)


def test_the_persistent_kill_switch_blocks_and_survives_restart(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)
    bridge.state.trip_kill_switch("breach")
    signal = _buy()
    assert _offer(bridge, signal).reasons == ("KILL_SWITCH",)
    _untouched(bridge, signal)
    restarted = _bridge(tmp_path)
    assert _offer(restarted, signal).reasons == ("KILL_SWITCH",)  # nothing reset it
    assert restarted.state.kill_switch_state()[0] is True


def test_a_risk_denial_is_rejected_and_not_recorded(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)
    signal = _buy()
    result = _offer(bridge, signal, account=_account(open_positions=1))
    assert "MAX_CONCURRENT" in result.reasons
    assert not result.accepted
    _untouched(bridge, signal)
    streak = _offer(bridge, signal, account=_account(consecutive_losses=3))
    assert "CONSECUTIVE_LOSSES" in streak.reasons


def test_an_invalid_account_is_rejected(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)
    result = _offer(bridge, _buy(), account=_account(equity=float("nan")))
    assert "ACCOUNT_STATE_INVALID" in result.reasons


def test_a_safety_violation_is_rejected_and_not_recorded(tmp_path: Path) -> None:
    signal = _buy()
    tight = _bridge(tmp_path, safety=ExecutionSafety(max_lots=0.1))
    assert _offer(tight, signal).reasons == ("LOTS_ABOVE_MAXIMUM",)
    _untouched(tight, signal)
    wrong_env = _bridge(tmp_path, safety=ExecutionSafety(environment="live"))
    assert "ENVIRONMENT_NOT_CONFIRMED" in _offer(wrong_env, signal).reasons
    wrong_symbol = _bridge(tmp_path, safety=ExecutionSafety(allowed_symbols=("EURUSD",)))
    assert "SYMBOL_NOT_WHITELISTED" in _offer(wrong_symbol, signal).reasons


def test_the_daily_order_limit_applies_only_to_real_demo_intents(tmp_path: Path) -> None:
    safety = ExecutionSafety(max_orders_per_day=1)
    t2 = T + timedelta(minutes=15)
    dry = _bridge(tmp_path, safety=safety)
    assert _offer(dry, _buy(), T).accepted
    assert _offer(dry, _buy(timestamp=t2), t2).accepted  # dry-run does not use the budget
    folder = tmp_path / "demo"
    folder.mkdir()
    demo = _bridge(folder, safety=safety, dry_run=False)
    assert _offer(demo, _buy(), T).accepted
    assert _offer(demo, _buy(timestamp=t2), t2).reasons == ("ORDER_COUNT_EXCEEDED",)


def test_a_missing_magic_number_is_rejected(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path, magic=None)
    assert _offer(bridge, _buy()).reasons == ("MAGIC_NOT_CONFIGURED",)


def test_safety_dry_run_forces_dry_run(tmp_path: Path) -> None:
    forced = _bridge(tmp_path, safety=ExecutionSafety(dry_run=True), dry_run=False)
    result = _offer(forced, _buy())
    assert result.intent is not None
    assert result.intent.dry_run is True


def test_an_unreadable_state_fails_closed(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)
    conn = sqlite3.connect(bridge.state.path)
    conn.execute("DROP TABLE seen_signals")
    conn.commit()
    conn.close()
    result = _offer(bridge, _buy())
    assert result.accepted is False
    assert result.reasons == ("STATE_UNAVAILABLE",)


def test_the_bridge_sizes_exactly_like_the_paper_trader(tmp_path: Path) -> None:
    signal = _buy()
    paper = _trader().on_signal(signal, T, spread_points=30.0)
    bridged = _offer(_bridge(tmp_path), signal)
    assert paper.accepted
    assert bridged.accepted
    assert bridged.intent is not None
    assert bridged.intent.lots == pytest.approx(paper.lots)  # one sizing logic for both paths


def test_the_state_kill_switch_blocks_even_if_the_risk_engine_uses_an_in_memory_switch(
    tmp_path: Path,
) -> None:
    state = ExecutionState(tmp_path / "s.sqlite")
    bridge = SignalBridge(state, RiskEngine(RiskLimits(), PROP), ExecutionSafety(), magic=7)
    state.trip_kill_switch("breach")
    result = _offer(bridge, _buy())
    assert result.reasons == ("KILL_SWITCH",)
    assert not state.is_seen(_buy().inputs_hash)
