"""PAPER ACCEPTANCE REPLAY source: historical CLOSED bars served through the live-source interface.

It lets the real ``TradeEngine`` -> ``decision_core`` -> ``PaperDesk`` -> journal path run on burned
development data with no special trade logic. Differences from live, all explicit:

* the quote is the close of the last closed M1 bar (bid) plus that bar's spread (ask);
* every timeframe is FRESH and the collector is "alive" (history has no outages);
* the broker specification is the current one from ``live.json``.

It proves the pipeline end to end (decision, paper open, price evolution, SL/TP/time exit,
journal, markers). It does NOT prove live execution or any edge, and it refuses windows outside the
burned period. Nothing here can reach MT5.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl

from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.ledger import BarLedger
from xau_edge.market_data.session import market_status
from xau_edge.market_data.validators.market_calendar import MarketCalendar
from xau_edge.trading.frames import ORDER, MultiTfBars, from_frames
from xau_edge.trading.live_source import (
    REQUIRED,
    TAILS,
    LiveSnapshot,
    LiveTradingMarketSource,
    QuoteView,
    spec_from_broker,
)

BURNED_FROM = datetime(2025, 5, 1, tzinfo=UTC)
BURNED_TO = datetime(2026, 5, 1, tzinfo=UTC)
WARMUP = {
    Timeframe.M1: timedelta(days=4),
    Timeframe.M5: timedelta(days=10),
    Timeframe.M15: timedelta(days=20),
    Timeframe.M30: timedelta(days=30),
    Timeframe.H1: timedelta(days=60),
    Timeframe.H4: timedelta(days=200),
}


class ReplayMarketSource(LiveTradingMarketSource):
    """Serves ``LiveSnapshot`` objects for a moving replay clock (``set_time``)."""

    SOURCE_MODE = "ACCEPTANCE_REPLAY"

    def __init__(
        self,
        root: Path | str,
        calendar: MarketCalendar,
        start: datetime,
        end: datetime,
        *,
        symbol: str = "XAUUSD",
    ) -> None:
        super().__init__(root, calendar, symbol=symbol)
        if start < BURNED_FROM or end > BURNED_TO:
            msg = "refused: replay windows must lie inside the burned period 2025-05-01..2026-04-30"
            raise ValueError(msg)
        ledger = BarLedger(self.root)
        self.frames = from_frames(
            {
                tf: ledger.load(
                    symbol, tf, max(start - w, BURNED_FROM), min(end + timedelta(days=1), BURNED_TO)
                )
                for tf, w in WARMUP.items()
            }
        ).frames
        live_path = self.root / "live.json"
        live = json.loads(live_path.read_text(encoding="utf-8")) if live_path.exists() else {}
        self._spec = spec_from_broker(live.get("symbol_spec"))
        self.now = start
        self.fault: str | None = None
        """Test-only fault for acceptance runs: STALE_DATA, COLLECTOR_DOWN or NO_SPEC."""

    def set_time(self, now: datetime) -> None:
        self.now = now

    def _closed(self, tf: Timeframe) -> pl.DataFrame:
        frame = self.frames[tf]
        return frame.filter(pl.col("available_at") <= self.now)

    def latest_m1_open(self) -> datetime | None:
        closed = self._closed(Timeframe.M1)
        if closed.height == 0:
            return None
        newest = closed["timestamp"][-1]
        return newest if isinstance(newest, datetime) else None

    def current_quote(self, now: datetime) -> QuoteView | None:
        closed = self.frames[Timeframe.M1].filter(pl.col("available_at") <= now)
        if closed.height == 0:
            return None
        bid = float(closed["close"][-1])
        spread = float(closed["spread"][-1])
        point = self._spec.point if self._spec else 0.01
        age = 120.0 if self.fault == "STALE_DATA" else 0.0
        return QuoteView(bid, bid + spread * point, spread, now, age)

    def collector_alive(self, now: datetime) -> bool:
        return self.fault != "COLLECTOR_DOWN"

    def load(self, now: datetime | None = None) -> LiveSnapshot:
        stamp = now or self.now
        self.now = stamp
        frames = {tf: self._closed(tf).tail(TAILS[tf]) for tf in ORDER if tf in self.frames}
        bars = MultiTfBars({tf: df for tf, df in frames.items() if df.height})
        m1 = frames.get(Timeframe.M1)
        latest = None
        if m1 is not None and m1.height:
            newest = m1["available_at"][-1]
            latest = newest if isinstance(newest, datetime) else None
        return LiveSnapshot(
            now=stamp,
            bars=bars,
            quote=self.current_quote(stamp),
            spec=None if self.fault == "NO_SPEC" else self._spec,
            status=market_status(stamp, self.calendar),
            stale_timeframes=tuple(tf.value for tf in REQUIRED)
            if self.fault == "STALE_DATA" and market_status(stamp, self.calendar).value == "OPEN"
            else (),
            freshness={
                tf.value: "STALE" if self.fault == "STALE_DATA" else "FRESH" for tf in bars.frames
            },
            collector_alive=self.collector_alive(stamp),
            latest_m1_close=latest,
            problems=(),
        )
