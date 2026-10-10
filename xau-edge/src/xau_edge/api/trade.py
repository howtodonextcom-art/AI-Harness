"""The ``/trade/*`` routes: the live paper-trading desk (read-only data + two paper actions).

GET routes only read the engine's current decision. The two POST routes (``/trade/paper/open`` and
``/trade/paper/close``) reach the PAPER desk only: the client names a ``setup_id`` or a
``trade_id``, never a price, side or size, and the server re-checks that the setup is still the
live one. No route here can reach MT5; a Host/Origin/Content-Type guard and a custom header keep a
browser tab on another site from posting to it.
"""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from xau_edge.market_data.calendars import ftmo_calendar
from xau_edge.ops.code_version import current_code_version
from xau_edge.ops.notifier import Notifier, build_dispatcher
from xau_edge.ops.process_lock import WriterLock, WriterLockError
from xau_edge.ops.settings import OpsSettings
from xau_edge.strategies.edge_program import SERVER_CLOCK
from xau_edge.trading.baseline import BaselineConfig
from xau_edge.trading.engine import EngineConfig, TradeEngine
from xau_edge.trading.live_source import LiveTradingMarketSource
from xau_edge.trading.namespace import claim_root
from xau_edge.trading.paper_desk import DeskConfig, DeskRefusal, PaperDesk
from xau_edge.trading.risk_calc import RISK_CHOICES
from xau_edge.trading.setup_alerts import SetupAlerts
from xau_edge.trading.telemetry import DecisionTelemetry

_LOG = logging.getLogger(__name__)
DESK_HEADER = "x-paper-desk"
STEP_SECONDS = 5.0


def build_trade_engine(
    market_root: Path,
    trade_root: Path,
    *,
    code_version: str | None = None,
    source: LiveTradingMarketSource | None = None,
    clock: Callable[[], datetime] | None = None,
    baseline_version: str | None = None,
    notifier: Notifier | None = None,
) -> TradeEngine:
    """The production wiring: collector files in, paper desk + journal + alerts out.

    ``source`` / ``clock`` / ``notifier`` exist for the acceptance replay, which runs THE SAME
    wiring (writer lock, desk, alerts, engine) over burned bars with a replay clock; the source
    decides the namespace (LIVE or ACCEPTANCE_REPLAY) and a root can never mix the two.
    """
    code_version = code_version or current_code_version()
    source = source or LiveTradingMarketSource(market_root, ftmo_calendar())
    mode = source.SOURCE_MODE
    claim_root(trade_root, mode)
    lock = WriterLock(trade_root / "writer.lock", role="trade-engine", code_version=code_version)
    writer_error: str | None = None
    try:
        lock.acquire()
    except WriterLockError as exc:  # another API process owns the desk: read-only, loudly
        writer_error = f"SINGLE WRITER CONFLICT: {exc}"
        _LOG.error(writer_error)
    now = clock or (lambda: datetime.now(UTC))
    desk = PaperDesk(
        trade_root,
        DeskConfig(),
        code_version=code_version,
        clock=now,
        writable=writer_error is None,
        source_mode=mode,
    )
    telegram = notifier is None and OpsSettings().telegram_configured  # a boolean only
    alerts = (
        None
        if writer_error
        else SetupAlerts(
            build_dispatcher(notifier=notifier, fallback_path=trade_root / "alerts.jsonl"),
            trade_root / "alerts_state.json",
            delivery="TELEGRAM" if telegram else "FILE_FALLBACK",
        )
    )
    version = baseline_version or os.environ.get("XAU_EDGE_BASELINE_VERSION", "1.1.0")
    if version not in ("1.1.0", "1.2.0", "1.2.1"):
        msg = f"XAU_EDGE_BASELINE_VERSION must be 1.1.0, 1.2.0 or 1.2.1, not {version!r}"
        raise ValueError(msg)
    auto_paper = os.environ.get("XAU_EDGE_AUTO_PAPER", "false").lower() == "true"
    engine = TradeEngine(
        source,
        desk,
        EngineConfig(
            root=trade_root,
            code_version=code_version,
            baseline=BaselineConfig(allow_unknown_news=True, version=version),
            auto_paper=auto_paper and mode == "LIVE",  # never auto-open inside a replay
        ),
        broker_clock=SERVER_CLOCK,
        alerts=alerts,
        telemetry=DecisionTelemetry(trade_root, source_mode=mode),
        clock=now,
    )
    engine.writer_error = writer_error
    engine.writer_lock = lock  # held for the life of the process
    return engine


class EngineRunner:
    """Calls ``engine.step`` every few seconds on a daemon thread (errors never kill it)."""

    def __init__(self, engine: TradeEngine, interval: float = STEP_SECONDS) -> None:
        self.engine = engine
        self.interval = interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="trade-engine", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.engine.step()
            except Exception:
                _LOG.exception("trade engine step failed")
            self._stop.wait(self.interval)


class OpenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    setup_id: str = Field(min_length=8, max_length=64)
    risk_pct: float = Field(gt=0, le=0.5)


class CloseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trade_id: str = Field(min_length=4, max_length=64)


def _refusal(exc: DeskRefusal) -> HTTPException:
    return HTTPException(status_code=409, detail={"code": exc.code, "message": exc.message})


def add_trade_routes(  # noqa: PLR0915 - one small function per route
    app: FastAPI, engine: TradeEngine, *, port: int, allowed_origins: tuple[str, ...]
) -> None:
    hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}

    def guard(request: Request) -> None:
        if request.headers.get("host", "").lower() not in hosts:
            raise HTTPException(status_code=403, detail={"code": "BAD_HOST"})
        if request.headers.get("origin") not in allowed_origins:
            raise HTTPException(status_code=403, detail={"code": "BAD_ORIGIN"})
        ctype = request.headers.get("content-type", "").split(";")[0].strip().lower()
        if ctype != "application/json":
            raise HTTPException(status_code=403, detail={"code": "BAD_CONTENT_TYPE"})
        if request.headers.get(DESK_HEADER) != "1":
            raise HTTPException(status_code=403, detail={"code": "MISSING_DESK_HEADER"})

    def local_host(request: Request) -> None:
        """Reads are local too (a DNS-rebinding page must not read the desk)."""
        if request.headers.get("host", "").lower() not in hosts:
            raise HTTPException(status_code=403, detail={"code": "BAD_HOST"})

    reader = [Depends(local_host)]

    @app.get("/trade/decision", dependencies=reader)
    def decision() -> dict[str, Any]:
        """The current decision. It also advances the engine to now (it never touches MT5)."""
        engine.step()
        return engine.view()

    @app.get("/trade/risk", dependencies=reader)
    def risk(
        entry: Annotated[float, Query(gt=0)],
        stop_loss: Annotated[float, Query(gt=0)],
        take_profit: Annotated[float | None, Query(gt=0)] = None,
        risk_pct: Annotated[float, Query(gt=0, le=0.5)] = 0.25,
        equity: Annotated[float | None, Query(gt=0)] = None,
    ) -> dict[str, Any]:
        return engine.risk(
            equity=equity,
            risk_pct=risk_pct,
            entry=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

    @app.get("/trade/paper", dependencies=reader)
    def paper() -> dict[str, Any]:
        now = engine.now()
        with engine.lock:
            quote = engine.current_quote(now)
            return {
                "simulated": True,
                "risk_choices": list(RISK_CHOICES),
                "account": engine.desk.account(quote, now),
                "position": engine.desk.position_view(quote, now),
                "today": engine.desk.day_summary(now),
            }

    @app.get("/trade/journal", dependencies=reader)
    def journal(limit: Annotated[int, Query(ge=1, le=1000)] = 100) -> dict[str, Any]:
        with engine.lock:
            return {
                "simulated": True,
                "source_mode": engine.source_mode,
                "desk_fault": engine.desk.load_error or engine.desk.integrity_error,
                "open": engine.desk.open_trade(),
                "trades": engine.desk.closed_trades()[:limit],
                "evidence": engine.evidence(),
            }

    @app.get("/trade/markers", dependencies=reader)
    def markers(days: Annotated[int, Query(ge=1, le=14)] = 3) -> dict[str, Any]:
        """Chart markers from the REAL objects: logged actionable decisions and paper trades."""
        now = engine.now()
        with engine.lock:
            trades = list(engine.desk.trades.values())
        mode = engine.source_mode
        taken = {t["setup_id"] for t in trades}
        signals: list[dict[str, Any]] = []
        for back in range(days):
            for record in engine.telemetry.read_signals(now - timedelta(days=back)):
                if record.get("source_mode", "LIVE") != mode:
                    continue  # replay / fixture records never appear as live markers
                signals.append(
                    {
                        **record,
                        "price": record.get("entry"),
                        "source_mode": mode,
                        "taken": record["setup_id"] in taken,
                    }
                )
        paper = [
            {
                "trade_id": t["trade_id"],
                "side": t["side"],
                "status": t["status"],
                "entry_time": t.get("opened_at"),
                "entry_price": t.get("fill_price"),
                "exit_time": t.get("closed_at"),
                "exit_price": t.get("exit_price"),
                "exit_reason": t.get("exit_reason"),
                "net_pnl": t.get("net_pnl"),
                "r_multiple": t.get("r_multiple"),
                "duration_minutes": t.get("duration_minutes"),
                "sl": t.get("sl"),
                "initial_sl": t.get("initial_sl"),
                "tp": t.get("tp"),
                "strategy_version": t.get("strategy_version"),
            }
            for t in trades
            if t["status"] in ("OPEN", "CLOSED") and t.get("source_mode", "LIVE") == mode
        ]
        return {"simulated": True, "source_mode": mode, "signals": signals, "paper_trades": paper}

    @app.get("/trade/signals", dependencies=reader)
    def signal_history(limit: Annotated[int, Query(ge=1, le=200)] = 30) -> dict[str, Any]:
        """Recent actionable decisions of THIS source mode (never mixed with replay)."""
        now = engine.now()
        mode = engine.source_mode
        with engine.lock:
            taken = {t["setup_id"] for t in engine.desk.trades.values()}
        rows: list[dict[str, Any]] = []
        for back in range(14):
            for record in engine.telemetry.read_signals(now - timedelta(days=back)):
                if record.get("source_mode", "LIVE") == mode:
                    rows.append({**record, "taken": record["setup_id"] in taken})
        rows.sort(key=lambda r: str(r.get("at")), reverse=True)
        return {"source_mode": mode, "signals": rows[:limit]}

    @app.get("/trade/telemetry", dependencies=reader)
    def telemetry() -> dict[str, Any]:
        return engine.telemetry.summary(engine.now())

    @app.post("/trade/paper/open")
    def paper_open(body: OpenRequest, request: Request) -> dict[str, Any]:
        guard(request)
        try:
            return engine.paper_open(setup_id=body.setup_id, risk_pct=body.risk_pct)
        except DeskRefusal as exc:
            raise _refusal(exc) from exc

    @app.post("/trade/paper/close")
    def paper_close(body: CloseRequest, request: Request) -> dict[str, Any]:
        guard(request)
        try:
            return engine.paper_close(body.trade_id)
        except DeskRefusal as exc:
            raise _refusal(exc) from exc
