"""Incremental market collector: quotes, closed bars, reconciliation, health (restart-safe).

Two independent loops share one object: the QUOTE loop (cheap, about once a second) and the BAR loop
(a few seconds). Bars are only ever stored when CLOSED, the store never overwrites a bar, and every
restart or reconnect first reconciles an overlap window against the terminal and records missing,
duplicate or changed bars as events. The collector reads market data only (the feed has no order
function) and never fetches the whole history repeatedly.
"""

from __future__ import annotations

import json
import math
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl

from xau_edge.domain.market import FeedHealth, MarketStatus, Quote
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.atomic import atomic_write_text
from xau_edge.market_data.disk import disk_report
from xau_edge.market_data.freshness import (
    bar_freshness,
    consistency_warnings,
    missed_closed_bars,
)
from xau_edge.market_data.ledger import AppendResult, BarLedger
from xau_edge.market_data.mt5.feed import Mt5Feed, SymbolMapping
from xau_edge.market_data.session import market_status
from xau_edge.market_data.tick_collection import ingest_recent
from xau_edge.market_data.tick_ledger import TickLedger
from xau_edge.market_data.validators.market_calendar import MarketCalendar

ALL_TIMEFRAMES = (
    Timeframe.M1,
    Timeframe.M5,
    Timeframe.M15,
    Timeframe.M30,
    Timeframe.H1,
    Timeframe.H4,
)
INITIAL_BARS = {Timeframe.M1: 1500, Timeframe.M5: 600, Timeframe.M15: 400, Timeframe.M30: 300}
DEFAULT_INITIAL = 300
MAX_FETCH = 5000
OVERLAP_BARS = 200
SETTLE = timedelta(seconds=20)
"""A just-closed bar is stored only after this long: late ticks may still be arriving."""
TICK_LAG_LIMIT_SECONDS = 90.0
ROWS_CACHE_SECONDS = 300.0
SPEC_REFRESH_SECONDS = 600.0


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class ReconcileReport:
    """Result of comparing the stored overlap window with the terminal."""

    timeframe: str
    compared: int
    missing_in_store: int
    only_in_store: int
    changed: int
    appended: int

    @property
    def clean(self) -> bool:
        return self.missing_in_store == 0 and self.changed == 0 and self.only_in_store == 0


@dataclass
class CollectorStatus:
    """What the health check and the dashboard read (never a credential)."""

    updated_at: str
    health: str
    reasons: list[str]
    market_status: str
    connected: bool
    demo_account: bool
    server: str | None
    broker_symbol: str
    quote: dict[str, Any] | None
    last_closed: dict[str, str | None]
    last_bar_age_seconds: dict[str, float | None]
    stored_rows: dict[str, int]
    stale_timeframes: list[str]
    events_last_hour: dict[str, int] = field(default_factory=dict)
    note: str = ""
    freshness: dict[str, str] = field(default_factory=dict)
    missed_bars: dict[str, int | None] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    disk: dict[str, Any] = field(default_factory=dict)
    tick_store: dict[str, Any] = field(default_factory=dict)
    tick_errors: int = 0
    terminal_build: int | None = None
    account_trade_allowed: bool | None = None
    terminal_algo_allowed: bool | None = None


def evaluate_health(
    *,
    connected: bool,
    demo: bool,
    market: MarketStatus,
    quote: Quote | None,
    freshness: dict[str, str],
    recent_changes: int,
    store_ok: bool,
    disk_level: str = "GOOD",
    tick_lag_seconds: float | None = None,
) -> tuple[FeedHealth, list[str], list[str]]:
    """GOOD, DEGRADED, STALE, DISCONNECTED or UNKNOWN, with every reason and the stale timeframes.

    Freshness is calendar-aware (see ``freshness``): a timeframe is STALE only when it missed bars
    the market was open for. A closed market is never a failure by itself.
    """
    if not connected:
        return FeedHealth.DISCONNECTED, ["terminal not connected"], []
    if not demo:
        return FeedHealth.UNKNOWN, ["account is not a DEMO account"], []
    stale_reasons: list[str] = []
    soft_reasons: list[str] = []
    trading = market in (MarketStatus.OPEN, MarketStatus.UNKNOWN)
    if not store_ok:
        stale_reasons.append("bar store unreadable")
    if trading and (quote is None or quote.timestamp is None or quote.stale):
        stale_reasons.append("quote is stale or missing while the market should be open")
    stale = [
        tf
        for tf, state in freshness.items()
        if state == "STALE" or (trading and state == "UNKNOWN")
    ]
    if stale:
        stale_reasons.append("stale timeframes: " + ", ".join(stale))
    if recent_changes:
        soft_reasons.append(f"{recent_changes} stored bar(s) differ from the terminal")
    if disk_level == "CRITICAL":
        soft_reasons.append("disk space is critically low")
    if trading and tick_lag_seconds is not None and tick_lag_seconds > TICK_LAG_LIMIT_SECONDS:
        soft_reasons.append(f"tick ingestion is {tick_lag_seconds:.0f}s behind")
    if stale_reasons:
        return FeedHealth.STALE, stale_reasons + soft_reasons, stale
    if soft_reasons:
        return FeedHealth.DEGRADED, soft_reasons, stale
    return FeedHealth.GOOD, ["all checks passed"], stale


class MarketCollector:
    """Keeps the bar ledger current from one MT5 feed."""

    def __init__(
        self,
        feed: Mt5Feed,
        ledger: BarLedger,
        mapping: SymbolMapping,
        calendar: MarketCalendar,
        *,
        timeframes: tuple[Timeframe, ...] = ALL_TIMEFRAMES,
        status_path: Path | None = None,
        now: Callable[[], datetime] = _utc_now,
        tick_ledger: TickLedger | None = None,
    ) -> None:
        self.feed = feed
        self.ledger = ledger
        self.mapping = mapping
        self.calendar = calendar
        self.timeframes = timeframes
        self.status_path = status_path
        self._now = now
        self.tick_ledger = tick_ledger
        self._last_quote: Quote | None = None
        self._tick_errors = 0
        self._spec: dict[str, Any] | None = None
        self._spec_at: datetime = datetime.min.replace(tzinfo=UTC)
        self._rows_cache: dict[str, tuple[datetime, int]] = {}
        self._last_forming: dict[str, dict[str, Any]] | None = None
        self._errors: list[str] = []
        self._recent: deque[dict[str, Any]] = deque(maxlen=500)
        self.live_path = None if status_path is None else status_path.with_name("live.json")

    @property
    def symbol(self) -> str:
        return self.mapping.canonical_symbol

    # -- loops ---------------------------------------------------------------------------------

    def poll_quote(self) -> Quote:
        status = market_status(self._now(), self.calendar)
        quote = self.feed.quote(self.mapping, status)
        self._last_quote = quote
        if quote.timestamp is not None and (
            not self._recent or self._recent[-1]["time"] != quote.timestamp.isoformat()
        ):
            self._recent.append(
                {"time": quote.timestamp.isoformat(), "bid": quote.bid, "ask": quote.ask,
                 "spread_points": quote.spread_points}
            )  # fmt: skip
        return quote

    def poll_ticks(self) -> int:
        """Store ticks up to ``now - 3 s`` (live ingestion); returns the new tick count."""
        if self.tick_ledger is None:
            return 0
        try:
            stats = ingest_recent(
                self.feed, self.tick_ledger, symbol=self.symbol,
                broker_symbol=self.mapping.broker_symbol, now=self._now(),
            )  # fmt: skip
        except RuntimeError as exc:
            self._tick_errors += 1
            self._errors.append(f"tick ingest: {exc}"[:200])
            return 0
        return stats.ticks_new

    def forming_bars(self) -> dict[str, dict[str, Any]]:
        """The currently forming bar of every timeframe (UI only; never stored)."""
        out: dict[str, dict[str, Any]] = {}
        for tf in self.timeframes:
            frame = self.feed.latest_bars(self.mapping.broker_symbol, tf, 1, include_forming=True)
            if frame.height == 0:
                continue
            row = frame.row(0, named=True)
            if row["timestamp"] + tf.delta > self._now():
                out[tf.value] = {
                    **row,
                    "timestamp": row["timestamp"].isoformat(),
                    "is_closed": False,
                }
        return out

    def _symbol_spec(self) -> dict[str, Any] | None:
        """The broker's contract specification, refreshed every 10 minutes (sizing needs it)."""
        now = self._now()
        if self._spec is None or (now - self._spec_at).total_seconds() > SPEC_REFRESH_SECONDS:
            try:
                self._spec = dict(self.feed.symbol_spec(self.mapping.broker_symbol))
                self._spec_at = now
            except RuntimeError as exc:
                self._errors.append(f"symbol spec: {exc}"[:200])
        return self._spec

    def _forming(self) -> dict[str, dict[str, Any]]:
        self._last_forming = self.forming_bars()
        return self._last_forming

    def write_live(self) -> None:
        """Atomically publish the latest quote, forming bars and recent ticks for the API/UI."""
        if self.live_path is None or self._last_quote is None:
            return
        payload = {
            "updated_at": self._now().isoformat(),
            "quote": json.loads(self._last_quote.model_dump_json()),
            "forming": self._forming(),
            "symbol_spec": self._symbol_spec(),
            "ticks": list(self._recent)[-200:],
        }
        try:
            atomic_write_text(self.live_path, json.dumps(payload, default=str))
        except OSError as exc:  # a locked file must not end collection; the API shows it as stale
            self._errors.append(f"live.json: {exc}"[:200])

    def _count_needed(self, tf: Timeframe, latest: datetime | None) -> int:
        if latest is None:
            return INITIAL_BARS.get(tf, DEFAULT_INITIAL)
        missing = (self._now() - latest) / tf.delta
        return int(min(MAX_FETCH, max(OVERLAP_BARS // 4, math.ceil(missing) + 5)))

    def poll_bars(self) -> dict[str, AppendResult]:
        """Fetch what is newer than the store (plus a small overlap) and store the closed bars."""
        out: dict[str, AppendResult] = {}
        for tf in self.timeframes:
            latest = self.ledger.latest(self.symbol, tf)
            count = self._count_needed(tf, latest)
            fetched = self._settled(
                self.feed.latest_bars(self.mapping.broker_symbol, tf, count), tf
            )
            out[tf.value] = self.ledger.append_closed(
                self.symbol, tf, fetched, now=self._now(), reason="poll"
            )
            self._note_gap(tf, latest, fetched)
        return out

    def _settled(self, frame: pl.DataFrame, tf: Timeframe) -> pl.DataFrame:
        """Only bars that closed at least ``SETTLE`` ago (a fresh bar may still lack late ticks)."""
        cutoff = self._now() - SETTLE
        return frame.filter(pl.col("timestamp") + pl.duration(minutes=tf.minutes) <= cutoff)

    def _note_gap(self, tf: Timeframe, latest: datetime | None, fetched: pl.DataFrame) -> None:
        """Log a GAP when the new bars start well after the last stored bar (market open only)."""
        if latest is None or fetched.height == 0:
            return
        newer = fetched.filter(pl.col("timestamp") > latest)
        if newer.height == 0:
            return
        first = newer["timestamp"].min()
        if not isinstance(first, datetime):
            return
        gap = first - latest
        if (
            gap > tf.delta * 1.5
            and market_status(latest + tf.delta, self.calendar) == MarketStatus.OPEN
        ):
            slots = int(gap / tf.delta) - 1
            self.ledger.log_event(
                self.symbol,
                "GAP",
                {"timeframe": tf.value, "after": latest.isoformat(), "before": first.isoformat(),
                 "missing_slots_at_most": slots},
                now=self._now(),
            )  # fmt: skip

    def reconcile(self, tf: Timeframe, bars: int = OVERLAP_BARS) -> ReconcileReport:
        """Compare the last ``bars`` stored bars with the terminal; store anything missing."""
        fetched = self._settled(self.feed.latest_bars(self.mapping.broker_symbol, tf, bars), tf)
        if fetched.height == 0:
            return ReconcileReport(tf.value, 0, 0, 0, 0, 0)
        start = fetched["timestamp"].min()
        stored = self.ledger.load(
            self.symbol, tf, start=start if isinstance(start, datetime) else None
        )
        left = fetched.join(stored, on="timestamp", how="left", suffix="_s")
        missing = int(left["open_s"].is_null().sum())
        both = left.filter(pl.col("open_s").is_not_null())
        changed = int(
            both.filter(
                (pl.col("open") != pl.col("open_s"))
                | (pl.col("high") != pl.col("high_s"))
                | (pl.col("low") != pl.col("low_s"))
                | (pl.col("close") != pl.col("close_s"))
                | (pl.col("tick_volume") != pl.col("tick_volume_s"))
            ).height
        )
        only_store = stored.join(fetched.select("timestamp"), on="timestamp", how="anti").height
        result = self.ledger.append_closed(
            self.symbol, tf, fetched, now=self._now(), reason="reconcile"
        )
        report = ReconcileReport(tf.value, fetched.height, missing, only_store, changed, result.new)
        self.ledger.log_event(
            self.symbol,
            "RECONCILED" if report.clean else "RECONCILE_DIFFERENCES",
            {"timeframe": tf.value, "compared": report.compared, "missing_in_store": missing,
             "only_in_store": only_store, "changed": changed, "appended": result.new},
            now=self._now(),
        )  # fmt: skip
        return report

    def reconcile_all(self) -> list[ReconcileReport]:
        return [self.reconcile(tf) for tf in self.timeframes]

    # -- status --------------------------------------------------------------------------------

    def _stored_rows(self, tf: Timeframe, now: datetime) -> int:
        """Row count per timeframe, cached: reading 100k rows every few seconds is wasteful."""
        cached = self._rows_cache.get(tf.value)
        if cached is not None and (now - cached[0]).total_seconds() < ROWS_CACHE_SECONDS:
            return cached[1]
        rows = self.ledger.load(self.symbol, tf).height
        self._rows_cache[tf.value] = (now, rows)
        return rows

    def status(self) -> CollectorStatus:
        now = self._now()
        facts = self.feed.facts()
        market = market_status(now, self.calendar)
        last_closed: dict[str, str | None] = {}
        ages: dict[str, float | None] = {}
        rows: dict[str, int] = {}
        missed: dict[str, int | None] = {}
        fresh: dict[str, str] = {}
        store_ok = True
        for tf in self.timeframes:
            try:
                latest = self.ledger.latest(self.symbol, tf)
                rows[tf.value] = self._stored_rows(tf, now) if latest else 0
            except RuntimeError:
                store_ok, latest = False, None
            last_closed[tf.value] = None if latest is None else (latest + tf.delta).isoformat()
            ages[tf.value] = None if latest is None else (now - (latest + tf.delta)).total_seconds()
            missed[tf.value] = missed_closed_bars(latest, tf, now, self.calendar)
            fresh[tf.value] = bar_freshness(missed[tf.value], tf)
        recent = [
            e
            for e in self.ledger.events(self.symbol)
            if e.get("kind") in {"BAR_CHANGED", "GAP"}
            and datetime.fromisoformat(e["at"]) > now - timedelta(hours=1)
        ]
        repaired = {
            (e.get("timeframe"), t)
            for e in self.ledger.events(self.symbol)
            if e.get("kind") == "BAR_REPAIRED"
            for t in [b["timestamp"] for b in e.get("bars", [])]
        }
        changes = sum(
            1
            for e in recent
            if e["kind"] == "BAR_CHANGED"
            for t in e.get("timestamps", [])
            if (e.get("timeframe"), t) not in repaired
        )
        disk = disk_report(self.ledger.root, self.symbol)
        tick_store = self._tick_store(now)
        health, reasons, stale = evaluate_health(
            connected=bool(facts.connected),
            demo=facts.demo,
            market=market,
            quote=self._last_quote,
            freshness=fresh,
            recent_changes=changes,
            store_ok=store_ok,
            disk_level=str(disk["level"]),
            tick_lag_seconds=tick_store.get("lag_seconds"),
        )
        quote = self._last_quote
        warnings = consistency_warnings(quote, self._last_forming)
        if disk["level"] == "WARN":
            warnings.append("disk space is getting low")
        return CollectorStatus(
            updated_at=now.isoformat(),
            health=health.value,
            reasons=reasons,
            market_status=market.value,
            connected=bool(facts.connected),
            demo_account=facts.demo,
            server=facts.server,
            broker_symbol=self.mapping.broker_symbol,
            quote=None if quote is None else json.loads(quote.model_dump_json()),
            last_closed=last_closed,
            last_bar_age_seconds=ages,
            stored_rows=rows,
            stale_timeframes=stale,
            events_last_hour={
                "changes": changes,
                "gaps": sum(1 for e in recent if e["kind"] == "GAP"),
            },
            note="; ".join(self._errors[-3:]),
            freshness=fresh,
            missed_bars=missed,
            warnings=warnings,
            disk=disk,
            tick_store=tick_store,
            tick_errors=self._tick_errors,
            terminal_build=facts.build,
            account_trade_allowed=facts.account_trade_allowed,
            terminal_algo_allowed=facts.trade_allowed,
        )

    def _tick_store(self, now: datetime) -> dict[str, Any]:
        if self.tick_ledger is None:
            return {"enabled": False}
        covered = self.tick_ledger.coverage(self.symbol)
        until = max((b for _, b in covered), default=None)
        return {
            "enabled": True,
            "covered_until": None if until is None else until.isoformat(),
            "lag_seconds": None if until is None else (now - until).total_seconds(),
            "coverage_windows": len(covered),
            "earliest_covered": None if not covered else covered[0][0].isoformat(),
        }

    def write_status(self) -> CollectorStatus:
        status = self.status()
        if self.status_path is not None:
            try:
                write_status_file(self.status_path, status)
            except OSError as exc:  # keep collecting; a stale status file is shown as stale
                self._errors.append(f"status file: {exc}"[:200])
        return status

    # -- run -----------------------------------------------------------------------------------

    def run_once(self) -> CollectorStatus:
        """One quote refresh and one bar poll (used by tests and by ``--once``)."""
        self.poll_quote()
        self.poll_bars()
        self.poll_ticks()
        self.write_live()
        return self.write_status()

    def run(
        self,
        stop: Callable[[], bool],
        *,
        quote_interval: float = 1.0,
        bar_interval: float = 5.0,
        reconcile_interval: float = 600.0,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Quote loop and bar loop until ``stop()``; reconciles on start and periodically."""
        self.reconcile_all()
        next_bar = next_reconcile = clock()
        next_reconcile += reconcile_interval
        while not stop():
            self.poll_quote()
            self.write_live()
            t = clock()
            if t >= next_bar:
                self.poll_bars()
                self.poll_ticks()
                next_bar = t + bar_interval
                self.write_status()
            if t >= next_reconcile:
                self.reconcile_all()
                next_reconcile = t + reconcile_interval
            sleep(quote_interval)


def write_status_file(path: Path, status: CollectorStatus) -> None:
    """Atomic write of the status JSON (readers never see a torn file)."""
    atomic_write_text(path, json.dumps(status.__dict__, indent=2, default=str) + "\n")


def read_status_file(
    path: Path, *, now: datetime | None = None, max_age_seconds: float = 60.0
) -> dict[str, Any]:
    """The last status, marked UNKNOWN/STALE when the file is missing, torn or too old."""
    stamp = now or _utc_now()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        updated = datetime.fromisoformat(raw["updated_at"])
    except (OSError, ValueError, KeyError, TypeError):
        return {
            "health": FeedHealth.UNKNOWN.value,
            "reasons": ["collector status missing"],
            "collector_running": False,
        }
    age = (stamp - updated).total_seconds()
    raw["status_age_seconds"] = age
    raw["collector_running"] = age <= max_age_seconds
    if age > max_age_seconds:
        raw["health"] = FeedHealth.STALE.value
        raw["reasons"] = [*raw.get("reasons", []), f"collector status is {age:.0f}s old"]
    return raw  # type: ignore[no-any-return]
