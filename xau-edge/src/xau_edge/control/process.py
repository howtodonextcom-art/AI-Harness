"""Start, stop and inspect the bot process for the web control plane (ADR-0023).

Two backends, chosen automatically:

* NSSM: when the bot service is installed, the manager only runs ``nssm start|stop <service>``
  with fixed arguments (never a shell). The service's own command line, including any
  ``--confirm-mode``, is whatever the owner installed with ``scripts/install_services.ps1``.
* subprocess: otherwise ``scripts/demo_trader.py`` is started as a detached child of the API, with
  ``--confirm-mode DEMO`` only when the chosen runtime mode is DEMO; its pid goes to a file.

Whatever the backend, the bot's lock file (``demo_trader.lock``) is the single source of truth for
"a bot is running": a start is refused while a live process holds it, so two bots never run.
A stop is soft: a stop request is written, the bot ends after the current cycle, and only after
``stop_timeout`` seconds is the process terminated.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Protocol

from xau_edge.control.paths import ControlPaths
from xau_edge.control.runtime_mode import RuntimeMode
from xau_edge.control.sentinel import clear_stop, request_stop
from xau_edge.execution.runner import pid_alive
from xau_edge.observability import log_event

_LOG = logging.getLogger(__name__)

Backend = Literal["nssm", "subprocess"]

EXIT_MEANING = {
    0: "đã dừng bình thường",
    2: "không khởi tạo được terminal MT5",
    3: "bot từ chối khởi động (tài khoản, whitelist, cấu hình hoặc xác nhận chế độ)",
    4: "một bot khác đang giữ lock",
    5: "lỗi terminal tạm thời",
    6: "lỗi nghiêm trọng (state, journal hoặc loại tài khoản)",
    7: "lỗi không xác định lặp lại",
}


class BotState(StrEnum):
    """What the dashboard shows."""

    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    ERROR = "ERROR"


class ProcessControlError(RuntimeError):
    """A lifecycle action could not be carried out; ``code`` is a stable machine-readable id."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class CommandResult:
    """Outcome of an external command."""

    returncode: int
    stdout: str


Runner = Callable[[Sequence[str], float], CommandResult]


class Spawned(Protocol):
    """The part of ``subprocess.Popen`` the manager uses."""

    @property
    def pid(self) -> int:
        """Process id."""
        ...

    def poll(self) -> int | None:
        """Exit code, or ``None`` while running."""
        ...


Spawner = Callable[[Sequence[str], Path, Path], Spawned]


def _decode(raw: bytes) -> str:
    """NSSM may print UTF-16; anything else is read as UTF-8."""
    if b"\x00" in raw:
        return raw.decode("utf-16-le", errors="replace").replace("\x00", "")
    return raw.decode("utf-8", errors="replace")


def run_command(args: Sequence[str], timeout: float) -> CommandResult:
    """Run a fixed command line without a shell; failures become a non-zero code."""
    try:
        done = subprocess.run(  # noqa: S603 - fixed argument list, no shell
            list(args), capture_output=True, timeout=timeout, check=False, shell=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        log_event(_LOG, "control.command_failed", logging.WARNING, error=type(exc).__name__)
        return CommandResult(-1, "")
    return CommandResult(done.returncode, _decode(done.stdout or b""))


def spawn_detached(args: Sequence[str], cwd: Path, log_path: Path) -> Spawned:
    """Start the bot detached from the API's console, output appended to ``log_path``."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    kwargs: dict[str, Any] = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS  # type: ignore[attr-defined,unused-ignore]
        )
    else:
        kwargs["start_new_session"] = True
    with log_path.open("ab") as log:
        return subprocess.Popen(  # noqa: S603 - fixed argument list, no shell
            list(args),
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            shell=False,
            **kwargs,
        )


def terminate_pid(pid: int) -> None:
    """Hard stop (TerminateProcess on Windows); used only after the soft stop timed out."""
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as exc:
        log_event(_LOG, "control.terminate_failed", logging.WARNING, error=type(exc).__name__)


def read_lock_owner(path: Path) -> int | None:
    """The pid written in the bot's lock file, if readable."""
    try:
        text = path.read_text(encoding="utf-8").strip()
        return int(json.loads(text)["pid"]) if text.startswith("{") else int(text)
    except (OSError, ValueError, KeyError, TypeError):
        return None


def last_cycle(path: Path) -> dict[str, Any] | None:
    """The last line of the cycle journal, reduced to non-identifying fields."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            return {
                k: row.get(k)
                for k in ("recorded_at", "decision_time", "direction", "reasons", "skipped")
            }
    return None


@dataclass(frozen=True)
class ProcessInfo:
    """The bot process as the control plane sees it."""

    state: BotState
    backend: Backend
    pid: int | None
    detail: str
    held_by_api: bool = False


@dataclass(frozen=True)
class StopOutcome:
    """What a stop did."""

    was_running: bool
    graceful: bool
    waited_seconds: float
    last_cycle: dict[str, Any] | None
    detail: str


@dataclass(frozen=True)
class StartOutcome:
    """What a start did."""

    info: ProcessInfo
    first_cycle_seen: bool


class ProcessManager:
    """Lifecycle of the single bot process."""

    def __init__(
        self,
        paths: ControlPaths,
        *,
        repo_root: Path,
        python: str = sys.executable,
        script: Path | None = None,
        terminal_path: str | None = None,
        nssm: str | None = None,
        service: str = "xau-edge-bot",
        runner: Runner = run_command,
        spawner: Spawner = spawn_detached,
        is_alive: Callable[[int], bool] = pid_alive,
        terminate: Callable[[int], None] = terminate_pid,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        start_timeout: float = 90.0,
        stop_timeout: float = 60.0,
        poll_seconds: float = 0.5,
    ) -> None:
        self.paths = paths
        self.repo_root = repo_root
        self.python = python
        self.script = script or repo_root / "scripts" / "demo_trader.py"
        self.terminal_path = terminal_path
        self.nssm = nssm
        self.service = service
        self._run = runner
        self._spawn = spawner
        self._alive = is_alive
        self._terminate = terminate
        self._now = now
        self._monotonic = monotonic
        self._sleep = sleep
        self.start_timeout = start_timeout
        self.stop_timeout = stop_timeout
        self.poll_seconds = poll_seconds
        self._transition: BotState | None = None
        self._child: Spawned | None = None
        self._last_error: str | None = None
        self._lock = threading.Lock()

    # -- inspection ----------------------------------------------------------------------------

    def nssm_installed(self) -> bool:
        """True when the bot service exists (``nssm status`` answers)."""
        if not self.nssm:
            return False
        return self._run([self.nssm, "status", self.service], 15.0).returncode == 0

    def backend(self) -> Backend:
        """NSSM when the service is installed, else a subprocess of the API."""
        return "nssm" if self.nssm_installed() else "subprocess"

    def nssm_confirm_mode(self) -> str | None:
        """The ``--confirm-mode`` the service was installed with (``None`` = dry-run only)."""
        if not self.nssm:
            return None
        result = self._run([self.nssm, "get", self.service, "AppParameters"], 15.0)
        if result.returncode != 0:
            return None
        words = result.stdout.split()
        for i, word in enumerate(words[:-1]):
            if word == "--confirm-mode":
                return words[i + 1].strip().upper()
        return None

    def _nssm_status(self) -> str:
        if not self.nssm:
            return ""
        return self._run([self.nssm, "status", self.service], 15.0).stdout.strip()

    def running_pid(self) -> int | None:
        """The pid of a live process holding the bot lock (the API itself excluded)."""
        owner = read_lock_owner(self.paths.lock)
        if owner is None or owner == os.getpid():
            return None
        return owner if self._alive(owner) else None

    def api_holds_lock(self) -> bool:
        """True while this API process holds the bot lock (smoke or flatten in progress)."""
        return read_lock_owner(self.paths.lock) == os.getpid()

    def info(self) -> ProcessInfo:  # noqa: PLR0911 - one answer per observed state
        """Current state; never raises."""
        backend = self.backend()
        pid = self.running_pid()
        if self._transition is not None:
            return ProcessInfo(self._transition, backend, pid, "thao tác đang chạy")
        if self.api_holds_lock():
            return ProcessInfo(
                BotState.STOPPED, backend, None, "API đang giữ lock (smoke/flatten)", True
            )
        if pid is not None:
            return ProcessInfo(BotState.RUNNING, backend, pid, "bot đang giữ lock")
        if backend == "nssm":
            status = self._nssm_status()
            if "SERVICE_START_PENDING" in status or "SERVICE_RUNNING" in status:
                return ProcessInfo(BotState.STARTING, backend, None, "dịch vụ đang khởi động")
            if "SERVICE_STOP_PENDING" in status:
                return ProcessInfo(BotState.STOPPING, backend, None, "dịch vụ đang dừng")
            if "SERVICE_PAUSED" in status:
                return ProcessInfo(BotState.ERROR, backend, None, "dịch vụ đang tạm dừng")
        if self._last_error:
            return ProcessInfo(BotState.ERROR, backend, None, self._last_error)
        return ProcessInfo(BotState.STOPPED, backend, None, "bot không chạy")

    # -- actions -------------------------------------------------------------------------------

    def start(self, mode: RuntimeMode) -> StartOutcome:
        """Start the bot in ``mode`` (the runtime file must already say so)."""
        with self._lock:
            if self.running_pid() is not None or self.api_holds_lock():
                raise ProcessControlError("BOT_ALREADY_RUNNING", "bot đang chạy hoặc lock bị giữ")
            backend = self.backend()
            if backend == "nssm" and "SERVICE_RUNNING" in self._nssm_status():
                raise ProcessControlError("BOT_ALREADY_RUNNING", "dịch vụ bot đang chạy")
            self._transition = BotState.STARTING
            self._last_error = None
            started = self._now()
            try:
                clear_stop(self.paths.stop_sentinel)
                if backend == "nssm":
                    self._start_nssm(mode)
                else:
                    self._start_child(mode, started)
                seen = self._await_start(started)
            except ProcessControlError as exc:
                self._last_error = exc.message
                raise
            finally:
                self._transition = None
            return StartOutcome(self.info(), seen)

    def _start_nssm(self, mode: RuntimeMode) -> None:
        if mode is RuntimeMode.DEMO and self.nssm_confirm_mode() != RuntimeMode.DEMO.value:
            msg = (
                "dịch vụ NSSM chưa được cài với -ConfirmMode DEMO; cài lại bằng "
                "scripts/install_services.ps1 -ConfirmMode DEMO"
            )
            raise ProcessControlError("NSSM_NOT_DEMO_CONFIRMED", msg)
        result = self._run([self.nssm or "nssm", "start", self.service], 60.0)
        if result.returncode != 0:
            raise ProcessControlError("START_FAILED", "nssm start thất bại")

    def _start_child(self, mode: RuntimeMode, started: datetime) -> None:
        args = [self.python, str(self.script)]
        if self.terminal_path:
            args += ["--terminal-path", self.terminal_path]
        if mode is RuntimeMode.DEMO:
            args += ["--confirm-mode", RuntimeMode.DEMO.value]
        try:
            child = self._spawn(args, self.repo_root, self.paths.bot_log)
        except OSError as exc:
            raise ProcessControlError(
                "START_FAILED", "không khởi chạy được tiến trình bot"
            ) from exc
        self._child = child
        self.paths.exec_dir.mkdir(parents=True, exist_ok=True)
        self.paths.process.write_text(
            json.dumps({"pid": child.pid, "started_at": started.isoformat(), "mode": mode.value}),
            encoding="utf-8",
        )

    def _child_exit(self) -> int | None:
        return self._child.poll() if self._child is not None else None

    def _heartbeat_since(self, started: datetime) -> bool:
        try:
            raw = json.loads(self.paths.heartbeat.read_text(encoding="utf-8"))
            return datetime.fromisoformat(str(raw["at"])) >= started
        except (OSError, ValueError, KeyError, TypeError):
            return False

    def _await_start(self, started: datetime) -> bool:
        """Wait until the bot holds the lock and writes a heartbeat; an early exit is an error."""
        deadline = self._monotonic() + self.start_timeout
        holding = False
        while self._monotonic() < deadline:
            code = self._child_exit()
            if code is not None:
                meaning = EXIT_MEANING.get(code, "lỗi không xác định")
                msg = f"bot thoát ngay với mã {code}: {meaning}"
                raise ProcessControlError("BOT_EXITED", msg)
            holding = holding or self.running_pid() is not None
            if holding and self._heartbeat_since(started):
                return True
            self._sleep(self.poll_seconds)
        if not holding and self.running_pid() is None:
            raise ProcessControlError("START_TIMEOUT", "bot không giữ lock sau thời gian chờ")
        return False

    def stop(self) -> StopOutcome:
        """Soft stop: request, wait for the lock to be freed, terminate only after the timeout."""
        with self._lock:
            backend = self.backend()
            pid = self.running_pid()
            if pid is None and backend == "subprocess":
                return StopOutcome(
                    False, True, 0.0, last_cycle(self.paths.cycles), "bot không chạy"
                )
            self._transition = BotState.STOPPING
            begin = self._monotonic()
            graceful = True
            try:
                request_stop(self.paths.stop_sentinel, self._now())
                deadline = begin + self.stop_timeout
                while self.running_pid() is not None and self._monotonic() < deadline:
                    self._sleep(self.poll_seconds)
                if backend == "nssm":
                    self._run([self.nssm or "nssm", "stop", self.service], 90.0)
                still = self.running_pid()
                if still is not None:
                    graceful = False
                    self._terminate(still)
                    self._sleep(self.poll_seconds)
                if self.running_pid() is not None:
                    raise ProcessControlError("STOP_FAILED", "bot vẫn chạy sau khi dừng cưỡng bức")
            finally:
                clear_stop(self.paths.stop_sentinel)
                self._transition = None
                self._child = None
            self._last_error = None
            detail = "dừng mềm sau chu kỳ hiện tại" if graceful else "quá thời gian, đã terminate"
            return StopOutcome(
                pid is not None,
                graceful,
                round(self._monotonic() - begin, 1),
                last_cycle(self.paths.cycles),
                detail,
            )
