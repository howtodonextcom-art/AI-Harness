"""Acceptance worlds: the REAL desk wiring run over burned bars at chosen moments.

A scenario freezes the engine at a moment of the burned period (a real BUY or SELL setup found by
the v1.1/v1.2.1 replay, a weekend, ...) and can optionally inject ONE infrastructure fault (stale
data, a corrupt paper state, a second writer, ...). The world uses ``build_trade_engine`` itself,
so what is exercised is the production wiring, over a ``ReplayMarketSource`` and a replay clock.

Everything it produces carries ``source_mode = ACCEPTANCE_REPLAY``; its root is claimed by that
mode and can never be the live root. It proves the product path (decision, plan, paper open,
price evolution, exits, journal, markers, UI) end to end. It does not prove live execution or edge.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl

from xau_edge.api.trade import build_trade_engine
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.calendars import ftmo_calendar
from xau_edge.ops.notifier import NullNotifier
from xau_edge.ops.process_lock import WriterLock
from xau_edge.trading.engine import TradeEngine
from xau_edge.trading.replay_source import BURNED_TO, ReplayMarketSource

WARM_STEPS = 48
"""M5 closes stepped before the frozen moment (the lifecycle looks back 36 bars)."""


def at(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    version: str
    moment: datetime
    fault: str | None = None
    clock_offset_seconds: int = 0
    corrupt_state: bool = False
    writer_conflict: bool = False
    tags: tuple[str, ...] = field(default=())


# Moments are the decision times of REAL setups found by the burned-data acceptance replays
# (docs/reports/PAPER_LIFECYCLE_ACCEPTANCE.md); none of them was constructed by hand.
SCENARIOS: dict[str, Scenario] = {
    s.name: s
    for s in (
        Scenario("wait", "an ordinary WAIT", "1.2.1", at("2025-12-02T12:00:00")),
        Scenario(
            "buy_tp",
            "a real BUY setup that later takes profit (v1.2.1)",
            "1.2.1",
            at("2025-12-05T14:45:00"),
        ),
        Scenario(
            "sell_ready",
            "a real SELL setup that later hits its stop (v1.2.1)",
            "1.2.1",
            at("2025-08-14T18:05:00"),
        ),
        Scenario(
            "sell_tp",
            "a SELL that later reaches its target (v1.1)",
            "1.1.0",
            at("2025-08-14T11:05:00"),
        ),
        Scenario(
            "buy_closure_near",
            "a BUY an hour before the daily close: the closure policy blocks it",
            "1.2.1",
            at("2025-12-09T20:50:00"),
        ),
        Scenario(
            "buy_time", "a BUY that later exits on time (v1.1)", "1.1.0", at("2025-08-04T15:40:00")
        ),
        Scenario(
            "market_closed", "Saturday: the market is closed", "1.2.1", at("2025-12-06T12:00:00")
        ),
        Scenario(
            "stale", "a BUY with stale data", "1.2.1", at("2025-12-05T14:45:00"), fault="STALE_DATA"
        ),
        Scenario(
            "expired",
            "a BUY whose validity ran out",
            "1.2.1",
            at("2025-12-05T14:45:00"),
            clock_offset_seconds=400,
        ),
        Scenario(
            "paper_corrupt",
            "a BUY with a corrupt paper state",
            "1.2.1",
            at("2025-12-05T14:45:00"),
            corrupt_state=True,
        ),
        Scenario(
            "writer_conflict",
            "a BUY while another process owns the desk",
            "1.2.1",
            at("2025-12-05T14:45:00"),
            writer_conflict=True,
        ),
        Scenario(
            "no_spec",
            "the broker specification is missing",
            "1.2.1",
            at("2025-12-05T14:45:00"),
            fault="NO_SPEC",
        ),
        Scenario(
            "collector_down",
            "the collector is not publishing",
            "1.2.1",
            at("2025-12-05T14:45:00"),
            fault="COLLECTOR_DOWN",
        ),
    )
}


class AcceptanceWorld:
    """One scenario's engine, desk and replay clock (a fresh root each time)."""

    def __init__(self, market_root: Path, out_root: Path, scenario: Scenario) -> None:
        self.scenario = scenario
        self.market_root = market_root
        self.root = out_root / scenario.name
        if self.root.exists():
            shutil.rmtree(self.root, ignore_errors=True)
        self.root.mkdir(parents=True)
        start = scenario.moment - timedelta(minutes=5 * WARM_STEPS)
        end = min(scenario.moment + timedelta(days=2), BURNED_TO)
        self.source = ReplayMarketSource(market_root, ftmo_calendar(), start, end)
        self.source.fault = scenario.fault
        self.now = start
        self._held: WriterLock | None = None
        if scenario.corrupt_state:
            (self.root / "paper_desk.json").write_text("{this is not json", encoding="utf-8")
        if scenario.writer_conflict:
            self._held = WriterLock(self.root / "writer.lock", role="another-api-process")
            self._held.acquire()
        self.engine: TradeEngine = build_trade_engine(
            market_root,
            self.root,
            code_version=f"acceptance-{scenario.name}",
            source=self.source,
            clock=lambda: self.now + timedelta(seconds=scenario.clock_offset_seconds),
            baseline_version=scenario.version,
            notifier=NullNotifier(),
        )
        self._advance(scenario.moment)

    # ---- the replay clock -------------------------------------------------------------------

    def _closes(self, start: datetime, end: datetime) -> list[datetime]:
        frame = self.source.frames[Timeframe.M5]
        closes = frame.filter((pl.col("available_at") > start) & (pl.col("available_at") <= end))
        return [c for c in closes["available_at"].to_list() if isinstance(c, datetime)]

    def _advance(self, target: datetime) -> int:
        steps = 0
        for close in self._closes(self.now, target):
            self.now = close
            self.source.set_time(close)
            self.engine.step(close)
            steps += 1
        self.now = target
        self.source.set_time(target)
        self.engine.step(target)  # the live loop also steps between bar closes
        return steps

    def advance_to(self, target: datetime) -> int:
        """Replay forward to ``target`` (never backwards), one M5 close at a time."""
        if target < self.now:
            msg = "the replay clock only moves forward; reset the scenario to go back"
            raise ValueError(msg)
        return self._advance(target)

    def advance_minutes(self, minutes: int) -> int:
        return self.advance_to(self.now + timedelta(minutes=minutes))

    # ---- the market API a chart needs -------------------------------------------------------

    def bars(self, timeframe: str, limit: int) -> dict[str, Any]:
        tf = Timeframe.parse(timeframe)
        frame = self.source.frames[tf].filter(pl.col("available_at") <= self.now).tail(limit)
        rows = [
            {
                "time": r["timestamp"].isoformat(),
                "open": r["open"],
                "high": r["high"],
                "low": r["low"],
                "close": r["close"],
                "tick_volume": r["tick_volume"],
                "spread": r["spread"],
                "is_closed": True,
            }
            for r in frame.iter_rows(named=True)
        ]
        return {
            "symbol": "XAUUSD",
            "timeframe": tf.value,
            "source": "ACCEPTANCE REPLAY of burned FTMO bars (NOT LIVE)",
            "volume_type": "TICK_VOLUME",
            "real_volume_policy": "tick volume only; never real volume",
            "closed_only": True,
            "bars": rows,
        }

    def close(self) -> None:
        lock = getattr(self.engine, "writer_lock", None)
        if lock is not None:
            lock.release()
        if self._held is not None:
            self._held.release()
