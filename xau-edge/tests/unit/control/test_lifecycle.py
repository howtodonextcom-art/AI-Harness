# ruff: noqa: F811
"""Soft stop in BotApp, the stop sentinel, the process manager (NSSM and subprocess, all fake)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tests.unit.api.test_api import frames  # noqa: F401 - fixture import
from tests.unit.execution.test_app import Harness
from xau_edge.control.paths import ControlPaths
from xau_edge.control.process import (
    BotState,
    CommandResult,
    ProcessControlError,
    ProcessManager,
)
from xau_edge.control.runtime_mode import RuntimeMode
from xau_edge.control.sentinel import StopSentinel, request_stop
from xau_edge.execution.app import EXIT_OK
from xau_edge.signals.engine import MarketFrames

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
BOT_PID = 4242


# -- BotApp soft stop ---------------------------------------------------------------------------


def test_a_stop_requested_before_the_loop_runs_no_cycle(
    tmp_path: Path,
    frames: MarketFrames,
) -> None:
    h = Harness(tmp_path, frames, stop_requested=lambda: True)
    assert h.app.run() == EXIT_OK
    assert h.refreshes == 0
    heartbeat = json.loads((tmp_path / "exec" / "heartbeat.json").read_text(encoding="utf-8"))
    assert heartbeat["status"] == "STOPPED"
    events = [json.loads(line) for line in (tmp_path / "j.jsonl").read_text("utf-8").splitlines()]
    assert events[-1]["event"] == "bot.stopped"
    assert events[-1]["source"] == "web"


def test_a_stop_during_the_wait_ends_the_loop_after_the_current_cycle(
    tmp_path: Path,
    frames: MarketFrames,
) -> None:
    calls = {"n": 0}

    def stop() -> bool:
        calls["n"] += 1
        return calls["n"] > 3  # the cycle completes, the wait is interrupted

    h = Harness(tmp_path, frames, stop_requested=stop)
    assert h.app.run() == EXIT_OK
    assert h.refreshes == 1
    assert len(h.sleeps) <= 3
    assert all(s <= 1.0 for s in h.sleeps)
    assert len((tmp_path / "cycles.jsonl").read_text("utf-8").splitlines()) == 1


def test_a_stale_stop_request_never_stops_a_later_start(tmp_path: Path) -> None:
    path = tmp_path / "stop.json"
    request_stop(path, NOW - timedelta(minutes=5))
    assert StopSentinel(path, NOW)() is False
    request_stop(path, NOW + timedelta(seconds=1))
    assert StopSentinel(path, NOW)() is True
    assert StopSentinel(tmp_path / "none.json", NOW)() is False


# -- process manager ----------------------------------------------------------------------------


class FakeChild:
    def __init__(self, pid: int, code: int | None = None) -> None:
        self.pid = pid
        self.code = code

    def poll(self) -> int | None:
        return self.code


class World:
    """Fake OS: a monotonic clock moved by sleep, live pids, NSSM answers, a bot that obeys."""

    def __init__(self, tmp_path: Path, *, nssm: bool = False, confirm: str = "") -> None:
        self.paths = ControlPaths(tmp_path / "data")
        self.paths.exec_dir.mkdir(parents=True)
        self.t = 0.0
        self.alive: set[int] = set()
        self.commands: list[list[str]] = []
        self.spawned: list[list[str]] = []
        self.terminated: list[int] = []
        self.nssm = nssm
        self.confirm = confirm
        self.service_running = False
        self.exit_code: int | None = None
        self.obeys_stop = True
        self.takes_lock = True

    # collaborators
    def runner(self, args: Sequence[str], timeout: float) -> CommandResult:
        self.commands.append(list(args))
        if not self.nssm:
            return CommandResult(-1, "")
        verb = args[1]
        if verb == "status":
            return CommandResult(
                0, "SERVICE_RUNNING" if self.service_running else "SERVICE_STOPPED"
            )
        if verb == "get":
            return CommandResult(0, f"run --extra mt5 python scripts/demo_trader.py {self.confirm}")
        if verb == "start":
            self.service_running = True
            self._bot_starts()
            return CommandResult(0, "")
        if verb == "stop":
            self.service_running = False
            self._bot_exits()
            return CommandResult(0, "")
        return CommandResult(1, "")

    def spawner(self, args: Sequence[str], cwd: Path, log: Path) -> FakeChild:
        self.spawned.append(list(args))
        if self.exit_code is None:
            self._bot_starts()
        return FakeChild(BOT_PID, self.exit_code)

    def sleep(self, seconds: float) -> None:
        self.t += seconds
        if self.obeys_stop and self.paths.stop_sentinel.exists():
            self._bot_exits()

    def terminate(self, pid: int) -> None:
        self.terminated.append(pid)
        self._bot_exits()

    # bot behaviour
    def _bot_starts(self) -> None:
        if not self.takes_lock:
            return
        self.alive.add(BOT_PID)
        self.paths.lock.write_text(json.dumps({"pid": BOT_PID}), encoding="utf-8")
        self.paths.heartbeat.write_text(
            json.dumps({"at": (NOW + timedelta(seconds=5)).isoformat(), "status": "OK"}), "utf-8"
        )

    def _bot_exits(self) -> None:
        self.alive.discard(BOT_PID)
        self.paths.lock.unlink(missing_ok=True)
        row = {
            "decision_time": "2026-10-08T11:45:00+00:00",
            "direction": "WAIT",
            "reasons": ["NO_VALIDATED_EDGE"],
            "recorded_at": "x",
        }
        with self.paths.cycles.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")

    def manager(self) -> ProcessManager:
        return ProcessManager(
            self.paths,
            repo_root=Path("repo"),
            python="python.exe",
            script=Path("repo/scripts/demo_trader.py"),
            nssm="nssm.exe" if self.nssm else None,
            runner=self.runner,
            spawner=self.spawner,
            is_alive=lambda pid: pid in self.alive,
            terminate=self.terminate,
            now=lambda: NOW,
            monotonic=lambda: self.t,
            sleep=self.sleep,
            start_timeout=30.0,
            stop_timeout=20.0,
        )


def test_subprocess_start_in_dry_run_passes_no_confirmation(tmp_path: Path) -> None:
    w = World(tmp_path)
    outcome = w.manager().start(RuntimeMode.DRY_RUN)
    assert w.spawned == [["python.exe", str(Path("repo/scripts/demo_trader.py"))]]
    assert outcome.info.state is BotState.RUNNING
    assert outcome.first_cycle_seen is True
    assert json.loads(w.paths.process.read_text("utf-8"))["pid"] == BOT_PID


def test_subprocess_start_in_demo_confirms_demo_and_nothing_else(tmp_path: Path) -> None:
    w = World(tmp_path)
    w.manager().start(RuntimeMode.DEMO)
    assert w.spawned[0][-2:] == ["--confirm-mode", "DEMO"]
    assert not any("FUNDED" in a for a in w.spawned[0])


def test_a_second_bot_is_never_started_while_the_lock_is_held(tmp_path: Path) -> None:
    w = World(tmp_path)
    w.alive.add(BOT_PID)
    w.paths.lock.write_text(json.dumps({"pid": BOT_PID}), encoding="utf-8")
    with pytest.raises(ProcessControlError) as info:
        w.manager().start(RuntimeMode.DRY_RUN)
    assert info.value.code == "BOT_ALREADY_RUNNING"
    assert w.spawned == []


def test_a_lock_left_by_a_dead_process_does_not_block_a_start(tmp_path: Path) -> None:
    w = World(tmp_path)
    w.paths.lock.write_text(json.dumps({"pid": 999}), encoding="utf-8")
    assert w.manager().start(RuntimeMode.DRY_RUN).info.state is BotState.RUNNING


def test_a_bot_that_refuses_to_start_shows_error_with_its_exit_code(tmp_path: Path) -> None:
    w = World(tmp_path)
    w.exit_code = 3
    manager = w.manager()
    with pytest.raises(ProcessControlError) as info:
        manager.start(RuntimeMode.DEMO)
    assert info.value.code == "BOT_EXITED"
    assert "3" in info.value.message
    assert manager.info().state is BotState.ERROR


def test_start_clears_a_leftover_stop_request(tmp_path: Path) -> None:
    w = World(tmp_path)
    w.obeys_stop = False
    request_stop(w.paths.stop_sentinel, NOW - timedelta(hours=1))
    w.manager().start(RuntimeMode.DRY_RUN)
    assert not w.paths.stop_sentinel.exists()


def test_stop_is_soft_and_reports_the_last_completed_cycle(tmp_path: Path) -> None:
    w = World(tmp_path)
    manager = w.manager()
    manager.start(RuntimeMode.DRY_RUN)
    outcome = manager.stop()
    assert outcome.was_running is True
    assert outcome.graceful is True
    assert w.terminated == []
    assert outcome.last_cycle is not None
    assert outcome.last_cycle["decision_time"] == "2026-10-08T11:45:00+00:00"
    assert not w.paths.stop_sentinel.exists()
    assert manager.info().state is BotState.STOPPED


def test_stop_terminates_only_after_the_timeout(tmp_path: Path) -> None:
    w = World(tmp_path)
    manager = w.manager()
    manager.start(RuntimeMode.DRY_RUN)
    w.obeys_stop = False
    outcome = manager.stop()
    assert outcome.graceful is False
    assert w.terminated == [BOT_PID]
    assert w.t >= 20.0


def test_stop_when_nothing_runs_is_a_no_op(tmp_path: Path) -> None:
    w = World(tmp_path)
    outcome = w.manager().stop()
    assert outcome.was_running is False
    assert not w.paths.stop_sentinel.exists()


def test_nssm_backend_uses_fixed_nssm_commands_and_never_spawns(tmp_path: Path) -> None:
    w = World(tmp_path, nssm=True)
    manager = w.manager()
    assert manager.backend() == "nssm"
    manager.start(RuntimeMode.DRY_RUN)
    assert ["nssm.exe", "start", "xau-edge-bot"] in w.commands
    assert w.spawned == []
    manager.stop()
    assert ["nssm.exe", "stop", "xau-edge-bot"] in w.commands
    assert all(isinstance(c, list) and c[0] == "nssm.exe" for c in w.commands)


def test_nssm_demo_needs_a_service_installed_with_confirm_mode_demo(tmp_path: Path) -> None:
    w = World(tmp_path, nssm=True, confirm="")
    with pytest.raises(ProcessControlError) as info:
        w.manager().start(RuntimeMode.DEMO)
    assert info.value.code == "NSSM_NOT_DEMO_CONFIRMED"
    assert ["nssm.exe", "start", "xau-edge-bot"] not in w.commands
    ok = World(tmp_path / "ok", nssm=True, confirm="--confirm-mode DEMO")
    assert ok.manager().start(RuntimeMode.DEMO).info.state is BotState.RUNNING


def test_without_nssm_the_backend_is_a_subprocess(tmp_path: Path) -> None:
    assert World(tmp_path).manager().backend() == "subprocess"
