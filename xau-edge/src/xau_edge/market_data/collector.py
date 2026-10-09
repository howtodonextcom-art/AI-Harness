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
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl

from xau_edge.domain.market import FeedHealth, MarketStatus, Quote
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.ledger import AppendResult, BarLedger
from xau_edge.market_data.mt5.feed import Mt5Feed, SymbolMapping
from xau_edge.market_data.session import market_status
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


def evaluate_health(
    *,
    connected: bool,
    demo: bool,
    market: MarketStatus,
    quote: Quote | None,
    bar_age_seconds: dict[str, float | None],
    timeframes: dict[str, int],
    recent_changes: int,
    store_ok: bool,
) -> tuple[FeedHealth, list[str], list[str]]:
    """GOOD, DEGRADED, STALE, DISCONNECTED or UNKNOWN, with reasons and stale timeframes."""
    reasons: list[str] = []
    stale: list[str] = []
    if not connected:
        return FeedHealth.DISCONNECTED, ["terminal not connected"], []
    if not demo:
        return FeedHealth.UNKNOWN, ["account is not a DEMO account"], []
    if not store_ok:
        reasons.append("bar store unreadable")
    trading = market in (MarketStatus.OPEN, MarketStatus.UNKNOWN)
    if trading and (quote is None or quote.timestamp is None or quote.stale):
        reasons.append("quote is stale or missing while the market should be open")
    for tf, limit_minutes in timeframes.items():
        age = bar_age_seconds.get(tf)
        if age is None:
            if trading:
                stale.append(tf)
        elif trading and age > limit_minutes * 60:
            stale.append(tf)
    if stale:
        reasons.append("stale timeframes: " + ", ".join(stale))
    if recent_changes:
        reasons.append(f"{recent_changes} stored bar(s) differ from the terminal")
    if any("stale" in r or "unreadable" in r for r in reasons):
        return (
            FeedHealth.STALE
            if not store_ok or stale or (quote is None or quote.stale)
            else FeedHealth.DEGRADED,
            reasons,
            stale,
        )
    if reasons:
        return FeedHealth.DEGRADED, reasons, stale
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
    ) -> None:
        self.feed = feed
        self.ledger = ledger
        self.mapping = mapping
        self.calendar = calendar
        self.timeframes = timeframes
        self.status_path = status_path
        self._now = now
        self._last_quote: Quote | None = None
        self._errors: list[str] = []

    @property
    def symbol(self) -> str:
        return self.mapping.canonical_symbol

    # -- loops ---------------------------------------------------------------------------------

    def poll_quote(self) -> Quote:
        status = market_status(self._now(), self.calendar)
        quote = self.feed.quote(self.mapping, status)
        self._last_quote = quote
        return quote

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
            fetched = self.feed.latest_bars(self.mapping.broker_symbol, tf, count)
            out[tf.value] = self.ledger.append_closed(
                self.symbol, tf, fetched, now=self._now(), reason="poll"
            )
            self._note_gap(tf, latest, fetched)
        return out

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
        fetched = self.feed.latest_bars(self.mapping.broker_symbol, tf, bars)
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

    def status(self) -> CollectorStatus:
        now = self._now()
        facts = self.feed.facts()
        market = market_status(now, self.calendar)
        last_closed: dict[str, str | None] = {}
        ages: dict[str, float | None] = {}
        rows: dict[str, int] = {}
        store_ok = True
        for tf in self.timeframes:
            try:
                latest = self.ledger.latest(self.symbol, tf)
                rows[tf.value] = self.ledger.load(self.symbol, tf).height if latest else 0
            except RuntimeError:
                store_ok, latest = False, None
            last_closed[tf.value] = None if latest is None else (latest + tf.delta).isoformat()
            ages[tf.value] = None if latest is None else (now - (latest + tf.delta)).total_seconds()
        limits = {tf.value: max(3 * tf.minutes, 5) for tf in self.timeframes}
        recent = [
            e
            for e in self.ledger.events(self.symbol)
            if e.get("kind") in {"BAR_CHANGED", "GAP"}
            and datetime.fromisoformat(e["at"]) > now - timedelta(hours=1)
        ]
        changes = sum(1 for e in recent if e["kind"] == "BAR_CHANGED")
        health, reasons, stale = evaluate_health(
            connected=bool(facts.connected),
            demo=facts.demo,
            market=market,
            quote=self._last_quote,
            bar_age_seconds=ages,
            timeframes=limits,
            recent_changes=changes,
            store_ok=store_ok,
        )
        quote = self._last_quote
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
            events_last_hour={"changes": changes, "gaps": len(recent) - changes},
            note="; ".join(self._errors[-3:]),
        )

    def write_status(self) -> CollectorStatus:
        status = self.status()
        if self.status_path is not None:
            write_status_file(self.status_path, status)
        return status

    # -- run -----------------------------------------------------------------------------------

    def run_once(self) -> CollectorStatus:
        """One quote refresh and one bar poll (used by tests and by ``--once``)."""
        self.poll_quote()
        self.poll_bars()
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
            t = clock()
            if t >= next_bar:
                self.poll_bars()
                next_bar = t + bar_interval
                self.write_status()
            if t >= next_reconcile:
                self.reconcile_all()
                next_reconcile = t + reconcile_interval
            sleep(quote_interval)


def write_status_file(path: Path, status: CollectorStatus) -> None:
    """Atomic write of the status JSON (readers never see a torn file)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(status.__dict__, indent=2, default=str) + "\n", encoding="utf-8")
    tmp.replace(path)


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
