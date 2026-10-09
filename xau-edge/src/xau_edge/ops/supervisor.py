"""One supervisor for the market data stack (collector, API, optional dashboard).

Why one: two competing supervisors (a service wrapper AND a scheduled-task restart) fight over the
same children and hide failures. This is the single owner of the child processes. It is started
by one Windows Task Scheduler logon task (the MT5 terminal is a desktop app, not a Session-0
service), restarts a dead child with exponential backoff, keeps PID/heartbeat files, writes each
child's output through a rotating log, and can be stopped cleanly with a stop file or Ctrl+C.

The supervisor never starts or stops MetaTrader 5 and never touches market data itself.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from xau_edge.market_data.atomic import atomic_write_text

BACKOFF_START = 2.0
BACKOFF_MAX = 60.0
STABLE_AFTER = 120.0  # a child that ran this long is healthy again: reset its backoff
LOG_BYTES = 10_000_000
LOG_BACKUPS = 5


@dataclass(frozen=True)
class ChildSpec:
    """How to run one child process."""

    name: str
    argv: Sequence[str]
    cwd: Path
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class _Child:
    spec: ChildSpec
    process: subprocess.Popen[bytes] | None = None
    started_at: float = 0.0
    restarts: int = 0
    backoff: float = BACKOFF_START
    next_start: float = 0.0
    last_exit: int | None = None
    logger: logging.Logger | None = None
    pump: threading.Thread | None = None


def process_alive(pid: int) -> bool:
    """Is ``pid`` a running process (works on Windows without extra packages)."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes  # noqa: PLC0415

        kernel = ctypes.windll.kernel32  # type: ignore[attr-defined,unused-ignore]
        handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        ok = kernel.GetExitCodeProcess(handle, ctypes.byref(code))
        kernel.CloseHandle(handle)
        return bool(ok) and code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def kill_tree(process: subprocess.Popen[bytes]) -> None:
    """Terminate a child AND everything it started (npx -> node, uv -> python, ...)."""
    if sys.platform == "win32":
        subprocess.run(  # noqa: S603 - fixed argv
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],  # noqa: S607
            capture_output=True, check=False,
        )  # fmt: skip
    else:
        process.terminate()


def read_pid(path: Path) -> int | None:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _rotating_logger(name: str, path: Path) -> logging.Logger:
    path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(f"xau_edge.supervisor.child.{name}.{path}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        handler = RotatingFileHandler(
            path, maxBytes=LOG_BYTES, backupCount=LOG_BACKUPS, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        logger.addHandler(handler)
    return logger


class Supervisor:
    """Keeps every child running until told to stop."""

    def __init__(
        self,
        children: Sequence[ChildSpec],
        *,
        run_dir: Path,
        log_dir: Path,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.run_dir = run_dir
        self.log_dir = log_dir
        self._clock = clock
        self._sleep = sleep
        self._children = [_Child(spec) for spec in children]
        self._stop = threading.Event()

    # -- files ---------------------------------------------------------------------------------

    @property
    def pid_file(self) -> Path:
        return self.run_dir / "supervisor.pid"

    @property
    def stop_file(self) -> Path:
        return self.run_dir / "supervisor.stop"

    @property
    def state_file(self) -> Path:
        return self.run_dir / "supervisor.json"

    def already_running(self) -> bool:
        pid = read_pid(self.pid_file)
        return pid is not None and pid != os.getpid() and process_alive(pid)

    # -- children ------------------------------------------------------------------------------

    def _pump(self, child: _Child, process: subprocess.Popen[bytes]) -> None:
        logger = child.logger
        stream = process.stdout
        if stream is None:
            return
        try:
            for raw in iter(stream.readline, b""):
                if logger is not None:
                    logger.info(raw.decode("utf-8", errors="replace").rstrip())
        finally:
            stream.close()

    def _start(self, child: _Child) -> None:
        spec = child.spec
        child.logger = _rotating_logger(spec.name, self.log_dir / f"{spec.name}.log")
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1", **spec.env}
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        child.process = subprocess.Popen(  # noqa: S603 - argv is built by our own scripts
            list(spec.argv), cwd=spec.cwd, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, creationflags=flags,
        )  # fmt: skip
        child.started_at = self._clock()
        child.pump = threading.Thread(target=self._pump, args=(child, child.process), daemon=True)
        child.pump.start()
        (self.run_dir / f"{spec.name}.pid").write_text(str(child.process.pid), encoding="utf-8")
        child.logger.info(
            "SUPERVISOR started pid=%s restarts=%s", child.process.pid, child.restarts
        )

    def _reap(self, child: _Child) -> None:
        process = child.process
        if process is None or process.poll() is None:
            return
        now = self._clock()
        ran = now - child.started_at
        child.last_exit = process.returncode
        pump = child.pump
        if pump is not None:
            pump.join(timeout=2)
        kill_tree(process)  # leftovers of a dead wrapper would keep the port busy
        child.process = None
        child.restarts += 1
        child.backoff = (
            BACKOFF_START if ran >= STABLE_AFTER else min(BACKOFF_MAX, child.backoff * 2)
        )
        child.next_start = now + child.backoff
        if child.logger:
            child.logger.info(
                "SUPERVISOR child exited code=%s after %.0fs; restart in %.0fs",
                child.last_exit, ran, child.backoff,
            )  # fmt: skip

    def tick(self) -> None:
        """One supervision pass: reap dead children, start the ones that are due."""
        for child in self._children:
            self._reap(child)
            if child.process is None and self._clock() >= child.next_start:
                self._start(child)

    def snapshot(self) -> dict[str, Any]:
        children = {}
        for child in self._children:
            alive = child.process is not None and child.process.poll() is None
            children[child.spec.name] = {
                "alive": alive,
                "pid": child.process.pid if alive and child.process else None,
                "restarts": child.restarts,
                "last_exit": child.last_exit,
                "uptime_seconds": round(self._clock() - child.started_at) if alive else 0,
            }
        return {
            "supervisor_pid": os.getpid(),
            "updated_at": datetime.now(UTC).isoformat(),
            "children": children,
        }

    def _write_state(self) -> None:
        atomic_write_text(self.state_file, json.dumps(self.snapshot(), indent=2))

    # -- lifecycle -----------------------------------------------------------------------------

    def request_stop(self) -> None:
        self._stop.set()

    def stop_children(self, grace: float = 10.0) -> None:
        for child in self._children:
            process = child.process
            if process is None or process.poll() is not None:
                continue
            kill_tree(process)
        deadline = time.monotonic() + grace
        for child in self._children:
            process = child.process
            if process is None:
                continue
            try:
                process.wait(timeout=max(0.1, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                process.kill()
            if child.pump is not None:
                child.pump.join(timeout=2)
            (self.run_dir / f"{child.spec.name}.pid").unlink(missing_ok=True)

    def run(self, interval: float = 2.0) -> int:
        """Supervise until stopped (stop file, request_stop or Ctrl+C). Returns an exit code."""
        self.run_dir.mkdir(parents=True, exist_ok=True)
        if self.already_running():
            return 3
        self.stop_file.unlink(missing_ok=True)
        self.pid_file.write_text(str(os.getpid()), encoding="utf-8")
        try:
            while not self._stop.is_set() and not self.stop_file.exists():
                self.tick()
                self._write_state()
                self._sleep(interval)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop_children()
            self._write_state()
            self.pid_file.unlink(missing_ok=True)
            self.stop_file.unlink(missing_ok=True)
        return 0
