"""Single-writer ownership: refusal, release, crash recovery and a real start race."""

from __future__ import annotations

import multiprocessing as mp
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from xau_edge.ops.process_lock import WriterLock, WriterLockError

HOLDER = """
import os, sys, time
from xau_edge.ops.process_lock import WriterLock
lock = WriterLock(sys.argv[1], role="holder")
lock.acquire()
print("held", os.getpid(), flush=True)
time.sleep(60)
"""


def test_the_first_owner_acquires_and_a_second_is_refused_with_the_owner_named(
    tmp_path: Path,
) -> None:
    path = tmp_path / "writer.lock"
    first = WriterLock(path, role="trade-engine", code_version="abc123")
    assert first.acquire().stale_owner is None
    second = WriterLock(path, role="other")
    with pytest.raises(WriterLockError) as info:
        second.acquire()
    assert info.value.owner is not None
    assert (
        info.value.owner["role"] == "trade-engine" and info.value.owner["code_version"] == "abc123"
    )
    assert "only one process may write" in str(info.value)
    assert not second.held
    first.release()


def test_release_frees_the_lock_and_it_can_be_taken_again(tmp_path: Path) -> None:
    path = tmp_path / "writer.lock"
    with WriterLock(path), pytest.raises(WriterLockError):
        WriterLock(path).acquire()
    again = WriterLock(path)
    again.acquire()
    assert again.held
    again.release()


def test_a_crashed_owner_never_leaves_a_stale_lock(tmp_path: Path) -> None:
    path = tmp_path / "writer.lock"
    proc = subprocess.Popen(  # noqa: S603 - fixed argv
        [sys.executable, "-c", HOLDER, str(path)], stdout=subprocess.PIPE, text=True
    )
    try:
        assert proc.stdout is not None
        tag, pid_text = proc.stdout.readline().split()
        holder_pid = int(pid_text)  # the real interpreter (the launcher may be a different pid)
        assert tag == "held"
        with pytest.raises(WriterLockError) as info:  # a real second process is refused
            WriterLock(path).acquire()
        assert info.value.owner is not None and info.value.owner["pid"] == holder_pid
        os.kill(holder_pid, signal.SIGTERM)  # a crash: no cleanup code runs in the holder
        proc.wait(timeout=20)
        deadline = time.monotonic() + 10
        recovered = None
        while recovered is None and time.monotonic() < deadline:
            try:
                recovered = WriterLock(path).acquire()
            except WriterLockError:
                time.sleep(0.1)
        assert recovered is not None
        assert recovered.stale_owner is not None and recovered.stale_owner["pid"] == holder_pid
    finally:
        proc.kill()
        if proc.stdout is not None:
            proc.stdout.close()
        proc.wait(timeout=20)


def _race(path: str, queue: mp.Queue) -> None:  # type: ignore[type-arg]
    lock = WriterLock(path, role="racer")
    try:
        lock.acquire()
    except WriterLockError:
        queue.put("refused")
        return
    queue.put("won")
    time.sleep(1.5)  # keep ownership while the others try
    lock.release()


def test_concurrent_starts_produce_exactly_one_owner(tmp_path: Path) -> None:
    ctx = mp.get_context("spawn")
    queue = ctx.Queue()
    path = str(tmp_path / "race.lock")
    procs = [ctx.Process(target=_race, args=(path, queue)) for _ in range(5)]
    for p in procs:
        p.start()
    results = sorted(queue.get(timeout=60) for _ in procs)
    for p in procs:
        p.join(timeout=30)
    assert results.count("won") == 1 and results.count("refused") == 4
