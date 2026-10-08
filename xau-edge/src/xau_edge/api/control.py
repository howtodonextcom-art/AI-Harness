"""``/control/*``: the local web control plane (ADR-0023), mounted only with XAU_EDGE_WEB_CONTROL.

Security, checked by a middleware BEFORE any route code or body parsing runs:

* the API binds 127.0.0.1 only and every ``/control`` request must carry ``Host`` equal to
  ``127.0.0.1:<port>`` or ``localhost:<port>`` (DNS-rebinding guard);
* every ``/control`` request needs the right ``X-XAU-Control-Token`` (random per API start, read
  server-side by the dashboard; never in the browser bundle);
* every POST also needs an ``Origin`` from ``ALLOWED_ORIGINS`` and ``Content-Type:
  application/json``, plus an ``Idempotency-Key`` header;
* POSTs are rate-limited, and smoke/flatten have their own persistent limits.

Failures answer 403 with a code; no response or log line carries a stack trace, a file path or a
secret. The only modes a request can name are DRY_RUN and DEMO; nothing here can reach a funded
or live setting, change ``.env`` or reset the kill switch.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from collections import deque
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from xau_edge.control.jobs import IdempotencyConflictError, Job, JobBusyError
from xau_edge.control.runtime_mode import RuntimeModeError
from xau_edge.control.security import TOKEN_HEADER, check_token
from xau_edge.control.service import ActionBlockedError, ConfirmationError, ControlService
from xau_edge.observability import log_event

_LOG = logging.getLogger(__name__)

PREFIX = "/control"
IDEMPOTENCY_HEADER = "Idempotency-Key"
_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,100}$")
POST_LIMIT_PER_MINUTE = 20


class EmptyRequest(BaseModel):
    """Start, stop and restart take no parameters."""

    model_config = ConfigDict(extra="forbid")


class ModeRequest(BaseModel):
    """The only two modes the web can select."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["DRY_RUN", "DEMO"]
    confirm: str = Field(default="", max_length=20)


class ConfirmRequest(BaseModel):
    """Smoke and flatten: only the typed confirmation word, no order parameter of any kind."""

    model_config = ConfigDict(extra="forbid")

    confirm: str = Field(max_length=20)


def _deny(code: str, message: str, status: int = 403) -> JSONResponse:
    return JSONResponse({"detail": {"code": code, "message": message}}, status_code=status)


class _PostRate:
    """Sliding one-minute window over all control POSTs."""

    def __init__(self, limit: int, clock: Callable[[], float] = time.monotonic) -> None:
        self.limit = limit
        self._clock = clock
        self._hits: deque[float] = deque()
        self._lock = threading.Lock()

    def allow(self) -> bool:
        now = self._clock()
        with self._lock:
            while self._hits and now - self._hits[0] > 60.0:
                self._hits.popleft()
            if len(self._hits) >= self.limit:
                return False
            self._hits.append(now)
            return True


def install_control_guard(
    app: FastAPI, *, token: str, port: int, allowed_origins: tuple[str, ...]
) -> None:
    """Host, token, Origin and Content-Type checks for every ``/control`` request."""
    hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    rate = _PostRate(POST_LIMIT_PER_MINUTE)

    @app.middleware("http")
    async def control_guard(  # noqa: PLR0911 - one answer per refused check
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path
        if path != PREFIX and not path.startswith(PREFIX + "/"):
            return await call_next(request)
        if request.headers.get("host", "").lower() not in hosts:
            return _deny("BAD_HOST", "chỉ chấp nhận Host 127.0.0.1/localhost của API")
        if not check_token(token, request.headers.get(TOKEN_HEADER)):
            return _deny("BAD_TOKEN", "thiếu hoặc sai token điều khiển")
        if request.method not in {"GET", "POST"}:
            return _deny("METHOD_NOT_ALLOWED", "chỉ GET và POST", 405)
        if request.method == "POST":
            if request.headers.get("origin") not in allowed_origins:
                return _deny("BAD_ORIGIN", "Origin không được phép")
            ctype = request.headers.get("content-type", "").split(";")[0].strip().lower()
            if ctype != "application/json":
                return _deny("BAD_CONTENT_TYPE", "Content-Type phải là application/json")
            if not rate.allow():
                return _deny("RATE_LIMITED", "quá nhiều yêu cầu điều khiển; chờ một phút", 429)
        try:
            return await call_next(request)
        except Exception as exc:
            log_event(_LOG, "control.request_failed", logging.ERROR, error=type(exc).__name__)
            return _deny("INTERNAL_ERROR", "lỗi nội bộ", 500)


def _key(value: str | None) -> str:
    if value is None or not _KEY_PATTERN.match(value):
        raise HTTPException(
            status_code=400,
            detail={"code": "IDEMPOTENCY_KEY_REQUIRED", "message": "cần Idempotency-Key hợp lệ"},
        )
    return value


def _accepted(submit: Callable[[], tuple[Job, bool]]) -> JSONResponse:
    try:
        job, replayed = submit()
    except ActionBlockedError as exc:
        limited = any(b.code == "RATE_LIMITED" for b in exc.blockers)
        return JSONResponse(
            {
                "detail": {
                    "code": "RATE_LIMITED" if limited else "ACTION_BLOCKED",
                    "message": "; ".join(b.message for b in exc.blockers),
                    "blockers": [b.model_dump() for b in exc.blockers],
                }
            },
            status_code=429 if limited else 409,
        )
    except ConfirmationError as exc:
        return _deny("CONFIRMATION_MISMATCH", f"gõ đúng chữ {exc.expected} để xác nhận", 400)
    except JobBusyError as exc:
        return _deny("JOB_BUSY", f"đang chạy thao tác {exc.active.kind}", 409)
    except IdempotencyConflictError:
        return _deny("IDEMPOTENCY_CONFLICT", "Idempotency-Key đã dùng cho thao tác khác", 409)
    except RuntimeModeError:
        return _deny("BAD_MODE", "chỉ DRY_RUN hoặc DEMO", 422)
    return JSONResponse({"job": job.to_dict(), "replayed": replayed}, status_code=202)


def add_control_routes(app: FastAPI, service: ControlService) -> None:
    """The ``/control`` routes, registered on the app itself so the route table shows them all."""
    key_header = Header(default=None, alias=IDEMPOTENCY_HEADER)

    @app.get(PREFIX + "/status")
    def status() -> dict[str, Any]:
        return service.status()

    @app.get(PREFIX + "/preflight")
    def preflight(probe: bool = True) -> dict[str, Any]:
        return service.preflight(probe=probe).model_dump(mode="json")

    @app.get(PREFIX + "/bot")
    def bot() -> dict[str, Any]:
        body = service.status()
        return {
            "bot": body["bot"],
            "configured_mode": body["configured_mode"],
            "actions": {k: body["actions"][k] for k in ("start", "stop", "restart")},
        }

    @app.get(PREFIX + "/jobs")
    def jobs() -> dict[str, Any]:
        active = service.jobs.active()
        return {
            "active": active.to_dict() if active else None,
            "recent": [j.to_dict() for j in service.jobs.recent(20)],
        }

    @app.get(PREFIX + "/jobs/{job_id}")
    def job(job_id: str) -> dict[str, Any]:
        found = service.jobs.get(job_id)
        if found is None:
            raise HTTPException(
                status_code=404, detail={"code": "NO_SUCH_JOB", "message": "không có job này"}
            )
        return found.to_dict()

    @app.get(PREFIX + "/journal")
    def journal() -> dict[str, Any]:
        return {"events": service.journal_tail()}

    @app.post(PREFIX + "/bot/start", status_code=202)
    def start(body: EmptyRequest, key: str | None = key_header) -> JSONResponse:
        del body
        return _accepted(lambda: service.start(_key(key)))

    @app.post(PREFIX + "/bot/stop", status_code=202)
    def stop(body: EmptyRequest, key: str | None = key_header) -> JSONResponse:
        del body
        return _accepted(lambda: service.stop(_key(key)))

    @app.post(PREFIX + "/bot/restart", status_code=202)
    def restart(body: EmptyRequest, key: str | None = key_header) -> JSONResponse:
        del body
        return _accepted(lambda: service.restart(_key(key)))

    @app.post(PREFIX + "/mode", status_code=202)
    def mode(body: ModeRequest, key: str | None = key_header) -> JSONResponse:
        return _accepted(lambda: service.set_mode(body.mode, body.confirm, _key(key)))

    @app.post(PREFIX + "/smoke", status_code=202)
    def smoke(body: ConfirmRequest, key: str | None = key_header) -> JSONResponse:
        return _accepted(lambda: service.smoke(body.confirm, _key(key)))

    @app.post(PREFIX + "/flatten", status_code=202)
    def flatten(body: ConfirmRequest, key: str | None = key_header) -> JSONResponse:
        return _accepted(lambda: service.flatten(body.confirm, _key(key)))


def mount_control(
    app: FastAPI, service: ControlService, *, port: int, allowed_origins: tuple[str, ...]
) -> None:
    """Add the guard and the routes to ``app``."""
    install_control_guard(app, token=service.token, port=port, allowed_origins=allowed_origins)
    add_control_routes(app, service)
