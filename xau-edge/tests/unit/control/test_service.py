"""Control service: lifecycle, mode, smoke and flatten on fakes (no real terminal, no real NSSM)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.unit.brokers.test_executor import MAGIC, T
from tests.unit.control.fakes import Rig, demo_terminal
from xau_edge.brokers.mt5_demo.executor import (
    SMOKE_COMMENT,
    ExecutorConfig,
    Mt5DemoExecutor,
    build_smoke_intent,
)
from xau_edge.brokers.mt5_demo.reader import DemoReader
from xau_edge.control.jobs import IdempotencyConflictError
from xau_edge.control.process import BotState
from xau_edge.control.runtime_mode import RuntimeMode, read_runtime_mode, write_runtime_mode
from xau_edge.control.service import ActionBlockedError, ConfirmationError
from xau_edge.execution.journal import ExecutionJournal
from xau_edge.execution.reconcile import Reconciler
from xau_edge.execution.state import ExecutionState
from xau_edge.market_data.broker_clock import BrokerClock


def _codes(blockers: list[dict[str, str]]) -> set[str]:
    return {b["code"] for b in blockers}


def _actions(rig: Rig) -> dict[str, dict[str, object]]:
    return rig.service.status()["actions"]  # type: ignore[no-any-return]


def _open_bot_position(rig: Rig) -> str:
    """Open one bot-owned position on the fake terminal, recorded in the bot's state."""
    state = ExecutionState(rig.paths.exec_dir / "state.sqlite")
    reader = DemoReader(rig.term, BrokerClock.parse("NY+7"))
    executor = Mt5DemoExecutor(
        rig.term,
        reader,
        state,
        ExecutionJournal(rig.tmp / "setup.jsonl"),
        Reconciler(state, magic=MAGIC, allowed_accounts=("555",), trip_on_mismatch=True),
        ExecutorConfig(
            enabled=True,
            dry_run=False,
            allowed_accounts=("555",),
            symbols=("XAUUSD",),
            magic=MAGIC,
            max_lots=1.0,
            smoke=True,
        ),
    )
    result = executor.submit_smoke(build_smoke_intent(rig.term.ask, T, magic=MAGIC), T)
    assert result.status == "FILLED"
    assert result.ticket is not None
    rig.term.sent.clear()
    rig.term.kill_switch_at_send.clear()
    return result.ticket


# -- F2 lifecycle ---------------------------------------------------------------------------------


def test_start_runs_a_fresh_preflight_and_starts_dry_run(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    job, replayed = rig.service.start("key-start-1")
    assert replayed is False
    assert job.status == "SUCCEEDED", job.message
    assert rig.process.calls == ["start:DRY_RUN"]
    assert rig.probes == 1
    events = rig.journal()
    assert events[-1]["event"] == "control.bot.start"
    assert events[-1]["source"] == "web"


def test_start_is_blocked_while_the_bot_runs(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    rig.process.state = BotState.RUNNING
    assert "BOT_ALREADY_RUNNING" in _codes(_actions(rig)["start"]["blockers"])  # type: ignore[arg-type]
    with pytest.raises(ActionBlockedError):
        rig.service.start("key-start-2")
    assert rig.process.calls == []


def test_start_is_blocked_by_a_tripped_kill_switch(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    ExecutionState(rig.paths.exec_dir / "state.sqlite").trip_kill_switch("TEST")
    with pytest.raises(ActionBlockedError) as info:
        rig.service.start("key-start-3")
    assert "KILL_SWITCH_TRIPPED" in {b.code for b in info.value.blockers}
    assert rig.process.calls == []


def test_start_is_blocked_by_a_failing_preflight(tmp_path: Path) -> None:
    rig = Rig(tmp_path, env={"XAU_EDGE_ENABLE_FUNDED_TRADING": "true"})
    with pytest.raises(ActionBlockedError) as info:
        rig.service.start("key-start-4")
    assert "PREFLIGHT_FAIL" in {b.code for b in info.value.blockers}


def test_a_terminal_failure_found_by_the_fresh_preflight_refuses_the_start(tmp_path: Path) -> None:
    rig = Rig(tmp_path, terminal=demo_terminal(trade_mode_demo=False))
    job, _ = rig.service.start("key-start-5")
    assert job.status == "REFUSED"
    assert job.error_code == "PREFLIGHT_FAIL"
    assert rig.process.calls == []
    assert rig.journal()[-1]["result"] == "REFUSED"


def test_stop_is_soft_and_reports_the_last_cycle(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    rig.process.state = BotState.RUNNING
    job, _ = rig.service.stop("key-stop-1")
    assert job.status == "SUCCEEDED"
    assert job.result["last_cycle"]["decision_time"] == "2026-03-04T13:45:00+00:00"
    assert rig.process.calls == ["stop"]


def test_stop_when_nothing_runs_is_not_offered(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    assert "BOT_NOT_RUNNING" in _codes(_actions(rig)["stop"]["blockers"])  # type: ignore[arg-type]


def test_demo_start_from_web_needs_demo_chosen_on_the_mode_card(tmp_path: Path) -> None:
    rig = Rig(tmp_path, env={"XAU_EDGE_DEMO_DRY_RUN": "false"})
    blockers = _codes(_actions(rig)["start"]["blockers"])  # type: ignore[arg-type]
    assert "DEMO_NOT_CONFIRMED_FROM_WEB" in blockers


# -- idempotency, one job at a time ---------------------------------------------------------------


def test_the_same_idempotency_key_never_runs_an_action_twice(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    first, _ = rig.service.start("key-idem-1")
    again, replayed = rig.service.start("key-idem-1")
    assert replayed is True
    assert again.id == first.id
    assert rig.process.calls == ["start:DRY_RUN"]


def test_a_key_reused_for_another_action_is_refused(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    rig.service.start("key-idem-2")
    with pytest.raises(IdempotencyConflictError):
        rig.service.stop("key-idem-2")


# -- F3 mode --------------------------------------------------------------------------------------


def test_demo_needs_the_typed_word(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    for word in ("", "demo", "YES", "DEMO "):
        with pytest.raises(ConfirmationError):
            rig.service.set_mode("DEMO", word, f"key-mode-{len(word)}x")
    assert read_runtime_mode(rig.paths.runtime_mode) is None


def test_switching_to_demo_writes_the_file_starts_and_confirms(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    job, _ = rig.service.set_mode("DEMO", "DEMO", "key-mode-demo")
    assert job.status == "SUCCEEDED", job.message
    record = read_runtime_mode(rig.paths.runtime_mode)
    assert record is not None
    assert record.mode is RuntimeMode.DEMO
    assert record.source == "web"
    assert rig.process.calls == ["start:DEMO"]
    results = [e["result"] for e in rig.journal() if e["event"] == "control.mode"]
    assert results == ["WRITTEN", "CONFIRMED"]


def test_switching_a_running_bot_stops_it_first(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    rig.process.state = BotState.RUNNING
    job, _ = rig.service.set_mode("DEMO", "DEMO", "key-mode-run")
    assert job.status == "SUCCEEDED", job.message
    assert rig.process.calls == ["stop", "start:DEMO"]


def test_a_bot_that_does_not_report_the_new_mode_fails_the_job(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    rig.process.reported_mode = "dry-run"
    job, _ = rig.service.set_mode("DEMO", "DEMO", "key-mode-mismatch")
    assert job.status == "FAILED"
    assert job.error_code == "MODE_MISMATCH"


@pytest.mark.parametrize(
    ("env", "terminal", "code"),
    [
        (
            {"XAU_EDGE_ENABLE_DEMO_TRADING": "false", "XAU_EDGE_DEMO_SMOKE": "false"},
            None,
            "ENV_DEMO_DISABLED",
        ),
        ({"MT5_TRADE_PASSWORD": ""}, None, "NO_TRADE_PASSWORD"),
        ({"XAU_EDGE_DEMO_ALLOWED_ACCOUNTS": "999"}, None, "ACCOUNT_NOT_WHITELISTED"),
        ({}, demo_terminal(terminal_trade_allowed=False), "TERMINAL_TRADE_DISABLED"),
        ({}, demo_terminal(trade_mode_demo=False), "NOT_DEMO_ACCOUNT"),
    ],
)
def test_demo_is_refused_when_a_condition_is_unmet(
    tmp_path: Path, env: dict[str, str], terminal: object, code: str
) -> None:
    rig = Rig(tmp_path, env=env, terminal=terminal)  # type: ignore[arg-type]
    if code in {"ENV_DEMO_DISABLED", "NO_TRADE_PASSWORD"}:  # known before touching the terminal
        with pytest.raises(ActionBlockedError) as info:
            rig.service.set_mode("DEMO", "DEMO", "key-mode-cond")
        assert code in {b.code for b in info.value.blockers}
    else:  # found by the fresh read-only probe inside the job
        job, _ = rig.service.set_mode("DEMO", "DEMO", "key-mode-cond")
        assert job.status == "REFUSED"
        assert code in str(rig.journal()) or job.error_code == code
    assert read_runtime_mode(rig.paths.runtime_mode) is None
    assert not any(c.startswith("start:DEMO") for c in rig.process.calls)


def test_demo_refused_after_stopping_restarts_the_previous_mode(tmp_path: Path) -> None:
    rig = Rig(tmp_path, terminal=demo_terminal(terminal_trade_allowed=False))
    rig.process.state = BotState.RUNNING
    rig.service._cache.terminal = None  # the bot held the terminal: nothing known yet
    job, _ = rig.service.set_mode("DEMO", "DEMO", "key-mode-back")
    assert job.status == "REFUSED"
    assert rig.process.calls == ["stop", "start:DRY_RUN"]


def test_dry_run_needs_no_typed_word_and_is_journaled(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    write_runtime_mode(rig.paths.runtime_mode, RuntimeMode.DEMO, T)
    job, _ = rig.service.set_mode("DRY_RUN", "", "key-mode-dry")
    assert job.status == "SUCCEEDED", job.message
    record = read_runtime_mode(rig.paths.runtime_mode)
    assert record is not None
    assert record.mode is RuntimeMode.DRY_RUN
    assert any(e["event"] == "control.mode" and e["mode"] == "DRY_RUN" for e in rig.journal())


@pytest.mark.parametrize("bad", ["FUNDED", "LIVE", "demo", "DRY-RUN", ""])
def test_the_service_never_accepts_another_mode(tmp_path: Path, bad: str) -> None:
    rig = Rig(tmp_path)
    with pytest.raises(ValueError, match="DRY_RUN or DEMO"):
        rig.service.set_mode(bad, "DEMO", "key-mode-bad")
    assert read_runtime_mode(rig.paths.runtime_mode) is None


# -- F4 smoke -------------------------------------------------------------------------------------


def _demo(rig: Rig) -> None:
    write_runtime_mode(rig.paths.runtime_mode, RuntimeMode.DEMO, T)


def test_smoke_sends_one_labelled_order_closes_it_and_reconciles(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    _demo(rig)
    rig.process.state = BotState.RUNNING
    job, _ = rig.service.smoke("SMOKE", "key-smoke-1")
    assert job.status == "SUCCEEDED", job.message
    r = job.result
    assert r["status"] == "FILLED"
    assert r["close_status"] == "FILLED"
    assert r["reconcile_clean"] is True
    assert "fill_price" in r
    assert "slippage_points" in r
    assert "round_trip_seconds" in r
    assert "KHÔNG phải bằng chứng edge" in r["note"]
    opens = [s for s in rig.term.sent if "position" not in s]
    assert len(opens) == 1
    assert opens[0]["volume"] == 0.01
    assert opens[0]["comment"] == SMOKE_COMMENT
    assert rig.process.calls == ["stop", "start:DEMO"]
    assert not rig.paths.lock.exists()


def test_smoke_needs_the_typed_word(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    _demo(rig)
    with pytest.raises(ConfirmationError):
        rig.service.smoke("smoke", "key-smoke-2")
    assert rig.term.sent == []


def test_smoke_is_blocked_with_an_open_bot_position(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    _demo(rig)
    _open_bot_position(rig)
    with pytest.raises(ActionBlockedError) as info:
        rig.service.smoke("SMOKE", "key-smoke-3")
    assert "BOT_POSITION_OPEN" in {b.code for b in info.value.blockers}
    assert rig.term.sent == []


def test_smoke_is_blocked_outside_demo_and_when_env_forbids_it(tmp_path: Path) -> None:
    rig = Rig(tmp_path, env={"XAU_EDGE_DEMO_SMOKE": "false"})
    codes = _codes(_actions(rig)["smoke"]["blockers"])  # type: ignore[arg-type]
    assert {"MODE_NOT_DEMO", "SMOKE_DISABLED_IN_ENV"} <= codes


def test_smoke_is_blocked_by_a_tripped_kill_switch(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    _demo(rig)
    ExecutionState(rig.paths.exec_dir / "state.sqlite").trip_kill_switch("TEST")
    codes = _codes(_actions(rig)["smoke"]["blockers"])  # type: ignore[arg-type]
    assert "KILL_SWITCH_TRIPPED" in codes


def test_smoke_is_rate_limited(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    _demo(rig)
    job, _ = rig.service.smoke("SMOKE", "key-smoke-4")
    assert job.status == "SUCCEEDED", job.message
    with pytest.raises(ActionBlockedError) as info:
        rig.service.smoke("SMOKE", "key-smoke-5")
    assert "RATE_LIMITED" in {b.code for b in info.value.blockers}


def test_smoke_is_blocked_in_the_ftmo_guard_window(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    _demo(rig)
    late = T.replace(hour=21, minute=50)  # 23:50 Prague: overnight rollover risk
    rig.deps.now = lambda: late
    codes = _codes(_actions(rig)["smoke"]["blockers"])  # type: ignore[arg-type]
    assert "FTMO_GUARD" in codes


# -- F5 flatten -----------------------------------------------------------------------------------


def test_flatten_trips_the_kill_switch_first_and_closes_only_bot_positions(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    ticket = _open_bot_position(rig)
    rig.term.positions.append(
        type(rig.term.positions[0])(
            ticket=5555,
            symbol="XAUUSD",
            type=0,
            volume=0.1,
            price_open=2000.0,
            sl=0.0,
            tp=0.0,
            magic=0,
            comment="manual",
            time=int(T.timestamp()),
        )
    )
    rig.process.state = BotState.RUNNING
    job, _ = rig.service.flatten("FLATTEN", "key-flat-1")
    assert job.status == "SUCCEEDED", job.message
    closes = [s for s in rig.term.sent if "position" in s]
    assert [str(c["position"]) for c in closes] == [ticket]
    assert rig.term.kill_switch_at_send == [True]
    assert [p.ticket for p in rig.term.positions] == [5555]
    assert job.result["manual_positions_untouched"] == 1
    assert job.result["still_open_tickets"] == []
    assert "kill_switch.py reset" in job.result["reset_command"]
    tripped, reason = ExecutionState(rig.paths.exec_dir / "state.sqlite").kill_switch_state()
    assert tripped is True
    assert reason == "WEB_FLATTEN"
    assert rig.process.calls == ["stop"]  # never restarted automatically


def test_flatten_is_allowed_with_the_kill_switch_already_tripped(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    ExecutionState(rig.paths.exec_dir / "state.sqlite").trip_kill_switch("EARLIER")
    assert _actions(rig)["flatten"]["allowed"] is True
    job, _ = rig.service.flatten("FLATTEN", "key-flat-2")
    assert job.status == "SUCCEEDED"
    assert rig.connects == 0  # nothing to close: no terminal session at all


def test_flatten_needs_the_typed_word(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    with pytest.raises(ConfirmationError):
        rig.service.flatten("flatten", "key-flat-3")
    tripped, _ = ExecutionState(rig.paths.exec_dir / "state.sqlite").kill_switch_state()
    assert tripped is False


def test_flatten_reports_positions_it_could_not_close(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    ticket = _open_bot_position(rig)
    rig.term.send_behaviour = "reject"
    job, _ = rig.service.flatten("FLATTEN", "key-flat-4")
    assert job.result["still_open_tickets"] == [ticket]
    assert "MT5" in job.result["manual_hint"]


def test_flatten_is_refused_when_funded_is_configured(tmp_path: Path) -> None:
    rig = Rig(tmp_path, env={"XAU_EDGE_ENABLE_FUNDED_TRADING": "true"})
    codes = _codes(_actions(rig)["flatten"]["blockers"])  # type: ignore[arg-type]
    assert codes & {"FUNDED_NOT_CONTROLLED_FROM_WEB", "ENV_INVALID"}
    with pytest.raises(ActionBlockedError):
        rig.service.flatten("FLATTEN", "key-flat-5")
    assert not (rig.paths.exec_dir / "state.sqlite").exists()


def test_one_job_at_a_time(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    held: list[object] = []
    rig.jobs._executor = held.append  # the job stays RUNNING
    rig.service.start("key-busy-1")
    assert rig.jobs.active() is not None
    with pytest.raises(ActionBlockedError) as info:
        rig.service.flatten("FLATTEN", "key-busy-2")
    assert {b.code for b in info.value.blockers} == {"JOB_RUNNING"}
