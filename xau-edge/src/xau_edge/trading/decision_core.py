"""One pure function from a market snapshot to a decision: the SAME path for live, replay and paper.

``evaluate`` takes closed bars, the executable quote, the broker specification and flags, and
returns the ``MarketState`` and the ``TradingSignal``. Live dry-run, the replay smoke test and the
paper desk all call it, so "same snapshot -> same decision" is true by construction and is tested
as a parity requirement (a mismatch is a blocker). It performs no I/O and reads no clock.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any

from xau_edge.market_data.broker_clock import BrokerClock
from xau_edge.trading.baseline import BaselineConfig, DecisionContext, decide
from xau_edge.trading.frames import MultiTfBars
from xau_edge.trading.market_state import MarketState, SnapshotMemo, build_market_state
from xau_edge.trading.schema import Refusal, TradeDecision, TradingSignal
from xau_edge.trading.setup_machine import lifecycle
from xau_edge.trading.sizing import SymbolSpec

ROLES = {
    "H4": "REGIME / BLOCKER",
    "H1": "DIRECTION",
    "M30": "CONTEXT (display only)",
    "M15": "SETUP",
    "M5": "TRIGGER",
    "M1": "EXECUTION TIMING",
}
REFUSAL_TEXT = {
    Refusal.NO_DIRECTION: "H1 has no clear direction",
    Refusal.TIMEFRAME_CONFLICT: "the timeframes conflict (H4 or M15 is against H1)",
    Refusal.NO_SETUP: "no M15 pullback setup inside the H1 trend",
    Refusal.NO_TRIGGER: "M5 has not triggered (or M1 is strongly against the entry)",
    Refusal.SPREAD_TOO_WIDE: "the spread is too wide for this volatility",
    Refusal.VOLUME_TOO_LOW: "M1 tick volume is far below its own average (quiet market)",
    Refusal.VOLATILITY_TOO_HIGH: "volatility is too high (or M1 is abnormal)",
    Refusal.VOLATILITY_TOO_LOW: "volatility is too low",
    Refusal.TOO_CLOSE_TO_RESISTANCE: "too close to resistance for a BUY",
    Refusal.TOO_CLOSE_TO_SUPPORT: "too close to support for a SELL",
    Refusal.RR_TOO_LOW: "no target gives the minimum net risk/reward",
    Refusal.INVALID_STOP_DISTANCE: "no acceptable stop distance (broker minimum or too wide)",
    Refusal.RISK_LIMIT: "a risk limit blocks the trade (or the lot is below the broker minimum)",
    Refusal.DAILY_LIMIT: "the daily limit is reached",
    Refusal.COOLDOWN: "cooling down after the previous trade",
    Refusal.NEWS_UNKNOWN: "news is not verified (no economic calendar)",
    Refusal.NEWS_WINDOW: "inside a high-impact news window",
    Refusal.STALE_DATA: "market data is stale",
    Refusal.MARKET_CLOSED: "the market is closed",
    Refusal.BROKER_DISCONNECTED: "the broker is disconnected",
    Refusal.UNKNOWN_STATE: "a required timeframe or the broker specification is missing",
}


@dataclass(frozen=True)
class SnapshotInputs:
    """What one decision looks at. No clock, no files."""

    bars: MultiTfBars
    now: datetime
    bid: float | None
    ask: float | None
    spread_points: float | None
    spec: SymbolSpec | None
    equity: float | None
    news_state: str
    market_open: bool
    data_ok: bool


def evaluate_many(
    inputs: SnapshotInputs,
    configs: dict[str, BaselineConfig],
    clock: BrokerClock | None,
    memo: SnapshotMemo | None = None,
) -> tuple[MarketState, dict[str, TradingSignal]]:
    """One market state (and one setup lifecycle) shared by several baseline variants.

    The variants differ only in ``decide``; the market state and the lifecycle are pure functions
    of the closed bars, so computing them once per decision gives exactly the decisions that
    ``evaluate`` would give for each variant separately (a test asserts it).
    """
    state = build_market_state(
        inputs.bars,
        inputs.now,
        spread_points=inputs.spread_points,
        news_state=inputs.news_state,
        broker_clock=clock,
        market_open=inputs.market_open,
        memo=memo,
    )
    spec = inputs.spec or SymbolSpec()
    life = (
        lifecycle(inputs.bars, inputs.now, memo=memo)
        if any(c.version == "1.2.0" for c in configs.values())
        else None
    )  # v1.2 only: a pure function of the closed bars
    base = DecisionContext(
        spec=spec,
        equity=inputs.equity,
        market_open=inputs.market_open,
        data_ok=inputs.data_ok,
        spec_known=inputs.spec is not None,
        bid=inputs.bid,
        ask=inputs.ask,
    )
    signals = {
        name: decide(
            state,
            replace(base, lifecycle=life) if cfg.version == "1.2.0" else base,
            cfg,
        )
        for name, cfg in configs.items()
    }
    return state, signals


def evaluate(
    inputs: SnapshotInputs,
    config: BaselineConfig,
    clock: BrokerClock | None,
    memo: SnapshotMemo | None = None,
) -> tuple[MarketState, TradingSignal]:
    """The market state and the decision for ``inputs`` (deterministic)."""
    state, signals = evaluate_many(inputs, {"v": config}, clock, memo)
    return state, signals["v"]


def comparable(signal: TradingSignal) -> dict[str, Any]:
    """The part of a decision that must be IDENTICAL across live, replay and paper."""
    return {
        "decision": signal.decision.value,
        "entry": signal.entry_price,
        "sl": signal.stop_loss,
        "tp": signal.take_profit,
        "rr": signal.risk_reward,
        "lots": signal.position_size,
        "refusals": [r.value for r in signal.refusal_reasons],
        "reasons": list(signal.reasons),
        "setup_id": signal.setup_id,
        "expiry": None if signal.signal_expiry is None else signal.signal_expiry.isoformat(),
    }


def explain(signal: TradingSignal) -> list[str]:
    """Plain sentences for the screen: why BUY/SELL, or exactly why WAIT."""
    if signal.decision is TradeDecision.WAIT:
        lines = [REFUSAL_TEXT.get(r, r.value) for r in signal.refusal_reasons]
        return [f"WAIT because: {line}" for line in lines]
    side = signal.decision.value
    lines = [
        f"{side}: H1 direction is {signal.h1_bias.lower()}",
        f"M15 setup: {signal.m15_setup}",
        f"M5 trigger: {signal.m5_trigger}",
        f"M1 execution: {signal.m1_execution_state} (tick volume {signal.volume_state})",
        f"spread {signal.spread_state}, volatility {signal.volatility_regime}",
        f"stop {signal.stop_model}, net R/R {signal.risk_reward:.2f}"
        if signal.risk_reward is not None
        else "",
    ]
    return [line for line in lines if line]
