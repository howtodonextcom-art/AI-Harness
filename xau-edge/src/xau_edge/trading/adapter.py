"""Adapter from ``TradingSignal`` to the platform's existing ``Signal`` (the bridge's input).

The existing evidence gate stays untouched: a BUY/SELL baseline is expressed exactly as the
documented UNVALIDATED lean (ADR-0019 override): direction WAIT with the single reason
``NO_VALIDATED_EDGE``, the lean in ``candidate_direction`` and the levels filled in. Without the
operator's explicit override (enabled, strategy id named) the bridge refuses it, so the baseline
can never reach a broker by default. A WAIT keeps its mapped refusal reasons and no lean.
"""

from __future__ import annotations

from xau_edge.signals.schema import Direction, EvidenceStatus, NoTradeReason, Signal
from xau_edge.trading.schema import Refusal, TradeDecision, TradingSignal

_MAP: dict[Refusal, NoTradeReason] = {
    Refusal.SPREAD_TOO_WIDE: NoTradeReason.SPREAD_EXCESSIVE,
    Refusal.STALE_DATA: NoTradeReason.DATA_INVALID,
    Refusal.UNKNOWN_STATE: NoTradeReason.DATA_INVALID,
    Refusal.BROKER_DISCONNECTED: NoTradeReason.DATA_INVALID,
    Refusal.NEWS_WINDOW: NoTradeReason.NEWS_RISK,
    Refusal.TIMEFRAME_CONFLICT: NoTradeReason.HTF_BIAS_CONFLICT,
    Refusal.RR_TOO_LOW: NoTradeReason.RISK_REWARD_POOR,
    Refusal.NO_ENTRY_TRIGGER: NoTradeReason.ENTRY_QUALITY_POOR,
    Refusal.VOLATILITY_TOO_HIGH: NoTradeReason.REGIME_UNSUPPORTED,
    Refusal.VOLATILITY_TOO_LOW: NoTradeReason.REGIME_UNSUPPORTED,
}


def to_legacy_signal(signal: TradingSignal, *, timeframe: str = "M5") -> Signal:
    """The same decision in the schema the bridge, risk engine and journal already understand."""
    if signal.decision is TradeDecision.WAIT:
        reasons = tuple(
            dict.fromkeys(
                _MAP.get(r, NoTradeReason.EDGE_INSUFFICIENT) for r in signal.refusal_reasons
            )
        )
        return Signal(
            symbol=signal.symbol,
            timestamp=signal.timestamp,
            timeframe=timeframe,
            direction=Direction.WAIT,
            market_regime=signal.market_regime,
            higher_timeframe_bias=signal.h1_bias,
            explanation=signal.reasons,
            reasons=reasons,
            inputs_hash=signal.signal_id,
            code_version=signal.code_version,
        )
    lean = Direction.BUY if signal.decision is TradeDecision.BUY else Direction.SELL
    assert signal.entry_price is not None  # noqa: S101 - guaranteed by TradingSignal validation
    return Signal(
        symbol=signal.symbol,
        timestamp=signal.timestamp,
        timeframe=timeframe,
        direction=Direction.WAIT,
        candidate_direction=lean,
        market_regime=signal.market_regime,
        higher_timeframe_bias=signal.h1_bias,
        entry_zone=(signal.entry_price, signal.entry_price),
        stop_loss=signal.stop_loss,
        take_profit_1=signal.take_profit,
        take_profit_2=signal.take_profit_2,
        risk_reward=signal.risk_reward,
        signal_expiry=signal.signal_expiry,
        explanation=signal.reasons,
        evidence_status=EvidenceStatus.NONE,
        reasons=(NoTradeReason.NO_VALIDATED_EDGE,),
        inputs_hash=signal.signal_id,
        code_version=signal.code_version,
    )
