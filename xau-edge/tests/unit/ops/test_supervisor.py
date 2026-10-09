"""The market stack supervisor: restart with backoff, single instance, clean stop, rotating logs."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from xau_edge.ops.supervisor import (
    BACKOFF_MAX,
    BACKOFF_START,
    ChildSpec,
    Supervisor,
    process_alive,
    read_pid,
)

PY = sys.executable


def make(
    tmp_path: Path, code: str, *, name: str = "child", clock: list[float] | None = None
) -> Supervisor:
    spec = ChildSpec(name, [PY, "-c", code], tmp_path)
    ticks = clock if clock is not None else [0.0]
    return Supervisor(
        [spec],
        run_dir=tmp_path / "run",
        log_dir=tmp_path / "logs",
        clock=lambda: ticks[0],
        sleep=lambda _s: None,
    )


def wait_exit(sup: Supervisor) -> None:
    child = sup._children[0]
    assert child.process is not None
    child.process.wait(timeout=20)


def test_process_alive_and_read_pid(tmp_path: Path) -> None:
    assert process_alive(os.getpid())
    assert not process_alive(0)
    assert not process_alive(2_000_000_000)
    file = tmp_path / "p"
    file.write_text("123", encoding="utf-8")
    assert read_pid(file) == 123
    assert read_pid(tmp_path / "missing") is None


def test_dead_child_is_restarted_with_growing_backoff(tmp_path: Path) -> None:
    clock = [0.0]
    sup = make(tmp_path, "import sys; sys.exit(7)", clock=clock)
    (tmp_path / "run").mkdir()
    sup.tick()
    wait_exit(sup)
    sup.tick()  # reaps: exit 7, schedules a restart after the first backoff
    child = sup._children[0]
    assert child.process is None
    assert child.last_exit == 7
    assert child.restarts == 1
    assert child.next_start == BACKOFF_START * 2
    sup.tick()
    assert child.process is None  # not due yet
    clock[0] = 1000.0
    sup.tick()
    assert child.process is not None  # restarted
    wait_exit(sup)
    sup.tick()
    assert child.backoff <= BACKOFF_MAX


def test_stable_child_resets_backoff(tmp_path: Path) -> None:
    clock = [0.0]
    sup = make(tmp_path, "import sys; sys.exit(1)", clock=clock)
    (tmp_path / "run").mkdir()
    child = sup._children[0]
    child.backoff = 30.0
    sup.tick()
    clock[0] = 500.0  # it "ran" for 500 s before dying
    wait_exit(sup)
    sup.tick()
    assert child.backoff == BACKOFF_START


def test_snapshot_reports_children_and_pid_files(tmp_path: Path) -> None:
    sup = make(tmp_path, "import time; time.sleep(30)", name="collector")
    (tmp_path / "run").mkdir()
    try:
        sup.tick()
        snap = sup.snapshot()
        assert snap["children"]["collector"]["alive"] is True
        pid = read_pid(tmp_path / "run" / "collector.pid")
        assert pid is not None and process_alive(pid)
    finally:
        sup.stop_children(grace=5)
    assert not (tmp_path / "run" / "collector.pid").exists()


def test_child_output_goes_to_a_rotating_log(tmp_path: Path) -> None:
    sup = make(tmp_path, "print('hello from child', flush=True)", name="api")
    (tmp_path / "run").mkdir()
    sup.tick()
    wait_exit(sup)
    time.sleep(0.5)
    log = (tmp_path / "logs" / "api.log").read_text(encoding="utf-8")
    assert "hello from child" in log
    assert "SUPERVISOR started" in log


def test_run_stops_on_stop_file_and_cleans_up(tmp_path: Path) -> None:
    sup = make(tmp_path, "import time; time.sleep(60)")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    calls = {"n": 0}

    def sleeper(_s: float) -> None:
        calls["n"] += 1
        if calls["n"] == 2:
            (run_dir / "supervisor.stop").write_text("stop", encoding="utf-8")

    sup._sleep = sleeper
    assert sup.run() == 0
    assert not (run_dir / "supervisor.pid").exists()
    state = json.loads((run_dir / "supervisor.json").read_text(encoding="utf-8"))
    assert state["children"]["child"]["alive"] is False


def test_second_supervisor_refuses_to_start(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    other = make(tmp_path, "pass")
    parent_pid = os.getppid()  # a live process that is not us
    (run_dir / "supervisor.pid").write_text(str(parent_pid), encoding="utf-8")
    assert other.already_running()
    assert other.run() == 3
