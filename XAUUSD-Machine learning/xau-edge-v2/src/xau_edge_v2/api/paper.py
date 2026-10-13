"""Paper desk routes and the background engine. PAPER only: no route here reaches a broker.

Reads are plain GETs. The two writes (open the current plan, close a position) change only V2's
own SQLite file; they refuse a foreign Origin, recompute everything on the server (the client never
supplies a price, size or level), and answer with a named error code when refused.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from xau_edge_v2.api.context import AppContext
from xau_edge_v2.api.intelligence import live_intelligence
from xau_edge_v2.api.state import _spec, live_decision
from xau_edge_v2.core.decision import DecisionConfig
from xau_edge_v2.domain.contract import (
    ErrorBody,
    JournalResponse,
    PaperActionResult,
    PaperPositionsResponse,
    PaperSummary,
    Timeframe,
)
from xau_edge_v2.ops.alerts import Alerter, TelegramNotifier, problems_from_checks
from xau_edge_v2.paper.backup import MirrorState, sync_mirror
from xau_edge_v2.paper.desk import MinuteBar

router = APIRouter(prefix="/api/v2/paper", tags=["paper"])
ERRORS: dict[int | str, dict[str, Any]] = {
    403: {"model": ErrorBody},
    404: {"model": ErrorBody},
    409: {"model": ErrorBody},
}
RISK_PCT = DecisionConfig().risk_pct
log = logging.getLogger("xau_edge_v2.paper")
ALERT_PASS_SECONDS = 15.0


def _ctx(request: Request) -> AppContext:
    ctx: AppContext = request.app.state.ctx
    return ctx


def _error(status: int, code: str, message: str) -> JSONResponse:
    body = ErrorBody(error_code=code, message=message)
    return JSONResponse(body.model_dump(), status_code=status)


class ForeignOrigin(Exception):
    """A write came from a web page that is not this application."""


def same_origin(request: Request) -> None:
    allowed: set[str] = request.app.state.allowed_origins
    origin = request.headers.get("origin")
    if origin is not None and origin not in allowed:
        raise ForeignOrigin


def _quote_prices(ctx: AppContext, now: datetime) -> tuple[float | None, float | None]:
    quote = ctx.live.quote(ctx.calendar, now)
    return (quote.bid, quote.ask) if quote.available else (None, None)


@router.get("/summary", response_model=PaperSummary)
def summary(request: Request) -> PaperSummary:
    ctx, now = _ctx(request), datetime.now(UTC)
    bid, ask = _quote_prices(ctx, now)
    return ctx.desk.summary(now, RISK_PCT, bid, ask)


@router.get("/positions", response_model=PaperPositionsResponse)
def positions(
    request: Request,
    status: Annotated[str | None, Query(pattern="^(OPEN|CLOSED)$")] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> PaperPositionsResponse:
    ctx = _ctx(request)
    bid, ask = _quote_prices(ctx, datetime.now(UTC))
    rows = ctx.desk.store.positions(status, limit)
    return PaperPositionsResponse(positions=tuple(ctx.desk.view(r, bid, ask) for r in rows))


@router.get("/journal", response_model=JournalResponse)
def journal(request: Request, limit: Annotated[int, Query(ge=1, le=1000)] = 200) -> JournalResponse:
    return JournalResponse(events=tuple(_ctx(request).desk.journal(limit)))


@router.post(
    "/open-current",
    response_model=PaperActionResult,
    responses=ERRORS,
    dependencies=[Depends(same_origin)],
)
def open_current(request: Request) -> PaperActionResult | JSONResponse:
    """Open a PAPER position from the decision the server computes right now (BUY/SELL only)."""
    ctx, now = _ctx(request), datetime.now(UTC)
    if ctx.desk.open_row() is not None:
        return _error(409, "POSITION_ALREADY_OPEN", "đã có một lệnh PAPER đang mở")
    decision = live_decision(ctx)
    if decision is None or decision.action not in ("BUY", "SELL"):
        why = ", ".join(decision.refusals) if decision else "no data"
        return _error(409, "NO_VALID_PLAN", f"chưa có kế hoạch hợp lệ ({why})")
    spec, _ = _spec(ctx)
    row = ctx.desk.open_position(now, decision, spec, "MANUAL")
    if row is None:
        return _error(409, "SETUP_ALREADY_USED", "setup này đã được mở trước đó")
    bid, ask = _quote_prices(ctx, now)
    return PaperActionResult(
        ok=True, message="đã mở lệnh PAPER", position=ctx.desk.view(row, bid, ask)
    )


@router.post(
    "/positions/{position_id}/close",
    response_model=PaperActionResult,
    responses=ERRORS,
    dependencies=[Depends(same_origin)],
)
def close_position(request: Request, position_id: str) -> PaperActionResult | JSONResponse:
    """Close an open PAPER position at the current quote (bid for a BUY, ask for a SELL)."""
    ctx, now = _ctx(request), datetime.now(UTC)
    row = ctx.desk.store.position(position_id)
    if row is None:
        return _error(404, "POSITION_NOT_FOUND", "không có lệnh này")
    if row["status"] != "OPEN":
        return _error(409, "POSITION_NOT_OPEN", "lệnh đã đóng")
    quote = ctx.live.quote(ctx.calendar, now)
    if quote.state != "FRESH" or quote.bid is None or quote.ask is None:
        return _error(409, "QUOTE_UNAVAILABLE", "không có quote mới để đóng lệnh")
    done = ctx.desk.close_manual(position_id, now, quote.bid, quote.ask)
    if done is None:
        return _error(409, "POSITION_NOT_OPEN", "lệnh đã đóng")
    return PaperActionResult(
        ok=True, message="đã đóng lệnh PAPER", position=ctx.desk.view(done, quote.bid, quote.ask)
    )


# ---- the engine ----------------------------------------------------------------------
def minute_bars(ctx: AppContext, after_us: int) -> list[MinuteBar]:
    """Closed M1 bars that opened after ``after_us`` (newest few hundred at most)."""
    frame = ctx.store.tail(Timeframe.M1, 600)
    if frame.height == 0:
        return []
    out: list[MinuteBar] = []
    for ts, high, low, spread in zip(
        frame["timestamp"].dt.epoch("us").to_list(),
        frame["high"].to_list(),
        frame["low"].to_list(),
        frame["spread"].to_list(),
        strict=True,
    ):
        if ts > after_us:
            out.append(MinuteBar(int(ts), float(high), float(low), float(spread or 0.0)))
    return out


@dataclass
class EngineStatus:
    """What the watchdog (and /health) needs to know about the background loop."""

    started: datetime
    ticks: int = 0
    errors: int = 0
    last_ok: datetime | None = None
    last_error: str | None = None
    last_error_at: datetime | None = None
    last_ms: float = 0.0
    last_backup: datetime | None = None
    integrity: list[str] = field(default_factory=list)
    logged_bars: int = 0
    mirrors: list[MirrorState] = field(default_factory=list)


def engine_status(ctx: AppContext) -> EngineStatus:
    status = ctx.cache.get("engine")
    if not isinstance(status, EngineStatus):
        cfg = ctx.settings
        mirrors = [MirrorState(path=p, offdevice=False) for p in cfg.backup_mirrors]
        if cfg.backup_offdevice_dir is not None:
            mirrors.append(MirrorState(path=cfg.backup_offdevice_dir, offdevice=True))
        status = EngineStatus(started=datetime.now(UTC), mirrors=mirrors)
        ctx.cache["engine"] = status
    return status


def get_alerter(ctx: AppContext) -> Alerter:
    """The alert state machine; it sends only when a Telegram bot and chat are configured."""
    alerter = ctx.cache.get("alerter")
    if not isinstance(alerter, Alerter):
        cfg = ctx.settings
        notifier = None
        if cfg.alerts_enabled and cfg.telegram_bot_token is not None and cfg.telegram_chat_id:
            notifier = TelegramNotifier(
                cfg.telegram_bot_token.get_secret_value(), cfg.telegram_chat_id
            )
        alerter = Alerter(
            notifier,
            confirm_seconds=cfg.alert_confirm_seconds,
            renotify_seconds=cfg.alert_renotify_seconds,
        )
        ctx.cache["alerter"] = alerter
    return alerter


def evaluate_alerts(ctx: AppContext, now: datetime | None = None) -> list[str]:
    """Turn the current /health problems into (at most a few) operational messages."""
    from xau_edge_v2.api.health import build_health  # noqa: PLC0415 - health imports this module

    health = build_health(ctx)
    rows = [(c.id, c.label, c.state, c.detail) for c in health.checks]
    return get_alerter(ctx).evaluate(problems_from_checks(rows), now)


def startup_notice(ctx: AppContext, now: datetime) -> bool:
    """One 'service started' message, at most once per 30 minutes (restart loops stay quiet)."""
    alerter = get_alerter(ctx)
    if not alerter.configured:
        return False
    last = ctx.desk.store.account("alert_startup_at")
    if last is not None and (now - datetime.fromisoformat(last)).total_seconds() < 1800:
        return False
    sent = alerter.startup(now)
    if sent:
        with ctx.desk.store._tx() as db:
            db.execute(
                "INSERT INTO account (key, value) VALUES ('alert_startup_at', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (now.isoformat(),),
            )
    return sent


def log_forward(ctx: AppContext, moment: datetime) -> bool:
    """Log the decision seen at the newest closed M5 bar (once per bar). False when nothing new."""
    frame = ctx.store.tail(Timeframe.M5, 1)
    if frame.height == 0:
        return False
    latest = int(frame["timestamp"].dt.epoch("us").to_list()[0])
    last = ctx.desk.store.last_logged_bar()
    if last is not None and latest <= last:
        return False
    decision = live_decision(ctx)
    if decision is None:
        return False
    state = decision.state
    return ctx.desk.store.log_decision(
        {
            "bar_open_us": latest,
            "logged_at": moment.astimezone(UTC).isoformat(),
            "action": decision.action,
            "readiness_level": decision.readiness_level,
            "bias": decision.bias,
            "refusals": json.dumps(list(decision.refusals)),
            "price": None if state is None else state.price,
            "spread_points": None if state is None else state.spread,
            "atr_m15": decision.atr,
            "market_status": ctx.calendar.status(moment).value,
            "data_quality": None if state is None else state.data_quality,
            "decision_id": decision.decision_id,
            "strategy_version": decision.strategy_version,
            "setup_id": decision.setup_id or None,
        }
    )


def sync_mirrors(ctx: AppContext, moment: datetime) -> int:
    """Bring every mirror up to date with the newest local backup (retry a failure every 5 min)."""
    status = engine_status(ctx)
    folder = ctx.settings.paper_db.parent / "backups"
    local = sorted(folder.glob("paper-*.sqlite3"))
    if not local:
        return 0
    newest, done = local[-1], 0
    for mirror in status.mirrors:
        if mirror.last_file == newest.name:
            continue
        if mirror.last_attempt is not None and (moment - mirror.last_attempt).total_seconds() < 300:
            continue
        done += int(sync_mirror(mirror, newest, ctx.settings.backup_keep, moment))
    return done


def maybe_backup(ctx: AppContext, moment: datetime) -> Path | None:
    """One online backup per UTC day (and at start), keeping the newest ``backup_keep``; then the
    mirrors (which also catch up when a mirror was unreachable at the time)."""
    status = engine_status(ctx)
    if status.last_backup is not None and status.last_backup.date() == moment.date():
        sync_mirrors(ctx, moment)
        return None
    folder = ctx.settings.paper_db.parent / "backups"
    target = ctx.desk.store.backup_to(folder / f"paper-{moment:%Y%m%d-%H%M%S}.sqlite3")
    status.last_backup = moment
    for old in sorted(folder.glob("paper-*.sqlite3"))[: -ctx.settings.backup_keep]:
        old.unlink(missing_ok=True)
    sync_mirrors(ctx, moment)
    return target


def engine_tick(ctx: AppContext, now: datetime | None = None) -> list[str]:
    """One pass: manage open positions with new bars, log the forward observation, (auto mode)
    open a valid plan. Returns the ids changed (closed or opened) so the caller can tell clients.
    """
    moment = now or datetime.now(UTC)
    desk = ctx.desk
    changed: list[str] = []
    bid, ask = _quote_prices(ctx, moment)
    open_rows = desk.store.positions("OPEN", 50)
    if open_rows:
        floor = min(int(r["last_bar_us"]) for r in open_rows)
        changed += desk.manage(moment, minute_bars(ctx, floor), bid, ask)
    if log_forward(ctx, moment):
        engine_status(ctx).logged_bars += 1
    live_intelligence(ctx)  # records every state transition in decision_events (event-driven)
    if desk.auto and desk.open_row() is None:
        decision = live_decision(ctx)
        if (
            decision is not None
            and decision.action in ("BUY", "SELL")
            and decision.expiry is not None
            and decision.expiry > moment
        ):
            spec, _ = _spec(ctx)
            row = desk.open_position(moment, decision, spec, "AUTO")
            if row is not None:
                changed.append(row["id"])
    return changed


async def run_engine(ctx: AppContext) -> None:
    """The background loop (cancelled at shutdown). An error never stops it; it is counted and shown."""
    status = engine_status(ctx)
    status.integrity = await asyncio.to_thread(ctx.desk.store.integrity)
    await asyncio.to_thread(startup_notice, ctx, datetime.now(UTC))
    if status.integrity:
        log.error("paper database integrity problems", extra={"problems": status.integrity})
    last_alert_pass = 0.0
    while True:
        started = time.perf_counter()
        try:
            changed = await asyncio.to_thread(engine_tick, ctx)
            await asyncio.to_thread(maybe_backup, ctx, datetime.now(UTC))
            status.ticks += 1
            status.last_ok = datetime.now(UTC)
            if changed:
                log.info("paper engine", extra={"changed": changed})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            status.errors += 1
            status.last_error, status.last_error_at = (
                f"{type(exc).__name__}: {exc}",
                datetime.now(UTC),
            )
            log.exception("paper engine pass failed")
        status.last_ms = (time.perf_counter() - started) * 1000
        if time.monotonic() - last_alert_pass >= ALERT_PASS_SECONDS:
            last_alert_pass = time.monotonic()
            try:  # an alerting failure is logged but never counted against the engine
                await asyncio.to_thread(evaluate_alerts, ctx)
            except Exception:
                log.exception("alert evaluation failed")
        await asyncio.sleep(ctx.settings.paper_poll_seconds)
