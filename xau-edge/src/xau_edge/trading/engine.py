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

from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.atomic import atomic_write_text
from xau_edge.market_data.broker_clock import BrokerClock
from xau_edge.trading.baseline import BaselineConfig
from xau_edge.trading.decision_core import ROLES, SnapshotInputs, evaluate, explain
from xau_edge.trading.demo_lock import demo_lock_status
from xau_edge.trading.funnel import stages_from_signal, waiting_for
from xau_edge.trading.live_source import LiveSnapshot, LiveTradingMarketSource, news_state
from xau_edge.trading.market_state import MarketState, SnapshotMemo
from xau_edge.trading.paper_desk import BarExtras, DeskRefusal, PaperDesk
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
                from xau_edge.market_data.session import market_status  # noqa: PLC0415

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
                return False
            return True

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
        if newest is not None and newest != self._last_telemetry_m1:
            self._last_telemetry_m1 = newest  # type: ignore[assignment]
            self.telemetry.append(signal, at=now)
        if signal.decision is not TradeDecision.WAIT:
            m5_bar = state.snapshots.get("M5")
            self.telemetry.append_signal(
                signal, at=now, bar_time=None if m5_bar is None else m5_bar.bar_open
            )
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

    def view(self, now: datetime | None = None) -> dict[str, Any]:
        """The current decision with everything the /trade screen shows (JSON-safe)."""
        with self._lock:
            stamp = now or self._clock()
            signal, state, snap = self._signal, self._state, self._snap
            collector = self._read_collector()
            demo = demo_lock_status(collector)
            if signal is None or state is None or snap is None:
                return {
                    "available": False,
                    "generated_at": stamp.isoformat(),
                    "problems": [*self._errors[-3:], "the engine has not produced a decision yet"],
                    "demo": demo,
                    "evidence": self._evidence(),
                }
            quote = self._live_quote(stamp)
            expired = signal.signal_expiry is not None and stamp >= signal.signal_expiry
            actionable_side = signal.decision is not TradeDecision.WAIT and not expired
            blockers = (
                self.desk.can_open(stamp, state.session, self.config.default_risk_pct, quote)
                if actionable_side
                else []
            )
            plans = None
            if (
                actionable_side
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
            decision = signal.model_dump(mode="json")
            decision["decision_id"] = signal.decision_id
            decision["expired"] = expired
            decision["seconds_to_expiry"] = (
                None
                if signal.signal_expiry is None
                else max(0.0, (signal.signal_expiry - stamp).total_seconds())
            )
            problems = list(snap.problems)
            if self.desk.load_error:
                problems.append(self.desk.load_error)
            if not snap.market_open:
                problems = [p for p in problems if "collector" not in p and "quote" not in p]
            return {
                "available": True,
                "generated_at": signal.generated_at.isoformat()
                if signal.generated_at
                else stamp.isoformat(),
                "served_at": stamp.isoformat(),
                "data_as_of": None
                if snap.latest_m1_close is None
                else snap.latest_m1_close.isoformat(),
                "data_age_seconds": snap.data_age_seconds,
                "source": "FTMO MT5 via data/market (closed canonical bars + live quote)",
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
                "actionable": bool(actionable_side and not blockers and snap.usable),
                "explanation": explain(signal),
                "why_wait": {
                    "stages": stages_from_signal(signal),
                    "waiting_for": waiting_for(signal),
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
                "evidence": self._evidence(),
                "desk": {
                    "can_open": bool(actionable_side and not blockers),
                    "blockers": blockers,
                    "account": self.desk.account(quote, stamp),
                    "position": self.desk.position_view(quote, stamp),
                    "today": self.desk.day_summary(stamp),
                },
                "telemetry": self.telemetry.summary(stamp),
                "alerts": None if self.alerts is None else self.alerts.summary(stamp),
                "auto_paper": self.config.auto_paper,
                "demo": demo,
                "problems": problems,
                "engine_errors": self._errors[-3:],
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
            quote = snap.quote
            if quote is None:
                raise DeskRefusal("QUOTE_STALE", "no live quote")
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
