"""Read-only MT5 data feed: terminal facts, symbol discovery, quotes, ticks and latest bars.

Everything here goes through ``ReadOnlyMt5Client`` (market-data allowlist) and refuses anything but
a DEMO account (unless the caller explicitly passes ``require_demo=False`` after identifying a
funded account by whitelist, as the funded bot does). No function here can place, check, modify or
close an order. All times returned by the terminal are server wall-clock labelled as UTC and are
converted to true UTC with the broker clock (``BrokerClock``); the quote's age doubles as a live
check of that clock (a wrong offset shows up as a negative or hours-long age).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import polars as pl

from xau_edge.domain.bars import coerce_bars, empty_bars
from xau_edge.domain.market import MarketStatus, Quote, Tick, conform_ticks, empty_ticks
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.broker_clock import BrokerClock
from xau_edge.market_data.mt5.source import (
    Mt5AccountError,
    Mt5DataClient,
    ReadOnlyMt5Client,
)

DEFAULT_STALE_SECONDS = 30.0
MAX_TICKS_PER_CALL = 200_000
MAX_BARS_PER_CALL = 99_000
_MIN_AGE = -5.0  # a tick newer than "now" by more than this means the clock offset is wrong


class SymbolNotFoundError(RuntimeError):
    """No broker symbol matches the canonical symbol."""


@dataclass(frozen=True)
class SymbolMapping:
    """Canonical symbol, the broker's own name for it and where that was established."""

    canonical_symbol: str
    broker_symbol: str
    broker_server: str | None
    source: str = "mt5"
    exact: bool = True


@dataclass(frozen=True)
class TerminalFacts:
    """Safe facts about the terminal (no login, no balance, no credentials)."""

    build: int | None
    version: tuple[int, int, str] | None
    connected: bool | None
    trade_allowed: bool | None
    max_bars: int | None
    company: str | None
    server: str | None
    demo: bool


def _utc_now() -> datetime:
    return datetime.now(UTC)


class Mt5Feed:
    """Quotes, ticks, symbol metadata and bars from a running MT5 terminal (data only)."""

    def __init__(
        self,
        client: Mt5DataClient,
        clock: BrokerClock,
        *,
        now: Callable[[], datetime] = _utc_now,
        require_demo: bool = True,
        stale_seconds: float = DEFAULT_STALE_SECONDS,
    ) -> None:
        self._client = ReadOnlyMt5Client(client)
        self._clock = clock
        self._now = now
        self._require_demo = require_demo
        self.stale_seconds = stale_seconds

    @property
    def client(self) -> ReadOnlyMt5Client:
        """The read-only client (market-data functions only), e.g. for independent cross-checks."""
        return self._client

    # -- connection and facts ------------------------------------------------------------------

    def guard(self) -> None:
        """Refuse anything but a DEMO account (a live password also trades)."""
        if not self._require_demo:
            return
        info = self._client.account_info()
        if info is None or info.trade_mode != self._client.ACCOUNT_TRADE_MODE_DEMO:
            msg = "refusing to use MT5: the connected account is not a DEMO account"
            raise Mt5AccountError(msg)

    def facts(self) -> TerminalFacts:
        """Terminal build, connection and server label; never credentials or balances."""
        info = self._client.terminal_info()
        account = self._client.account_info()
        version = self._client.version()
        demo = bool(
            account is not None and account.trade_mode == self._client.ACCOUNT_TRADE_MODE_DEMO
        )
        return TerminalFacts(
            build=getattr(info, "build", None),
            version=tuple(version) if version else None,
            connected=getattr(info, "connected", None),
            trade_allowed=getattr(info, "trade_allowed", None),
            max_bars=getattr(info, "maxbars", None),
            company=getattr(info, "company", None),
            server=getattr(account, "server", None),
            demo=demo,
        )

    # -- symbols -------------------------------------------------------------------------------

    def discover_symbol(self, canonical: str = "XAUUSD") -> SymbolMapping:
        """The broker symbol for ``canonical`` (exact name first, then a unique prefix match)."""
        self.guard()
        names = [s.name for s in (self._client.symbols_get() or [])]
        server = getattr(self._client.account_info(), "server", None)
        if canonical in names:
            return SymbolMapping(canonical, canonical, server, exact=True)
        loose = sorted(n for n in names if n.upper().startswith(canonical.upper()))
        if len(loose) == 1:
            return SymbolMapping(canonical, loose[0], server, exact=False)
        msg = (
            f"no unique broker symbol for {canonical}: "
            f"{'ambiguous ' + ', '.join(loose[:5]) if loose else 'none found'}"
        )
        raise SymbolNotFoundError(msg)

    def select(self, broker_symbol: str) -> bool:
        """Make the symbol visible in Market Watch (required before quotes and history)."""
        return bool(self._client.symbol_select(broker_symbol, True))

    def symbol_spec(self, broker_symbol: str) -> dict[str, float | int | str | None]:
        """Contract specification as the broker reports it (never hard-coded)."""
        info = self._client.symbol_info(broker_symbol)
        if info is None:
            msg = f"symbol_info failed for {broker_symbol}: {self._client.last_error()}"
            raise RuntimeError(msg)
        keys = (
            "digits", "point", "trade_tick_size", "trade_tick_value", "trade_contract_size",
            "trade_stops_level", "trade_freeze_level", "volume_min", "volume_step",
            "volume_max", "spread", "spread_float", "currency_base", "currency_profit",
        )  # fmt: skip
        return {k: getattr(info, k, None) for k in keys}

    # -- time ----------------------------------------------------------------------------------

    def to_utc(self, server_epoch_seconds: int | float) -> datetime:
        """Server wall-clock epoch (labelled UTC by MT5) -> true UTC instant."""
        naive = datetime.fromtimestamp(float(server_epoch_seconds), UTC).replace(tzinfo=None)
        series = self._clock.server_to_utc(
            pl.Series([naive], dtype=pl.Datetime("us")), strict=False
        )
        value = series[0]
        if value is None:
            msg = "ambiguous or non-existent server time"
            raise ValueError(msg)
        return value  # type: ignore[no-any-return]

    def _server_wall(self, utc_dt: datetime) -> datetime:
        return self._clock.label_as_utc(utc_dt)

    # -- quote ---------------------------------------------------------------------------------

    def quote(self, mapping: SymbolMapping, status: MarketStatus = MarketStatus.UNKNOWN) -> Quote:
        """The latest quote with its age; stale when older than ``stale_seconds`` while OPEN."""
        self.guard()
        tick = self._client.symbol_info_tick(mapping.broker_symbol)
        if tick is None:
            return Quote(
                canonical_symbol=mapping.canonical_symbol, broker_symbol=mapping.broker_symbol,
                bid=None, ask=None, mid=None, last=None, spread_price=None, spread_points=None,
                timestamp=None, age_seconds=None, stale=True, market_status=status,
                note=f"no tick: {self._client.last_error()}",
            )  # fmt: skip
        stamp = self.to_utc(tick.time_msc / 1000.0 if getattr(tick, "time_msc", 0) else tick.time)
        age = (self._now() - stamp).total_seconds()
        bid, ask = float(tick.bid), float(tick.ask)
        point = float(
            getattr(self._client.symbol_info(mapping.broker_symbol), "point", 0.01) or 0.01
        )
        both = bid > 0 and ask > 0
        note = ""
        if age < _MIN_AGE:
            note = "tick is in the future: the broker clock offset looks wrong"
        stale = age > self.stale_seconds and status in (MarketStatus.OPEN, MarketStatus.UNKNOWN)
        return Quote(
            canonical_symbol=mapping.canonical_symbol,
            broker_symbol=mapping.broker_symbol,
            bid=bid if bid > 0 else None,
            ask=ask if ask > 0 else None,
            mid=(bid + ask) / 2 if both else None,
            last=float(tick.last) if tick.last else None,
            spread_price=ask - bid if both else None,
            spread_points=(ask - bid) / point if both else None,
            timestamp=stamp,
            age_seconds=age,
            stale=stale or bool(note),
            market_status=status,
            note=note,
        )

    # -- ticks ---------------------------------------------------------------------------------

    def ticks_range(
        self, broker_symbol: str, start: datetime, end: datetime, *, limit: int = MAX_TICKS_PER_CALL
    ) -> list[Tick]:
        """Ticks in ``[start, end)`` (true UTC bounds), at most ``limit`` (bounded memory)."""
        self.guard()
        if end <= start or limit < 1:
            return []
        limit = min(limit, MAX_TICKS_PER_CALL)
        raw = self._client.copy_ticks_range(
            broker_symbol,
            self._server_wall(start),
            self._server_wall(end),
            self._client.COPY_TICKS_ALL,
        )
        if raw is None:
            msg = f"copy_ticks_range failed: {self._client.last_error()}"
            raise RuntimeError(msg)
        return self._ticks(broker_symbol, raw[:limit])

    def ticks_frame(
        self, broker_symbol: str, start: datetime, end: datetime, *, limit: int = MAX_TICKS_PER_CALL
    ) -> tuple[pl.DataFrame, bool]:
        """Ticks in ``[start, end)`` as a frame (vectorised) and whether ``limit`` cut it short.

        Columns: ``timestamp_msc`` (true-UTC epoch milliseconds), ``timestamp`` (UTC), ``bid``,
        ``ask``, ``last``, ``volume``, ``flags`` (``volume_real`` when the terminal provides it).
        A truncated window must be split by the caller; nothing is silently dropped here.
        """
        self.guard()
        limit = max(1, min(limit, MAX_TICKS_PER_CALL))
        if end <= start:
            return empty_ticks(), False
        # The terminal works in whole seconds: over-fetch one second each side, then cut exactly.
        pad = timedelta(seconds=1)
        raw = self._client.copy_ticks_range(
            broker_symbol,
            self._server_wall(start.replace(microsecond=0) - pad),
            self._server_wall(end.replace(microsecond=0) + pad + pad),
            self._client.COPY_TICKS_ALL,
        )
        if raw is None:
            msg = f"copy_ticks_range failed: {self._client.last_error()}"
            raise RuntimeError(msg)
        truncated = len(raw) > limit
        raw = raw[:limit]
        if len(raw) == 0:
            return empty_ticks(), False
        names = raw.dtype.names or ()
        msc = (
            raw["time_msc"].astype("int64")
            if "time_msc" in names
            else raw["time"].astype("int64") * 1000
        )
        naive = pl.from_epoch(pl.Series(msc), time_unit="ms").cast(pl.Datetime("us"))
        utc = self._clock.server_to_utc(naive, strict=False)
        offset_ms = (utc.cast(pl.Int64) // 1000) - msc  # the broker offset in ms (whole hours)
        frame = pl.DataFrame(
            {
                "timestamp_msc": pl.Series(msc) + offset_ms,
                "bid": raw["bid"].astype("float64"),
                "ask": raw["ask"].astype("float64"),
                "last": raw["last"].astype("float64"),
                "volume": raw["volume"].astype("int64") if "volume" in names else 0,
                "flags": raw["flags"].astype("int64") if "flags" in names else 0,
            }
        ).with_columns(
            pl.from_epoch("timestamp_msc", time_unit="ms")
            .dt.replace_time_zone("UTC")
            .alias("timestamp")
        )
        start_ms = int(start.timestamp() * 1000)
        end_ms = int(end.timestamp() * 1000)
        frame = frame.filter(
            (pl.col("timestamp_msc") >= start_ms) & (pl.col("timestamp_msc") < end_ms)
        )
        return conform_ticks(frame.drop_nulls("timestamp_msc")), truncated

    def ticks_from(self, broker_symbol: str, start: datetime, count: int) -> list[Tick]:
        """Up to ``count`` ticks from ``start`` onwards."""
        self.guard()
        count = max(1, min(count, MAX_TICKS_PER_CALL))
        raw = self._client.copy_ticks_from(
            broker_symbol, self._server_wall(start), count, self._client.COPY_TICKS_ALL
        )
        if raw is None:
            msg = f"copy_ticks_from failed: {self._client.last_error()}"
            raise RuntimeError(msg)
        return self._ticks(broker_symbol, raw)

    def _ticks(self, broker_symbol: str, raw: Any) -> list[Tick]:
        names = raw.dtype.names or ()
        out: list[Tick] = []
        for row in raw:
            bid, ask, last = float(row["bid"]), float(row["ask"]), float(row["last"])
            msc = int(row["time_msc"]) if "time_msc" in names else int(row["time"]) * 1000
            out.append(
                Tick(
                    broker_symbol=broker_symbol,
                    timestamp=self.to_utc(msc / 1000.0),
                    timestamp_msc=msc,
                    bid=bid or None,
                    ask=ask or None,
                    last=last or None,
                    volume=int(row["volume"]) if "volume" in names else None,
                    volume_real=float(row["volume_real"]) if "volume_real" in names else None,
                    flags=int(row["flags"]) if "flags" in names else None,
                    spread=(ask - bid) if bid and ask else None,
                )
            )
        return out

    # -- bars ----------------------------------------------------------------------------------

    def _frame(self, rates: Any) -> pl.DataFrame:
        naive = pl.from_epoch(pl.Series(rates["time"]), time_unit="s").cast(pl.Datetime("us"))
        frame = pl.DataFrame(
            {
                "timestamp": self._clock.server_to_utc(naive, strict=False),
                "open": rates["open"],
                "high": rates["high"],
                "low": rates["low"],
                "close": rates["close"],
                "tick_volume": rates["tick_volume"].astype("int64"),
                "spread": rates["spread"].astype("int64"),
                "real_volume": rates["real_volume"].astype("int64"),
            }
        ).drop_nulls("timestamp")
        return coerce_bars(frame)

    def latest_bars(
        self, broker_symbol: str, timeframe: Timeframe, count: int, *, include_forming: bool = False
    ) -> pl.DataFrame:
        """The last ``count`` bars (true UTC open times); the forming bar only when asked.

        ``copy_rates_from_pos`` is the call that makes the terminal load history up to its
        "Max bars in chart" limit, so a count above ``MAX_BARS_PER_CALL`` is refused here.
        """
        self.guard()
        count = max(1, min(count, MAX_BARS_PER_CALL))
        constant = getattr(self._client, f"TIMEFRAME_{timeframe.value}", None)
        if constant is None:
            msg = f"MT5 client has no constant for timeframe {timeframe.value}"
            raise RuntimeError(msg)
        rates = self._client.copy_rates_from_pos(broker_symbol, constant, 0, count)
        if rates is None:
            msg = f"copy_rates_from_pos failed: {self._client.last_error()}"
            raise RuntimeError(msg)
        if len(rates) == 0:
            return empty_bars()
        frame = self._frame(rates)
        if include_forming:
            return frame
        closes = pl.col("timestamp") + pl.duration(minutes=timeframe.minutes)
        return frame.filter(closes <= self._now())

    def bars_range(
        self,
        broker_symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
        *,
        include_forming: bool = False,
    ) -> pl.DataFrame:
        """Bars in ``[start, end)`` (true UTC); only what the terminal holds is returned."""
        self.guard()
        constant = getattr(self._client, f"TIMEFRAME_{timeframe.value}", None)
        if constant is None:
            msg = f"MT5 client has no constant for timeframe {timeframe.value}"
            raise RuntimeError(msg)
        rates = self._client.copy_rates_range(
            broker_symbol, constant, self._server_wall(start), self._server_wall(end)
        )
        if rates is None:
            msg = f"copy_rates_range failed: {self._client.last_error()}"
            raise RuntimeError(msg)
        if len(rates) == 0:
            return empty_bars()
        frame = self._frame(rates).filter(
            (pl.col("timestamp") >= start) & (pl.col("timestamp") < end)
        )
        if include_forming:
            return frame
        closes = pl.col("timestamp") + pl.duration(minutes=timeframe.minutes)
        return frame.filter(closes <= self._now())


def spread_summary(ticks: list[Tick]) -> dict[str, float | None]:
    """Median / p95 / max spread (price units) of a tick list (None when no bid/ask pairs)."""
    values = np.array([t.spread for t in ticks if t.spread is not None], dtype=np.float64)
    if values.size == 0:
        return {"median": None, "p95": None, "max": None, "n": 0.0}
    return {
        "median": float(np.median(values)),
        "p95": float(np.quantile(values, 0.95)),
        "max": float(values.max()),
        "n": float(values.size),
    }


__all__ = [
    "Mt5Feed",
    "SymbolMapping",
    "SymbolNotFoundError",
    "TerminalFacts",
    "spread_summary",
]
