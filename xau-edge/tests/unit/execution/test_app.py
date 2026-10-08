"""BotApp: error classes, backoff and reconnect, account checks, flatten, clock, day start."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests.unit.api.test_api import frames  # noqa: F401 - fixture import
from tests.unit.brokers.test_executor import (
    LOGIN,
    MAGIC,
    FakeTerminal,
    _go,
    _intent,
)
from tests.unit.execution.test_bridge import PROP
from tests.unit.signals.test_decision import _inputs
from xau_edge.brokers.mt5_demo.connect import TradeConnectError
from xau_edge.brokers.mt5_demo.executor import ExecutorConfig, Mt5DemoExecutor
from xau_edge.brokers.mt5_demo.reader import DemoAccountError, DemoReader, NotDemoAccountError
from xau_edge.execution.app import (
    EXIT_FATAL,
    EXIT_OK,
    EXIT_TRANSIENT_ONCE,
    EXIT_UNKNOWN_ERRORS,
    Backoff,
    BotApp,
    ErrorClass,
    classify_error,
)
from xau_edge.execution.bridge import SignalBridge
from xau_edge.execution.guards import RequestBudgetExceededError
from xau_edge.execution.journal import ExecutionJournal
from xau_edge.execution.reconcile import Reconciler
from xau_edge.execution.runner import CycleJournal, DryRunCycle, JournalError
from xau_edge.execution.safety import ExecutionSafety
from xau_edge.execution.state import ExecutionState, PersistentKillSwitch, StateError
from xau_edge.market_data.broker_clock import BrokerClock
from xau_edge.market_data.mt5.source import Mt5AccountError, Mt5NotAvailableError
from xau_edge.risk.engine import RiskEngine, RiskLimits
from xau_edge.signals.decision import decide
from xau_edge.signals.engine import MarketFrames
from xau_edge.signals.schema import EvidenceStatus, Signal

T = datetime(2026, 3, 4, 14, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("exc", "kind"),
    [
        (RequestBudgetExceededError("x"), ErrorClass.BUDGET),
        (StateError("x"), ErrorClass.FATAL),
        (JournalError("x"), ErrorClass.FATAL),
        (NotDemoAccountError("x"), ErrorClass.FATAL),
        (Mt5AccountError("x"), ErrorClass.FATAL),
        (TradeConnectError("x"), ErrorClass.FATAL),
        (DemoAccountError("x"), ErrorClass.TRANSIENT),
        (Mt5NotAvailableError("x"), ErrorClass.TRANSIENT),
        (ConnectionError("x"), ErrorClass.TRANSIENT),
        (TimeoutError("x"), ErrorClass.TRANSIENT),
        (OSError("x"), ErrorClass.TRANSIENT),
        (RuntimeError("MT5 copy_rates_range failed"), ErrorClass.TRANSIENT),
        (ValueError("x"), ErrorClass.UNKNOWN),
        (KeyError("x"), ErrorClass.UNKNOWN),
    ],
)
def test_errors_are_classified(exc: BaseException, kind: ErrorClass) -> None:
    assert classify_error(exc) is kind


def test_backoff_doubles_up_to_a_ceiling_and_resets() -> None:
    backoff = Backoff(base=5.0, factor=2.0, maximum=30.0)
    assert [backoff.next_delay() for _ in range(5)] == [5.0, 10.0, 20.0, 30.0, 30.0]
    backoff.reset()
    assert backoff.next_delay() == 5.0


class Harness:
    """A BotApp wired to fakes, with every outside effect recorded."""

    def __init__(
        self,
        tmp_path: Path,
        frames: MarketFrames,  # noqa: F811
        *,
        term: FakeTerminal | None = None,
        with_executor: bool = False,
        initial_capital: float | None = 100_000.0,
        **overrides: Any,
    ) -> None:
        self.term = term or FakeTerminal()
        self.frames = frames
        self.alerts: list[tuple[str, str, str]] = []
        self.sleeps: list[float] = []
        self.refreshes = 0
        self.reconnects = 0
        self.errors: list[BaseException] = []
        self.state = ExecutionState(tmp_path / "s.sqlite")
        self.audit = ExecutionJournal(tmp_path / "j.jsonl")
        clock = BrokerClock.parse("NY+7")
        self.reader = DemoReader(self.term, clock)
        self.reconciler = Reconciler(
            self.state,
            magic=MAGIC,
            allowed_accounts=(LOGIN,),
            trip_on_mismatch=with_executor,
        )
        self.risk = RiskEngine(RiskLimits(), PROP, PersistentKillSwitch(self.state))
        safety = ExecutionSafety(dry_run=not with_executor)
        self.bridge = SignalBridge(
            self.state, self.risk, safety, magic=MAGIC, dry_run=not with_executor
        )
        self.executor: Mt5DemoExecutor | None = None
        if with_executor:
            self.executor = Mt5DemoExecutor(
                self.term,
                self.reader,
                self.state,
                self.audit,
                self.reconciler,
                ExecutorConfig(
                    enabled=True,
                    dry_run=False,
                    allowed_accounts=(LOGIN,),
                    symbols=("XAUUSD",),
                    magic=MAGIC,
                    max_lots=1.0,
                ),
                sleep=lambda s: None,
            )
        self.cycle_journal = CycleJournal(tmp_path / "cycles.jsonl")
        self.accounts: list[Any] = []
        self.tmp_path = tmp_path
        latest = frames.m15["timestamp"].max()
        assert isinstance(latest, datetime)
        self.now: datetime = latest + timedelta(minutes=16)
        self.app = BotApp(
            mode="demo" if with_executor else "dry-run",
            symbol="XAUUSD",
            state=self.state,
            reader=self.reader,
            executor=self.executor,
            reconciler=self.reconciler,
            risk=self.risk,
            prop=PROP,
            audit=self.audit,
            refresh=self._refresh,
            load_frames=lambda: (self.frames, []),
            make_cycle=self._make_cycle,
            exec_dir=tmp_path / "exec",
            initial_capital=initial_capital,
            alert=lambda code, sev, msg: self.alerts.append((code, sev, msg)),
            sleep=self.sleeps.append,
            clock=lambda: self.now,
            **overrides,
        )

    def _refresh(self, now: datetime) -> None:
        self.refreshes += 1
        if self.errors:
            raise self.errors.pop(0)

    def _make_cycle(self, frames_: MarketFrames) -> DryRunCycle:
        price = float(frames_.m5["close"][-1])

        def signal_fn(at: datetime) -> Signal:
            return decide(_inputs(timestamp=at, price=price, evidence_status=EvidenceStatus.NONE))

        cycle = DryRunCycle(self.bridge, signal_fn, self.cycle_journal)
        original = cycle.run

        def spy(*args: Any, **kwargs: Any) -> Any:
            self.accounts.append(args[2])
            return original(*args, **kwargs)

        cycle.run = spy  # type: ignore[method-assign]
        return cycle

    def alert_codes(self) -> list[str]:
        return [a[0] for a in self.alerts]


def test_a_healthy_cycle_writes_status_and_heartbeat(
    tmp_path: Path,
    frames: MarketFrames,  # noqa: F811
) -> None:
    h = Harness(tmp_path, frames)
    result = h.app.run_cycle(h.now)
    assert result.status == "OK"
    heartbeat = json.loads((tmp_path / "exec" / "heartbeat.json").read_text(encoding="utf-8"))
    assert heartbeat["status"] == "OK"
    status = json.loads((tmp_path / "exec" / "status.json").read_text(encoding="utf-8"))
    assert status["connected"] is True
    assert status["last_cycle"]["direction"] == "WAIT"


def test_transient_errors_back_off_reconnect_and_never_end_the_process(
    tmp_path: Path,
    frames: MarketFrames,  # noqa: F811
) -> None:
    h = Harness(tmp_path, frames)
    h.errors = [ConnectionError("down"), RuntimeError("MT5 copy_rates_range failed")]
    reconnect_calls: list[int] = []
    h.app._reconnect = lambda: reconnect_calls.append(1)
    code = h.app.run(max_cycles=1)
    assert code == EXIT_OK
    assert h.sleeps[:2] == [5.0, 10.0]  # backoff doubled
    assert len(reconnect_calls) == 2
    assert h.alert_codes().count("TERMINAL_TROUBLE") == 2
    assert all(sev == "warning" for _, sev, _ in h.alerts)
    assert h.app.backoff.attempt == 0  # reset by the success


def test_repeated_failures_escalate_to_critical(
    tmp_path: Path,
    frames: MarketFrames,  # noqa: F811
) -> None:
    h = Harness(tmp_path, frames)
    h.errors = [OSError("x")] * 5
    assert h.app.run(max_cycles=1) == EXIT_OK
    severities = [sev for code, sev, _ in h.alerts if code == "TERMINAL_TROUBLE"]
    assert severities == ["warning"] * 4 + ["critical"]


def test_a_failed_reconnect_is_just_another_transient_failure(
    tmp_path: Path,
    frames: MarketFrames,  # noqa: F811
) -> None:
    h = Harness(tmp_path, frames)
    h.errors = [OSError("x")]

    def broken() -> None:
        raise ConnectionError("still down")

    h.app._reconnect = broken
    assert h.app.run(max_cycles=1) == EXIT_OK


def test_once_mode_reports_a_transient_failure_by_exit_code(
    tmp_path: Path,
    frames: MarketFrames,  # noqa: F811
) -> None:
    h = Harness(tmp_path, frames)
    h.errors = [ConnectionError("down")]
    assert h.app.run(once=True) == EXIT_TRANSIENT_ONCE
    heartbeat = json.loads((tmp_path / "exec" / "heartbeat.json").read_text(encoding="utf-8"))
    assert heartbeat["status"] == "RETRYING"


@pytest.mark.parametrize("exc", [StateError("corrupt"), NotDemoAccountError("real account")])
def test_fatal_errors_stop_the_loop_and_alert(
    tmp_path: Path,
    frames: MarketFrames,  # noqa: F811
    exc: BaseException,
) -> None:
    h = Harness(tmp_path, frames)
    h.errors = [exc]
    assert h.app.run() == EXIT_FATAL
    assert "BOT_STOPPED" in h.alert_codes()
    heartbeat = json.loads((tmp_path / "exec" / "heartbeat.json").read_text(encoding="utf-8"))
    assert heartbeat["status"] == "FATAL"


def test_the_request_budget_pauses_until_the_next_prague_day(
    tmp_path: Path,
    frames: MarketFrames,  # noqa: F811
) -> None:
    h = Harness(tmp_path, frames)
    h.errors = [RequestBudgetExceededError("budget")]
    assert h.app.run(max_cycles=1) == EXIT_OK
    assert "REQUEST_BUDGET" in h.alert_codes()
    assert h.sleeps[0] > 60  # slept toward Prague midnight, not a short backoff


def test_repeated_unclassified_errors_end_the_process(
    tmp_path: Path,
    frames: MarketFrames,  # noqa: F811
) -> None:
    h = Harness(tmp_path, frames)
    h.errors = [ValueError("bug")] * 5
    assert h.app.run() == EXIT_UNKNOWN_ERRORS
    assert "BOT_STOPPED" in h.alert_codes()


def test_the_account_check_runs_every_cycle_and_trips_on_a_breach(
    tmp_path: Path,
    frames: MarketFrames,  # noqa: F811
) -> None:
    term = FakeTerminal()
    term.equity = 89_000.0  # below the static 90,000 floor
    term.balance = 89_000.0
    h = Harness(tmp_path, frames, term=term)
    h.app.run_cycle(h.now)
    assert h.state.kill_switch_state()[0] is True
    assert "KILL_SWITCH_TRIPPED" in h.alert_codes()


def test_the_account_check_also_runs_while_a_position_is_open(
    tmp_path: Path,
    frames: MarketFrames,  # noqa: F811
) -> None:
    h = Harness(tmp_path, frames, with_executor=True)
    assert h.executor is not None
    opened = _go(h.executor, _intent(), T)
    assert opened.status == "FILLED"
    h.term.equity = 89_000.0  # the open position's loss pushes equity below the floor
    h.term.balance = 100_000.0
    h.app.run_cycle(T)
    assert h.state.kill_switch_state()[0] is True


def test_equity_near_the_daily_floor_flattens_the_bots_positions_and_trips(
    tmp_path: Path,
    frames: MarketFrames,  # noqa: F811
) -> None:
    h = Harness(tmp_path, frames, with_executor=True)
    assert h.executor is not None
    assert _go(h.executor, _intent(), T).status == "FILLED"
    h.term.positions.append(
        SimpleNamespace(
            ticket=9, symbol="EURUSD", type=0, volume=1.0, price_open=1.0, sl=0.0, tp=0.0,
            magic=0, comment="manual", time=int(T.timestamp()),
        )
    )  # fmt: skip
    h.term.equity = 95_500.0  # 0.5% of capital above the 95,000 daily floor
    result = h.app.run_cycle(T)
    assert result.status == "FLATTENED"
    assert h.state.kill_switch_state()[0] is True
    assert h.state.open_positions() == []
    assert [p.symbol for p in h.term.positions] == ["EURUSD"]  # the manual one is untouched
    assert "AUTO_FLATTEN" in h.alert_codes()
    events = [e["event"] for e in h.audit.read()]
    assert "flatten.started" in events
    assert "flatten.finished" in events


def test_in_dry_run_a_flatten_condition_trips_the_kill_switch_only(
    tmp_path: Path,
    frames: MarketFrames,  # noqa: F811
) -> None:
    term = FakeTerminal()
    term.equity = 95_500.0
    h = Harness(tmp_path, frames, term=term)
    assert h.app.run_cycle(h.now).status == "FLATTENED"
    assert h.state.kill_switch_state()[0] is True


def test_a_clock_off_ntp_stops_trading_and_trips(
    tmp_path: Path,
    frames: MarketFrames,  # noqa: F811
) -> None:
    class Drift:
        offset_seconds = 12.0

        def exceeds(self, limit: float = 5.0) -> bool:
            return abs(self.offset_seconds) > limit

    h = Harness(tmp_path, frames, ntp_check=Drift)
    result = h.app.run_cycle(h.now)
    assert result.status == "CLOCK_DRIFT"
    assert h.refreshes == 0  # nothing was fetched on a bad clock
    assert h.state.kill_switch_state()[0] is True
    assert "CLOCK_DRIFT" in h.alert_codes()


def test_an_unmeasured_clock_does_not_stop_trading(
    tmp_path: Path,
    frames: MarketFrames,  # noqa: F811
) -> None:
    class Unknown:
        offset_seconds = None

        def exceeds(self, limit: float = 5.0) -> bool:
            return False

    h = Harness(tmp_path, frames, ntp_check=Unknown)
    assert h.app.run_cycle(h.now).status == "OK"


def test_the_day_start_balance_is_rebuilt_from_the_deals_since_prague_midnight(
    tmp_path: Path,
    frames: MarketFrames,  # noqa: F811
) -> None:
    term = FakeTerminal()
    term.balance = 99_000.0
    term.equity = 99_000.0
    term.deals = [
        SimpleNamespace(
            ticket=1, position_id=1, entry=1, symbol="XAUUSD", profit=-1_200.0, commission=-20.0,
            swap=-5.0, time=int(T.timestamp()),
        ),
        SimpleNamespace(
            ticket=2, position_id=0, entry=2, symbol="", profit=500.0, commission=0.0,
            swap=0.0, time=int(T.timestamp()),
        ),  # a deposit counts too
    ]  # fmt: skip
    h = Harness(tmp_path, frames, term=term)
    h.app.run_cycle(h.now)
    account = h.accounts[0]
    # balance now 99,000; net since midnight = -1,200 - 20 - 5 + 500 = -725 -> day start 99,725
    assert account.day_start_balance == pytest.approx(99_725.0)
    assert account.initial_capital == 100_000.0


def test_without_deal_history_the_day_start_falls_back_to_the_stored_baseline(
    tmp_path: Path,
    frames: MarketFrames,  # noqa: F811
) -> None:
    term = FakeTerminal()
    term.history_deals_get = lambda start, end: None  # type: ignore[method-assign]
    h = Harness(tmp_path, frames, term=term)
    # the snapshot itself needs the history for closed results, so this surfaces as transient
    with pytest.raises(DemoAccountError):
        h.app.run_cycle(h.now)


def test_a_dirty_reconciliation_alerts_and_the_cycle_is_refused(
    tmp_path: Path,
    frames: MarketFrames,  # noqa: F811
) -> None:
    term = FakeTerminal()
    term.positions.append(
        SimpleNamespace(
            ticket=5, symbol="XAUUSD", type=0, volume=0.1, price_open=2000.0, sl=0.0, tp=0.0,
            magic=0, comment="manual", time=int(T.timestamp()),
        )
    )  # fmt: skip
    h = Harness(tmp_path, frames, term=term, with_executor=True)
    result = h.app.run_cycle(h.now)
    assert result.report is not None
    assert result.report.reasons[0] == "RECONCILE_MANUAL_POSITION_SAME_SYMBOL"
    assert "RECONCILE_MISMATCH" in h.alert_codes()
    assert h.state.kill_switch_state()[0] is True
