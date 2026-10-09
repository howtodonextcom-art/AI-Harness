"""The ONE production market-data adapter of the trading desk: closed canonical bars + live quote.

Reads only what the MT5 collector writes (``data/market``: the closed-bar ledger, ``live.json``,
``collector_status.json``). It never opens a connection to MT5 and never reads the legacy research
store (``data/raw``). Everything it hands to the Trading Core is closed, validated and fresh, or
the snapshot says exactly which part is not:

* only CLOSED bars (the ledger stores nothing else); the forming bar never reaches a decision;
* a timeframe is stale when it missed bars the market was open for (calendar-aware, see
  ``market_data.freshness``); a stale required timeframe or quote makes the decision WAIT
  (``STALE_DATA``), a closed market makes it WAIT (``MARKET_CLOSED``) without a stale alarm;
* the quote must be recent while the market is open; its age is part of the snapshot.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

from xau_edge.domain.market import MarketStatus
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.freshness import bar_freshness, missed_closed_bars
from xau_edge.market_data.ledger import BarLedger, LedgerError
from xau_edge.market_data.session import market_status
from xau_edge.market_data.validators.market_calendar import MarketCalendar
from xau_edge.trading.frames import FrameError, MultiTfBars, from_frames
from xau_edge.trading.sizing import SymbolSpec

_LOG = logging.getLogger(__name__)

REQUIRED = (Timeframe.H4, Timeframe.H1, Timeframe.M15, Timeframe.M5, Timeframe.M1)
"""Timeframes a decision cannot be made without (M30 is context only)."""
ALL_TIMEFRAMES = (
    Timeframe.M1,
    Timeframe.M5,
    Timeframe.M15,
    Timeframe.M30,
    Timeframe.H1,
    Timeframe.H4,
)
TAILS = {
    Timeframe.M1: 3000,
    Timeframe.M5: 2000,
    Timeframe.M15: 1500,
    Timeframe.M30: 1000,
    Timeframe.H1: 1000,
    Timeframe.H4: 600,
}
QUOTE_STALE_SECONDS = 30.0
COLLECTOR_STALE_SECONDS = 60.0


@dataclass(frozen=True)
class QuoteView:
    """The executable quote and how old it is."""

    bid: float
    ask: float
    spread_points: float
    timestamp: datetime
    age_seconds: float

    @property
    def stale(self) -> bool:
        return self.age_seconds > QUOTE_STALE_SECONDS


@dataclass(frozen=True)
class LiveSnapshot:
    """Everything one decision may look at, with the reasons it may not be trusted."""

    now: datetime
    bars: MultiTfBars
    quote: QuoteView | None
    spec: SymbolSpec | None
    status: MarketStatus
    stale_timeframes: tuple[str, ...]
    freshness: dict[str, str]
    collector_alive: bool
    latest_m1_close: datetime | None
    problems: tuple[str, ...] = field(default=())

    @property
    def market_open(self) -> bool:
        return self.status in (MarketStatus.OPEN, MarketStatus.UNKNOWN)

    @property
    def data_age_seconds(self) -> float | None:
        if self.latest_m1_close is None:
            return None
        return (self.now - self.latest_m1_close).total_seconds()

    @property
    def usable(self) -> bool:
        """True when a BUY/SELL may be computed (open, fresh bars and quote, live collector)."""
        return (
            self.market_open
            and not self.stale_timeframes
            and self.quote is not None
            and not self.quote.stale
            and self.collector_alive
        )


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def spec_from_broker(raw: dict[str, Any] | None) -> SymbolSpec | None:
    """The broker's own contract specification (never hard-coded); None when not available."""
    if not raw:
        return None
    try:
        return SymbolSpec(
            point=float(raw["point"]),
            tick_size=float(raw["trade_tick_size"]),
            tick_value=float(raw["trade_tick_value"]),
            contract_size=float(raw["trade_contract_size"]),
            volume_min=float(raw["volume_min"]),
            volume_max=float(raw["volume_max"]),
            volume_step=float(raw["volume_step"]),
            stops_level_points=int(raw.get("trade_stops_level") or 0),
            freeze_level_points=int(raw.get("trade_freeze_level") or 0),
            digits=int(raw.get("digits") or 2),
        )
    except (KeyError, TypeError, ValueError):
        return None


class LiveTradingMarketSource:
    """Loads a ``LiveSnapshot`` from the collector's files (read-only, no MT5 connection)."""

    def __init__(
        self,
        root: Path | str,
        calendar: MarketCalendar,
        *,
        symbol: str = "XAUUSD",
        tails: dict[Timeframe, int] | None = None,
    ) -> None:
        self.root = Path(root)
        self.calendar = calendar
        self.symbol = symbol
        self.ledger = BarLedger(self.root)
        self.tails = tails or TAILS

    def latest_m1_open(self) -> datetime | None:
        """Cheap change detector: the open time of the newest stored M1 bar."""
        try:
            return self.ledger.latest(self.symbol, Timeframe.M1)
        except LedgerError:
            return None

    def _quote(self, live: dict[str, Any] | None, now: datetime) -> QuoteView | None:
        if live is None or not isinstance(live.get("quote"), dict):
            return None
        quote = live["quote"]
        try:
            bid, ask = float(quote["bid"]), float(quote["ask"])
            stamp = datetime.fromisoformat(str(quote["timestamp"]))
            spread = float(quote["spread_points"])
        except (KeyError, TypeError, ValueError):
            return None
        if not (bid > 0 and ask >= bid):
            return None
        return QuoteView(bid, ask, spread, stamp, max(0.0, (now - stamp).total_seconds()))

    def load(self, now: datetime | None = None) -> LiveSnapshot:
        stamp = now or datetime.now(UTC)
        problems: list[str] = []
        status = market_status(stamp, self.calendar)
        live = _read_json(self.root / "live.json")
        collector = _read_json(self.root / "collector_status.json")
        alive = False
        if collector is not None:
            try:
                alive = (
                    stamp - datetime.fromisoformat(str(collector["updated_at"]))
                ).total_seconds() <= COLLECTOR_STALE_SECONDS
            except (KeyError, ValueError):
                alive = False
        if not alive:
            problems.append("the market collector is not running")
        frames: dict[Timeframe, pl.DataFrame] = {}
        freshness: dict[str, str] = {}
        latest_close: datetime | None = None
        for tf in ALL_TIMEFRAMES:
            try:
                frame = self.ledger.tail(self.symbol, tf, self.tails[tf])
            except LedgerError as exc:
                problems.append(f"{tf.value}: {exc}")
                freshness[tf.value] = "UNKNOWN"
                continue
            if frame.height == 0:
                freshness[tf.value] = "UNKNOWN"
                continue
            frames[tf] = frame
            newest = frame["timestamp"].max()
            if isinstance(newest, datetime):
                if tf is Timeframe.M1:
                    latest_close = newest + tf.delta
                freshness[tf.value] = bar_freshness(
                    missed_closed_bars(newest, tf, stamp, self.calendar), tf
                )
        try:
            bars = from_frames(frames)
        except FrameError as exc:
            problems.append(f"bars unusable: {exc}")
            bars = MultiTfBars({})
        open_market = status in (MarketStatus.OPEN, MarketStatus.UNKNOWN)
        stale = tuple(
            tf.value
            for tf in REQUIRED
            if open_market and freshness.get(tf.value, "UNKNOWN") in ("STALE", "UNKNOWN")
        )
        quote = self._quote(live, stamp)
        if open_market and quote is None:
            problems.append("no live quote")
        elif open_market and quote is not None and quote.stale:
            problems.append(f"the quote is {quote.age_seconds:.0f}s old")
        spec = spec_from_broker(live.get("symbol_spec") if live else None)
        return LiveSnapshot(
            now=stamp,
            bars=bars,
            quote=quote,
            spec=spec,
            status=status,
            stale_timeframes=stale,
            freshness=freshness,
            collector_alive=alive,
            latest_m1_close=latest_close,
            problems=tuple(problems),
        )


def news_state(now: datetime, calendar_path: Path | str | None) -> str:
    """CLEAR, BLOCKED or UNKNOWN. Without a calendar covering ``now`` it is UNKNOWN, never CLEAR."""
    if not calendar_path or not Path(calendar_path).exists():
        return "UNKNOWN"
    from xau_edge.news.calendar import news_blocked  # noqa: PLC0415
    from xau_edge.news.pit import load_calendar_asof  # noqa: PLC0415

    try:
        calendar = load_calendar_asof(calendar_path, now)
        return (
            "BLOCKED"
            if news_blocked(calendar, now, before_minutes=30, after_minutes=15)
            else "CLEAR"
        )
    except Exception as exc:
        _LOG.warning("news calendar unusable: %s", type(exc).__name__)
        return "UNKNOWN"


__all__ = [
    "REQUIRED",
    "LiveSnapshot",
    "LiveTradingMarketSource",
    "QuoteView",
    "news_state",
    "spec_from_broker",
]
