"""Long control actions as jobs: one state-changing job at a time, idempotent by key (ADR-0023).

``JobManager.submit`` returns at once with a job id; the work runs on a background thread (tests
run it inline). A second submit with the SAME idempotency key returns the same job, so a double
click never runs an action twice. A submit with a new key while another job is active is refused.
Every failure becomes a stable error code and a short message: no exception text, stack trace or
file path reaches the response.
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from xau_edge.execution.guards import PRAGUE
from xau_edge.observability import log_event

_LOG = logging.getLogger(__name__)

JobStatus = Literal["RUNNING", "SUCCEEDED", "FAILED", "REFUSED"]
Executor = Callable[[Callable[[], None]], None]


class JobRefusedError(Exception):
    """A precondition of the action is not met; nothing (more) was changed."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class JobFailedError(Exception):
    """The action started and could not finish."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class JobBusyError(Exception):
    """Another state-changing job is running."""

    def __init__(self, active: Job) -> None:
        super().__init__("another control job is running")
        self.active = active


class IdempotencyConflictError(Exception):
    """The key was already used for a different action."""


@dataclass
class JobStep:
    """One progress line."""

    at: datetime
    message: str


@dataclass
class Job:
    """A control action and its progress."""

    id: str
    kind: str
    idempotency_key: str
    created_at: datetime
    status: JobStatus = "RUNNING"
    finished_at: datetime | None = None
    steps: list[JobStep] = field(default_factory=list)
    result: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready view."""
        return {
            "id": self.id,
            "kind": self.kind,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "steps": [{"at": s.at.isoformat(), "message": s.message} for s in self.steps],
            "result": self.result,
            "error_code": self.error_code,
            "message": self.message,
        }


class JobContext:
    """Handed to the work function: progress lines only."""

    def __init__(self, job: Job, clock: Callable[[], datetime], lock: threading.Lock) -> None:
        self._job = job
        self._clock = clock
        self._lock = lock

    def step(self, message: str) -> None:
        """Append a progress line."""
        with self._lock:
            self._job.steps.append(JobStep(self._clock(), message))


def _thread_executor(fn: Callable[[], None]) -> None:
    threading.Thread(target=fn, name="control-job", daemon=True).start()


class JobManager:
    """Registry of jobs; at most one RUNNING at a time."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        executor: Executor = _thread_executor,
        keep: int = 50,
    ) -> None:
        self._clock = clock
        self._executor = executor
        self._keep = keep
        self._jobs: OrderedDict[str, Job] = OrderedDict()
        self._keys: dict[str, str] = {}
        self._lock = threading.Lock()

    def active(self) -> Job | None:
        """The running job, if any."""
        with self._lock:
            return next((j for j in self._jobs.values() if j.status == "RUNNING"), None)

    def get(self, job_id: str) -> Job | None:
        """A job by id."""
        with self._lock:
            return self._jobs.get(job_id)

    def recent(self, limit: int = 10) -> list[Job]:
        """Newest first."""
        with self._lock:
            return list(reversed(self._jobs.values()))[:limit]

    def submit(
        self, kind: str, key: str, work: Callable[[JobContext], dict[str, Any]]
    ) -> tuple[Job, bool]:
        """Start ``work`` as a job; returns ``(job, replayed)``."""
        with self._lock:
            known = self._keys.get(key)
            if known is not None and known in self._jobs:
                job = self._jobs[known]
                if job.kind != kind:
                    raise IdempotencyConflictError(key)
                return job, True
            running = next((j for j in self._jobs.values() if j.status == "RUNNING"), None)
            if running is not None:
                raise JobBusyError(running)
            job = Job(uuid.uuid4().hex, kind, key, self._clock())
            self._jobs[job.id] = job
            self._keys[key] = job.id
            while len(self._jobs) > self._keep:
                old_id, old = next(iter(self._jobs.items()))
                if old.status == "RUNNING":
                    break
                self._jobs.pop(old_id)
                self._keys.pop(old.idempotency_key, None)
        ctx = JobContext(job, self._clock, self._lock)
        self._executor(lambda: self._run(job, ctx, work))
        return job, False

    def _finish(self, job: Job, status: JobStatus, code: str | None, message: str) -> None:
        with self._lock:
            job.status = status
            job.error_code = code
            job.message = message
            job.finished_at = self._clock()

    def _run(self, job: Job, ctx: JobContext, work: Callable[[JobContext], dict[str, Any]]) -> None:
        try:
            result = work(ctx)
        except JobRefusedError as exc:
            self._finish(job, "REFUSED", exc.code, exc.message)
        except JobFailedError as exc:
            self._finish(job, "FAILED", exc.code, exc.message)
        except Exception as exc:
            log_event(_LOG, "control.job_crashed", logging.ERROR, kind=job.kind,
                      error=type(exc).__name__)  # fmt: skip
            self._finish(job, "FAILED", "INTERNAL_ERROR", "lỗi nội bộ; xem log của API")
        else:
            with self._lock:
                job.result = result
            self._finish(job, "SUCCEEDED", None, "hoàn tất")


@dataclass(frozen=True)
class RateRule:
    """At most one action per ``min_interval`` and ``max_per_day`` per Prague day."""

    min_interval: timedelta
    max_per_day: int | None = None


class RateLimiter:
    """Persistent history of rate-limited actions (survives an API restart)."""

    def __init__(
        self,
        path: Path,
        rules: dict[str, RateRule],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.path = path
        self.rules = rules
        self._clock = clock
        self._lock = threading.Lock()

    def _load(self) -> dict[str, list[datetime]]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return {k: [datetime.fromisoformat(v) for v in vs] for k, vs in raw.items()}
        except FileNotFoundError:
            return {}
        except (OSError, ValueError, TypeError, AttributeError):
            # unreadable history: treat as "just used" (fail closed for smoke)
            now = self._clock()
            return {k: [now] for k in self.rules}

    def blocked(self, kind: str) -> str | None:
        """A Vietnamese reason when ``kind`` may not run now, else ``None``."""
        rule = self.rules.get(kind)
        if rule is None:
            return None
        now = self._clock()
        with self._lock:
            history = self._load().get(kind, [])
        if history:
            wait = rule.min_interval - (now - max(history))
            if wait > timedelta(0):
                return f"giới hạn tần suất: chờ thêm {int(wait.total_seconds()) + 1} giây"
        if rule.max_per_day is not None:
            today = now.astimezone(PRAGUE).date()
            used = sum(1 for t in history if t.astimezone(PRAGUE).date() == today)
            if used >= rule.max_per_day:
                return f"giới hạn {rule.max_per_day} lần mỗi ngày (giờ Prague) đã dùng hết"
        return None

    def record(self, kind: str) -> None:
        """Remember one use of ``kind`` now (history older than two days is dropped)."""
        now = self._clock()
        with self._lock:
            data = self._load()
            keep = [t for t in data.get(kind, []) if now - t < timedelta(days=2)]
            data[kind] = [*keep, now]
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name(self.path.name + ".tmp")
            tmp.write_text(
                json.dumps({k: [t.isoformat() for t in v] for k, v in data.items()}), "utf-8"
            )
            tmp.replace(self.path)
