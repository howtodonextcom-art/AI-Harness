"""The trader-facing truth computed on the server: hero, conditions, plan, funnel, evidence."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from tests.unit.market_data.test_collector_ledger import FakeClient, make_collector
from tests.unit.trading.helpers import SPEC, aligned_state
from xau_edge.api.trade import build_trade_engine
from xau_edge.domain.market import MarketStatus
from xau_edge.market_data.calendars import ftmo_calendar
from xau_edge.market_data.session import market_status
from xau_edge.trading.baseline import BaselineConfig, DecisionContext, decide
from xau_edge.trading.cockpit import (
    F4_MIN_TRADES,
    action_for,
    condition,
    forward_acceptance,
    funnel,
    hero_state,
    setup_history,
    strategy_info,
    trade_plan,
)
from xau_edge.trading.namespace import NamespaceError, claim_root
from xau_edge.trading.paper_desk import DeskRefusal
from xau_edge.trading.schema import TradeDecision, TradingSignal
from xau_edge.trading.setup_machine import SetupLifecycle, SetupPhase

NOW = datetime(2026, 3, 2, 10, 5, tzinfo=UTC)


def lifecycle(phase: SetupPhase, fires: bool = False) -> SetupLifecycle:
    return SetupLifecycle(phase, 1, NOW, NOW, 1, fires, "t")


def signal(*, wait: bool = False, phase: SetupPhase = SetupPhase.TRIGGERED) -> TradingSignal:
    cfg = BaselineConfig(version="1.2.1")
    state = aligned_state(h1_trend="NEUTRAL") if wait else aligned_state()
    ctx = DecisionContext(spec=SPEC, equity=100_000.0, lifecycle=lifecycle(phase, fires=not wait))
    return decide(state, ctx, cfg)


def plans(ok: bool = True) -> list[dict[str, Any]]:
    return [
        {"risk_pct": r, "ok": ok, "lots": 0.5, "risk_amount": 25.0, "gain_at_tp": 50.0}
        for r in (0.1, 0.25, 0.5)
    ]


def plan_of(sig: TradingSignal, ok: bool = True, expired: bool = False) -> dict[str, Any] | None:
    return trade_plan(
        sig, plans=plans(ok), default_risk_pct=0.25, expired=expired, seconds_to_expiry=120.0
    )


def hero(sig: TradingSignal | None, **over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "signal": sig, "conditions": [], "expired": False,
        "plan": None if sig is None else plan_of(sig), "position": None, "last_exit": None,
        "market_open": True, "now": NOW,
    }  # fmt: skip
    base.update(over)
    return hero_state(**base)


# -- strategy visibility -----------------------------------------------------------------------


def test_only_the_active_version_is_marked_active() -> None:
    info = strategy_info("1.1.0")
    status = {v["version"]: v["status"] for v in info["installed"]}
    assert status == {
        "1.1.0": "ACTIVE",
        "1.2.0": "AVAILABLE_INACTIVE",
        "1.2.1": "AVAILABLE_INACTIVE",
    }
    assert info["label"] == "xau_mtf_baseline v1.1.0" and "UNVALIDATED" in info["evidence"]
    assert strategy_info("1.2.1")["installed"][2]["status"] == "ACTIVE"


# -- hero: WAIT is not UNAVAILABLE -------------------------------------------------------------


def test_a_plain_wait_is_wait_and_an_infrastructure_failure_is_never_wait() -> None:
    assert hero(signal(wait=True))["state"] == "WAIT"
    assert hero(None)["state"] == "UNAVAILABLE"
    err = [condition("SPEC_MISSING", "ERROR", "no spec")]
    assert hero(signal(wait=True), conditions=err)["state"] == "UNAVAILABLE"
    for code in ("ENGINE_ERROR", "WRITER_LOCK", "MT5_DISCONNECTED", "NO_DECISION"):
        assert (
            hero(signal(wait=True), conditions=[condition(code, "ERROR", "x")])["state"]
            == "UNAVAILABLE"
        )


def test_stale_data_hides_a_buy_behind_stale_not_actionable() -> None:
    for code in ("DATA_STALE", "QUOTE_STALE", "COLLECTOR_STALE"):
        h = hero(signal(), conditions=[condition(code, "ERROR", "x")])
        assert h["state"] == "STALE" and "NOT ACTIONABLE" in h["label"]


def test_closed_market_is_its_own_state_not_wait() -> None:
    assert hero(signal(wait=True), market_open=False)["state"] == "MARKET_CLOSED"


def test_buy_ready_sell_ready_not_actionable_expired_and_position_open() -> None:
    buy = signal()
    assert buy.decision is TradeDecision.BUY
    ready = hero(buy)
    assert ready["state"] == "BUY_READY" and ready["tone"] == "buy" and ready["side"] == "BUY"
    assert hero(buy, plan=plan_of(buy, ok=False))["state"] == "NOT_ACTIONABLE"  # no valid lot
    assert "SETUP DETECTED" in hero(buy, plan=plan_of(buy, ok=False))["label"]
    assert hero(buy, expired=True)["state"] == "EXPIRED_SETUP"
    position = {"status": "OPEN", "side": "BUY"}
    assert (
        hero(buy, position=position)["state"] == "POSITION_OPEN"
    )  # a position outranks a new setup


def test_a_setup_that_lacks_a_plan_field_is_not_actionable() -> None:
    buy = signal().model_copy(update={"take_profit": None})
    plan = plan_of(buy)
    assert plan is not None and not plan["complete"] and "take_profit" in plan["missing"]
    assert hero(buy, plan=plan)["state"] == "NOT_ACTIONABLE"


def test_armed_exited_and_old_exit_states() -> None:
    armed = signal(wait=True, phase=SetupPhase.ARMED).model_copy(
        update={"metadata": {"setup_phase": "ARMED"}}
    )
    assert hero(armed)["state"] == "SETUP_ARMED"
    recent = {
        "trade_id": "T1",
        "closed_at": (NOW - timedelta(minutes=5)).isoformat(),
        "exit_reason": "TAKE_PROFIT",
    }
    old = {**recent, "closed_at": (NOW - timedelta(hours=3)).isoformat()}
    assert hero(signal(wait=True), last_exit=recent)["state"] == "EXITED"
    assert hero(signal(wait=True), last_exit=old)["state"] == "WAIT"


# -- plan card ---------------------------------------------------------------------------------


def test_the_plan_card_carries_every_field_the_trader_needs() -> None:
    plan = plan_of(signal())
    assert plan is not None and plan["complete"] and plan["missing"] == []
    for key in (
        "planned_entry",
        "sl",
        "tp1",
        "rr_net",
        "lots",
        "risk_amount",
        "potential_tp_value",
        "expires_at",
        "invalidation",
        "strategy_version",
        "entry_basis",
        "setup_id",
    ):
        assert plan[key] is not None, key
    assert (plan["entry_basis"] == "ask" and plan["tp2"] is not None) or plan["tp2"] is None
    assert plan_of(signal(wait=True)) is None


# -- forward acceptance ------------------------------------------------------------------------


def trade(tid: str, status: str, **over: Any) -> dict[str, Any]:
    done = {
        "exit_reason": "TAKE_PROFIT",
        "exit_price": 1.0,
        "net_pnl": 1.0,
        "r_multiple": 1.0,
        "mfe_r": 1.0,
        "mae_r": 0.1,
    }
    base = {
        "trade_id": tid,
        "status": status,
        "source_mode": "LIVE",
        **(done if status == "CLOSED" else {}),
    }
    return {**base, **over}


def test_forward_levels_rise_only_with_live_evidence() -> None:
    sig = [{"setup_id": "s1", "source_mode": "LIVE"}]
    assert forward_acceptance([], [], source_mode="LIVE")["level"] == "F0"
    assert forward_acceptance(sig, [], source_mode="LIVE")["level"] == "F1"
    assert forward_acceptance(sig, [trade("T1", "OPEN")], source_mode="LIVE")["level"] == "F2"
    assert forward_acceptance(sig, [trade("T1", "CLOSED")], source_mode="LIVE")["level"] == "F3"
    many = [trade(f"T{i}", "CLOSED") for i in range(F4_MIN_TRADES)]
    assert forward_acceptance(sig, many, source_mode="LIVE")["level"] == "F4"


def test_a_correctness_failure_keeps_f4_out_of_reach() -> None:
    many = [trade(f"T{i}", "CLOSED") for i in range(F4_MIN_TRADES)]
    many[0]["mae_r"] = None  # a closed trade with a missing field
    result = forward_acceptance([{"setup_id": "s"}], many, source_mode="LIVE")
    assert result["level"] == "F3" and result["counts"]["correctness_failures"] == 1


def test_replay_and_fixture_evidence_can_never_raise_the_live_level() -> None:
    replay_trades = [trade(f"T{i}", "CLOSED", source_mode="ACCEPTANCE_REPLAY") for i in range(5)]
    replay_signals = [{"setup_id": "s", "source_mode": "ACCEPTANCE_REPLAY"}]
    assert forward_acceptance(replay_signals, replay_trades, source_mode="LIVE")["level"] == "F0"
    assert (
        forward_acceptance(replay_signals, replay_trades, source_mode="ACCEPTANCE_REPLAY")["live"]
        is False
    )


# -- funnel ------------------------------------------------------------------------------------


def test_the_funnel_counts_setups_signals_trades_and_refusal_groups() -> None:
    rows: list[dict[str, Any]] = [
        {"decision": "WAIT", "refusals": ["NO_SETUP"], "setup_phase": "NONE", "armed_at": None},
        {"decision": "WAIT", "refusals": ["NO_TRIGGER"], "setup_phase": "ARMED", "armed_at": "a1"},
        {"decision": "WAIT", "refusals": ["NO_TRIGGER"], "setup_phase": "ARMED", "armed_at": "a1"},
        {"decision": "BUY", "refusals": [], "setup_phase": "TRIGGERED", "armed_at": "a1"},
        {
            "decision": "WAIT",
            "refusals": ["VOLATILITY_TOO_HIGH"],
            "setup_phase": "EXPIRED",
            "armed_at": "a2",
        },
        {
            "decision": "WAIT",
            "refusals": ["SPREAD_TOO_WIDE"],
            "setup_phase": "NONE",
            "armed_at": None,
        },
        {"decision": "WAIT", "refusals": ["RR_TOO_LOW"], "setup_phase": "NONE", "armed_at": None},
    ]
    trades = [
        {"status": "CLOSED", "created_at": "2026-03-02T10:00:00+00:00", "exit_reason": "STOP_LOSS"},
        {"status": "CANCELLED", "created_at": "2026-03-02T10:00:00+00:00"},
    ]
    out = funnel(rows, [{"side": "BUY"}, {"side": "SELL"}], trades, NOW)
    assert out["decisions"] == 7 and out["armed_setups"] == 2
    assert (
        out["triggered_setups"] == 1
        and out["expired_setups"] == 1
        and out["invalidated_setups"] == 0
    )
    assert (out["actionable_buy"], out["actionable_sell"]) == (1, 1)
    assert (out["paper_opens"], out["paper_exits"], out["exit_reasons"]) == (1, 1, {"STOP_LOSS": 1})
    assert out["refusals"]["NO_TRIGGER"] == 2 and out["refusals"]["VOLATILITY"] == 1
    assert out["refusals"]["SPREAD"] == 1 and out["refusals"]["RR"] == 1
    assert set(out["refusals"]) >= {"NO_DIRECTION", "TIMEFRAME_CONFLICT", "RISK", "STALE"}


# -- namespaces --------------------------------------------------------------------------------


def test_a_trade_root_belongs_to_one_source_mode(tmp_path: Path) -> None:
    claim_root(tmp_path / "live", "LIVE")
    claim_root(tmp_path / "live", "LIVE")  # idempotent
    with pytest.raises(NamespaceError):
        claim_root(tmp_path / "live", "ACCEPTANCE_REPLAY")
    with pytest.raises(NamespaceError):
        claim_root(tmp_path / "x", "NOT_A_MODE")


# -- engine integration ------------------------------------------------------------------------


@pytest.fixture
def live_world(tmp_path: Path) -> tuple[Path, Path, FakeClient]:
    client = FakeClient()
    market = tmp_path / "market"
    make_collector(market, client).run_once()
    live = json.loads((market / "live.json").read_text(encoding="utf-8"))
    live["symbol_spec"] = {
        "point": 0.01, "trade_tick_size": 0.01, "trade_tick_value": 1.0,
        "trade_contract_size": 100.0,
        "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01, "trade_stops_level": 0,
        "trade_freeze_level": 0, "digits": 2,
    }  # fmt: skip
    (market / "live.json").write_text(json.dumps(live), encoding="utf-8")
    return market, tmp_path / "trade", client


def test_a_second_process_on_the_same_desk_is_read_only_and_says_so(
    live_world: tuple[Path, Path, FakeClient],
) -> None:
    market, trade, _ = live_world
    owner = build_trade_engine(market, trade, code_version="t")
    assert owner.writer_error is None and owner.desk.writable
    second = build_trade_engine(market, trade, code_version="t")
    assert second.writer_error is not None and "SINGLE WRITER CONFLICT" in second.writer_error
    assert not second.desk.writable and second.alerts is None
    view = second.view()
    assert view["hero"]["state"] == "UNAVAILABLE" and "WRITER_LOCK" in view["hero"]["detail"]
    assert view["status_strip"]["paper_desk"]["state"] == "READ_ONLY"
    with pytest.raises(DeskRefusal) as info:
        second.paper_open(setup_id="abcdef0123", risk_pct=0.25)
    assert info.value.code in ("WRITER_LOCK", "NO_DECISION", "DECISION_CHANGED")
    assert not list(trade.glob("decisions-*.jsonl")) or owner.writer_error is None


def test_a_corrupt_paper_state_blocks_entries_and_the_server_says_so(
    live_world: tuple[Path, Path, FakeClient],
) -> None:
    market, trade, _ = live_world
    engine = build_trade_engine(market, trade, code_version="t")
    engine.writer_lock.release()  # let a new engine in the same process own it
    (trade / "paper_desk.json").parent.mkdir(parents=True, exist_ok=True)
    (trade / "paper_desk.json").write_text("{broken", encoding="utf-8")
    broken = build_trade_engine(market, trade, code_version="t")
    assert broken.desk.fault is not None and broken.desk.fault[0] == "PAPER_STATE_ERROR"
    view = broken.view()
    assert view["status_strip"]["paper_desk"]["state"] == "ERROR"
    assert any(c["code"] == "PAPER_STATE_ERROR" for c in view["conditions"])
    broken.step()
    view = broken.view()
    buy = broken.desk  # noqa: F841 - the desk is the gate, not the decision
    assert broken.desk.can_open(NOW, "LONDON", 0.25, None)[0] == "PAPER_STATE_ERROR"
    assert view["status_strip"]["paper_desk"]["detail"].startswith(
        "paper desk state was unreadable"
    )


def test_the_closure_probe_sees_the_weekly_close_inside_the_maximum_hold(
    live_world: tuple[Path, Path, FakeClient],
) -> None:
    market, trade, _ = live_world
    engine = build_trade_engine(market, trade, code_version="t")
    engine.source.calendar = ftmo_calendar()
    at = datetime(2026, 3, 6, 15, 0, tzinfo=UTC)  # a Friday afternoon
    while market_status(at, engine.source.calendar) is MarketStatus.OPEN:
        at += timedelta(minutes=1)
    assert market_status(at, engine.source.calendar) is not MarketStatus.OPEN
    near = engine.closure_probe(at - timedelta(minutes=60), 120)
    assert near is not None and near[1] in ("WEEKEND_OR_HOLIDAY", "DAILY_BREAK")
    assert engine.closure_probe(at - timedelta(hours=6), 120) is None
    assert (
        engine.desk.can_open(at - timedelta(minutes=60), "NEW_YORK", 0.25, None).count(
            "CLOSURE_NEAR"
        )
        == 1
    )
    assert "CLOSURE_NEAR" not in engine.desk.can_open(
        at - timedelta(hours=6), "NEW_YORK", 0.25, None
    )


# -- setup history ------------------------------------------------------------------------------


def _rec(
    at: str, armed: str | None, phase: str | None, decision: str = "WAIT", h1: str = "BULLISH"
) -> dict[str, Any]:
    return {
        "at": at,
        "armed_at": armed,
        "setup_phase": phase,
        "decision": decision,
        "h1": h1,
        "strategy_version": "1.2.1",
    }


def test_setup_history_says_how_each_armed_setup_ended() -> None:

    rows = [
        _rec("2026-03-02T10:00:00+00:00", "2026-03-02T09:55:00+00:00", "ARMED"),
        _rec("2026-03-02T10:05:00+00:00", "2026-03-02T09:55:00+00:00", "TRIGGERED", "BUY"),
        _rec("2026-03-02T11:00:00+00:00", "2026-03-02T10:50:00+00:00", "ARMED", h1="BEARISH"),
        _rec("2026-03-02T11:30:00+00:00", "2026-03-02T10:50:00+00:00", "EXPIRED", h1="BEARISH"),
        _rec("2026-03-02T12:00:00+00:00", "2026-03-02T11:55:00+00:00", "ARMED"),
        _rec("2026-03-02T12:05:00+00:00", "2026-03-02T11:55:00+00:00", "INVALIDATED"),
        _rec("2026-03-02T12:10:00+00:00", None, "NONE"),
        _rec("2026-03-02T13:00:00+00:00", "2026-03-02T12:55:00+00:00", "ARMED"),
    ]
    history = setup_history(rows)
    by_armed = {h["armed_at"][11:16]: h for h in history}
    assert [h["outcome"] for h in history] == [
        "ARMED",
        "INVALIDATED",
        "EXPIRED",
        "TRIGGERED",
    ]  # newest first
    assert by_armed["09:55"]["actionable"] is True
    assert by_armed["09:55"]["side"] == "BUY"
    assert by_armed["10:50"]["side"] == "SELL"
    assert by_armed["10:50"]["actionable"] is False  # expired unseen: it never offered a trade
    assert len(history) == 4  # the phase-less record is not a setup


def test_a_version_without_a_lifecycle_lists_no_armed_setups() -> None:

    assert setup_history([_rec("2026-03-02T10:00:00+00:00", None, "SAME_BAR", "BUY")]) == []


# -- action: the one thing to do now --------------------------------------------------------------


def _hero(state: str, side: str | None = None) -> dict[str, Any]:
    return {"state": state, "side": side, "label": state, "tone": "x", "detail": ""}


def test_every_hero_state_maps_to_one_action() -> None:
    buy = signal()
    wait = signal(wait=True)
    assert action_for(_hero("BUY_READY", "BUY"), buy, None)["code"] == "BUY"
    assert action_for(_hero("SELL_READY", "SELL"), buy, None)["code"] == "SELL"
    assert action_for(_hero("UNAVAILABLE"), None, None)["code"] == "UNAVAILABLE"
    assert action_for(_hero("STALE"), buy, None)["code"] == "UNAVAILABLE"
    assert action_for(_hero("MARKET_CLOSED"), wait, None) == {
        "code": "WAIT",
        "stage": "CLOSED",
        "side": None,
        "bias": None,
        "thesis": None,
        "missing": None,
    }
    assert action_for(_hero("EXITED"), wait, None)["code"] == "EXIT"
    assert action_for(_hero("EXPIRED_SETUP", "BUY"), buy, None)["code"] == "WAIT"
    for state in ("WAIT", "SETUP_ARMED"):
        # a lean of the market is a bias, never the primary action
        assert action_for(_hero(state), wait, None)["code"] == "WAIT"


def test_a_ready_setup_the_desk_would_refuse_is_never_a_buy_or_sell() -> None:
    """Red-team finding: a taken-and-closed setup kept a giant BUY with only the button disabled."""
    buy = signal()
    dup = {"code": "DUPLICATE_SETUP", "message": "this setup was already taken"}
    blocked = action_for(_hero("BUY_READY", "BUY"), buy, None, [dup])
    assert (blocked["code"], blocked["stage"], blocked["side"]) == ("WAIT", "BLOCKED", "BUY")
    assert blocked["blocked_by"] == dup
    assert action_for(_hero("BUY_READY", "BUY"), buy, None, [])["code"] == "BUY"


def test_hold_reports_whether_the_entry_thesis_still_stands() -> None:
    bull = signal()  # H1 bullish in the helper state
    hold = action_for(_hero("POSITION_OPEN", "BUY"), bull, {"side": "BUY", "status": "OPEN"})
    assert (hold["code"], hold["stage"], hold["thesis"]) == ("HOLD", "OPEN", "INTACT")
    weak = action_for(_hero("POSITION_OPEN", "SELL"), bull, {"side": "SELL", "status": "OPEN"})
    assert weak["thesis"] == "WEAK"
    assert action_for(_hero("POSITION_OPEN", "BUY"), None, {"side": "BUY"})["thesis"] == "UNKNOWN"
