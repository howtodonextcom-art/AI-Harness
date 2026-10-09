"""Read-only MT5 market data endpoints (``/md/*``) over the bar ledger and the collector's files.

The API never opens an MT5 connection: the collector owns the terminal and publishes ``live.json``
(quote, forming bars, recent ticks) and ``collector_status.json``; closed bars come from the ledger.
Transport is polling (the UI refreshes about once a second): simple, restart-safe, proxy-friendly.
Closed bars are the default; the forming bar is added only on request and is marked
``is_closed=false`` so no scientific consumer can take it by accident. Volume is TICK volume.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import polars as pl
from fastapi import FastAPI, HTTPException, Query

from xau_edge.domain.market import FeedHealth, MarketStatus
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.collector import read_status_file
from xau_edge.market_data.ledger import BarLedger, LedgerError
from xau_edge.market_data.session import market_status
from xau_edge.market_data.validators.market_calendar import MarketCalendar

STALE_QUOTE_SECONDS = 30.0
MAX_BARS = 5000
MAX_TICKS = 500


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


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
    cal = calendar or MarketCalendar()

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

    @app.get("/md/status")
    def md_status() -> dict[str, Any]:
        status = read_status_file(root / "collector_status.json", now=now())
        status["market_status"] = market_status(now(), cal).value
        status["source"] = "FTMO MT5"
        status["volume_type"] = "TICK_VOLUME"
        return status

    @app.get("/md/{sym}/quote")
    def md_quote(sym: str) -> dict[str, Any]:
        check(sym)
        live = _read_json(root / "live.json")
        status = market_status(now(), cal)
        if live is None or not isinstance(live.get("quote"), dict):
            return {"available": False, "stale": True, "market_status": status.value,
                    "note": "collector has not published a quote"}  # fmt: skip
        quote: dict[str, Any] = live["quote"]
        stamp = quote.get("timestamp")
        age = None
        if stamp:
            age = (now() - datetime.fromisoformat(stamp)).total_seconds()
        file_age = (now() - datetime.fromisoformat(live["updated_at"])).total_seconds()
        trading = status in (MarketStatus.OPEN, MarketStatus.UNKNOWN)
        stale = trading and (
            age is None or age > STALE_QUOTE_SECONDS or file_age > STALE_QUOTE_SECONDS
        )
        extra = {"available": True, "age_seconds": age, "stale": stale, "source": "FTMO MT5"}
        extra |= {"market_status": status.value, "collector_age_seconds": file_age}
        return {**quote, **extra}

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
            frame = ledger.load(symbol, tf, end=end).tail(limit)
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
