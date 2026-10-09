"""Transparent rule-based baseline: REGIME -> DIRECTION -> SETUP -> ENTRY -> PAYOFF -> RISK.

This is an OPERATIONAL baseline. It exists to exercise the whole decision and execution pipeline,
to collect forward signals and to measure execution. It is NOT a validated edge and is labelled
``UNVALIDATED_BASELINE`` everywhere. WAIT is the normal answer; there is no indicator vote count:
a trade needs a coherent chain, and a lower timeframe may BLOCK a trade but may never reverse the
direction chosen by H1 (and H4 may veto it). Every threshold is in ``BaselineConfig`` and the whole
config is versioned with ``STRATEGY_VERSION``.
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
STRATEGY_VERSION = "1.0.0"
BLOCKING_H4 = {"BUY": "TREND_DOWN", "SELL": "TREND_UP"}


class BaselineConfig(BaseModel):
    """Thresholds of the chain (configuration, not logic)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    levels: LevelConfig = Field(default_factory=LevelConfig)
    risk_pct: float = Field(default=0.25, gt=0, le=1.0)
    min_clear_atr: float = Field(default=1.0, ge=0)
    """Minimum free distance to the opposing support/resistance, in ATR(M15)."""
    allow_unknown_news: bool = False
    block_high_volatility: bool = True
    block_low_volatility: bool = True
    expiry_bars_m5: int = Field(default=3, ge=1)
    require_m1: bool = False
    """When True a missing M1 feed blocks the trade; otherwise M1 only vetoes when present."""
    blocked_regimes: tuple[str, ...] = ("SHOCK", "HIGH_VOLATILITY")


@dataclass(frozen=True)
class DecisionContext:
    """What the engine needs besides the market state (account, symbol, guards)."""

    spec: SymbolSpec
    equity: float | None = None
    broker_connected: bool = True
    cooldown_active: bool = False
    daily_limit_hit: bool = False
    risk_limit_hit: bool = False


def _wait(
    state: MarketState, reasons: list[Refusal], chain: list[str], cfg: BaselineConfig
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
        timestamp=state.timestamp,
        symbol=state.symbol,
        decision=TradeDecision.WAIT,
        strategy_id=STRATEGY_ID,
        strategy_version=STRATEGY_VERSION,
        market_regime=state.h4_regime,
        h4_bias=state.h4_regime,
        h1_bias=state.h1_trend,
        m30_state=state.m30_structure,
        m15_setup=f"{state.m15_structure}/{state.m15_pullback}",
        m5_trigger=state.m5_momentum,
        m1_execution_state=state.m1_micro_state,
        spread=state.spread,
        atr=state.atr_m15,
        volume_state=_volume_state(state),
        volume_type=state.volume_type,
        reasons=tuple(chain),
        refusal_reasons=unique,
        code_version=STRATEGY_VERSION,
        metadata={"risk_pct": cfg.risk_pct},
    )


def _volume_state(state: MarketState) -> str:
    z = state.volume_zscore_m1
    if z is None:
        return "UNKNOWN"
    return "HIGH" if z >= 1.0 else "LOW" if z <= -1.0 else "NORMAL"


def _gates(state: MarketState, ctx: DecisionContext, cfg: BaselineConfig) -> list[Refusal]:
    out: list[Refusal] = []
    if not ctx.broker_connected:
        out.append(Refusal.BROKER_DISCONNECTED)
    if state.data_quality in ("STALE", "UNKNOWN"):
        out.append(Refusal.STALE_DATA)
    if "H1" not in state.available_timeframes or "H4" not in state.available_timeframes:
        out.append(Refusal.UNKNOWN_STATE)
    if state.news_state == "BLOCKED" or (
        state.news_state == "UNKNOWN" and not cfg.allow_unknown_news
    ):
        out.append(Refusal.NEWS_WINDOW)
    if state.execution_quality in ("POOR", "UNKNOWN"):
        out.append(Refusal.SPREAD_TOO_WIDE)
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
    return out


def decide(  # noqa: PLR0911, PLR0912 - one refusal per link of the chain
    state: MarketState, ctx: DecisionContext, cfg: BaselineConfig | None = None
) -> TradingSignal:
    """The baseline decision for ``state`` (deterministic: same state, same answer)."""
    cfg = cfg or BaselineConfig()
    chain = [
        f"H4:{state.h4_regime}",
        f"H1:{state.h1_trend}",
        f"M30:{state.m30_structure}",
        f"M15:{state.m15_structure}/{state.m15_pullback}",
        f"M5:{state.m5_momentum}",
        f"M1:{state.m1_micro_state}",
        f"SPREAD:{state.execution_quality}",
        f"VOLUME:{_volume_state(state)}({state.volume_type})",
    ]
    gates = _gates(state, ctx, cfg)
    if gates:
        return _wait(state, gates, chain, cfg)

    # 1. DIRECTION from H1 (the only source of direction)
    if state.h1_trend == "BULLISH":
        side, direction = "BUY", 1
    elif state.h1_trend == "BEARISH":
        side, direction = "SELL", -1
    else:
        return _wait(state, [Refusal.NO_DIRECTIONAL_EDGE], chain, cfg)
    # 2. REGIME: H4 may veto the direction
    if state.h4_regime == BLOCKING_H4[side]:
        return _wait(state, [Refusal.TIMEFRAME_CONFLICT], [*chain, f"H4 vetoes {side}"], cfg)
    # 3. SETUP on M30/M15: not against the direction, pullback inside the trend
    up_word, down_word = ("UP", "DOWN")
    with_trend = up_word if direction > 0 else down_word
    against = down_word if direction > 0 else up_word
    if against in (state.m30_structure, state.m15_structure):
        return _wait(state, [Refusal.TIMEFRAME_CONFLICT], [*chain, "M30/M15 against H1"], cfg)
    pullback = "PULLBACK_IN_UPTREND" if direction > 0 else "PULLBACK_IN_DOWNTREND"
    if state.m15_structure != with_trend or state.m15_pullback != pullback:
        return _wait(state, [Refusal.NO_SETUP], chain, cfg)
    # 4. ENTRY trigger on M5
    if state.m5_momentum != with_trend:
        return _wait(state, [Refusal.NO_ENTRY_TRIGGER], chain, cfg)
    # 5. M1 execution quality may only block
    vetoes = ("ACTIVE_DOWN", "ABNORMAL") if direction > 0 else ("ACTIVE_UP", "ABNORMAL")
    if state.m1_micro_state in vetoes or (cfg.require_m1 and state.m1_micro_state == "UNKNOWN"):
        return _wait(state, [Refusal.NO_ENTRY_TRIGGER], [*chain, "M1 blocks the entry"], cfg)
    # 6. LOCATION: room to the opposing support/resistance
    atr = state.atr_m15
    price = state.price
    if atr is None or atr <= 0 or price is None:
        return _wait(state, [Refusal.UNKNOWN_STATE], chain, cfg)
    opposing = state.distance_to_resistance if direction > 0 else state.distance_to_support
    if opposing is not None and opposing < cfg.min_clear_atr * atr:
        reason = Refusal.TOO_CLOSE_TO_RESISTANCE if direction > 0 else Refusal.TOO_CLOSE_TO_SUPPORT
        return _wait(state, [reason], chain, cfg)
    # 7. LEVELS and net payoff
    swing = state.snapshots.get("M5")
    swing_level = None
    if swing is not None:
        swing_level = swing.last_swing_low if direction > 0 else swing.last_swing_high
    spread_price = (state.spread or 0.0) * ctx.spec.point
    entry = price + direction * spread_price / 2  # a market order pays half the spread
    stop = compute_stop(direction, entry, swing_level, atr, cfg.levels)
    if stop is None:
        return _wait(state, [Refusal.RISK_LIMIT], [*chain, "no acceptable stop"], cfg)
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
        return _wait(state, [Refusal.RR_TOO_LOW], chain, cfg)
    # 8. SIZE
    lots: float | None = None
    if ctx.equity is not None:
        sized = size_for_risk(ctx.equity, cfg.risk_pct, entry, stop.price, ctx.spec)
        if not sized.allowed:
            return _wait(state, [Refusal.RISK_LIMIT], [*chain, *sized.reasons], cfg)
        lots = sized.lots
    decision = TradeDecision.BUY if direction > 0 else TradeDecision.SELL
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
        timestamp=state.timestamp,
        symbol=state.symbol,
        decision=decision,
        strategy_id=STRATEGY_ID,
        strategy_version=STRATEGY_VERSION,
        evidence_status=EvidenceLabel.UNVALIDATED_BASELINE,
        market_regime=state.h4_regime,
        h4_bias=state.h4_regime,
        h1_bias=state.h1_trend,
        m30_state=state.m30_structure,
        m15_setup=f"{state.m15_structure}/{state.m15_pullback}",
        m5_trigger=state.m5_momentum,
        m1_execution_state=state.m1_micro_state,
        entry_type=EntryType.MARKET,
        entry_price=entry,
        stop_loss=stop.price,
        take_profit=targets.tp1,
        take_profit_2=targets.tp2,
        risk_reward=targets.net_rr,
        required_win_rate=targets.required_win_rate,
        stop_model=stop.model,
        risk_pct=cfg.risk_pct,
        position_size=lots,
        spread=state.spread,
        atr=atr,
        volume_state=_volume_state(state),
        volume_type=state.volume_type,
        signal_expiry=state.timestamp + timedelta(minutes=5 * cfg.expiry_bars_m5),
        reasons=reasons,
        code_version=STRATEGY_VERSION,
        metadata={
            "gross_rr": targets.gross_rr,
            "capped_by_structure": str(targets.capped_by_structure),
        },
    )
