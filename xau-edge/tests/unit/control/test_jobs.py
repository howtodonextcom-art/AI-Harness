"""Job manager (one job at a time, idempotency, safe errors) and the persistent rate limiter."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from tests.unit.brokers.test_executor import T
from xau_edge.control.jobs import (
    IdempotencyConflictError,
    JobBusyError,
    JobContext,
    JobFailedError,
    JobManager,
    JobRefusedError,
    RateLimiter,
    RateRule,
)


def _inline() -> JobManager:
    return JobManager(clock=lambda: T, executor=lambda fn: fn())


def _ok(ctx: JobContext) -> dict[str, Any]:
    ctx.step("did it")
    return {"done": True}


def test_a_job_runs_and_records_its_steps() -> None:
    jobs = _inline()
    job, replayed = jobs.submit("bot.start", "k-00000001", _ok)
    assert replayed is False
    assert job.status == "SUCCEEDED"
    assert job.result == {"done": True}
    assert [s.message for s in job.steps] == ["did it"]


def test_the_same_key_replays_the_same_job_and_never_runs_twice() -> None:
    jobs = _inline()
    runs: list[int] = []

    def work(ctx: JobContext) -> dict[str, Any]:
        runs.append(1)
        return {}

    first, _ = jobs.submit("smoke", "k-00000002", work)
    again, replayed = jobs.submit("smoke", "k-00000002", work)
    assert replayed is True
    assert again is first
    assert runs == [1]
    with pytest.raises(IdempotencyConflictError):
        jobs.submit("flatten", "k-00000002", work)


def test_only_one_job_runs_at_a_time() -> None:
    pending: list[Callable[[], None]] = []
    jobs = JobManager(clock=lambda: T, executor=pending.append)
    jobs.submit("bot.start", "k-00000003", _ok)
    with pytest.raises(JobBusyError):
        jobs.submit("flatten", "k-00000004", _ok)
    pending.pop()()
    assert jobs.active() is None
    job, _ = jobs.submit("flatten", "k-00000004", _ok)
    pending.pop()()
    assert job.status == "SUCCEEDED"


def test_failures_become_codes_without_exception_text() -> None:
    jobs = _inline()

    def refused(ctx: JobContext) -> dict[str, Any]:
        raise JobRefusedError("KILL_SWITCH_TRIPPED", "kill switch đang tripped")

    def failed(ctx: JobContext) -> dict[str, Any]:
        raise JobFailedError("START_FAILED", "không khởi động được")

    def crashed(ctx: JobContext) -> dict[str, Any]:
        raise RuntimeError(r"C:\secret\path password=hunter2")

    assert jobs.submit("a", "k-00000005", refused)[0].status == "REFUSED"
    assert jobs.submit("b", "k-00000006", failed)[0].error_code == "START_FAILED"
    job, _ = jobs.submit("c", "k-00000007", crashed)
    assert job.status == "FAILED"
    assert job.error_code == "INTERNAL_ERROR"
    assert "hunter2" not in str(job.to_dict())
    assert "secret" not in str(job.to_dict())


def test_smoke_limits_one_per_ten_minutes_and_five_per_prague_day(tmp_path: Path) -> None:
    now = {"t": T}
    limiter = RateLimiter(
        tmp_path / "limits.json",
        {"smoke": RateRule(timedelta(minutes=10), 5)},
        clock=lambda: now["t"],
    )
    assert limiter.blocked("smoke") is None
    for i in range(5):
        now["t"] = T + timedelta(minutes=11 * i)
        assert limiter.blocked("smoke") is None
        limiter.record("smoke")
        now["t"] += timedelta(minutes=5)
        assert limiter.blocked("smoke") is not None
    now["t"] = T + timedelta(hours=2)
    assert "5" in (limiter.blocked("smoke") or "")
    now["t"] = T + timedelta(days=1)
    assert limiter.blocked("smoke") is None


def test_limits_survive_a_restart_and_a_corrupt_file_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "limits.json"
    rules = {"smoke": RateRule(timedelta(minutes=10), 5)}
    RateLimiter(path, rules, clock=lambda: T).record("smoke")
    assert RateLimiter(path, rules, clock=lambda: T).blocked("smoke") is not None
    path.write_text("{broken", encoding="utf-8")
    assert RateLimiter(path, rules, clock=lambda: T).blocked("smoke") is not None
