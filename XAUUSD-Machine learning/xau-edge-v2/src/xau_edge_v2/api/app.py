"""FastAPI app: read-only REST + WebSocket, plus the static single-page web build (same origin)."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Response, WebSocket
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from xau_edge_v2 import __version__
from xau_edge_v2.api import forward, human, intelligence, market, model, paper
from xau_edge_v2.api.context import AppContext
from xau_edge_v2.api.health import build_health
from xau_edge_v2.api.live_socket import serve_socket
from xau_edge_v2.api.state import build_state
from xau_edge_v2.config import Settings
from xau_edge_v2.data.bar_store import BarStore
from xau_edge_v2.data.broker_profile import default_calendar, load_profile
from xau_edge_v2.data.live_feed import LiveFeed
from xau_edge_v2.data.tick_store import TickStore
from xau_edge_v2.domain.contract import (
    ErrorBody,
    HealthResponse,
    StateSnapshot,
    WsEvent,
)
from xau_edge_v2.observability import configure_logging
from xau_edge_v2.paper.desk import PaperDesk
from xau_edge_v2.paper.store import PaperStore

_ASSET_CACHE = "public, max-age=31536000, immutable"


class SpaStaticFiles(StaticFiles):
    """Static files with an SPA fallback to index.html (never for /api or /ws) and cache headers."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        rel = path.replace("\\", "/")  # Starlette hands us OS separators on Windows
        try:
            response = await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or rel.startswith(("api/", "ws")) or "." in rel:
                raise
            response = await super().get_response("index.html", scope)
        if response.status_code == 200:
            immutable = rel.startswith("assets/")
            response.headers["Cache-Control"] = _ASSET_CACHE if immutable else "no-cache"
        return response


def _allowed_origins(settings: Settings) -> set[str]:
    hosts = {"127.0.0.1", "localhost"}
    ports = {settings.port, 5173}  # 5173: the Vite dev server
    return {f"http://{h}:{p}" for h in hosts for p in ports}


def create_app(settings: Settings | None = None) -> FastAPI:  # noqa: PLR0915 - app wiring
    cfg = settings or Settings()
    log = configure_logging(cfg.log_dir)
    profile_clock = load_profile().clock
    ctx = AppContext(
        settings=cfg,
        store=BarStore(cfg.data_root),
        ticks=TickStore(cfg.data_root),
        live=LiveFeed(cfg.data_root),
        calendar=default_calendar(),
        started=datetime.now(UTC),
        broker_clock=profile_clock,
        desk=PaperDesk(
            PaperStore(cfg.paper_db),
            start_equity=cfg.paper_equity,
            auto=cfg.auto_paper,
            clock=profile_clock,
        ),
    )
    allowed = _allowed_origins(cfg)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        task = asyncio.create_task(paper.run_engine(ctx)) if cfg.engine_enabled else None
        try:
            yield
        finally:
            if task is not None:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
            ctx.desk.store.close()

    app = FastAPI(
        title="XAU EDGE v2",
        version=__version__,
        docs_url="/api/v2/docs",
        openapi_url="/api/v2/openapi.json",
        lifespan=lifespan,
    )
    app.state.ctx = ctx
    app.state.allowed_origins = allowed
    app.add_middleware(GZipMiddleware, minimum_size=500)
    app.include_router(market.router)
    app.include_router(paper.router)
    app.include_router(model.router)
    app.include_router(forward.router)
    app.include_router(human.router)
    app.include_router(intelligence.router)

    @app.exception_handler(HTTPException)
    async def _http_error(request: Request, exc: HTTPException) -> JSONResponse:
        if request.url.path.startswith("/api/"):
            body = ErrorBody(error_code=f"HTTP_{exc.status_code}", message=str(exc.detail))
            return JSONResponse(body.model_dump(), status_code=exc.status_code)
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    @app.exception_handler(paper.ForeignOrigin)
    async def _foreign(_: Request, __: paper.ForeignOrigin) -> JSONResponse:
        body = ErrorBody(
            error_code="FOREIGN_ORIGIN", message="yêu cầu ghi từ nguồn không được phép"
        )
        return JSONResponse(body.model_dump(), status_code=403)

    @app.exception_handler(RequestValidationError)
    async def _bad_request(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(p) for p in first.get("loc", ()))
        body = ErrorBody(
            error_code="REQUEST_INVALID", message=f"{where}: {first.get('msg', 'invalid')}"
        )
        return JSONResponse(body.model_dump(), status_code=422)

    @app.middleware("http")
    async def _log(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = uuid.uuid4().hex[:12]
        t0 = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        if request.url.path.startswith("/api/"):
            log.info(
                "request",
                extra={
                    "request_id": request_id,
                    "path": request.url.path,
                    "status": response.status_code,
                    "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
                    "error_code": None if response.status_code < 400 else str(response.status_code),
                },
            )
        return response

    @app.get("/api/v2/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return build_health(ctx)

    @app.get("/api/v2/state", response_model=StateSnapshot)
    def state() -> StateSnapshot:
        return build_state(ctx)

    @app.websocket("/ws")
    async def ws(socket: WebSocket) -> None:
        await serve_socket(socket, ctx, allowed)

    def _openapi() -> dict[str, Any]:
        """OpenAPI plus the WebSocket event type (FastAPI does not describe sockets)."""
        if app.openapi_schema is None:
            spec = get_openapi(title=app.title, version=app.version, routes=app.routes)
            event = WsEvent.model_json_schema(ref_template="#/components/schemas/{model}")
            spec.setdefault("components", {}).setdefault("schemas", {})["WsEvent"] = event
            app.openapi_schema = spec
        return app.openapi_schema

    app.openapi = _openapi  # type: ignore[method-assign]

    _mount_web(app, cfg.web_dist, log)
    return app


def _mount_web(app: FastAPI, dist: Path, log: logging.Logger) -> None:
    if (dist / "index.html").is_file():
        app.mount("/", SpaStaticFiles(directory=dist, html=True), name="web")
        return
    log.warning("web build missing", extra={"error_code": "WEB_NOT_BUILT"})

    @app.get("/", include_in_schema=False)
    def _missing() -> JSONResponse:
        body = ErrorBody(error_code="WEB_NOT_BUILT", message="cd apps/web && npm run build")
        return JSONResponse(body.model_dump(), status_code=404)
