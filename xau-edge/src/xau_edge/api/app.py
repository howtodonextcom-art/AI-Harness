"""FastAPI application: read-only research endpoints (brief section 33).

There is no endpoint that can place, modify or cancel a REAL order. The one write endpoint is
``POST /paper/orders``: it takes no trade parameters from the client and reaches only the paper
broker. A test walks the route table and fails if any other route accepts a non-GET method.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict

from xau_edge import __version__ as package_version
from xau_edge.api.service import (
    SYMBOL,
    ApiContext,
    analogue_view,
    backtest_records,
    bars_view,
    features_view,
    json_dict,
    model_records,
    regime_view,
)
from xau_edge.domain.timeframe import Timeframe
from xau_edge.execution.trader import TradeOutcome
from xau_edge.signals.engine import EVIDENCE_FAMILY, evidence_params, generate_signal
from xau_edge.signals.evidence import evidence_status

ALLOWED_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000")


class PaperOrderRequest(BaseModel):
    """The only client input to the paper endpoint: which decision bar (default: the latest)."""

    model_config = ConfigDict(extra="forbid")

    at: str | None = None


TimeframeParam = Annotated[str, Query(description="M5, M15, H1 or H4")]


def _symbol(symbol: str) -> None:
    if symbol.upper() != SYMBOL:
        raise HTTPException(status_code=404, detail=f"unsupported symbol {symbol!r}; only {SYMBOL}")


def _timeframe(value: str) -> Timeframe:
    try:
        return Timeframe.parse(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _bounds(ctx: ApiContext) -> tuple[datetime, datetime]:
    m15 = ctx.frames().m15["timestamp"]
    first, latest = m15.min(), m15.max()
    if not isinstance(first, datetime) or not isinstance(latest, datetime):
        raise HTTPException(status_code=503, detail="no market data loaded")
    return first, latest + Timeframe.M15.delta


def _at(ctx: ApiContext, at: str | None) -> datetime:
    first, last = _bounds(ctx)
    if at is None:
        return last
    try:
        parsed = datetime.fromisoformat(at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise HTTPException(status_code=422, detail="at must include a timezone, e.g. ...Z")
    moment = parsed.astimezone(UTC)
    if not first <= moment <= last:
        raise HTTPException(
            status_code=422,
            detail=f"at must be within the data range {first.isoformat()}..{last.isoformat()}",
        )
    return moment


def _decision_bar(at: datetime) -> datetime:
    """The M15 close at or before ``at`` (cache key: all times inside one bar share a result)."""
    minutes = at.hour * 60 + at.minute
    floored = minutes - minutes % Timeframe.M15.minutes
    return at.replace(hour=floored // 60, minute=floored % 60, second=0, microsecond=0)


def create_app(ctx: ApiContext) -> FastAPI:  # noqa: PLR0915 - one small function per route
    """Build the application around an ``ApiContext`` (data, registry, limits)."""
    app = FastAPI(title="XAU EDGE", version=package_version, docs_url="/docs", redoc_url=None)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(ALLOWED_ORIGINS),
        allow_methods=["GET"],
        allow_headers=["Accept", "Content-Type"],
    )

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "version": package_version, "live_trading": False}

    @app.get("/market/{symbol}")
    def market(
        symbol: str,
        timeframe: TimeframeParam = "M15",
        limit: Annotated[int, Query(ge=1, le=5000)] = 500,
    ) -> dict[str, Any]:
        _symbol(symbol)
        tf = _timeframe(timeframe)
        return {"symbol": SYMBOL, "timeframe": tf.value, "bars": bars_view(ctx.frames(), tf, limit)}

    @app.get("/features/{symbol}")
    def features(
        symbol: str,
        timeframe: TimeframeParam = "M15",
        limit: Annotated[int, Query(ge=1, le=500)] = 50,
    ) -> dict[str, Any]:
        _symbol(symbol)
        tf = _timeframe(timeframe)
        return {
            "symbol": SYMBOL,
            "timeframe": tf.value,
            "rows": features_view(ctx.frames(), tf, limit),
        }

    @app.get("/regime/{symbol}")
    def regime(symbol: str) -> dict[str, Any]:
        _symbol(symbol)
        return {"symbol": SYMBOL, **regime_view(ctx.frames())}

    @app.get("/patterns/{symbol}")
    def patterns(
        symbol: str, at: str | None = None, k: Annotated[int, Query(ge=1, le=20)] = 10
    ) -> dict[str, Any]:
        _symbol(symbol)
        moment = _at(ctx, at)
        view = ctx.cached(
            f"patterns-{k}", _decision_bar(moment), lambda: analogue_view(ctx.frames(), moment, k)
        )
        return {"symbol": SYMBOL, **view}

    @app.get("/signals/{symbol}")
    def signals(symbol: str, at: str | None = None) -> dict[str, Any]:
        _symbol(symbol)
        moment = _at(ctx, at)
        provider = ctx.signal_provider or (
            lambda when: generate_signal(ctx.frames(), when, ctx.registry)
        )
        signal = ctx.cached("signal", _decision_bar(moment), lambda: provider(moment))
        body = json_dict(signal.model_dump(mode="json"))
        reasons = body["reasons"]
        body["news_status"] = (
            "unknown"
            if "NEWS_UNKNOWN" in reasons
            else "risk"
            if "NEWS_RISK" in reasons
            else "clear"
        )
        body["data_as_of"] = _bounds(ctx)[1].isoformat()
        return body

    @app.post("/paper/orders")
    def paper_order(request: PaperOrderRequest | None = None) -> dict[str, Any]:
        """Offer the CURRENT signal to the paper trader.

        The client chooses nothing about the trade: direction, levels and size all come from the
        server-side signal after the risk engine and safety checks. It can only reach the paper
        broker; WAIT (the normal answer) places nothing.
        """
        if ctx.paper is None:
            raise HTTPException(status_code=503, detail="paper trading is not configured")
        frames = ctx.frames()
        _, last = _bounds(ctx)
        moment = _at(ctx, request.at if request else None)
        if _decision_bar(moment) != _decision_bar(last):
            raise HTTPException(
                status_code=422, detail="paper orders are only accepted for the latest decision bar"
            )
        provider = ctx.signal_provider or (lambda when: generate_signal(frames, when, ctx.registry))
        signal = ctx.cached("signal", _decision_bar(moment), lambda: provider(moment))
        age = ctx.clock() - last
        stale = age.total_seconds() > ctx.max_data_age_minutes * 60
        m5 = frames.m5.tail(1)
        spread = float(m5["spread"][0])
        with ctx._paper_lock:
            if stale:
                outcome = TradeOutcome(False, ("DATA_STALE",))
            else:
                ctx.paper.broker.set_quote(last, bid=float(m5["close"][0]), spread_points=spread)
                outcome = ctx.paper.on_signal(signal, last, spread_points=spread)
        return json_dict(
            {
                "accepted": outcome.accepted,
                "dry_run": outcome.dry_run,
                "reasons": list(outcome.reasons),
                "position_id": outcome.position_id,
                "lots": outcome.lots,
                "signal_direction": signal.direction.value,
                "signal_hash": signal.inputs_hash,
                "data_as_of": last.isoformat(),
            }
        )

    @app.get("/paper/account")
    def paper_account() -> dict[str, Any]:
        if ctx.paper is None:
            raise HTTPException(status_code=503, detail="paper trading is not configured")
        return json_dict(ctx.paper.broker.get_account().model_dump())

    @app.get("/paper/positions")
    def paper_positions() -> dict[str, Any]:
        if ctx.paper is None:
            raise HTTPException(status_code=503, detail="paper trading is not configured")
        return {"positions": [json_dict(p.model_dump()) for p in ctx.paper.broker.get_positions()]}

    @app.get("/backtests")
    def backtests() -> dict[str, Any]:
        return {"runs": backtest_records(ctx.registry)}

    @app.get("/backtests/{run_id}")
    def backtest(run_id: str) -> dict[str, Any]:
        try:
            record = ctx.registry.get(run_id)
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail="no such run") from exc
        return json_dict(record.model_dump(mode="json"))

    @app.get("/models")
    def models() -> dict[str, Any]:
        return {"models": model_records(ctx.models_dir)}

    @app.get("/risk/status")
    def risk_status() -> dict[str, Any]:
        return {
            "live_trading": False,
            "kill_switch": {
                "tripped": ctx.paper.risk.kill_switch.tripped if ctx.paper else False,
                "reason": ctx.paper.risk.kill_switch.reason if ctx.paper else "",
                "note": "read-only application: no executor is running",
            },
            "limits": ctx.limits.model_dump(mode="json"),
            "prop_profile": {
                "name": ctx.prop.name,
                "daily_loss_limit_pct": ctx.prop.daily_loss_limit_pct,
                "max_loss_limit_pct": ctx.prop.max_loss_limit_pct,
                "max_loss_kind": ctx.prop.max_loss_kind,
                "verified_on": ctx.prop.verified_on.isoformat(),
                "ea_restrictions": ctx.prop.ea_restrictions,
            },
            "evidence_status": evidence_status(
                ctx.registry, family=EVIDENCE_FAMILY, params=evidence_params()
            ).value,
        }

    return app
