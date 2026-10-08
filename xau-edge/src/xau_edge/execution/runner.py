"""One dry-run decision cycle on real (or replayed) bars: data check -> signal -> bridge -> journal.

The runner is broker-neutral and only produces ``OrderIntent`` objects through ``SignalBridge``. It
never submits anything. Each cycle appends exactly one JSON line to an append-only journal that
records WHY the system acted or refused, so a day of WAIT is auditable. If the journal cannot be
written the cycle raises instead of continuing unrecorded.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from xau_edge.domain.timeframe import Timeframe
from xau_edge.execution.bridge import SignalBridge
from xau_edge.execution.order_intent import OrderIntent
from xau_edge.execution.reconcile import ReconcileResult
from xau_edge.observability import log_event
from xau_edge.risk.engine import AccountState
from xau_edge.signals.engine import MarketFrames
from xau_edge.signals.schema import Signal

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class SubmitOutcome:
    """What an executor answered for an intent (status and ticket only)."""

    status: str
    ticket: str | None = None


class JournalError(RuntimeError):
    """The cycle journal could not be read or written; the cycle must not continue unrecorded."""


@dataclass(frozen=True)
class CycleReport:
    """What one cycle did."""

    recorded_at: str
    decision_time: str | None
    direction: str
    signal_hash: str
    accepted: bool
    reasons: tuple[str, ...]
    intent_id: str | None
    dry_run: bool
    data_age_minutes: float | None
    skipped: bool = False
    order_status: str | None = None
    ticket: str | None = None


class CycleJournal:
    """Append-only JSON-lines record of cycles (no secrets: only decisions and hashes)."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            msg = f"cannot create the journal directory: {exc}"
            raise JournalError(msg) from exc

    def append(self, report: CycleReport) -> None:
        """Write one line; raises ``JournalError`` on failure."""
        try:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(asdict(report), sort_keys=True) + "\n")
        except OSError as exc:
            msg = f"cannot write the journal: {exc}"
            raise JournalError(msg) from exc

    def last_decision_time(self) -> datetime | None:
        """Decision time of the latest non-skipped line, so a restart does not repeat a bar."""
        if not self.path.exists():
            return None
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            msg = f"cannot read the journal: {exc}"
            raise JournalError(msg) from exc
        for line in reversed(lines):
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                msg = "the journal contains a line that is not valid JSON"
                raise JournalError(msg) from exc
            if row.get("decision_time") and not row.get("skipped"):
                return datetime.fromisoformat(row["decision_time"])
        return None


class DryRunCycle:
    """Runs one decision per closed M15 bar through the bridge, never beyond an intent."""

    def __init__(
        self,
        bridge: SignalBridge,
        signal_fn: Callable[[datetime], Signal],
        journal: CycleJournal,
        *,
        max_data_age: timedelta = timedelta(minutes=30),
        submit: Callable[[OrderIntent, datetime], SubmitOutcome] | None = None,
        strategy_id: str | None = None,
    ) -> None:
        self.bridge = bridge
        self.signal_fn = signal_fn
        self.journal = journal
        self.max_data_age = max_data_age
        self.submit = submit
        self.strategy_id = strategy_id
        """The strategy whose signals ``signal_fn`` produces (the bridge's override checks it)."""

    def run(
        self,
        frames: MarketFrames,
        now: datetime,
        account: AccountState,
        *,
        force: bool = False,
        reconcile: ReconcileResult | None = None,
    ) -> CycleReport:
        """Process the latest closed M15 bar once; returns (and journals) the report."""
        if reconcile is not None and not reconcile.clean:
            reasons = tuple(f"RECONCILE_{code}" for code in reconcile.codes)
            return self._record(self._skip(now, reasons[0], None, None, extra=reasons[1:]))
        latest = frames.m15["timestamp"].max()
        if not isinstance(latest, datetime) or frames.m5.height == 0:
            return self._record(self._skip(now, "DATA_EMPTY", None, None))
        at = latest.astimezone(UTC) + Timeframe.M15.delta
        age = now - at
        if age < timedelta(0):
            return self._record(self._skip(now, "DATA_IN_FUTURE", at, None))
        age_minutes = age.total_seconds() / 60.0
        if age > self.max_data_age:
            return self._record(self._skip(now, "DATA_STALE", at, age_minutes, skipped=False))
        previous = self.journal.last_decision_time()
        if not force and previous is not None and at <= previous:
            return self._skip(now, "BAR_ALREADY_PROCESSED", at, age_minutes)  # not journalled
        signal = self.signal_fn(at)
        spread = float(frames.m5["spread"][-1])
        result = self.bridge.process(
            signal, now, account=account, spread_points=spread, strategy_id=self.strategy_id
        )
        outcome: SubmitOutcome | None = None
        if result.intent is not None and not result.intent.dry_run and self.submit is not None:
            outcome = self.submit(result.intent, now)
        report = CycleReport(
            recorded_at=now.isoformat(),
            decision_time=at.isoformat(),
            direction=signal.direction.value,
            signal_hash=signal.inputs_hash,
            accepted=result.accepted,
            reasons=result.reasons,
            intent_id=result.intent.intent_id if result.intent else None,
            dry_run=self.bridge.dry_run,
            data_age_minutes=age_minutes,
            order_status=outcome.status if outcome else None,
            ticket=outcome.ticket if outcome else None,
        )
        return self._record(report)

    def _skip(
        self,
        now: datetime,
        reason: str,
        at: datetime | None,
        age_minutes: float | None,
        *,
        skipped: bool = True,
        extra: tuple[str, ...] = (),
    ) -> CycleReport:
        return CycleReport(
            recorded_at=now.isoformat(),
            decision_time=at.isoformat() if at else None,
            direction="WAIT",
            signal_hash="",
            accepted=False,
            reasons=(reason, *extra),
            intent_id=None,
            dry_run=self.bridge.dry_run,
            data_age_minutes=age_minutes,
            skipped=skipped,
        )

    def _record(self, report: CycleReport) -> CycleReport:
        self.journal.append(report)
        log_event(
            _LOG,
            "cycle.done",
            decision_time=report.decision_time,
            direction=report.direction,
            accepted=report.accepted,
            reasons=list(report.reasons),
        )
        return report


class LockHeldError(RuntimeError):
    """Another instance holds the lock file."""


def pid_alive(pid: int) -> bool:  # noqa: PLR0911 - one answer per platform and error
    """True if a process with this id is running (never signals it: could kill it on Windows)."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes  # noqa: PLC0415 - Windows only

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined,unused-ignore]
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True  # cannot tell: assume alive (fail closed)
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _lock_owner(path: Path) -> int | None:
    """The pid written in a lock file (new JSON format or the old bare number), if readable."""
    try:
        text = path.read_text(encoding="utf-8").strip()
        return int(json.loads(text)["pid"]) if text.startswith("{") else int(text)
    except (OSError, ValueError, KeyError, TypeError):
        return None


def acquire_lock(path: Path) -> None:
    """Refuse to run twice; a lock whose owner process is gone is taken over automatically.

    The lock records the pid and the start time. If the file cannot be read or the pid cannot be
    shown to be dead, the lock is treated as held (fail closed: never run two bots).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            owner = _lock_owner(path)
            if owner is not None and not pid_alive(owner):
                log_event(_LOG, "lock.stale_released", logging.WARNING, pid=owner)
                path.unlink(missing_ok=True)
                continue
            msg = (
                f"another instance holds {path} (pid {owner}); delete it only if it is not running"
            )
            raise LockHeldError(msg) from None
        with os.fdopen(fd, "w") as handle:
            handle.write(
                json.dumps({"pid": os.getpid(), "started_at": datetime.now(UTC).isoformat()})
            )
        return
    msg = f"could not take the lock {path}"
    raise LockHeldError(msg)


def next_close(now: datetime) -> datetime:
    """The next M15 boundary strictly after ``now``."""
    step = Timeframe.M15.delta
    base = now.replace(minute=0, second=0, microsecond=0)
    return base + step * ((now - base) // step + 1)


def write_heartbeat(path: Path, now: datetime, status: str) -> None:
    """Small file an external watcher can check for freshness."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"at": now.isoformat(), "status": status}), encoding="utf-8")
