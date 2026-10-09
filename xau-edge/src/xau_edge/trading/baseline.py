"""Transparent rule-based baseline: REGIME > DIRECTION > SETUP > TRIGGER > EXECUTION > PLAN > RISK.

This is an OPERATIONAL baseline. It exists to exercise the whole decision and execution pipeline,
to collect forward signals and to measure execution. It is NOT a validated edge and is labelled
``UNVALIDATED_BASELINE`` everywhere. WAIT is the normal answer; there is no indicator vote count:
a trade needs a coherent chain, and a lower timeframe may BLOCK a trade but may never reverse the
direction chosen by H1.

Timeframe roles (phase 1):

* H4  REGIME / BLOCKER: may veto a trade against a strong H4 trend, never creates one;
* H1  DIRECTION: the ONLY source of BUY versus SELL;
* M30 CONTEXT: displayed, never a veto (it must not add interacting rules);
* M15 SETUP: pullback inside the H1 trend (and structure not against it);
* M5  TRIGGER: momentum / structure break in the trend direction;
* M1  EXECUTION TIMING: spread, tick-volume activity and short-term volatility; may only block.

Tick volume (never exchange volume) only confirms activity: a QUIET M1 blocks, a HIGH one improves
``entry_quality``; high volume alone can never produce a BUY or SELL. Every threshold is in
``BaselineConfig`` and the whole config is versioned with ``STRATEGY_VERSION``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from pydantic import BaseModel, ConfigDict, Field

from xau_edge.trading.levels import LevelConfig, compute_stop, compute_targets
from xau_edge.trading.market_state import MarketState
from xau_edge.trading.schema import (
    EntryType,
    EvidenceLabel,
    Refusal,
    TradeDecision,
    TradingSignal,
    make_signal_id,
)
from xau_edge.trading.sizing import SymbolSpec, size_for_risk

STRATEGY_ID = "xau_mtf_baseline"
STRATEGY_VERSION = "1.1.0"
BLOCKING_H4 = {"BUY": "TREND_DOWN", "SELL": "TREND_UP"}
NEWS_NOT_VERIFIED = "NEWS NOT VERIFIED: no economic calendar, check the news yourself"


class BaselineConfig(BaseModel):
    """Thresholds of the chain (configuration, not logic)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    levels: LevelConfig = Field(default_factory=LevelConfig)
    risk_pct: float = Field(default=0.25, gt=0, le=1.0)
    min_clear_atr: float = Field(default=1.0, ge=0)
    """Minimum free distance to the opposing support/resistance, in ATR(M15)."""
    allow_unknown_news: bool = False
    """Paper desk: True (decision carries a NEWS NOT VERIFIED warning). Auto demo: keep False."""
    block_high_volatility: bool = True
    block_low_volatility: bool = True
    block_quiet_m1: bool = True
    """A QUIET M1 (tick volume well below its own average) blocks the entry (VOLUME_TOO_LOW)."""
    expiry_bars_m5: int = Field(default=3, ge=1)
    require_m1: bool = False
    """When True a missing M1 feed blocks the trade; otherwise M1 only vetoes when present."""
    blocked_regimes: tuple[str, ...] = ("SHOCK", "HIGH_VOLATILITY")


@dataclass(frozen=True)
class DecisionContext:
    """What the engine needs besides the market state (account, symbol, guards, live quote)."""

    spec: SymbolSpec
    equity: float | None = None
    broker_connected: bool = True
    cooldown_active: bool = False
    daily_limit_hit: bool = False
    risk_limit_hit: bool = False
    market_open: bool = True
    data_ok: bool = True
    """False when the live source says a required timeframe, the quote or the collector is stale."""
    spec_known: bool = True
    """False when the broker's symbol specification is unavailable (no sizing, no stop checks)."""
    bid: float | None = None
    ask: float | None = None
    """Executable quote: BUY enters at the ask, SELL at the bid (else last close +/- spread/2)."""


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


def _expiry_anchor(state: MarketState) -> tuple[object, object]:
    """(M5 trigger bar open, its close): the identity and the clock of a setup."""
    m5 = state.snapshots.get("M5")
    if m5 is None:
        return state.timestamp, state.timestamp
    return m5.bar_open, m5.bar_closed


def setup_identity(state: MarketState, side: str) -> str:
    """Stable while the same M5 trigger bar holds (alerts and paper orders key on this)."""
    opened, _ = _expiry_anchor(state)
    return make_signal_id({"setup": side, "s": state.symbol, "m5": opened, "v": STRATEGY_VERSION})


def _volume_state(state: MarketState) -> str:
    z = state.volume_zscore_m1
    if z is None:
        return "UNKNOWN"
    return "HIGH" if z >= 1.0 else "LOW" if z <= -1.0 else "NORMAL"


def _common(state: MarketState, cfg: BaselineConfig, ctx: DecisionContext) -> dict[str, object]:
    return {
        "timestamp": state.timestamp,
        "symbol": state.symbol,
        "strategy_id": STRATEGY_ID,
        "strategy_version": STRATEGY_VERSION,
        "market_regime": state.h4_regime,
        "h4_bias": state.h4_regime,
        "h1_bias": state.h1_trend,
        "m30_state": state.m30_structure,
        "m15_setup": f"{state.m15_structure}/{state.m15_pullback}",
        "m5_trigger": state.m5_momentum,
        "spread": state.spread,
        "volume_state": _volume_state(state),
        "volume_type": state.volume_type,
        "code_version": STRATEGY_VERSION,
        "news_state": state.news_state,
        "spread_state": state.spread_state,
        "volatility_regime": state.volatility_regime,
        "bid": ctx.bid,
        "ask": ctx.ask,
    }


def _wait(
    state: MarketState,
    reasons: list[Refusal],
    chain: list[str],
    cfg: BaselineConfig,
    ctx: DecisionContext,
    *,
    warnings: tuple[str, ...] = (),
) -> TradingSignal:
    unique = tuple(dict.fromkeys(reasons))
    return TradingSignal(
        signal_id=make_signal_id(
            {
                "t": state.timestamp,
                "s": state.symbol,
                "v": STRATEGY_VERSION,
                "r": [r.value for r in unique],
            }
        ),
        decision=TradeDecision.WAIT,
        m1_execution_state=m1_execution_state(state),
        atr=state.atr_m15,
        reasons=tuple(chain),
        refusal_reasons=unique,
        metadata={"risk_pct": cfg.risk_pct},
        warnings=warnings,
        **_common(state, cfg, ctx),
    )


def _gates(  # noqa: PLR0912 - one gate per condition
    state: MarketState, ctx: DecisionContext, cfg: BaselineConfig
) -> tuple[list[Refusal], tuple[str, ...]]:
    out: list[Refusal] = []
    warnings: list[str] = []
    if not ctx.market_open or not state.market_open:
        return [Refusal.MARKET_CLOSED], ()
    if not ctx.broker_connected:
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


def decide(  # noqa: PLR0911, PLR0912, PLR0915 - one refusal per link of the chain
    state: MarketState, ctx: DecisionContext, cfg: BaselineConfig | None = None
) -> TradingSignal:
    """The baseline decision for ``state`` (deterministic: same state, same answer)."""
    cfg = cfg or BaselineConfig()
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
    if gates:
        return _wait(state, gates, chain, cfg, ctx)

    # 1. DIRECTION from H1 (the only source of direction)
    if state.h1_trend == "BULLISH":
        side, direction = "BUY", 1
    elif state.h1_trend == "BEARISH":
        side, direction = "SELL", -1
    else:
        return _wait(state, [Refusal.NO_DIRECTION], chain, cfg, ctx, warnings=warnings)
    # 2. REGIME: H4 may veto the direction
    if state.h4_regime == BLOCKING_H4[side]:
        return _wait(
            state, [Refusal.TIMEFRAME_CONFLICT], [*chain, f"H4 vetoes {side}"], cfg, ctx,
            warnings=warnings,
        )  # fmt: skip
    # 3. SETUP on M15 (M30 is context only): structure not against H1, pullback inside the trend
    with_trend, against = ("UP", "DOWN") if direction > 0 else ("DOWN", "UP")
    if state.m15_structure == against:
        return _wait(
            state, [Refusal.TIMEFRAME_CONFLICT], [*chain, "M15 against H1"], cfg, ctx,
            warnings=warnings,
        )  # fmt: skip
    pullback = "PULLBACK_IN_UPTREND" if direction > 0 else "PULLBACK_IN_DOWNTREND"
    if state.m15_structure != with_trend or state.m15_pullback != pullback:
        return _wait(state, [Refusal.NO_SETUP], chain, cfg, ctx, warnings=warnings)
    # 4. TRIGGER on M5
    if state.m5_momentum != with_trend:
        return _wait(state, [Refusal.NO_TRIGGER], chain, cfg, ctx, warnings=warnings)
    # 5. EXECUTION quality on M1: it may only block
    exec_state = m1_execution_state(state, direction)
    if exec_state == "VOLATILE":
        return _wait(
            state, [Refusal.VOLATILITY_TOO_HIGH], [*chain, "M1 volatile: range and volume"],
            cfg, ctx, warnings=warnings,
        )  # fmt: skip
    if exec_state == "QUIET" and cfg.block_quiet_m1:
        return _wait(
            state, [Refusal.VOLUME_TOO_LOW], [*chain, "M1 tick volume far below its own average"],
            cfg, ctx, warnings=warnings,
        )  # fmt: skip
    if exec_state == "NOISY":
        return _wait(
            state, [Refusal.NO_TRIGGER], [*chain, "M1 candle is strongly against the entry"],
            cfg, ctx, warnings=warnings,
        )  # fmt: skip
    if exec_state == "STALE" and cfg.require_m1:
        return _wait(
            state, [Refusal.STALE_DATA], [*chain, "M1 feed missing"], cfg, ctx, warnings=warnings
        )
    # 6. LOCATION: room to the opposing support/resistance
    atr = state.atr_m15
    price = state.price
    if atr is None or atr <= 0 or price is None:
        return _wait(state, [Refusal.UNKNOWN_STATE], chain, cfg, ctx, warnings=warnings)
    opposing = state.distance_to_resistance if direction > 0 else state.distance_to_support
    if opposing is not None and opposing < cfg.min_clear_atr * atr:
        reason = Refusal.TOO_CLOSE_TO_RESISTANCE if direction > 0 else Refusal.TOO_CLOSE_TO_SUPPORT
        return _wait(state, [reason], chain, cfg, ctx, warnings=warnings)
    # 7. TRADE PLAN: MARKET entry at the executable quote, structure stop with an ATR floor
    swing = state.snapshots.get("M5")
    swing_level = None
    if swing is not None:
        swing_level = swing.last_swing_low if direction > 0 else swing.last_swing_high
    spread_price = (state.spread or 0.0) * ctx.spec.point
    quote = ctx.ask if direction > 0 else ctx.bid
    entry = quote if quote is not None else price + direction * spread_price / 2
    stop = compute_stop(direction, entry, swing_level, atr, cfg.levels)
    if stop is None or stop.distance < ctx.spec.min_stop_distance():
        return _wait(
            state, [Refusal.INVALID_STOP_DISTANCE], [*chain, "no acceptable stop"], cfg, ctx,
            warnings=warnings,
        )  # fmt: skip
    opposing_level = None
    if opposing is not None:
        opposing_level = price + direction * opposing
    targets = compute_targets(
        direction,
        entry,
        stop,
        cfg.levels,
        spread=spread_price,
        atr=atr,
        opposing_level=opposing_level,
    )
    if targets is None:
        return _wait(state, [Refusal.RR_TOO_LOW], chain, cfg, ctx, warnings=warnings)
    # 8. RISK: size from the broker's specification
    lots: float | None = None
    risk_amount: float | None = None
    if ctx.equity is not None:
        sized = size_for_risk(ctx.equity, cfg.risk_pct, entry, stop.price, ctx.spec)
        if not sized.allowed:
            return _wait(
                state, [Refusal.RISK_LIMIT], [*chain, *sized.reasons], cfg, ctx, warnings=warnings
            )  # fmt: skip
        lots, risk_amount = sized.lots, sized.risk_amount
    decision = TradeDecision.BUY if direction > 0 else TradeDecision.SELL
    _, trigger_close = _expiry_anchor(state)
    expiry = trigger_close + timedelta(minutes=5 * cfg.expiry_bars_m5)  # type: ignore[operator]
    entry_quality = "STRONG" if _volume_state(state) == "HIGH" else "ACCEPTABLE"
    reasons = (*chain, f"stop={stop.model} {stop.distance:.2f}", f"net_rr={targets.net_rr:.2f}")
    return TradingSignal(
        signal_id=make_signal_id(
            {
                "t": state.timestamp,
                "s": state.symbol,
                "v": STRATEGY_VERSION,
                "d": decision.value,
                "e": round(entry, 5),
                "sl": round(stop.price, 5),
                "tp": round(targets.tp1, 5),
            }
        ),
        decision=decision,
        evidence_status=EvidenceLabel.UNVALIDATED_BASELINE,
        m1_execution_state=exec_state,
        entry_type=EntryType.MARKET,
        entry_price=entry,
        stop_loss=stop.price,
        take_profit=targets.tp1,
        take_profit_2=targets.tp2,
        risk_reward=targets.net_rr,
        required_win_rate=targets.required_win_rate,
        stop_model=stop.model,
        risk_pct=cfg.risk_pct,
        risk_amount=risk_amount,
        position_size=lots,
        atr=atr,
        signal_expiry=expiry,
        reasons=reasons,
        entry_quality=entry_quality,
        setup_id=setup_identity(state, side),
        invalidation=(
            f"H1 turns {'bearish' if direction > 0 else 'bullish'}, or price closes beyond the stop"
        ),
        warnings=warnings,
        metadata={
            "gross_rr": targets.gross_rr,
            "capped_by_structure": str(targets.capped_by_structure),
        },
        **_common(state, cfg, ctx),
    )
