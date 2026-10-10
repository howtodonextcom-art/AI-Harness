"""The trade engine: live data -> market state -> decision -> plan -> paper desk -> journal/alerts.

One deterministic ``step`` is called every few seconds (a background thread in the API process).
It recomputes the decision only when something material changed (a new CLOSED M1 bar, the spread
bucket, market/quote/collector state), otherwise it re-serves the cached decision with refreshed
ages and expiry, so the answer does not flicker with every tick. The API is read-only against this
engine except for the two explicit paper actions (open from the CURRENT decision, close).

Everything the engine reads comes from ``LiveTradingMarketSource`` (the MT5 collector's files); it
never touches MT5 and never reads the legacy ``data/raw`` research store.
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from xau_edge.domain.market import MarketStatus
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.atomic import atomic_write_text
from xau_edge.market_data.broker_clock import BrokerClock
from xau_edge.market_data.session import market_status
from xau_edge.trading.baseline import BaselineConfig
from xau_edge.trading.cockpit import (
    blocker,
    condition,
    forward_acceptance,
    funnel,
    hero_state,
    read_all_signals,
    strategy_info,
    trade_plan,
)
from xau_edge.trading.decision_core import ROLES, SnapshotInputs, evaluate, explain
from xau_edge.trading.demo_lock import demo_lock_status
from xau_edge.trading.funnel import stages_from_signal, waiting_for
from xau_edge.trading.live_source import LiveSnapshot, LiveTradingMarketSource, news_state
from xau_edge.trading.market_context import market_context
from xau_edge.trading.market_state import MarketState, SnapshotMemo
from xau_edge.trading.namespace import claim_root
from xau_edge.trading.paper_desk import (
    CLOSURE_NEAR,
    BarExtras,
    DeskExit,
    DeskRefusal,
    PaperDesk,
)
from xau_edge.trading.risk_calc import DEFAULT_RISK_PCT, RISK_CHOICES, calculate
from xau_edge.trading.schema import TradeDecision, TradingSignal
from xau_edge.trading.setup_alerts import SetupAlerts
from xau_edge.trading.setup_machine import VALID_BARS
from xau_edge.trading.sizing import SymbolSpec
from xau_edge.trading.telemetry import DecisionTelemetry

_LOG = logging.getLogger(__name__)
OPERATIONAL_LABEL = "UNVALIDATED_OPERATIONAL_BASELINE"
RESEARCH_STATUS = (
    "No validated edge: Edge Program V1 = NO EDGE WITHIN BUDGET; V2 Batch A 0/20 passed Stage 1. "
    "This is an operational baseline for paper trading, not a forecast of profit."
)
SPREAD_BUCKET_POINTS = 10.0


@dataclass
class EngineConfig:
    root: Path = Path("data/trade")
    baseline: BaselineConfig = field(
        default_factory=lambda: BaselineConfig(allow_unknown_news=True)
    )
    news_calendar_path: str | None = None
    default_risk_pct: float = DEFAULT_RISK_PCT
    code_version: str = "unknown"
    auto_paper: bool = False
    """Local setting: open the PAPER desk automatically on an actionable decision. Default OFF.
    It only ever reaches the paper desk; nothing here can reach an MT5 order function."""


def cap_validity(signal: TradingSignal, last_m5_close: datetime) -> TradingSignal:
    """A signal is actionable only until the next M5 close.

    The lifecycle fires on the trigger bar (v1.1 changes the setup id with the next bar), so the
    baseline's 15-minute expiry would overstate how long the plan can be taken: never show it as
    valid longer than it can be.
    """
    if signal.decision is TradeDecision.WAIT or signal.signal_expiry is None:
        return signal
    return signal.model_copy(
        update={"signal_expiry": min(signal.signal_expiry, last_m5_close + timedelta(minutes=5))}
    )


def _bias_of(raw: str) -> int:
    """+1 / -1 / 0 from a RAW state label (never from a display string such as "ARMED (UP / …)")."""
    upper = raw.upper()
    if upper in {"BULLISH", "UP", "REVERSAL_UP", "TREND_UP", "ACTIVE_UP"}:
        return 1
    if upper in {"BEARISH", "DOWN", "REVERSAL_DOWN", "TREND_DOWN", "ACTIVE_DOWN"}:
        return -1
    return 0


class TradeEngine:
    """Computes and serves the current trading decision and drives the paper desk."""

    def __init__(
        self,
        source: LiveTradingMarketSource,
        desk: PaperDesk,
        config: EngineConfig,
        *,
        broker_clock: BrokerClock | None,
        alerts: SetupAlerts | None = None,
        telemetry: DecisionTelemetry | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.source = source
        self.desk = desk
        self.config = config
        self.broker_clock = broker_clock
        self.alerts = alerts
        self.telemetry = telemetry or DecisionTelemetry(config.root)
        self._clock = clock
        self._lock = threading.RLock()
        self._key: tuple[Any, ...] | None = None
        self._signal: TradingSignal | None = None
        self._state: MarketState | None = None
        self._snap: LiveSnapshot | None = None
        self._last_telemetry_m1: datetime | None = None
        self._errors: list[str] = []
        self._memo = SnapshotMemo()
        self.source_mode: str = getattr(source, "SOURCE_MODE", "LIVE")
        """LIVE or ACCEPTANCE_REPLAY: the namespace this engine, its desk and its logs belong to."""
        if desk.source_mode != self.source_mode:
            msg = f"the desk is {desk.source_mode} but the market source is {self.source_mode}"
            raise ValueError(msg)
        claim_root(config.root, self.source_mode)
        self.writer_error: str | None = None
        self.writer_lock: Any = None
        """Set by the builder when another process owns the desk (single writer)."""
        self._closure_cache: dict[tuple[str, int], tuple[datetime, str] | None] = {}
        self.desk.closure_probe = self.closure_probe
        self._forward_cache: tuple[tuple[Any, ...], dict[str, Any]] | None = None

    # ---- the cadence -------------------------------------------------------------------------

    def _read_collector(self) -> dict[str, Any] | None:
        try:
            value = json.loads(
                (self.source.root / "collector_status.json").read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            return None
        return value if isinstance(value, dict) else None

    def step(self, now: datetime | None = None) -> bool:
        """Advance to ``now``; returns True when the decision was recomputed."""
        with self._lock:
            stamp = now or self._clock()
            try:
                latest = self.source.latest_m1_open()
                live = self._live_quote(stamp)
                status = market_status(stamp, self.source.calendar)
                bucket = None if live is None else int(live.spread_points // SPREAD_BUCKET_POINTS)
                alive = self._collector_alive(stamp)
                key = (latest, status.value, bucket, None if live is None else live.stale, alive)
                if key == self._key and self._signal is not None:
                    return False
                self._key = key
                self._recompute(stamp)
            except Exception as exc:  # the loop must survive a bad cycle; the error is visible
                self._errors.append(f"{type(exc).__name__}: {exc}"[:300])
                _LOG.exception("trade engine cycle failed")
                self._key = None
                self._signal = None  # never keep serving a decision that could not be refreshed
                return False
            self._errors.clear()  # a recovered engine stops warning about the old failure
            return True

    def current_signal(self) -> TradingSignal | None:
        """The decision computed by the last cycle (None before the first one)."""
        return self._signal

    def now(self) -> datetime:
        """The engine's clock (the wall clock live, the replay clock in an acceptance replay)."""
        return self._clock()

    def closure_probe(self, now: datetime, horizon_minutes: int) -> tuple[datetime, str] | None:
        """(start, kind) of the first market closure within ``horizon_minutes`` of ``now``."""
        key = (f"{now:%Y%m%d%H%M}", horizon_minutes)
        if key in self._closure_cache:
            return self._closure_cache[key]
        found: tuple[datetime, str] | None = None
        for minutes in range(0, horizon_minutes + 1, 5):
            at = now + timedelta(minutes=minutes)
            status = market_status(at, self.source.calendar)
            if status not in (MarketStatus.OPEN, MarketStatus.UNKNOWN):
                kind = "DAILY_BREAK" if status is MarketStatus.ROLLOVER else "WEEKEND_OR_HOLIDAY"
                found = (at, kind)
                break
        if len(self._closure_cache) > 256:
            self._closure_cache.clear()
        self._closure_cache[key] = found
        return found

    @property
    def lock(self) -> threading.RLock:
        """Held by readers that iterate the desk while the engine thread may be mutating it."""
        return self._lock

    def _collector_alive(self, now: datetime) -> bool:
        return self.source.collector_alive(now)

    def current_quote(self, now: datetime) -> Any:
        return self._live_quote(now)

    def evidence(self) -> dict[str, Any]:
        return self._evidence()

    def _live_quote(self, now: datetime) -> Any:
        return self.source.current_quote(now)

    def _recompute(self, now: datetime) -> None:
        snap = self.source.load(now)
        quote = snap.quote
        news = news_state(now, self.config.news_calendar_path)
        equity = self.desk.equity(quote, now)
        data_ok = snap.usable if snap.market_open else True
        inputs = SnapshotInputs(
            bars=snap.bars,
            now=now,
            bid=None if quote is None else quote.bid,
            ask=None if quote is None else quote.ask,
            spread_points=None if quote is None else quote.spread_points,
            spec=snap.spec,
            equity=equity,
            news_state=news,
            market_open=snap.market_open,
            data_ok=data_ok,
        )
        state, signal = evaluate(inputs, self.config.baseline, self.broker_clock, self._memo)
        signal = signal.model_copy(
            update={"generated_at": now, "data_age_seconds": snap.data_age_seconds}
        )
        m5s = state.snapshots.get("M5")
        if m5s is not None:
            signal = cap_validity(signal, m5s.bar_closed)
        self._snap, self._state, self._signal = snap, state, signal
        latest_m1 = snap.bars.frames.get(Timeframe.M1)
        newest = (
            None if latest_m1 is None or latest_m1.height == 0 else latest_m1["timestamp"].max()
        )
        if newest is not None and newest != self._last_telemetry_m1 and not self.writer_error:
            self._last_telemetry_m1 = newest  # type: ignore[assignment]
            self.telemetry.append(signal, at=now)
        if signal.decision is not TradeDecision.WAIT and not self.writer_error:
            m5_bar = state.snapshots.get("M5")
            self.telemetry.append_signal(
                signal, at=now, bar_time=None if m5_bar is None else m5_bar.bar_open
            )
        if self.writer_error:
            return  # a read-only process computes the decision but changes nothing on disk
        self._drive_desk(snap, state, now)
        if self.config.auto_paper:
            self._auto_open(now)
        if self.alerts is not None:
            taken = {r["setup_id"] for r in self.desk.trades.values()}
            blockers = self.desk.can_open(now, state.session, self.config.default_risk_pct, quote)
            self.alerts.on_decision(signal, now, taken_setups=taken, blocked=bool(blockers))

    def _auto_open(self, now: datetime) -> None:
        """AUTO_PAPER (local setting, default off): take the current actionable decision."""
        signal, snap = self._signal, self._snap
        if signal is None or snap is None or signal.decision is TradeDecision.WAIT:
            return
        if not signal.setup_id or not snap.usable:
            return
        try:
            self._open_current(signal.setup_id, self.config.default_risk_pct, now)
        except DeskRefusal as exc:
            _LOG.info("auto paper not opened: %s", exc.code)

    def _drive_desk(self, snap: LiveSnapshot, state: MarketState, now: datetime) -> None:
        m1 = snap.bars.frames.get(Timeframe.M1)
        if m1 is None or m1.height == 0:
            return
        if self.desk.last_bar is None and self.desk.open_trade() is None:
            newest = m1["timestamp"].max()  # nothing open: start from the newest bar
            if isinstance(newest, datetime):
                self.desk.last_bar = newest
            return
        fresh = (
            m1 if self.desk.last_bar is None else m1.filter(m1["timestamp"] > self.desk.last_bar)
        )
        m5 = state.snapshots.get("M5")
        extras = BarExtras(
            atr=state.atr_m5,
            swing_low=None if m5 is None else m5.last_swing_low,
            swing_high=None if m5 is None else m5.last_swing_high,
        )
        closed = self.desk.process_bars(
            fresh.select("timestamp", "open", "high", "low", "close", "spread"),
            atr=extras.atr,
            swing_low=extras.swing_low,
            swing_high=extras.swing_high,
            invalidated={"BUY": state.h1_trend == "BEARISH", "SELL": state.h1_trend == "BULLISH"},
        )
        if self.alerts is not None:
            for trade in closed:
                self.alerts.on_paper_close(trade, now)
        self._close_for_closure(now)

    def _close_for_closure(self, now: datetime) -> None:
        """CLOSE_BEFORE_CLOSURE policy: leave the market before a closure (paper only)."""
        position = self.desk.open_trade()
        quote = self._live_quote(now)
        if position is None or quote is None or quote.stale or not self.desk.closure_due(now):
            return
        try:
            record = self.desk.manual_close(
                position["trade_id"], quote, now, reason=DeskExit.CLOSURE_CLOSE.value
            )
        except DeskRefusal as exc:
            _LOG.info("closure close refused: %s", exc.code)
            return
        if self.alerts is not None:
            self.alerts.on_paper_close(record, now)

    # ---- the view the API serves -------------------------------------------------------------

    def _m15_label(self, state: MarketState) -> str:
        signal = self._signal
        phase = None if signal is None else signal.metadata.get("setup_phase")
        base = f"{state.m15_structure} / {state.m15_pullback}"
        if phase in ("ARMED", "TRIGGERED"):
            return f"{phase} ({base})"
        return base

    def _m5_label(self, state: MarketState) -> str:
        signal = self._signal
        phase = None if signal is None else signal.metadata.get("setup_phase")
        if phase == "ARMED":
            return f"WAITING ({state.m5_momentum})"
        if (
            phase == "TRIGGERED"
            and signal is not None
            and signal.decision is not TradeDecision.WAIT
        ):
            return f"TRIGGERED ({state.m5_momentum})"
        return state.m5_momentum

    def _timeframe_rows(self, state: MarketState, snap: LiveSnapshot) -> list[dict[str, Any]]:
        label = {
            "H4": state.h4_regime,
            "H1": state.h1_trend,
            "M30": state.m30_structure,
            "M15": self._m15_label(state),
            "M5": self._m5_label(state),
            "M1": self._signal.m1_execution_state if self._signal else state.m1_micro_state,
        }
        raw = {
            "H4": state.h4_regime,
            "H1": state.h1_trend,
            "M30": state.m30_structure,
            "M15": state.m15_structure,
            "M5": state.m5_momentum,
            "M1": state.m1_micro_state,
        }
        rows: list[dict[str, Any]] = []
        for name in ("H4", "H1", "M30", "M15", "M5", "M1"):
            s = state.snapshots.get(name)
            rows.append(
                {
                    "timeframe": name,
                    "role": ROLES[name],
                    "state": label[name],
                    "bias": None if s is None else _bias_of(raw[name]),
                    "atr": None if s is None else s.atr,
                    "relative_tick_volume": None if s is None else s.volume_ratio,
                    "volume_zscore": None if s is None else s.volume_zscore,
                    "last_closed": None if s is None else s.bar_closed.isoformat(),
                    "freshness": snap.freshness.get(name, "UNKNOWN"),
                }
            )
        return rows

    def _conditions(  # noqa: PLR0912 - one rule per infrastructure condition
        self, snap: LiveSnapshot | None, state: MarketState | None, stamp: datetime
    ) -> list[dict[str, str]]:
        """Infrastructure and safety conditions, each with a severity (ERROR / WARN / INFO)."""
        out: list[dict[str, str]] = []
        if self.writer_error:
            out.append(condition("WRITER_LOCK", "ERROR", self.writer_error))
        fault = self.desk.fault
        if fault is not None and fault[0] == "PAPER_STATE_ERROR":
            out.append(condition("PAPER_STATE_ERROR", "ERROR", fault[1]))
        if self._errors and self._signal is None:
            out.append(condition("ENGINE_ERROR", "ERROR", self._errors[-1]))
        if snap is None or state is None:
            out.append(
                condition("NO_DECISION", "ERROR", "the engine has not produced a decision yet")
            )
            return out
        collector = self._read_collector() if self.source_mode == "LIVE" else {"connected": True}
        if snap.market_open:
            if not snap.collector_alive:
                out.append(
                    condition("COLLECTOR_STALE", "ERROR", "the market collector is not publishing")
                )
            if collector is not None and collector.get("connected") is False:
                out.append(
                    condition("MT5_DISCONNECTED", "ERROR", "the MT5 terminal is disconnected")
                )
            if snap.stale_timeframes:
                out.append(
                    condition(
                        "DATA_STALE", "ERROR", "stale bars: " + ", ".join(snap.stale_timeframes)
                    )
                )
            if snap.quote is None or snap.quote.stale:
                out.append(condition("QUOTE_STALE", "ERROR", "the live quote is missing or old"))
        else:
            out.append(
                condition("MARKET_CLOSED", "INFO", f"the market is {snap.status.value.lower()}")
            )
        if snap.spec is None:
            out.append(
                condition("SPEC_MISSING", "ERROR", "the broker symbol specification is unknown")
            )
        if state.news_state == "UNKNOWN":
            out.append(condition("NEWS_UNKNOWN", "WARN", "NEWS NOT VERIFIED: no economic calendar"))
        if self._errors:
            out.append(
                condition("ENGINE_ERROR", "WARN", "recent engine error: " + self._errors[-1])
            )
        return out

    def _entry_blockers(  # noqa: PLR0917 - everything the server needs to judge an entry
        self,
        signal: TradingSignal,
        snap: LiveSnapshot,
        state: MarketState,
        plan: dict[str, Any] | None,
        expired: bool,
        quote: Any,
        stamp: datetime,
    ) -> list[dict[str, str]]:
        """Why a PAPER entry is not allowed right now (the server enforces the same list)."""
        if signal.decision is TradeDecision.WAIT:
            return []
        out: list[dict[str, str]] = []
        if expired:
            out.append(blocker("EXPIRED"))
        if plan is None or not plan["complete"]:
            out.append(
                blocker(
                    "NOT_ACTIONABLE",
                    "the plan is incomplete: " + ", ".join(plan["missing"] if plan else ["plan"]),
                )
            )
        if not snap.usable:
            out.append(blocker("STALE_DATA"))
        if snap.spec is None:
            out.append(blocker("NO_SYMBOL_SPEC"))
        if any(
            r.get("setup_id") == signal.setup_id and r["status"] != "CANCELLED"
            for r in self.desk.trades.values()
        ):
            out.append(blocker("DUPLICATE_SETUP"))
        for code in self.desk.can_open(stamp, state.session, self.config.default_risk_pct, quote):
            if code == "PAPER_STATE_ERROR" and self.desk.fault:
                out.append(blocker(code, "PAPER STATE ERROR: " + self.desk.fault[1]))
            elif code == CLOSURE_NEAR:
                hit = self.desk.closure_blocks(stamp)
                kind = (
                    "daily market break"
                    if hit and hit[1] == "DAILY_BREAK"
                    else "weekly market close"
                )
                when = "" if hit is None else f" at {hit[0]:%Y-%m-%d %H:%M} UTC"
                out.append(blocker(code, f"PAPER ENTRY BLOCKED: the {kind} is approaching{when}"))
            else:
                out.append(blocker(code))
        return out

    def _forward(self, stamp: datetime) -> dict[str, Any]:
        signals_dir = self.config.root
        files = sorted(signals_dir.glob("signals-*.jsonl"))
        key = (
            tuple((f.name, f.stat().st_mtime_ns) for f in files),
            len(self.desk.trades),
            sum(1 for t in self.desk.trades.values() if t["status"] == "CLOSED"),
            self.source_mode,
        )
        if self._forward_cache is not None and self._forward_cache[0] == key:
            return self._forward_cache[1]
        result = forward_acceptance(
            read_all_signals(signals_dir), self.desk.trades.values(), source_mode=self.source_mode
        )
        self._forward_cache = (key, result)
        return result

    def _last_exit(self) -> dict[str, Any] | None:
        done = [
            t for t in self.desk.trades.values() if t["status"] == "CLOSED" and t.get("closed_at")
        ]
        if not done:
            return None
        last = max(done, key=lambda t: t["closed_at"])
        return {
            "trade_id": last["trade_id"],
            "closed_at": last["closed_at"],
            "exit_reason": last.get("exit_reason"),
            "net_pnl": last.get("net_pnl"),
            "r_multiple": last.get("r_multiple"),
        }

    def _last_exit_detail(self) -> dict[str, Any] | None:
        """The most recently closed paper trade, for the card that stays after the exit message."""
        done = [
            t for t in self.desk.trades.values() if t["status"] == "CLOSED" and t.get("closed_at")
        ]
        if not done:
            return None
        t = max(done, key=lambda x: x["closed_at"])
        return {
            "trade_id": t["trade_id"],
            "side": t["side"],
            "exit_reason": t.get("exit_reason"),
            "net_pnl": t.get("net_pnl"),
            "r_multiple": t.get("r_multiple"),
            "duration_minutes": t.get("duration_minutes"),
            "closed_at": t["closed_at"],
        }

    def _status_strip(
        self,
        conditions: list[dict[str, str]],
        hero: dict[str, Any],
        forward: dict[str, Any],
        demo: dict[str, Any],
    ) -> dict[str, Any]:
        codes = {c["code"]: c for c in conditions}
        if "COLLECTOR_STALE" in codes or "DATA_STALE" in codes or "QUOTE_STALE" in codes:
            data = {
                "state": "STALE",
                "detail": (
                    codes.get("DATA_STALE") or codes.get("QUOTE_STALE") or codes["COLLECTOR_STALE"]
                )["message"],
            }
        elif "MARKET_CLOSED" in codes:
            data = {"state": "CLOSED", "detail": codes["MARKET_CLOSED"]["message"]}
        elif "NO_DECISION" in codes or "MT5_DISCONNECTED" in codes:
            data = {
                "state": "UNAVAILABLE",
                "detail": (codes.get("MT5_DISCONNECTED") or codes["NO_DECISION"])["message"],
            }
        else:
            data = {"state": "GOOD", "detail": "bars and quote are fresh"}
        core_error = codes.get("ENGINE_ERROR")
        core = (
            {"state": "ERROR", "detail": core_error["message"]}
            if core_error and core_error["severity"] == "ERROR"
            else {"state": "RUNNING", "detail": "decisions are being computed"}
        )
        fault = self.desk.fault
        if fault is None:
            desk = {"state": "READY", "detail": "paper state verified against its journal"}
        elif fault[0] == "WRITER_LOCK":
            desk = {"state": "READ_ONLY", "detail": fault[1]}
        else:
            desk = {"state": "ERROR", "detail": fault[1]}
        version = self.config.baseline.version
        return {
            "data": data,
            "trading_core": core,
            "strategy": {
                "state": "ACTIVE",
                "label": f"v{version}",
                "detail": f"{self.config.baseline.version}",
            },
            "paper_desk": desk,
            "forward": {"state": forward["level"], "detail": forward["text"]},
            "demo": {
                "state": demo["status"],
                "detail": "paper only; the desk never sends an order",
            },
            "edge": {"state": "UNVALIDATED", "detail": OPERATIONAL_LABEL},
            "hero_state": hero["state"],
        }

    def view(self, now: datetime | None = None) -> dict[str, Any]:
        """The current decision with everything the /trade screen shows (JSON-safe)."""
        with self._lock:
            stamp = now or self._clock()
            signal, state, snap = self._signal, self._state, self._snap
            collector = self._read_collector() if self.source_mode == "LIVE" else None
            demo = demo_lock_status(collector)
            version = self.config.baseline.version
            conditions = self._conditions(snap, state, stamp)
            forward = self._forward(stamp)
            base: dict[str, Any] = {
                "source_mode": self.source_mode,
                "strategy": strategy_info(version),
                "conditions": conditions,
                "forward_acceptance": forward,
                "demo": demo,
                "evidence": self._evidence(),
                "generated_at": stamp.isoformat(),
                "paper_account_label": "PAPER ACCOUNT (simulated equity, not the FTMO account)",
            }
            if signal is None or state is None or snap is None:
                hero = hero_state(
                    signal=None, conditions=conditions, expired=False, plan=None, position=None,
                    last_exit=None, market_open=True, now=stamp,
                )  # fmt: skip
                return {
                    **base,
                    "available": False,
                    "hero": hero,
                    "decision_trusted": False,
                    "status_strip": self._status_strip(conditions, hero, forward, demo),
                    "problems": [*self._errors[-3:], "the engine has not produced a decision yet"],
                }
            quote = self._live_quote(stamp)
            expired = signal.signal_expiry is not None and stamp >= signal.signal_expiry
            actionable_side = signal.decision is not TradeDecision.WAIT and not expired
            plans = None
            if (
                signal.decision is not TradeDecision.WAIT
                and snap.spec is not None
                and signal.entry_price
                and signal.stop_loss
            ):
                equity = self.desk.equity(quote, stamp)
                plans = [
                    calculate(
                        equity=equity,
                        risk_pct=r,
                        entry=signal.entry_price,
                        stop_loss=signal.stop_loss,
                        take_profit=signal.take_profit,
                        spec=snap.spec,
                    ).as_dict()
                    for r in RISK_CHOICES
                ]
            seconds_left = (
                None
                if signal.signal_expiry is None
                else max(0.0, (signal.signal_expiry - stamp).total_seconds())
            )
            plan = trade_plan(
                signal,
                plans=plans,
                default_risk_pct=self.config.default_risk_pct,
                expired=expired,
                seconds_to_expiry=seconds_left,
            )
            entry_blockers = self._entry_blockers(signal, snap, state, plan, expired, quote, stamp)
            position = self.desk.position_view(quote, stamp)
            hero = hero_state(
                signal=signal, conditions=conditions, expired=expired, plan=plan, position=position,
                last_exit=self._last_exit(), market_open=snap.market_open, now=stamp,
            )  # fmt: skip
            decision = signal.model_dump(mode="json")
            decision["decision_id"] = signal.decision_id
            decision["expired"] = expired
            decision["seconds_to_expiry"] = seconds_left
            decision["source_mode"] = self.source_mode
            problems = list(snap.problems)
            if self.desk.load_error:
                problems.append(self.desk.load_error)
            if not snap.market_open:
                problems = [p for p in problems if "collector" not in p and "quote" not in p]
            trusted = hero["state"] not in ("UNAVAILABLE", "STALE")
            records = self.telemetry.read_day(stamp)
            todays_signals = self.telemetry.read_signals(stamp)
            return {
                **base,
                "available": True,
                "hero": hero,
                "decision_trusted": trusted,
                "status_strip": self._status_strip(conditions, hero, forward, demo),
                "market_context": market_context(
                    snap.bars.frames,
                    self.broker_clock,
                    stamp,
                    price=None if quote is None else quote.bid,
                    session=state.session,
                    market_open=snap.market_open,
                    calendar=self.source.calendar,
                ),
                "generated_at": signal.generated_at.isoformat()
                if signal.generated_at
                else stamp.isoformat(),
                "served_at": stamp.isoformat(),
                "data_as_of": None
                if snap.latest_m1_close is None
                else snap.latest_m1_close.isoformat(),
                "data_age_seconds": snap.data_age_seconds,
                "source": "FTMO MT5 via data/market (closed canonical bars + live quote)"
                if self.source_mode == "LIVE"
                else "ACCEPTANCE REPLAY of burned FTMO bars (NOT LIVE)",
                "market": {"status": snap.status.value, "open": snap.market_open},
                "quote": None
                if quote is None
                else {
                    "bid": quote.bid,
                    "ask": quote.ask,
                    "spread_points": quote.spread_points,
                    "age_seconds": quote.age_seconds,
                    "stale": quote.stale,
                },
                "decision": decision,
                "trade_plan": plan,
                "entry_blockers": entry_blockers,
                "actionable": bool(actionable_side and trusted and not entry_blockers),
                "explanation": explain(signal),
                "why_wait": {
                    "stages": stages_from_signal(signal),
                    "waiting_for": waiting_for(signal),
                    "waiting_for_code": None
                    if signal.decision is not TradeDecision.WAIT or not signal.refusal_reasons
                    else signal.refusal_reasons[0].value,
                    "blocked_by": [r.value for r in signal.refusal_reasons],
                },
                "setup": {
                    "phase": signal.metadata.get("setup_phase"),
                    "bars_since_armed": signal.metadata.get("setup_bars_since_armed"),
                    "valid_bars": VALID_BARS,
                    "strategy_version": signal.strategy_version,
                },
                "timeframes": self._timeframe_rows(state, snap),
                "volume": {
                    "type": "TICK_VOLUME",
                    "note": "tick volume (number of price changes), not exchange volume",
                    "state": signal.volume_state,
                    "m1_zscore": state.volume_zscore_m1,
                    "m1_relative": state.relative_volume_m1,
                    "m1_percentile": state.volume_percentile_m1,
                    "m1_acceleration": state.volume_acceleration_m1,
                },
                "structure": {
                    "h1_trend": state.h1_trend,
                    "m15_structure": state.m15_structure,
                    "recent_swing_high": state.recent_swing_high,
                    "recent_swing_low": state.recent_swing_low,
                    "nearest_resistance": state.nearest_resistance,
                    "nearest_support": state.nearest_support,
                    "pdh": state.pdh,
                    "pdl": state.pdl,
                    "bos": state.bos_state,
                    "choch": state.choch_state,
                    "volatility": state.volatility_regime,
                    "session": state.session,
                },
                "risk_plans": plans,
                "default_risk_pct": self.config.default_risk_pct,
                "risk_choices": list(RISK_CHOICES),
                "news": {
                    "state": state.news_state,
                    "warning": state.news_state == "UNKNOWN",
                    "text": "NEWS NOT VERIFIED: no economic calendar"
                    if state.news_state == "UNKNOWN"
                    else state.news_state,
                },
                "desk": {
                    "can_open": bool(actionable_side and trusted and not entry_blockers),
                    "blockers": entry_blockers,
                    "account": self.desk.account(quote, stamp),
                    "position": position,
                    "today": self.desk.day_summary(stamp),
                    "closure_policy": self.desk.config.closure_policy.value,
                    "limits": self._limits(quote, stamp),
                    "last_exit": self._last_exit_detail(),
                },
                "funnel": funnel(records, todays_signals, self.desk.trades.values(), stamp),
                "telemetry": self.telemetry.summary(stamp),
                "alerts": None
                if self.alerts is None
                else {
                    **self.alerts.summary(stamp),
                    "this_setup": self.alerts.status_of(signal.setup_id),
                },
                "auto_paper": self.config.auto_paper,
                "problems": problems,
                "engine_errors": self._errors[-3:],
            }

    def _limits(self, quote: Any, stamp: datetime) -> dict[str, Any]:
        """The governor daily limits next to where today stands."""
        cfg = self.desk.config.governor
        equity = self.desk.equity(quote, stamp)
        start = self.desk.day_start_equity(stamp)
        return {
            "daily_loss_stop_pct": cfg.daily_loss_stop_pct,
            "daily_loss_pct": round(self.desk.governor.daily_loss_pct(start, equity), 3),
            "max_trades_per_day": cfg.max_trades_per_day,
            "max_entry_drift_r": self.desk.config.max_entry_drift_r,
            "day_start_equity": round(start, 2),
        }

    def _evidence(self) -> dict[str, Any]:
        return {
            "operational": OPERATIONAL_LABEL,
            "validated_edge": False,
            "research": RESEARCH_STATUS,
            "label": "Not a validated edge. This is a transparent operational baseline.",
        }

    # ---- the two paper actions ---------------------------------------------------------------

    def paper_open(
        self, *, setup_id: str, risk_pct: float, now: datetime | None = None
    ) -> dict[str, Any]:
        """Take the CURRENT decision as a paper trade (only if it is still the same setup)."""
        with self._lock:
            stamp = now or self._clock()
            self.step(stamp)
            return self._open_current(setup_id, risk_pct, stamp)

    def _open_current(self, setup_id: str, risk_pct: float, stamp: datetime) -> dict[str, Any]:
        with self._lock:
            signal, state, snap = self._signal, self._state, self._snap
            if signal is None or state is None or snap is None:
                raise DeskRefusal("NO_DECISION", "the engine has no decision yet")
            if signal.setup_id != setup_id:
                raise DeskRefusal(
                    "DECISION_CHANGED", "the setup changed or is gone; refresh and look again"
                )
            if not snap.usable:
                raise DeskRefusal("STALE_DATA", "market data is not fresh enough to trade on")
            quote = self._live_quote(stamp)
            if quote is None or quote.stale:
                raise DeskRefusal("QUOTE_STALE", "no fresh live quote")
            market = {
                "session": state.session,
                "h4": state.h4_regime,
                "h1": state.h1_trend,
                "m30": state.m30_structure,
                "m15": f"{state.m15_structure}/{state.m15_pullback}",
                "m5": state.m5_momentum,
                "m1": signal.m1_execution_state,
                "volume_state": signal.volume_state,
                "volume_type": state.volume_type,
                "spread_points": state.spread,
                "spread_state": state.spread_state,
                "atr_m15": state.atr_m15,
                "atr_m5": state.atr_m5,
                "volatility": state.volatility_regime,
                "news_state": state.news_state,
                "swing_high": state.recent_swing_high,
                "swing_low": state.recent_swing_low,
                "pdh": state.pdh,
                "pdl": state.pdl,
                "data_age_seconds": snap.data_age_seconds,
                "strategy_version": signal.strategy_version,
                "setup_phase": signal.metadata.get("setup_phase"),
            }
            record = self.desk.open_from_decision(
                signal, risk_pct=risk_pct, quote=quote, spec=snap.spec, now=stamp, market=market
            )
            self._key = None  # the desk changed: the next step recomputes the blockers
            return record

    def paper_close(self, trade_id: str, now: datetime | None = None) -> dict[str, Any]:
        with self._lock:
            stamp = now or self._clock()
            self.step(stamp)  # process the bars that closed since the last cycle first
            quote = self._live_quote(stamp)
            if quote is None or quote.stale:
                raise DeskRefusal("QUOTE_STALE", "no fresh quote to close against")
            record = self.desk.manual_close(trade_id, quote, stamp)
            if self.alerts is not None:
                self.alerts.on_paper_close(record, stamp)
            self._key = None
            return record

    def risk(
        self,
        *,
        equity: float | None,
        risk_pct: float,
        entry: float,
        stop_loss: float,
        take_profit: float | None,
    ) -> dict[str, Any]:
        """The calculator (owner-supplied numbers; the broker spec is the live one)."""
        snap = self._snap or self.source.load(self._clock())
        spec: SymbolSpec | None = snap.spec
        if spec is None:
            return {"ok": False, "errors": ["SYMBOL_SPEC_UNAVAILABLE"]}
        base = (
            equity
            if equity is not None
            else self.desk.equity(self._live_quote(self._clock()), self._clock())
        )
        plan = calculate(
            equity=base,
            risk_pct=risk_pct,
            entry=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            spec=spec,
        )
        out = plan.as_dict()
        out["equity_used"] = round(base, 2)
        out["equity_source"] = "owner input" if equity is not None else "paper account (simulated)"
        return out

    def persist_latest(self) -> None:
        """Write the last view next to the journal (diagnostics; never read back as truth)."""
        try:
            atomic_write_text(
                self.config.root / "decision.json", json.dumps(self.view(), default=str)
            )
        except OSError:
            _LOG.warning("decision.json not written")
