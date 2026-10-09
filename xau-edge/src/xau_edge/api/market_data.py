"""Read-only MT5 market data endpoints (``/md/*``) over the bar ledger and the collector's files.

The API never opens an MT5 connection: the collector owns the terminal and publishes ``live.json``
(quote, forming bars, recent ticks) and ``collector_status.json``; closed bars come from the ledger.
Transport is polling (the UI refreshes about once a second): simple, restart-safe, proxy-friendly.
Closed bars are the default; the forming bar is added only on request and is marked
``is_closed=false`` so no scientific consumer can take it by accident. Volume is TICK volume.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

import polars as pl
from fastapi import FastAPI, HTTPException, Query

from xau_edge.domain.market import FeedHealth, MarketStatus
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.calendars import ftmo_calendar
from xau_edge.market_data.collector import read_status_file
from xau_edge.market_data.freshness import bar_freshness, missed_closed_bars
from xau_edge.market_data.ledger import BarLedger, LedgerError
from xau_edge.market_data.session import market_status
from xau_edge.market_data.tick_ledger import TickLedger, TickLedgerError
from xau_edge.market_data.validators.market_calendar import MarketCalendar

STALE_QUOTE_SECONDS = 30.0
MAX_BARS = 5000
MAX_TICKS = 500
MAX_HISTORY_TICKS = 5000
MAX_HISTORY_SPAN = timedelta(hours=1)
COLLECTOR_RUNNING_SECONDS = 30.0
COLLECTOR_STOPPED_SECONDS = 600.0


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _parse_utc(value: str, name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"{name} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise HTTPException(status_code=422, detail=f"{name} needs a timezone, e.g. ...Z")
    return parsed.astimezone(UTC)


def _bar_rows(frame: pl.DataFrame, *, closed: bool) -> list[dict[str, Any]]:
    return [
        {
            "time": r["timestamp"].isoformat(),
            "open": r["open"], "high": r["high"], "low": r["low"], "close": r["close"],
            "tick_volume": r["tick_volume"], "spread": r["spread"], "is_closed": closed,
        }
        for r in frame.iter_rows(named=True)
    ]  # fmt: skip


def add_market_data_routes(  # noqa: PLR0915 - one small function per route
    app: FastAPI,
    root: Path,
    *,
    symbol: str = "XAUUSD",
    calendar: MarketCalendar | None = None,
    clock: Any = None,
) -> None:
    """Mount the GET-only market data routes (``root`` is the ledger/collector directory)."""
    ledger = BarLedger(root)
    tick_ledger = TickLedger(root)
    cal = calendar or ftmo_calendar()

    def now() -> datetime:
        return clock() if clock else datetime.now(UTC)

    def check(sym: str) -> None:
        if sym.upper() != symbol:
            raise HTTPException(status_code=404, detail=f"unsupported symbol {sym!r}")

    def parse_tf(value: str) -> Timeframe:
        try:
            return Timeframe.parse(value)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    def collector_state(age: float | None) -> str:
        if age is None:
            return "STOPPED"
        if age <= COLLECTOR_RUNNING_SECONDS:
            return "RUNNING"
        return "STALE" if age <= COLLECTOR_STOPPED_SECONDS else "STOPPED"

    def quote_view() -> dict[str, Any]:
        live = _read_json(root / "live.json")
        status = market_status(now(), cal)
        closed = status not in (MarketStatus.OPEN, MarketStatus.UNKNOWN)
        if live is None or not isinstance(live.get("quote"), dict):
            return {"available": False, "stale": True, "state": "UNAVAILABLE",
                    "market_status": status.value, "reason": "no quote published yet",
                    "note": "collector has not published a quote"}  # fmt: skip
        quote: dict[str, Any] = live["quote"]
        stamp = quote.get("timestamp")
        age = (now() - datetime.fromisoformat(stamp)).total_seconds() if stamp else None
        file_age = (now() - datetime.fromisoformat(live["updated_at"])).total_seconds()
        collector_alive = file_age <= STALE_QUOTE_SECONDS
        old = age is None or age > STALE_QUOTE_SECONDS
        stale = not closed and (old or not collector_alive)
        if closed:
            state = "MARKET_CLOSED"
            reason = f"market is {status.value.lower()}: the last tick is expected to be old"
        elif not collector_alive:
            state = "STALE"
            reason = f"the collector stopped publishing {file_age:.0f}s ago"
        elif old:
            state = "STALE"
            reason = f"market is open but the last tick is {age:.0f}s old"
        else:
            state, reason = "FRESH", "last tick is recent"
        extra = {"available": True, "age_seconds": age, "stale": stale, "source": "FTMO MT5"}
        extra |= {"market_status": status.value, "collector_age_seconds": file_age}
        extra |= {"state": state, "reason": reason, "last_tick_time": stamp}
        return {**quote, **extra}

    def bars_freshness(stamp: datetime) -> dict[str, str]:
        """Freshness computed HERE from the ledger and calendar, never taken from the collector.

        A dead collector can only report the state it last saw; the API must notice on its own.
        """
        out: dict[str, str] = {}
        for tf in Timeframe:
            try:
                latest = ledger.latest(symbol, tf)
            except LedgerError:
                out[tf.value] = "UNKNOWN"
                continue
            out[tf.value] = bar_freshness(missed_closed_bars(latest, tf, stamp, cal), tf)
        return out

    @app.get("/md/status")
    def md_status() -> dict[str, Any]:
        stamp = now()
        status = read_status_file(root / "collector_status.json", now=stamp)
        age = status.get("status_age_seconds")
        collector = collector_state(age if isinstance(age, int | float) else None)
        market = market_status(stamp, cal)
        quote = quote_view()
        fresh = bars_freshness(stamp)
        status["freshness"] = fresh
        if not fresh:
            bars = "UNKNOWN"
        elif any(v == "STALE" for v in fresh.values()):
            bars = "STALE"
        else:
            bars = (
                "FRESH" if market in (MarketStatus.OPEN, MarketStatus.UNKNOWN) else "MARKET_CLOSED"
            )
        terminal = "UNKNOWN"
        if collector == "RUNNING":
            terminal = "CONNECTED" if status.get("connected") else "DISCONNECTED"
        action = None
        if collector != "RUNNING":
            action = "Run scripts/start_market_stack.ps1 (status_market_stack.ps1 shows why)."
        elif terminal == "DISCONNECTED":
            action = "Open the FTMO MT5 terminal and log in; the collector reconnects by itself."
        status |= {
            "market_status": market.value, "source": "FTMO MT5", "volume_type": "TICK_VOLUME",
            "components": {"terminal": terminal, "collector": collector, "api": "CONNECTED",
                           "market": market.value, "quote": quote["state"], "bars": bars},
            "recovery_action": action,
        }  # fmt: skip
        return status

    @app.get("/md/{sym}/quote")
    def md_quote(sym: str) -> dict[str, Any]:
        check(sym)
        return quote_view()

    @app.get("/md/{sym}/quality")
    def md_quality(sym: str) -> dict[str, Any]:
        check(sym)
        stamp = now()
        status = read_status_file(root / "collector_status.json", now=stamp)
        fresh_now = bars_freshness(stamp)
        depth = []
        for tf in Timeframe:
            try:
                first, last = ledger.earliest(symbol, tf), ledger.latest(symbol, tf)
            except LedgerError:
                first = last = None
            depth.append(
                {
                    "timeframe": tf.value,
                    "earliest": None if first is None else first.isoformat(),
                    "latest": None if last is None else last.isoformat(),
                    "rows": (status.get("stored_rows") or {}).get(tf.value),
                    "freshness": fresh_now.get(tf.value, "UNKNOWN"),
                }
            )
        events = [
            e for e in ledger.events(symbol)
            if e.get("kind") in {"BAR_CHANGED", "GAP", "RECONCILE_DIFFERENCES"}
        ][-10:]  # fmt: skip
        ticks = status.get("tick_store") or {}
        return {
            "history_depth": depth,
            "recent_events": events,
            "tick_store": ticks,
            "disk": status.get("disk") or {},
            "warnings": status.get("warnings") or [],
            "collector_health": status.get("health", "UNKNOWN"),
            "ledger_integrity": _read_json(root / "ledger-verification.json"),
        }

    @app.get("/md/{sym}/bars")
    def md_bars(
        sym: str,
        timeframe: str = "M15",
        limit: Annotated[int, Query(ge=1, le=MAX_BARS)] = 500,
        before: str | None = None,
        include_forming: bool = False,
    ) -> dict[str, Any]:
        check(sym)
        tf = parse_tf(timeframe)
        end = None
        if before:
            try:
                end = datetime.fromisoformat(before.replace("Z", "+00:00"))
            except ValueError as exc:
                raise HTTPException(status_code=422, detail="before must be ISO-8601") from exc
            if end.tzinfo is None:
                raise HTTPException(status_code=422, detail="before needs a timezone")
        try:
            frame = ledger.tail(symbol, tf, limit, end=end)
        except LedgerError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        bars = _bar_rows(frame, closed=True)
        if include_forming and end is None:
            live = _read_json(root / "live.json") or {}
            forming = (live.get("forming") or {}).get(tf.value)
            if forming and (not bars or forming["timestamp"] > bars[-1]["time"]):
                bars.append(
                    {
                        "time": forming["timestamp"], "open": forming["open"],
                        "high": forming["high"], "low": forming["low"], "close": forming["close"],
                        "tick_volume": forming["tick_volume"], "spread": forming["spread"],
                        "is_closed": False,
                    }
                )  # fmt: skip
        return {
            "symbol": symbol, "timeframe": tf.value, "source": "FTMO MT5",
            "volume_type": "TICK_VOLUME", "closed_only": not include_forming, "bars": bars,
        }  # fmt: skip

    @app.get("/md/{sym}/ticks")
    def md_ticks(
        sym: str, limit: Annotated[int, Query(ge=1, le=MAX_TICKS)] = 200
    ) -> dict[str, Any]:
        check(sym)
        live = _read_json(root / "live.json") or {}
        return {"symbol": symbol, "ticks": (live.get("ticks") or [])[-limit:], "source": "FTMO MT5"}

    @app.get("/md/{sym}/ticks/history")
    def md_ticks_history(
        sym: str,
        start: Annotated[str, Query(alias="from")],
        end: Annotated[str, Query(alias="to")],
        limit: Annotated[int, Query(ge=1, le=MAX_HISTORY_TICKS)] = 2000,
    ) -> dict[str, Any]:
        """Stored ticks in ``[from, to)``, strictly bounded in span and rows (no bulk export)."""
        check(sym)
        lo, hi = _parse_utc(start, "from"), _parse_utc(end, "to")
        if hi <= lo:
            raise HTTPException(status_code=422, detail="to must be after from")
        if hi - lo > MAX_HISTORY_SPAN:
            raise HTTPException(
                status_code=422,
                detail=f"span too large: at most {MAX_HISTORY_SPAN.total_seconds() / 60:.0f} min",
            )
        try:
            frame = tick_ledger.load(symbol, lo, hi, limit=limit + 1)
            gaps = tick_ledger.uncovered(symbol, lo, hi)
        except TickLedgerError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        truncated = frame.height > limit
        frame = frame.head(limit)
        rows = [
            [r["timestamp_msc"], r["bid"], r["ask"], r["last"], r["flags"]]
            for r in frame.iter_rows(named=True)
        ]
        return {
            "symbol": symbol, "from": lo.isoformat(), "to": hi.isoformat(),
            "columns": ["time_msc_utc", "bid", "ask", "last", "flags"],
            "ticks": rows, "truncated": truncated,
            "fully_covered": not gaps,
            "uncovered": [[a.isoformat(), b.isoformat()] for a, b in gaps],
            "source": "FTMO MT5",
        }  # fmt: skip

    @app.get("/md/{sym}/matrix")
    def md_matrix(sym: str) -> dict[str, Any]:
        check(sym)
        stamp = now()
        rows = []
        for tf in Timeframe:
            try:
                latest = ledger.latest(symbol, tf)
            except LedgerError:
                latest = None
            rows.append(
                {
                    "timeframe": tf.value,
                    "last_closed_bar_open": None if latest is None else latest.isoformat(),
                    "last_close_time": None if latest is None else (latest + tf.delta).isoformat(),
                    "age_seconds": None
                    if latest is None
                    else (stamp - (latest + tf.delta)).total_seconds(),
                }
            )  # fmt: skip
        health = read_status_file(root / "collector_status.json", now=stamp).get(
            "health", FeedHealth.UNKNOWN.value
        )
        return {"symbol": symbol, "health": health, "timeframes": rows}
