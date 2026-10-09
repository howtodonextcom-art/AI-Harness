"""The local web control plane behind ``/control/*`` (ADR-0023).

Everything a button does is decided here, never in the browser: which actions are available now
(with reasons when not), and the steps of each action, run as a job. The service reuses the bot's
own pieces (lock, kill switch, executor, reconciler, journal) and adds no new way to trade:

* the only modes it can select are DRY_RUN and DEMO (``runtime_mode.json``, bounded by ``.env``);
* the only orders it can cause are the labelled 0.01-lot smoke order and the closing of the bot's
  own positions (flatten), both through ``Mt5DemoExecutor``;
* it never resets the kill switch, never edits ``.env`` and never touches funded or live settings.

Every control action is journaled with ``source="web"``. Responses carry codes and short
Vietnamese messages, never exception text, file paths or secrets.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from pydantic import ValidationError

from xau_edge.brokers.mt5_demo.connect import (
    Mt5TradeSettings,
    TradeConnectError,
    connect_for_trading,
)
from xau_edge.brokers.mt5_demo.executor import (
    TRADE_SERVER_REQUESTS,
    ExecutorConfig,
    Mt5DemoExecutor,
)
from xau_edge.brokers.mt5_demo.reader import DemoReader
from xau_edge.config import Settings
from xau_edge.control.jobs import (
    IdempotencyConflictError,
    Job,
    JobContext,
    JobFailedError,
    JobManager,
    JobRefusedError,
    RateLimiter,
)
from xau_edge.control.operations import (
    FLATTEN_REASON,
    MANUAL_CLOSE_HINT,
    TradingKit,
    bot_positions_on_broker,
    run_flatten,
    run_smoke,
)
from xau_edge.control.paths import ControlPaths
from xau_edge.control.preflight import (
    RESET_COMMAND,
    Blocker,
    CredentialFacts,
    PreflightInputs,
    PreflightReport,
    RawTerminal,
    build_report,
    probe_terminal,
)
from xau_edge.control.process import (
    BotState,
    ProcessControlError,
    ProcessInfo,
    StartOutcome,
    StopOutcome,
)
from xau_edge.control.runtime_mode import (
    RuntimeMode,
    RuntimeModeError,
    RuntimeModeRecord,
    apply_runtime_mode,
    describe_settings_error,
    parse_runtime_mode,
    read_runtime_mode,
    write_runtime_mode,
)
from xau_edge.execution.guards import DAILY_REQUEST_BUDGET, CountingMt5, EntryGuard
from xau_edge.execution.journal import ExecutionJournal
from xau_edge.execution.reconcile import Reconciler
from xau_edge.execution.runner import JournalError, LockHeldError, acquire_lock
from xau_edge.execution.state import ExecutionState, StateError
from xau_edge.execution.status import BotStatus, read_status
from xau_edge.funded.rules import load_funded_rules
from xau_edge.market_data.profiles import BrokerProfile
from xau_edge.news.calendar import CalendarUnavailableError, load_calendar_file, news_blocked
from xau_edge.observability import log_event

_LOG = logging.getLogger(__name__)

SYMBOL = "XAUUSD"
WAIT_BANNER = "Không có edge được kiểm định: bot sẽ WAIT"
SLOW_FACTS_TTL = timedelta(minutes=5)
TERMINAL_TTL = timedelta(minutes=10)
PROBE_MIN_INTERVAL = timedelta(seconds=10)
SMOKE_HOLD_UNTIL = timedelta(minutes=5)
CONFIRM_WORDS = {"mode_demo": "DEMO", "smoke": "SMOKE", "flatten": "FLATTEN"}
_JOURNAL_FIELDS = (
    "at",
    "event",
    "source",
    "result",
    "error_code",
    "reason",
    "status",
    "mode",
    "kind",
    "ticket",
    "retcode",
    "reasons",
    "job_id",
)


class ProcessControl(Protocol):
    """The part of ``ProcessManager`` the service uses (a fake in tests)."""

    def info(self) -> ProcessInfo:
        """Current state."""
        ...

    def start(self, mode: RuntimeMode) -> StartOutcome:
        """Start in ``mode``."""
        ...

    def stop(self) -> StopOutcome:
        """Soft stop."""
        ...

    def nssm_installed(self) -> bool:
        """Service present."""
        ...

    def nssm_confirm_mode(self) -> str | None:
        """Installed ``--confirm-mode``."""
        ...


class ActionBlockedError(Exception):
    """The action is not available now; nothing was started."""

    def __init__(self, action: str, blockers: list[Blocker]) -> None:
        super().__init__(action)
        self.action = action
        self.blockers = blockers


class ConfirmationError(Exception):
    """The typed confirmation word is wrong."""

    def __init__(self, expected: str) -> None:
        super().__init__(expected)
        self.expected = expected


@dataclass(frozen=True)
class ControlConfig:
    """Where things are and how long to wait."""

    repo_root: Path
    terminal_path: str
    data_dir: Path | None = None
    env_file: Path | None = None
    profile_path: Path = Path("configs/brokers/ftmo_demo.yaml")
    registry_dir: Path = Path("experiments/runs")
    symbol: str = SYMBOL
    smoke_hold_seconds: float = 3.0
    mode_confirm_timeout: float = 240.0
    mode_confirm_poll: float = 2.0
    probe_timeout: float = 20.0

    def resolve(self, path: Path) -> Path:
        """A configured path, relative ones taken from the repository root."""
        return path if path.is_absolute() else self.repo_root / path


def _default_connect(mt5: Any, reader: DemoReader, terminal_path: str, env_file: Path) -> None:
    creds = Mt5TradeSettings(_env_file=env_file)
    connect_for_trading(mt5, reader, terminal_path, creds)
    mt5.symbol_select(reader.symbol, True)


def _load_mt5() -> Any:
    from xau_edge.market_data.mt5.source import load_mt5_module  # noqa: PLC0415 - optional

    return load_mt5_module()


@dataclass
class ControlDeps:
    """Collaborators with side effects; tests replace them with fakes."""

    load_settings: Callable[[], Settings]
    load_credentials: Callable[[], Mt5TradeSettings]
    load_mt5: Callable[[], Any] = _load_mt5
    connect_trading: Callable[[Any, DemoReader], None] | None = None
    clock_offset: Callable[[], float | None] = lambda: None
    max_clock_offset: float = 5.0
    strategy_check: Callable[[], bool | None] = lambda: None
    now: Callable[[], datetime] = lambda: datetime.now(UTC)
    sleep: Callable[[float], None] = time.sleep
    monotonic: Callable[[], float] = time.monotonic
    probe: Callable[[Callable[[], Any], str, float], RawTerminal] | None = None


@dataclass
class _SlowFacts:
    at: datetime
    clock_offset: float | None
    strategy_validated: bool | None
    news_end: datetime | None
    news_error: str | None
    funded_pending: int | None


@dataclass
class _Cache:
    slow: _SlowFacts | None = None
    terminal: RawTerminal | None = None
    terminal_at: datetime | None = None
    report: PreflightReport | None = None
    profile: BrokerProfile | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def _bot_mode_label(status: BotStatus | None, info: ProcessInfo) -> str | None:
    if status is None or info.state is not BotState.RUNNING:
        return None
    return {"dry-run": "DRY_RUN", "demo": "DEMO"}.get(status.mode, status.mode.upper())


class ControlService:
    """State and actions of the control plane."""

    def __init__(
        self,
        config: ControlConfig,
        deps: ControlDeps,
        *,
        process: ProcessControl,
        jobs: JobManager,
        limiter: RateLimiter,
        token: str,
        token_protected: bool | None,
    ) -> None:
        self.config = config
        self.deps = deps
        self.paths = ControlPaths(config.data_dir or config.repo_root / "data")
        self.process = process
        self.jobs = jobs
        self.limiter = limiter
        self.token = token
        self.token_protected = token_protected
        self._mt5 = threading.RLock()
        self._cache = _Cache()

    # -- facts ---------------------------------------------------------------------------------

    def _settings(self) -> tuple[Settings | None, str | None]:
        try:
            return self.deps.load_settings(), None
        except ValidationError as exc:
            return None, describe_settings_error(exc)
        except (ValueError, OSError):
            return None, "không đọc được cấu hình .env"

    def _credentials(self) -> CredentialFacts:
        try:
            c = self.deps.load_credentials()
        except (ValidationError, ValueError, OSError):
            return CredentialFacts(has_login=False, has_server=False, has_trade_password=False)
        return CredentialFacts(
            has_login=c.login is not None,
            has_server=bool(c.server),
            has_trade_password=bool(c.trade_password and c.trade_password.get_secret_value()),
        )

    def _runtime(self) -> tuple[RuntimeModeRecord | None, str | None]:
        try:
            return read_runtime_mode(self.paths.runtime_mode), None
        except RuntimeModeError:
            return None, "runtime_mode.json không hợp lệ (chỉ DRY_RUN hoặc DEMO)"

    def _status_json(self) -> BotStatus | None:
        try:
            return read_status(self.paths.status)
        except (ValueError, OSError):
            return None

    def _state(self, settings: Settings) -> ExecutionState:
        return ExecutionState(self.config.resolve(settings.demo_state_path))

    def _kill_switch(self, settings: Settings | None) -> tuple[bool | None, str]:
        if settings is None:
            return None, ""
        path = self.config.resolve(settings.demo_state_path)
        if not path.exists():
            return False, ""
        try:
            return ExecutionState(path).kill_switch_state()
        except (StateError, OSError):
            return None, ""

    def _bot_open_positions(self, settings: Settings) -> list[str]:
        path = self.config.resolve(settings.demo_state_path)
        if not path.exists():
            return []
        try:
            return [p.ticket for p in ExecutionState(path).open_positions()]
        except (StateError, OSError):
            return ["?"]

    def _journal(self, settings: Settings | None) -> ExecutionJournal:
        path = settings.demo_journal_path if settings else Path("data/execution/journal.jsonl")
        return ExecutionJournal(self.config.resolve(path))

    def record_web_event(self, event: str, **fields: Any) -> None:
        """Journal an action done through the web (best effort, never raises)."""
        try:
            settings = self.deps.load_settings()
        except Exception:
            settings = None
        self._record(settings, event, **fields)

    def _record(self, settings: Settings | None, event: str, **fields: Any) -> None:
        try:
            self._journal(settings).record(event, source="web", **fields)
        except JournalError:
            log_event(_LOG, "control.journal_failed", logging.ERROR, journal_event=event)
            raise

    def _profile(self) -> BrokerProfile:
        if self._cache.profile is None:
            self._cache.profile = BrokerProfile.from_yaml(
                self.config.resolve(self.config.profile_path)
            )
        return self._cache.profile

    def _slow_facts(self, settings: Settings | None, *, force: bool) -> _SlowFacts:
        now = self.deps.now()
        cached = self._cache.slow
        if cached is not None and not force and now - cached.at < SLOW_FACTS_TTL:
            return cached
        news_end: datetime | None = None
        news_error: str | None = None
        if settings is not None and settings.news_calendar_path is not None:
            try:
                cal = load_calendar_file(self.config.resolve(settings.news_calendar_path))
                news_end = cal.coverage[1]
            except (OSError, ValueError):
                news_error = "unreadable"
        pending: int | None = None
        if settings is not None:
            try:
                rules = load_funded_rules(self.config.resolve(settings.funded_profile_path))
                pending = len(rules.pending())
            except (OSError, ValueError):
                pending = None
        try:
            offset = self.deps.clock_offset()
        except Exception:
            offset = None
        try:
            validated = self.deps.strategy_check()
        except Exception:
            validated = None
        facts = _SlowFacts(now, offset, validated, news_end, news_error, pending)
        self._cache.slow = facts
        return facts

    def _files_writable(self) -> bool:
        probe = self.paths.exec_dir / ".write_probe"
        try:
            self.paths.exec_dir.mkdir(parents=True, exist_ok=True)
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except OSError:
            return False
        return True

    def _probe(self) -> RawTerminal:
        probe = self.deps.probe or (
            lambda load, path, timeout: probe_terminal(load, path, timeout_seconds=timeout)
        )
        terminal = probe(self.deps.load_mt5, self.config.terminal_path, self.config.probe_timeout)
        self._cache.terminal = terminal
        self._cache.terminal_at = self.deps.now()
        return terminal

    def _cached_terminal(self, info: ProcessInfo) -> RawTerminal | None:
        if info.state in (BotState.RUNNING, BotState.STARTING, BotState.STOPPING):
            return None
        at = self._cache.terminal_at
        if self._cache.terminal is None or at is None or self.deps.now() - at > TERMINAL_TTL:
            return RawTerminal(connected=None, error="NOT_CHECKED")
        return self._cache.terminal

    def _probe_if_free(self, info: ProcessInfo) -> RawTerminal | None:
        """Probe the terminal unless the bot or a job is using it (then use what is cached)."""
        if info.state is not BotState.STOPPED or info.held_by_api or self.jobs.active():
            return self._cached_terminal(info)
        at = self._cache.terminal_at
        if at is not None and self.deps.now() - at < PROBE_MIN_INTERVAL:
            return self._cached_terminal(info)
        if not self._mt5.acquire(blocking=False):
            return self._cached_terminal(info)
        try:
            with self._bot_lock():
                return self._probe()
        except JobRefusedError:
            return self._cached_terminal(info)
        finally:
            self._mt5.release()

    def _inputs(
        self, *, terminal: RawTerminal | None, info: ProcessInfo, force: bool
    ) -> PreflightInputs:
        settings, settings_error = self._settings()
        runtime, runtime_error = self._runtime()
        slow = self._slow_facts(settings, force=force)
        env_file = self.config.env_file or self.config.repo_root / ".env"
        return PreflightInputs(
            now=self.deps.now(),
            env_exists=env_file.exists(),
            settings=settings,
            settings_error=settings_error,
            credentials=self._credentials(),
            process=info,
            runtime=runtime,
            runtime_error=runtime_error,
            terminal=terminal,
            status=self._status_json(),
            kill_switch=self._kill_switch(settings),
            news_coverage_end=slow.news_end,
            news_error=slow.news_error,
            funded_pending=slow.funded_pending,
            clock_offset_seconds=slow.clock_offset,
            max_clock_offset_seconds=self.deps.max_clock_offset,
            strategy_validated=slow.strategy_validated,
            nssm_installed=self.process.nssm_installed(),
            nssm_confirm_mode=self.process.nssm_confirm_mode(),
            files_writable=self._files_writable(),
            token_protected=self.token_protected,
        )

    def preflight(self, *, probe: bool = True) -> PreflightReport:
        """Run every check; ``probe`` contacts the terminal (read-only) when it is free."""
        info = self.process.info()
        terminal = self._probe_if_free(info) if probe else self._cached_terminal(info)
        report = build_report(self._inputs(terminal=terminal, info=info, force=probe))
        self._cache.report = report
        return report

    def _fresh_report_locked(self) -> PreflightReport:
        """Inside a job, with the bot stopped and the lock held: probe the terminal now."""
        info = self.process.info()
        terminal = self._probe()
        report = build_report(self._inputs(terminal=terminal, info=info, force=True))
        self._cache.report = report
        return report

    # -- availability --------------------------------------------------------------------------

    def _smoke_window_blockers(self) -> list[Blocker]:
        now = self.deps.now()
        out: list[Blocker] = []
        try:
            reasons = EntryGuard(self._profile().validation.calendar)(now, now + SMOKE_HOLD_UNTIL)
        except (OSError, ValueError):
            reasons = ["PROFILE_UNREADABLE"]
        if reasons:
            msg = "vùng chặn FTMO (qua đêm Prague / nghỉ hằng ngày / cuối tuần): " + ", ".join(
                reasons
            )
            out.append(Blocker(code="FTMO_GUARD", message=msg))
        settings, _ = self._settings()
        if settings is not None and settings.news_calendar_path is not None:
            try:
                cal = load_calendar_file(self.config.resolve(settings.news_calendar_path))
                if news_blocked(cal, now, before_minutes=15, after_minutes=15):
                    out.append(Blocker(code="NEWS_WINDOW", message="đang trong cửa sổ tin tức"))
            except CalendarUnavailableError:
                out.append(
                    Blocker(code="NEWS_COVERAGE", message="lịch tin không phủ thời điểm này")
                )
            except (OSError, ValueError):
                out.append(Blocker(code="NEWS_UNREADABLE", message="không đọc được lịch tin"))
        return out

    def _start_blockers(self, report: PreflightReport, mode: RuntimeMode) -> list[Blocker]:
        out: list[Blocker] = []
        tripped, _ = self._kill_switch(self._settings()[0])
        if tripped:
            out.append(Blocker(code="KILL_SWITCH_TRIPPED", message="kill switch đang tripped"))
        if report.has_fail:
            msg = "preflight có mục fail: " + ", ".join(report.failing())
            out.append(Blocker(code="PREFLIGHT_FAIL", message=msg))
        if mode is RuntimeMode.DEMO:
            runtime, _ = self._runtime()
            if runtime is None or runtime.mode is not RuntimeMode.DEMO:
                out.append(
                    Blocker(
                        code="DEMO_NOT_CONFIRMED_FROM_WEB",
                        message="chọn DEMO ở thẻ Chế độ (gõ DEMO) trước khi chạy DEMO từ web",
                    )
                )
            out += [b for b in report.demo_blockers if b.code not in {o.code for o in out}]
        return out

    def actions(self, report: PreflightReport, info: ProcessInfo) -> dict[str, list[Blocker]]:
        """Blockers per action; an empty list means the button is enabled."""
        active = self.jobs.active()
        busy = [Blocker(code="JOB_RUNNING", message="đang có thao tác khác chạy")] if active else []
        settings, _ = self._settings()
        running = info.state in (BotState.RUNNING, BotState.STARTING)
        mode = report.configured_mode
        out: dict[str, list[Blocker]] = {}

        start = list(busy)
        if running or info.state is BotState.STOPPING or info.held_by_api:
            start.append(Blocker(code="BOT_ALREADY_RUNNING", message="bot đang chạy"))
        start += self._start_blockers(report, mode)
        out["start"] = start

        stop = list(busy)
        if info.state is BotState.STOPPED:
            stop.append(Blocker(code="BOT_NOT_RUNNING", message="bot không chạy"))
        out["stop"] = stop

        restart = list(stop)
        restart += self._start_blockers(report, mode)
        out["restart"] = restart

        demo = list(busy)
        if mode is RuntimeMode.DEMO and (running is False or _is_demo(self._status_json(), info)):
            demo.append(Blocker(code="ALREADY_DEMO", message="đang ở DEMO"))
        demo += report.demo_blockers
        out["mode_demo"] = demo

        dry = list(busy)
        if mode is RuntimeMode.DRY_RUN and not _is_demo(self._status_json(), info):
            dry.append(Blocker(code="ALREADY_DRY_RUN", message="đang ở DRY-RUN"))
        out["mode_dry_run"] = dry

        smoke = list(busy)
        if not report.smoke_enabled:
            smoke.append(
                Blocker(code="SMOKE_DISABLED_IN_ENV", message=".env chưa bật XAU_EDGE_DEMO_SMOKE")
            )
        if mode is not RuntimeMode.DEMO:
            smoke.append(Blocker(code="MODE_NOT_DEMO", message="chuyển sang DEMO trước"))
        smoke += [b for b in report.demo_blockers if b.code not in {s.code for s in smoke}]
        if settings is not None and self._bot_open_positions(settings):
            smoke.append(Blocker(code="BOT_POSITION_OPEN", message="bot đang có vị thế mở"))
        limited = self.limiter.blocked("smoke")
        if limited:
            smoke.append(Blocker(code="RATE_LIMITED", message=limited))
        smoke += self._smoke_window_blockers()
        out["smoke"] = smoke

        flatten = list(busy)
        if settings is None:
            flatten.append(Blocker(code="ENV_INVALID", message=".env chưa hợp lệ: dùng MT5 tay"))
        elif settings.enable_funded_trading:
            flatten.append(
                Blocker(
                    code="FUNDED_NOT_CONTROLLED_FROM_WEB",
                    message="FUNDED bật trong .env: web không điều khiển tài khoản funded",
                )
            )
        limited = self.limiter.blocked("flatten")
        if limited:
            flatten.append(Blocker(code="RATE_LIMITED", message=limited))
        out["flatten"] = flatten
        return out

    def status(self) -> dict[str, Any]:
        """Banner, bot card, actions and jobs in one answer (polled by the dashboard)."""
        info = self.process.info()
        report = build_report(
            self._inputs(terminal=self._cached_terminal(info), info=info, force=False)
        )
        settings, _ = self._settings()
        tripped, reason = self._kill_switch(settings)
        st = self._status_json()
        active = self.jobs.active()
        account = report.account_label or (
            self._cache.report.account_label if self._cache.report else None
        )
        return {
            "now": self.deps.now().isoformat(),
            "bot": {
                "state": info.state.value,
                "backend": info.backend,
                "pid": info.pid,
                "detail": info.detail,
                "running_mode": _bot_mode_label(st, info),
                "status_updated_at": st.updated_at.isoformat() if st else None,
                "last_cycle": st.last_cycle.model_dump(mode="json")
                if st and st.last_cycle
                else None,
            },
            "configured_mode": report.configured_mode.value,
            "mode_ceiling": report.mode_ceiling.value,
            "kill_switch": {"tripped": tripped, "reason": reason},
            "account_label": account,
            "strategy_validated": report.strategy_validated,
            "wait_banner": WAIT_BANNER if report.strategy_validated is not True else None,
            "preflight": {
                "generated_at": report.generated_at.isoformat(),
                "has_fail": report.has_fail,
                "counts": report.counts,
                "last_probe_at": (
                    self._cache.terminal_at.isoformat() if self._cache.terminal_at else None
                ),
            },
            "actions": {
                name: {
                    "allowed": not blockers,
                    "blockers": [b.model_dump() for b in blockers],
                }
                for name, blockers in self.actions(report, info).items()
            },
            "active_job": active.to_dict() if active else None,
            "recent_jobs": [j.to_dict() for j in self.jobs.recent(5)],
            "reset_command": RESET_COMMAND,
            "smoke_limits": "tối đa 1 lần / 10 phút và 5 lần / ngày",
        }

    def journal_tail(self, limit: int = 40) -> list[dict[str, Any]]:
        """The latest journal events, reduced to non-identifying fields."""
        settings, _ = self._settings()
        try:
            rows = self._journal(settings).read(limit)
        except JournalError:
            return []
        return [{k: r[k] for k in _JOURNAL_FIELDS if k in r} for r in reversed(rows)]

    # -- helpers for jobs ----------------------------------------------------------------------

    @contextmanager
    def _bot_lock(self) -> Iterator[None]:
        """Hold the bot's lock (so no bot can start) for the duration."""
        try:
            acquire_lock(self.paths.lock)
        except LockHeldError as exc:
            raise JobRefusedError("LOCK_HELD", "một bot/tiến trình khác đang giữ lock") from exc
        try:
            yield
        finally:
            self.paths.lock.unlink(missing_ok=True)

    def _require_settings(self) -> Settings:
        settings, err = self._settings()
        if settings is None:
            raise JobRefusedError("ENV_INVALID", err or ".env chưa hợp lệ")
        return settings

    def _stop_bot(self, ctx: JobContext) -> StopOutcome:
        ctx.step("Dừng bot mềm (sau chu kỳ hiện tại)")
        try:
            outcome = self.process.stop()
        except ProcessControlError as exc:
            raise JobFailedError(exc.code, exc.message) from exc
        ctx.step(outcome.detail)
        return outcome

    def _start_bot(self, ctx: JobContext, mode: RuntimeMode) -> StartOutcome:
        ctx.step(f"Khởi động bot ở {mode.value}")
        try:
            outcome = self.process.start(mode)
        except ProcessControlError as exc:
            raise JobFailedError(exc.code, exc.message) from exc
        ctx.step("bot đã chạy" + ("; đã có chu kỳ đầu" if outcome.first_cycle_seen else ""))
        return outcome

    def _refuse(self, settings: Settings | None, event: str, blockers: list[Blocker]) -> None:
        self._record(settings, event, result="REFUSED", error_code=blockers[0].code)
        raise JobRefusedError(blockers[0].code, "; ".join(b.message for b in blockers))

    def _restart_after(self, ctx: JobContext, was_running: bool, mode: RuntimeMode) -> str:
        if not was_running:
            return "bot không chạy trước đó: không khởi động lại"
        report = self.preflight(probe=False)
        blockers = self._start_blockers(report, mode)
        if blockers:
            ctx.step("Không khởi động lại bot: " + "; ".join(b.message for b in blockers))
            return "không khởi động lại: " + blockers[0].code
        try:
            self._start_bot(ctx, mode)
        except JobFailedError as exc:
            return "khởi động lại thất bại: " + exc.code
        return "đã khởi động lại bot"

    def _was_running(self) -> bool:
        return self.process.info().state in (BotState.RUNNING, BotState.STARTING)

    def _precheck(self, action: str) -> None:
        info = self.process.info()
        report = self.preflight(probe=False)
        blockers = self.actions(report, info)[action]
        if blockers:
            raise ActionBlockedError(action, blockers)

    # -- F2: lifecycle -------------------------------------------------------------------------

    def start(self, key: str) -> tuple[Job, bool]:
        """Start the bot in the configured mode."""
        if (replay := self._replay(key, "bot.start")) is not None:
            return replay
        self._precheck("start")
        return self.jobs.submit("bot.start", key, self._do_start)

    def _do_start(self, ctx: JobContext) -> dict[str, Any]:
        settings = self._require_settings()
        ctx.step("Preflight mới (terminal chỉ đọc)")
        with self._mt5, self._bot_lock():
            report = self._fresh_report_locked()
        mode = report.configured_mode
        blockers = self._start_blockers(report, mode)
        if mode is RuntimeMode.DEMO and report.demo_unverified:
            blockers.append(
                Blocker(code="TERMINAL_UNVERIFIED", message="chưa xác minh được terminal")
            )
        if blockers:
            self._refuse(settings, "control.bot.start", blockers)
        outcome = self._start_bot(ctx, mode)
        self._record(settings, "control.bot.start", result="OK", mode=mode.value)
        return {"mode": mode.value, "state": outcome.info.state.value, "pid": outcome.info.pid}

    def stop(self, key: str) -> tuple[Job, bool]:
        """Soft stop."""
        if (replay := self._replay(key, "bot.stop")) is not None:
            return replay
        self._precheck("stop")
        return self.jobs.submit("bot.stop", key, self._do_stop)

    def _do_stop(self, ctx: JobContext) -> dict[str, Any]:
        settings, _ = self._settings()
        outcome = self._stop_bot(ctx)
        self._record(settings, "control.bot.stop", result="OK")
        return {
            "was_running": outcome.was_running,
            "graceful": outcome.graceful,
            "waited_seconds": outcome.waited_seconds,
            "last_cycle": outcome.last_cycle,
        }

    def restart(self, key: str) -> tuple[Job, bool]:
        """Stop, then start again in the configured mode."""
        if (replay := self._replay(key, "bot.restart")) is not None:
            return replay
        self._precheck("restart")
        return self.jobs.submit("bot.restart", key, self._do_restart)

    def _do_restart(self, ctx: JobContext) -> dict[str, Any]:
        stopped = self._do_stop(ctx)
        started = self._do_start(ctx)
        return {"stop": stopped, "start": started}

    # -- F3: mode ------------------------------------------------------------------------------

    def set_mode(self, mode_value: str, confirm: str, key: str) -> tuple[Job, bool]:
        """Switch between DRY_RUN and DEMO (DEMO needs the typed word ``DEMO``)."""
        mode = parse_runtime_mode(mode_value)
        kind = f"mode.{mode.value}"
        if (replay := self._replay(key, kind)) is not None:
            return replay
        if mode is RuntimeMode.DEMO and confirm != CONFIRM_WORDS["mode_demo"]:
            raise ConfirmationError(CONFIRM_WORDS["mode_demo"])
        self._precheck("mode_demo" if mode is RuntimeMode.DEMO else "mode_dry_run")
        return self.jobs.submit(kind, key, lambda ctx: self._do_mode(ctx, mode))

    def _do_mode(self, ctx: JobContext, mode: RuntimeMode) -> dict[str, Any]:
        settings = self._require_settings()
        before, _ = self._runtime()
        previous = (
            apply_runtime_mode(settings, before)[0].demo_dry_run is False
            and settings.enable_demo_trading
        )
        prev_mode = RuntimeMode.DEMO if previous else RuntimeMode.DRY_RUN
        was_running = self._was_running()
        if was_running:
            self._stop_bot(ctx)
        if mode is RuntimeMode.DEMO:
            ctx.step("Preflight mới với terminal (chỉ đọc)")
            with self._mt5, self._bot_lock():
                report = self._fresh_report_locked()
            blockers = list(report.demo_blockers)
            if report.demo_unverified:
                blockers.append(
                    Blocker(code="TERMINAL_UNVERIFIED", message="chưa xác minh được terminal")
                )
            if blockers:
                note = self._restart_after(ctx, was_running, prev_mode)
                ctx.step(note)
                self._refuse(settings, "control.mode", blockers)
        ctx.step(f"Ghi runtime_mode.json = {mode.value}")
        write_runtime_mode(self.paths.runtime_mode, mode, self.deps.now(), source="web")
        self._record(settings, "control.mode", result="WRITTEN", mode=mode.value)
        if mode is RuntimeMode.DRY_RUN and not was_running:
            return {"mode": mode.value, "bot": "không chạy (chưa khởi động)"}
        report = self.preflight(probe=False)
        blockers = self._start_blockers(report, mode)
        if blockers:
            self._refuse(settings, "control.mode", blockers)
        started_at = self.deps.now()
        self._start_bot(ctx, mode)
        ctx.step("Chờ status.json xác nhận chế độ")
        self._await_mode(mode, started_at)
        self._record(settings, "control.mode", result="CONFIRMED", mode=mode.value)
        return {"mode": mode.value, "bot": "đang chạy, status.json đã xác nhận chế độ"}

    def _await_mode(self, mode: RuntimeMode, since: datetime) -> None:
        want = "demo" if mode is RuntimeMode.DEMO else "dry-run"
        deadline = self.deps.monotonic() + self.config.mode_confirm_timeout
        while self.deps.monotonic() < deadline:
            st = self._status_json()
            if st is not None and st.updated_at >= since and st.mode == want:
                return
            if st is not None and st.updated_at >= since and st.mode != want:
                msg = f"bot chạy ở '{st.mode}', không phải {mode.value}"
                raise JobFailedError("MODE_MISMATCH", msg)
            self.deps.sleep(self.config.mode_confirm_poll)
        raise JobFailedError("MODE_NOT_CONFIRMED", "status.json chưa xác nhận chế độ mới")

    # -- F4: smoke -----------------------------------------------------------------------------

    def smoke(self, confirm: str, key: str) -> tuple[Job, bool]:
        """One labelled 0.01-lot DEMO order, opened and closed (pipeline test only)."""
        if (replay := self._replay(key, "smoke")) is not None:
            return replay
        if confirm != CONFIRM_WORDS["smoke"]:
            raise ConfirmationError(CONFIRM_WORDS["smoke"])
        self._precheck("smoke")
        return self.jobs.submit("smoke", key, self._do_smoke)

    def _executor_config(self, settings: Settings, *, smoke: bool) -> ExecutorConfig:
        def csv(value: str) -> tuple[str, ...]:
            return tuple(v.strip() for v in value.split(",") if v.strip())

        return ExecutorConfig(
            enabled=settings.enable_demo_trading,
            dry_run=settings.demo_dry_run,
            allowed_accounts=csv(settings.demo_allowed_accounts),
            symbols=csv(settings.demo_allowed_symbols),
            magic=settings.demo_magic,
            max_lots=settings.demo_max_lots,
            deviation_points=settings.demo_deviation_points,
            smoke=smoke and settings.demo_smoke,
        )

    @contextmanager
    def _trading_kit(self, settings: Settings, config: ExecutorConfig) -> Iterator[TradingKit]:
        if settings.demo_magic is None:
            raise JobRefusedError("ENV_NO_MAGIC", "thiếu XAU_EDGE_DEMO_MAGIC")
        raw = self.deps.load_mt5()
        state = self._state(settings)
        client = CountingMt5(
            raw, state, budgeted=TRADE_SERVER_REQUESTS, budget=DAILY_REQUEST_BUDGET
        )
        reader = DemoReader(client, self._profile().clock, self.config.symbol)
        connect = self.deps.connect_trading or (
            lambda mt5, rd: _default_connect(
                mt5,
                rd,
                self.config.terminal_path,
                self.config.env_file or self.config.repo_root / ".env",
            )
        )
        try:
            connect(client, reader)
        except TradeConnectError as exc:
            raise JobFailedError(
                "TRADE_CONNECT_FAILED", "không kết nối được terminal bằng mật khẩu giao dịch"
            ) from exc
        try:
            reconciler = Reconciler(
                state,
                magic=settings.demo_magic,
                symbols=(self.config.symbol,),
                allowed_accounts=config.allowed_accounts,
                trip_on_mismatch=True,
            )
            executor = Mt5DemoExecutor(
                client, reader, state, self._journal(settings), reconciler, config
            )
            yield TradingKit(
                client, reader, state, reconciler, executor, self.config.symbol, settings.demo_magic
            )
        finally:
            with suppress(Exception):
                raw.shutdown()

    def _do_smoke(self, ctx: JobContext) -> dict[str, Any]:
        base = self._require_settings()
        runtime, _ = self._runtime()
        settings, _ = apply_runtime_mode(base, runtime)
        was_running = self._was_running()
        mode = RuntimeMode.DEMO
        if was_running:
            self._stop_bot(ctx)
        result: dict[str, Any] = {}
        try:
            with self._mt5, self._bot_lock():
                ctx.step("Preflight mới với terminal (chỉ đọc)")
                report = self._fresh_report_locked()
                blockers = list(report.demo_blockers)
                if report.configured_mode is not RuntimeMode.DEMO:
                    blockers.append(Blocker(code="MODE_NOT_DEMO", message="chưa ở DEMO"))
                if not report.smoke_enabled:
                    blockers.append(
                        Blocker(code="SMOKE_DISABLED_IN_ENV", message="smoke chưa bật trong .env")
                    )
                if self._bot_open_positions(settings):
                    blockers.append(
                        Blocker(code="BOT_POSITION_OPEN", message="bot đang có vị thế mở")
                    )
                limited = self.limiter.blocked("smoke")
                if limited:
                    blockers.append(Blocker(code="RATE_LIMITED", message=limited))
                blockers += self._smoke_window_blockers()
                if blockers:
                    self._refuse(settings, "control.smoke", blockers)
                ctx.step("Kết nối bằng mật khẩu giao dịch")
                with self._trading_kit(
                    settings, self._executor_config(settings, smoke=True)
                ) as kit:
                    if bot_positions_on_broker(kit):
                        self._refuse(
                            settings,
                            "control.smoke",
                            [Blocker(code="BOT_POSITION_OPEN", message="broker có vị thế của bot")],
                        )
                    self.limiter.record("smoke")
                    self._record(settings, "control.smoke", result="REQUESTED")
                    ctx.step("Gửi 1 lệnh BUY 0.01 lot (comment SMOKE), giữ vài giây rồi đóng")
                    result = run_smoke(
                        kit,
                        now=self.deps.now,
                        hold_seconds=self.config.smoke_hold_seconds,
                        sleep=self.deps.sleep,
                        monotonic=self.deps.monotonic,
                    )
                self._record(
                    settings,
                    "control.smoke",
                    result=result.get("status"),
                    retcode=result.get("retcode"),
                    reasons=result.get("reasons"),
                )
        finally:
            restart = self._restart_after(ctx, was_running, mode)
        result["restart"] = restart
        return result

    # -- F5: flatten ---------------------------------------------------------------------------

    def flatten(self, confirm: str, key: str) -> tuple[Job, bool]:
        """Kill switch first, stop the bot, close every bot position (never manual ones)."""
        if (replay := self._replay(key, "flatten")) is not None:
            return replay
        if confirm != CONFIRM_WORDS["flatten"]:
            raise ConfirmationError(CONFIRM_WORDS["flatten"])
        self._precheck("flatten")
        self.limiter.record("flatten")
        return self.jobs.submit("flatten", key, self._do_flatten)

    def _do_flatten(self, ctx: JobContext) -> dict[str, Any]:
        settings = self._require_settings()
        if settings.enable_funded_trading:
            self._refuse(
                settings,
                "control.flatten",
                [Blocker(code="FUNDED_NOT_CONTROLLED_FROM_WEB", message="FUNDED bật trong .env")],
            )
        ctx.step("Bật kill switch (WEB_FLATTEN) TRƯỚC khi làm gì khác")
        self._state(settings).trip_kill_switch(FLATTEN_REASON)
        self._record(settings, "control.flatten", result="KILL_SWITCH_TRIPPED")
        if self.process.info().state is not BotState.STOPPED:
            self._stop_bot(ctx)
        result: dict[str, Any] = {
            "kill_switch": "TRIPPED",
            "reset_command": RESET_COMMAND,
            "restart": "không tự khởi động lại (kill switch tripped)",
        }
        tickets = self._bot_open_positions(settings)
        if not tickets:
            ctx.step("Bot không có vị thế mở theo state: không cần kết nối MT5")
            result.update(positions=[], still_open_tickets=[], reconcile_clean=None)
            self._record(settings, "control.flatten", result="NOTHING_TO_CLOSE")
            return result
        ctx.step(f"Đóng {len(tickets)} vị thế của bot (đúng magic), không đụng lệnh tay")
        config = ExecutorConfig(
            enabled=True,
            dry_run=False,
            allowed_accounts=self._executor_config(settings, smoke=False).allowed_accounts,
            symbols=self._executor_config(settings, smoke=False).symbols,
            magic=settings.demo_magic,
            max_lots=settings.demo_max_lots,
            deviation_points=settings.demo_deviation_points,
        )
        try:
            with self._mt5, self._bot_lock(), self._trading_kit(settings, config) as kit:
                result.update(run_flatten(kit, now=self.deps.now))
        except (JobFailedError, JobRefusedError) as exc:
            result.update(
                error_code=exc.code,
                still_open_tickets=tickets,
                manual_hint=MANUAL_CLOSE_HINT,
            )
            self._record(settings, "control.flatten", result="FAILED", error_code=exc.code)
            raise JobFailedError(
                exc.code, f"{exc.message}; đóng tay các ticket {', '.join(tickets)} trong MT5"
            ) from exc
        for row in result["positions"]:
            self._record(
                settings,
                "control.flatten",
                result=row["status"],
                ticket=row["ticket"],
                retcode=row["retcode"],
            )
        return result

    # -- idempotency ---------------------------------------------------------------------------

    def _replay(self, key: str, kind: str) -> tuple[Job, bool] | None:
        """A known idempotency key returns its job without re-checking anything."""
        for job in self.jobs.recent(50):
            if job.idempotency_key == key:
                if job.kind != kind:
                    raise IdempotencyConflictError(key)
                return job, True
        return None


def _is_demo(status: BotStatus | None, info: ProcessInfo) -> bool:
    return _bot_mode_label(status, info) == "DEMO"
