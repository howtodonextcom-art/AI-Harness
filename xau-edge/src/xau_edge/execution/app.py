"""The bot application: one guarded cycle and the supervising loop.

``BotApp`` holds no terminal or file knowledge of its own; ``scripts/demo_trader.py`` builds the
real collaborators and the tests build fakes. What it adds on top of the pieces:

* every error is classified (T2.3): transient terminal trouble backs off, reconnects and retries
  without ever ending the process; state, journal and account-type errors are fatal (the supervisor
  restarts the process and the alert tells the operator); the request budget pauses until the next
  Prague day;
* the account checks run in EVERY cycle, even with a position open (T2.7): the kill switch
  trips on a breach, and equity close to a loss floor flattens the bot's positions (T2.13);
* the day-start balance is rebuilt from the deal history as the balance at 00:00 Prague (T2.8);
* a system clock more than a few seconds off NTP stops trading (T3.5);
* an optional ``prop_facts`` hook adds the FTMO-facing facts (evidence label, rollout tier, floor
  distances, requests, trading days, kill switch) to ``status.json`` every cycle (T4.5);
* an optional ``stop_requested`` hook ends the loop between cycles, never inside one (ADR-0023).
"""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from datetime import time as dtime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from xau_edge.brokers.mt5_demo.connect import TradeConnectError
from xau_edge.brokers.mt5_demo.executor import Mt5DemoExecutor
from xau_edge.brokers.mt5_demo.reader import DemoAccountError, DemoReader, NotDemoAccountError
from xau_edge.execution.guards import (
    PRAGUE,
    RequestBudgetExceededError,
    evaluate_flatten,
    next_prague_midnight,
)
from xau_edge.execution.journal import ExecutionJournal
from xau_edge.execution.reconcile import BrokerSnapshot, Reconciler, trailing_losses
from xau_edge.execution.runner import (
    CycleReport,
    DryRunCycle,
    JournalError,
    next_close,
    write_heartbeat,
)
from xau_edge.execution.safety import day_key
from xau_edge.execution.state import ExecutionState, StateError
from xau_edge.execution.status import StatusPropFacts, build_status, write_status
from xau_edge.market_data.mt5.source import Mt5AccountError, Mt5NotAvailableError
from xau_edge.observability import log_event
from xau_edge.risk.engine import AccountState, RiskEngine
from xau_edge.risk.prop_rules import PropProfile
from xau_edge.signals.engine import MarketFrames

_LOG = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_TRANSIENT_ONCE = 5
EXIT_FATAL = 6
EXIT_UNKNOWN_ERRORS = 7
MAX_UNKNOWN_ERRORS = 5
CRITICAL_AFTER_FAILURES = 5

AlertFn = Callable[[str, str, str], None]
"""``alert(code, severity, message)``: delivery, de-duplication and fallback are the caller's."""

PropFactsFn = Callable[[datetime, AccountState | None], StatusPropFacts]
"""``prop_facts(now, account)``: the FTMO-facing facts written into ``status.json`` each cycle."""


class ErrorClass(StrEnum):
    """How the loop reacts to an exception."""

    TRANSIENT = "TRANSIENT"
    BUDGET = "BUDGET"
    FATAL = "FATAL"
    UNKNOWN = "UNKNOWN"


def classify_error(exc: BaseException) -> ErrorClass:
    """Map an exception to a reaction. Order matters: several of these are RuntimeErrors."""
    if isinstance(exc, RequestBudgetExceededError):
        return ErrorClass.BUDGET
    if isinstance(
        exc, StateError | JournalError | NotDemoAccountError | Mt5AccountError | TradeConnectError
    ):
        return ErrorClass.FATAL
    if isinstance(
        exc,
        DemoAccountError | Mt5NotAvailableError | ConnectionError | TimeoutError | OSError,
    ):
        return ErrorClass.TRANSIENT
    if isinstance(exc, RuntimeError):  # the MT5 wrappers raise RuntimeError on a failed call
        return ErrorClass.TRANSIENT
    return ErrorClass.UNKNOWN


@dataclass
class Backoff:
    """Exponential delay with a ceiling; ``reset`` after a success."""

    base: float = 5.0
    factor: float = 2.0
    maximum: float = 300.0
    attempt: int = 0

    def next_delay(self) -> float:
        """The delay for this failure; the next failure waits longer."""
        delay = min(self.maximum, self.base * self.factor**self.attempt)
        self.attempt += 1
        return delay

    def reset(self) -> None:
        """Forget earlier failures."""
        self.attempt = 0


class ClockCheck(Protocol):
    """What the NTP check returns (``ops.clock_check.ClockCheckResult`` satisfies it)."""

    @property
    def offset_seconds(self) -> float | None:
        """Measured offset in seconds, ``None`` when unknown."""
        ...

    def exceeds(self, limit: float = ...) -> bool:
        """True if the measured offset is above the limit."""
        ...


@dataclass(frozen=True)
class CycleResult:
    """What one cycle ended as."""

    status: str
    report: CycleReport | None = None


def _noop_alert(code: str, severity: str, message: str) -> None:
    return None


class BotApp:
    """One guarded cycle (``run_cycle``) and the loop around it (``run``)."""

    def __init__(
        self,
        *,
        mode: str,
        symbol: str,
        state: ExecutionState,
        reader: DemoReader,
        executor: Mt5DemoExecutor | None,
        reconciler: Reconciler,
        risk: RiskEngine,
        prop: PropProfile,
        audit: ExecutionJournal,
        refresh: Callable[[datetime], None],
        load_frames: Callable[[], tuple[MarketFrames, list[str]]],
        make_cycle: Callable[[MarketFrames], DryRunCycle],
        exec_dir: Path,
        initial_capital: float | None = None,
        flatten_distance_pct: float = 1.0,
        warn_distance_pct: float = 2.0,
        alert: AlertFn = _noop_alert,
        ntp_check: Callable[[], ClockCheck | None] | None = None,
        reconnect: Callable[[], None] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        settle_seconds: float = 20.0,
        max_clock_offset_seconds: float = 5.0,
        prop_facts: PropFactsFn | None = None,
        stop_requested: Callable[[], bool] | None = None,
    ) -> None:
        self.mode = mode
        self.symbol = symbol
        self.state = state
        self.reader = reader
        self.executor = executor
        self.reconciler = reconciler
        self.risk = risk
        self.prop = prop
        self.audit = audit
        self._refresh = refresh
        self._load_frames = load_frames
        self._make_cycle = make_cycle
        self.exec_dir = exec_dir
        self.initial_capital = initial_capital
        self.flatten_distance_pct = flatten_distance_pct
        self.warn_distance_pct = warn_distance_pct
        self._alert = alert
        self._ntp_check = ntp_check
        self._reconnect = reconnect
        self._sleep = sleep
        self._clock = clock
        self.settle_seconds = settle_seconds
        self.max_clock_offset_seconds = max_clock_offset_seconds
        self._prop_facts = prop_facts
        self._stop_requested = stop_requested
        self.backoff = Backoff()

    # -- files ---------------------------------------------------------------------------------

    def _write(
        self,
        now: datetime,
        heartbeat: str,
        *,
        snapshot: BrokerSnapshot | None = None,
        reconcile: Any = None,
        report: CycleReport | None = None,
        account: AccountState | None = None,
    ) -> None:
        write_heartbeat(self.exec_dir / "heartbeat.json", now, heartbeat)
        tickets = frozenset(r.ticket for r in self._open_records())
        write_status(
            self.exec_dir / "status.json",
            build_status(
                now,
                mode=self.mode,  # type: ignore[arg-type]
                symbol=self.symbol,
                snapshot=snapshot,
                reconcile=reconcile,
                report=report,
                bot_tickets=tickets,
                prop=self._facts(now, account),
            ),
        )

    def _facts(self, now: datetime, account: AccountState | None) -> StatusPropFacts | None:
        """The hook's facts; a failing hook costs the status its prop facts, never the cycle."""
        if self._prop_facts is None:
            return None
        try:
            return self._prop_facts(now, account)
        except Exception as exc:
            log_event(_LOG, "status.prop_facts_failed", logging.WARNING, error=type(exc).__name__)
            return None

    def _open_records(self) -> list[Any]:
        try:
            return self.state.open_positions()
        except StateError:
            return []

    # -- account -------------------------------------------------------------------------------

    def _day_start_balance(self, now: datetime, balance: float, fallback: float) -> float:
        """Balance at 00:00 Europe/Prague: balance now minus the net result since then."""
        local = now.astimezone(PRAGUE)
        midnight = datetime.combine(local.date(), dtime.min, tzinfo=PRAGUE).astimezone(UTC)
        try:
            candidate = balance - self.reader.net_since(midnight, now)
        except DemoAccountError:
            return fallback
        return candidate if math.isfinite(candidate) and candidate > 0 else fallback

    def _account_state(self, now: datetime, snapshot: BrokerSnapshot) -> AccountState:
        balance = snapshot.account.balance
        day = day_key(now.astimezone(PRAGUE).date())
        baseline = self.state.account_baseline(day, balance, initial_capital=self.initial_capital)
        return AccountState(
            timestamp=now,
            initial_capital=self.initial_capital or baseline.initial_capital,
            balance=balance,
            equity=snapshot.account.equity,
            day_start_balance=self._day_start_balance(now, balance, baseline.day_start_balance),
            highest_eod_balance=baseline.highest_eod_balance,
            open_positions=len(snapshot.positions),
            open_lots=sum(p.lots for p in snapshot.positions),
            risk_taken_today=self.state.risk_taken(day),
            consecutive_losses=trailing_losses(snapshot.closed, self.state.all_bot_tickets()),
        )

    def _guard_account(self, now: datetime, account: AccountState) -> str | None:
        """Account checks that run every cycle; returns a status when the cycle must stop."""
        if self.risk.check_account(account):
            self._alert(
                "KILL_SWITCH_TRIPPED", "critical", f"account check: {self.risk.kill_switch.reason}"
            )
        decision = evaluate_flatten(account, self.prop, distance_pct=self.flatten_distance_pct)
        if decision.flatten:
            self._flatten(now, decision.reason)
            return "FLATTENED"
        if min(decision.daily_distance_pct, decision.max_distance_pct) <= self.warn_distance_pct:
            self._alert(
                "NEAR_DAILY_LOSS_FLOOR",
                "warning",
                f"equity is {decision.daily_distance_pct:.2f}% of capital above the daily floor",
            )
        return None

    def _flatten(self, now: datetime, reason: str) -> None:
        log_event(_LOG, "flatten.triggered", logging.CRITICAL, reason=reason)
        if self.executor is not None:
            results = self.executor.flatten_all(reason)
            summary = ", ".join(r.status for r in results) or "no open positions"
        else:
            self.state.trip_kill_switch(reason)
            summary = "dry-run: kill switch tripped, nothing to close"
        self.audit.record("flatten", reason=reason, summary=summary)
        self._alert("AUTO_FLATTEN", "critical", f"{reason}: {summary}")

    # -- one cycle -----------------------------------------------------------------------------

    def run_cycle(self, now: datetime, *, force: bool = False) -> CycleResult:
        """One full decision cycle; raises on terminal or storage trouble (``classify_error``)."""
        if self._ntp_check is not None:
            check = self._ntp_check()
            if check is not None and check.exceeds(self.max_clock_offset_seconds):
                self.state.trip_kill_switch(f"CLOCK_DRIFT: {check.offset_seconds}")
                self._alert("CLOCK_DRIFT", "critical", f"clock offset {check.offset_seconds} s")
                self._write(now, "CLOCK_DRIFT")
                return CycleResult("CLOCK_DRIFT")
        self._refresh(now)
        frames, invalid = self._load_frames()
        snapshot = self.reader.snapshot(now)
        if self.executor is not None:
            expired = self.executor.close_expired(now)
            for closed in expired:
                self.audit.record(
                    "expiry.close", status=closed.status, reasons=list(closed.reasons)
                )
            if expired:  # re-read only when something changed: every call counts to the budget
                snapshot = self.reader.snapshot(now)
        reconcile = self.reconciler.check(snapshot)
        self.audit.record("reconcile.result", clean=reconcile.clean, codes=list(reconcile.codes))
        if not reconcile.clean:
            self._alert("RECONCILE_MISMATCH", "critical", ", ".join(reconcile.codes))
        account = self._account_state(now, snapshot)
        if self._guard_account(now, account) == "FLATTENED":
            self._write(now, "FLATTENED", snapshot=snapshot, reconcile=reconcile, account=account)
            return CycleResult("FLATTENED")
        if invalid:
            self._alert("STALE_DATA", "warning", f"validation failed for {invalid}")
            self._write(
                now, "DATA_INVALID", snapshot=snapshot, reconcile=reconcile, account=account
            )
            return CycleResult("DATA_INVALID")
        report = self._make_cycle(frames).run(
            frames, now, account, force=force, reconcile=reconcile
        )
        self._alerts_from_report(report)
        self._write(
            now, "OK", snapshot=snapshot, reconcile=reconcile, report=report, account=account
        )
        return CycleResult("OK", report)

    def _alerts_from_report(self, report: CycleReport) -> None:
        if "DATA_STALE" in report.reasons:
            self._alert("STALE_DATA", "warning", "market data older than the limit")
        if report.order_status in ("REJECTED", "REFUSED", "UNKNOWN"):
            self._alert("ORDER_REFUSED", "critical", f"order {report.order_status}")
        if "KILL_SWITCH" in report.reasons:
            self._alert("KILL_SWITCH_TRIPPED", "critical", "kill switch is tripped")

    # -- the loop ------------------------------------------------------------------------------

    def run(  # noqa: PLR0911, PLR0912 - one exit per error class and per stop point
        self, *, once: bool = False, max_cycles: int = 0, force: bool = False
    ) -> int:
        """Run until stopped; returns a process exit code (0 normal)."""
        cycles = 0
        failures = 0
        unknown_failures = 0
        while True:
            now = self._clock()
            if self._stop_now():
                return self._stopped(now)
            try:
                self.run_cycle(now, force=force)
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                kind = classify_error(exc)
                log_event(
                    _LOG, "cycle.error", logging.ERROR, kind=kind.value, error=type(exc).__name__
                )
                if kind is ErrorClass.FATAL:
                    self._alert("BOT_STOPPED", "critical", f"fatal {type(exc).__name__}: {exc}")
                    self._safe_heartbeat(now, "FATAL")
                    return EXIT_FATAL
                if kind is ErrorClass.BUDGET:
                    self._alert("REQUEST_BUDGET", "critical", "daily request budget reached")
                    self._safe_heartbeat(now, "BUDGET_EXHAUSTED")
                    if once:
                        return EXIT_TRANSIENT_ONCE
                    wake = next_prague_midnight(now) + timedelta(seconds=30)
                    if self._pause(max(1.0, (wake - self._clock()).total_seconds())):
                        return self._stopped(self._clock())
                    continue
                if kind is ErrorClass.UNKNOWN:
                    unknown_failures += 1
                    if unknown_failures >= MAX_UNKNOWN_ERRORS:
                        self._alert("BOT_STOPPED", "critical", f"repeated {type(exc).__name__}")
                        self._safe_heartbeat(now, "FATAL")
                        return EXIT_UNKNOWN_ERRORS
                failures += 1
                severity = "critical" if failures >= CRITICAL_AFTER_FAILURES else "warning"
                self._alert("TERMINAL_TROUBLE", severity, f"{type(exc).__name__} (x{failures})")
                self._safe_heartbeat(now, "RETRYING")
                if once:
                    return EXIT_TRANSIENT_ONCE
                if self._pause(self.backoff.next_delay()):
                    return self._stopped(self._clock())
                self._try_reconnect()
                continue
            failures = 0
            unknown_failures = 0
            self.backoff.reset()
            cycles += 1
            if once or (max_cycles and cycles >= max_cycles):
                return EXIT_OK
            wake = next_close(self._clock()) + timedelta(seconds=self.settle_seconds)
            if self._pause(max(1.0, (wake - self._clock()).total_seconds())):
                return self._stopped(self._clock())

    def _stop_now(self) -> bool:
        return self._stop_requested is not None and self._stop_requested()

    def _pause(self, seconds: float) -> bool:
        """Wait; True when a soft stop was requested (checked at least once a second)."""
        if self._stop_requested is None:
            self._sleep(seconds)
            return False
        remaining = seconds
        while remaining > 0:
            if self._stop_requested():
                return True
            step = min(1.0, remaining)
            self._sleep(step)
            remaining -= step
        return self._stop_requested()

    def _stopped(self, now: datetime) -> int:
        """A soft stop between cycles: never in the middle of one (ADR-0023)."""
        log_event(_LOG, "bot.soft_stop", logging.WARNING)
        self._safe_heartbeat(now, "STOPPED")
        try:
            self.audit.record("bot.stopped", reason="stop requested", source="web")
        except JournalError as exc:
            log_event(_LOG, "bot.stop_journal_failed", logging.ERROR, error=type(exc).__name__)
        return EXIT_OK

    def _try_reconnect(self) -> None:
        if self._reconnect is None:
            return
        try:
            self._reconnect()
        except Exception as exc:
            log_event(_LOG, "reconnect.failed", logging.WARNING, error=type(exc).__name__)

    def _safe_heartbeat(self, now: datetime, status: str) -> None:
        try:
            write_heartbeat(self.exec_dir / "heartbeat.json", now, status)
        except OSError as exc:
            log_event(_LOG, "heartbeat.failed", logging.ERROR, error=str(exc))
