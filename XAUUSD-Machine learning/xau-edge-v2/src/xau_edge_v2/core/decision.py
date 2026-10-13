"""The decision: REGIME > DIRECTION > SETUP > TRIGGER > EXECUTION > PLAN > RISK (WAIT is normal).

This is V1's operational baseline v1.1.0 rewritten with NO behavioural change (G4 forbids strategy
tuning; parity is proven by ``scripts/parity/golden_core.py``). It is labelled UNVALIDATED: it
exists to exercise the pipeline, not as an edge. H1 is the ONLY source of BUY versus SELL;
H4 may only veto; M30 is display only; M1 may only block; tick volume only confirms activity.

Readiness (0..6) is the deterministic depth the chain reached, independent of the hard gates:
0 NEUTRAL (no H1 bias) / 1 BIAS / 2 WATCH (M15 with the trend) /
3 SETUP_ARMED (pullback inside it) /
4 TRIGGER (M5 confirms) / 5 PLAN_VALID (M1 ok, stop and payoff valid) / 6 READY (sized, no gate
blocks, i.e. BUY or SELL). A hard gate (stale data, closed market, spread...) forces WAIT and caps
the level at 5.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum

from xau_edge_v2.core.costs import CostEstimate, estimate_round_trip
from xau_edge_v2.core.market_state import MarketState
from xau_edge_v2.core.risk import (
    SymbolSpec,
    compute_stop,
    compute_targets,
    size_for_risk,
)

STRATEGY_ID = "xau_mtf_baseline"
STRATEGY_VERSION = "1.1.0"
BLOCKING_H4 = {"BUY": "TREND_DOWN", "SELL": "TREND_UP"}
NEWS_NOT_VERIFIED = "NEWS NOT VERIFIED: no economic calendar, check the news yourself"


class Refusal(StrEnum):
    NO_DIRECTION = "NO_DIRECTION"
    TIMEFRAME_CONFLICT = "TIMEFRAME_CONFLICT"
    NO_SETUP = "NO_SETUP"
    NO_TRIGGER = "NO_TRIGGER"
    SPREAD_TOO_WIDE = "SPREAD_TOO_WIDE"
    VOLUME_TOO_LOW = "VOLUME_TOO_LOW"
    VOLATILITY_TOO_HIGH = "VOLATILITY_TOO_HIGH"
    VOLATILITY_TOO_LOW = "VOLATILITY_TOO_LOW"
    TOO_CLOSE_TO_RESISTANCE = "TOO_CLOSE_TO_RESISTANCE"
    TOO_CLOSE_TO_SUPPORT = "TOO_CLOSE_TO_SUPPORT"
    RR_TOO_LOW = "RR_TOO_LOW"
    INVALID_STOP_DISTANCE = "INVALID_STOP_DISTANCE"
    RISK_LIMIT = "RISK_LIMIT"
    DAILY_LIMIT = "DAILY_LIMIT"
    COOLDOWN = "COOLDOWN"
    NEWS_UNKNOWN = "NEWS_UNKNOWN"
    NEWS_WINDOW = "NEWS_WINDOW"
    STALE_DATA = "STALE_DATA"
    MARKET_CLOSED = "MARKET_CLOSED"
    BROKER_DISCONNECTED = "BROKER_DISCONNECTED"
    UNKNOWN_STATE = "UNKNOWN_STATE"


@dataclass(frozen=True)
class DecisionConfig:
    """Thresholds of the chain (configuration, not logic). Defaults equal V1's baseline."""

    risk_pct: float = 0.25
    min_clear_atr: float = 1.0
    allow_unknown_news: bool = True
    """PAPER: the decision carries a NEWS NOT VERIFIED warning instead of refusing."""
    block_high_volatility: bool = True
    block_low_volatility: bool = True
    block_quiet_m1: bool = True
    expiry_bars_m5: int = 3
    require_m1: bool = False
    blocked_regimes: tuple[str, ...] = ("SHOCK", "HIGH_VOLATILITY")


@dataclass(frozen=True)
class DecisionContext:
    """What the engine needs besides the market state (symbol spec, equity, guards, quote)."""

    spec: SymbolSpec
    equity: float | None = None
    feed_connected: bool = True
    cooldown_active: bool = False
    daily_limit_hit: bool = False
    risk_limit_hit: bool = False
    market_open: bool = True
    market_status: str = "OPEN"
    data_ok: bool = True
    spec_known: bool = True
    bid: float | None = None
    ask: float | None = None
    """Executable quote: BUY enters at the ask, SELL at the bid (else last close +/- spread/2)."""


@dataclass(frozen=True)
class Decision:
    """BUY / SELL / WAIT with the whole chain of reasons and every level."""

    decision_id: str
    timestamp: datetime
    symbol: str
    action: str
    bias: str
    readiness_level: int
    reasons: tuple[str, ...]
    refusals: tuple[str, ...]
    warnings: tuple[str, ...]
    m1_execution_state: str
    atr: float | None
    evidence: str = "UNVALIDATED"
    strategy_id: str = STRATEGY_ID
    strategy_version: str = STRATEGY_VERSION
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    take_profit_2: float | None = None
    net_rr: float | None = None
    gross_rr: float | None = None
    required_win_rate: float | None = None
    stop_model: str | None = None
    capped_by_structure: bool = False
    risk_pct: float | None = None
    lots: float | None = None
    risk_amount: float | None = None
    expiry: datetime | None = None
    entry_quality: str = ""
    setup_id: str = ""
    invalidation: str | None = None
    cost: CostEstimate | None = None
    state: MarketState | None = field(default=None, repr=False, compare=False)


def make_id(parts: dict[str, object]) -> str:
    """Stable id from the decision inputs (the same closed bars give the same id)."""
    canonical = json.dumps(parts, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:20]


def m1_execution_state(state: MarketState, direction: int = 0) -> str:
    """GOOD, QUIET, NOISY, SPREAD_WIDE, VOLATILE or STALE (M1 may only block, never decide)."""
    if (
        "M1" not in state.available_timeframes
        or "M1" in state.stale_timeframes
        or state.m1_micro_state == "UNKNOWN"
    ):
        return "STALE"
    if state.execution_quality == "POOR":
        return "SPREAD_WIDE"
    micro = state.m1_micro_state
    if micro == "ABNORMAL":
        return "VOLATILE"
    if micro == "QUIET":
        return "QUIET"
    if (direction > 0 and micro == "ACTIVE_DOWN") or (direction < 0 and micro == "ACTIVE_UP"):
        return "NOISY"
    return "GOOD"


def _expiry_anchor(state: MarketState) -> tuple[datetime, datetime]:
    m5 = state.snapshots.get("M5")
    if m5 is None:
        return state.timestamp, state.timestamp
    return m5.bar_open, m5.bar_closed


def setup_identity(state: MarketState, side: str) -> str:
    """Stable while the same M5 trigger bar holds."""
    opened, _ = _expiry_anchor(state)
    return make_id({"setup": side, "s": state.symbol, "m5": opened, "v": STRATEGY_VERSION})


def _volume_state(state: MarketState) -> str:
    z = state.volume_zscore_m1
    if z is None:
        return "UNKNOWN"
    return "HIGH" if z >= 1.0 else "LOW" if z <= -1.0 else "NORMAL"


def _gates(  # noqa: PLR0912 - one gate per condition
    state: MarketState, ctx: DecisionContext, cfg: DecisionConfig
) -> tuple[list[Refusal], tuple[str, ...]]:
    out: list[Refusal] = []
    warnings: list[str] = []
    if ctx.market_status == "UNKNOWN":
        return [Refusal.UNKNOWN_STATE], ()
    if not ctx.market_open or not state.market_open:
        return [Refusal.MARKET_CLOSED], ()
    if not ctx.feed_connected:
        out.append(Refusal.BROKER_DISCONNECTED)
    if state.data_quality in ("STALE", "UNKNOWN") or not ctx.data_ok:
        out.append(Refusal.STALE_DATA)
    if not ctx.spec_known:
        out.append(Refusal.UNKNOWN_STATE)
    if "H1" not in state.available_timeframes or "H4" not in state.available_timeframes:
        out.append(Refusal.UNKNOWN_STATE)
    if state.news_state == "BLOCKED":
        out.append(Refusal.NEWS_WINDOW)
    elif state.news_state == "UNKNOWN":
        if cfg.allow_unknown_news:
            warnings.append(NEWS_NOT_VERIFIED)
        else:
            out.append(Refusal.NEWS_UNKNOWN)
    if state.execution_quality == "POOR":
        out.append(Refusal.SPREAD_TOO_WIDE)
    elif state.execution_quality == "UNKNOWN":
        out.append(Refusal.UNKNOWN_STATE)
    if state.volatility_regime == "HIGH" and cfg.block_high_volatility:
        out.append(Refusal.VOLATILITY_TOO_HIGH)
    if state.volatility_regime == "LOW" and cfg.block_low_volatility:
        out.append(Refusal.VOLATILITY_TOO_LOW)
    if state.h4_regime in cfg.blocked_regimes:
        out.append(Refusal.VOLATILITY_TOO_HIGH)
    if ctx.cooldown_active:
        out.append(Refusal.COOLDOWN)
    if ctx.daily_limit_hit:
        out.append(Refusal.DAILY_LIMIT)
    if ctx.risk_limit_hit:
        out.append(Refusal.RISK_LIMIT)
    return out, tuple(warnings)


def _bias(state: MarketState) -> str:
    return {"BULLISH": "BUY", "BEARISH": "SELL"}.get(state.h1_trend, "NEUTRAL")


def decide(  # noqa: PLR0911, PLR0912, PLR0915 - one refusal per link of the chain
    state: MarketState, ctx: DecisionContext, cfg: DecisionConfig | None = None
) -> Decision:
    """The baseline decision for ``state`` (deterministic: same state, same answer)."""
    cfg = cfg or DecisionConfig()
    chain = [
        f"H4:{state.h4_regime}",
        f"H1:{state.h1_trend}",
        f"M30:{state.m30_structure} (context only)",
        f"M15:{state.m15_structure}/{state.m15_pullback}",
        f"M5:{state.m5_momentum}",
        f"M1:{m1_execution_state(state)}",
        f"SPREAD:{state.execution_quality}",
        f"VOLUME:{_volume_state(state)}({state.volume_type})",
    ]
    gates, warnings = _gates(state, ctx, cfg)
    level = 0

    def wait(
        reasons: list[Refusal],
        extra: str | None = None,
        *,
        gate: bool = False,
        warn: tuple[str, ...] = (),
    ) -> Decision:
        unique = tuple(dict.fromkeys(r.value for r in reasons))
        return Decision(
            decision_id=make_id(
                {"t": state.timestamp, "s": state.symbol, "v": STRATEGY_VERSION, "r": list(unique)}
            ),
            timestamp=state.timestamp,
            symbol=state.symbol,
            action="WAIT",
            bias=_bias(state),
            readiness_level=min(level, 5),
            reasons=(*chain, extra) if extra else tuple(chain),
            refusals=unique,
            warnings=() if gate else warn,
            m1_execution_state=m1_execution_state(state),
            atr=state.atr_m15,
            risk_pct=cfg.risk_pct,
            state=state,
        )

    def refuse(reason: Refusal, extra: str | None = None) -> Decision:
        """A chain refusal; a hard gate, when there is one, takes precedence (as in V1)."""
        if gates:
            return wait(gates, gate=True)
        return wait([reason], extra, warn=warnings)

    if state.h1_trend == "BULLISH":
        side, direction = "BUY", 1
    elif state.h1_trend == "BEARISH":
        side, direction = "SELL", -1
    else:
        return refuse(Refusal.NO_DIRECTION)
    level = 1
    if state.h4_regime == BLOCKING_H4[side]:
        return refuse(Refusal.TIMEFRAME_CONFLICT, f"H4 vetoes {side}")
    with_trend, against = ("UP", "DOWN") if direction > 0 else ("DOWN", "UP")
    if state.m15_structure == against:
        return refuse(Refusal.TIMEFRAME_CONFLICT, "M15 against H1")
    if state.m15_structure == with_trend:
        level = 2
    pullback = "PULLBACK_IN_UPTREND" if direction > 0 else "PULLBACK_IN_DOWNTREND"
    if state.m15_structure != with_trend or state.m15_pullback != pullback:
        return refuse(Refusal.NO_SETUP)
    level = 3
    if state.m5_momentum != with_trend:
        return refuse(Refusal.NO_TRIGGER)
    level = 4
    exec_state = m1_execution_state(state, direction)
    if exec_state == "VOLATILE":
        return refuse(Refusal.VOLATILITY_TOO_HIGH, "M1 volatile: range and volume")
    if exec_state == "QUIET" and cfg.block_quiet_m1:
        return refuse(Refusal.VOLUME_TOO_LOW, "M1 tick volume far below its own average")
    if exec_state == "NOISY":
        return refuse(Refusal.NO_TRIGGER, "M1 candle is strongly against the entry")
    if exec_state == "STALE" and cfg.require_m1:
        return refuse(Refusal.STALE_DATA, "M1 feed missing")
    atr = state.atr_m15
    price = state.price
    if atr is None or atr <= 0 or price is None:
        return refuse(Refusal.UNKNOWN_STATE)
    opposing = state.distance_to_resistance if direction > 0 else state.distance_to_support
    if opposing is not None and opposing < cfg.min_clear_atr * atr:
        return refuse(
            Refusal.TOO_CLOSE_TO_RESISTANCE if direction > 0 else Refusal.TOO_CLOSE_TO_SUPPORT
        )
    swing = state.snapshots.get("M5")
    swing_level = None
    if swing is not None:
        swing_level = swing.last_swing_low if direction > 0 else swing.last_swing_high
    spread_price = (state.spread or 0.0) * ctx.spec.point
    quote = ctx.ask if direction > 0 else ctx.bid
    entry = quote if quote is not None else price + direction * spread_price / 2
    stop = compute_stop(direction, entry, swing_level, atr)
    if stop is None or stop.distance < ctx.spec.min_stop_distance():
        return refuse(Refusal.INVALID_STOP_DISTANCE, "no acceptable stop")
    opposing_level = None if opposing is None else price + direction * opposing
    targets = compute_targets(
        direction, entry, stop, spread=spread_price, atr=atr, opposing_level=opposing_level
    )
    if targets is None:
        return refuse(Refusal.RR_TOO_LOW)
    level = 5
    lots: float | None = None
    risk_amount: float | None = None
    if ctx.equity is not None:
        sized = size_for_risk(ctx.equity, cfg.risk_pct, entry, stop.price, ctx.spec)
        if not sized.allowed:
            if gates:
                return wait(gates, gate=True)
            return wait([Refusal.RISK_LIMIT], ", ".join(sized.reasons), warn=warnings)
        lots, risk_amount = sized.lots, sized.risk_amount
    if gates:
        return wait(gates, gate=True)
    _, trigger_close = _expiry_anchor(state)
    expiry = trigger_close + timedelta(minutes=5 * cfg.expiry_bars_m5)
    entry_quality = "STRONG" if _volume_state(state) == "HIGH" else "ACCEPTABLE"
    cost = (
        estimate_round_trip(lots, spread_price if state.spread is not None else None, ctx.spec)
        if lots is not None
        else None
    )
    return Decision(
        decision_id=make_id(
            {
                "t": state.timestamp,
                "s": state.symbol,
                "v": STRATEGY_VERSION,
                "d": side,
                "e": round(entry, 5),
                "sl": round(stop.price, 5),
                "tp": round(targets.tp1, 5),
            }
        ),
        timestamp=state.timestamp,
        symbol=state.symbol,
        action=side,
        bias=side,
        readiness_level=6,
        reasons=(*chain, f"stop={stop.model} {stop.distance:.2f}", f"net_rr={targets.net_rr:.2f}"),
        refusals=(),
        warnings=warnings,
        m1_execution_state=exec_state,
        atr=atr,
        entry_price=entry,
        stop_loss=stop.price,
        take_profit=targets.tp1,
        take_profit_2=targets.tp2,
        net_rr=targets.net_rr,
        gross_rr=targets.gross_rr,
        required_win_rate=targets.required_win_rate,
        stop_model=stop.model,
        capped_by_structure=targets.capped_by_structure,
        risk_pct=cfg.risk_pct,
        lots=lots,
        risk_amount=risk_amount,
        expiry=expiry,
        entry_quality=entry_quality,
        setup_id=setup_identity(state, side),
        invalidation=(
            f"H1 turns {'bearish' if direction > 0 else 'bullish'}, or price closes beyond the stop"
        ),
        cost=cost,
        state=state,
    )
