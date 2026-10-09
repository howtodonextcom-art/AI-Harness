"""Decision funnel diagnostics: the state of EVERY gate for one decision, never short-circuited.

``decide`` stops at the first refusal, which hides everything downstream. ``gate_vector`` evaluates
each gate of the baseline independently from the same ``MarketState`` and the same context, so the
pass rate, the conditional pass rate and the interaction of gates can be measured. It changes no
trading behaviour and is not used to decide; ``stage_report`` turns a decision plus the vector into
the ordered PASS / FAIL / not-reached list shown by the "Why WAIT?" drawer.

Gate values: ``True`` = passes, ``False`` = blocks, ``None`` = cannot be evaluated (a prerequisite
such as the H1 direction is missing).
"""

from __future__ import annotations

from typing import Any

from xau_edge.trading.baseline import BaselineConfig, DecisionContext, m1_execution_state
from xau_edge.trading.levels import compute_stop, compute_targets
from xau_edge.trading.market_state import MarketState
from xau_edge.trading.schema import TradeDecision, TradingSignal
from xau_edge.trading.sizing import size_for_risk

GATES = (
    "market_open",
    "data_ok",
    "spec_ok",
    "spread_ok",
    "vol_not_high",
    "vol_not_low",
    "h4_regime_ok",
    "h1_directional",
    "h4_not_against",
    "m15_not_against",
    "m15_structure_with",
    "m15_pullback",
    "m15_setup",
    "m5_trigger",
    "m1_not_volatile",
    "m1_not_quiet",
    "m1_not_noisy",
    "clearance_ok",
    "stop_ok",
    "rr_ok",
    "risk_ok",
)


def _direction(state: MarketState) -> int:
    return 1 if state.h1_trend == "BULLISH" else -1 if state.h1_trend == "BEARISH" else 0


def gate_vector(
    state: MarketState, ctx: DecisionContext, cfg: BaselineConfig
) -> dict[str, bool | None]:
    """Every gate of the v1.1 chain, evaluated independently."""
    out: dict[str, bool | None] = dict.fromkeys(GATES)
    out["market_open"] = bool(ctx.market_open and state.market_open)
    out["data_ok"] = state.data_quality not in ("STALE", "UNKNOWN") and ctx.data_ok
    out["spec_ok"] = ctx.spec_known and "H1" in state.available_timeframes
    out["spread_ok"] = state.execution_quality == "GOOD"
    out["vol_not_high"] = state.volatility_regime != "HIGH"
    out["vol_not_low"] = state.volatility_regime != "LOW"
    out["h4_regime_ok"] = state.h4_regime not in cfg.blocked_regimes
    direction = _direction(state)
    out["h1_directional"] = direction != 0
    if direction == 0:
        return out
    side = "BUY" if direction > 0 else "SELL"
    out["h4_not_against"] = state.h4_regime != ("TREND_DOWN" if side == "BUY" else "TREND_UP")
    with_trend, against = ("UP", "DOWN") if direction > 0 else ("DOWN", "UP")
    out["m15_not_against"] = state.m15_structure != against
    out["m15_structure_with"] = state.m15_structure == with_trend
    pullback = "PULLBACK_IN_UPTREND" if direction > 0 else "PULLBACK_IN_DOWNTREND"
    out["m15_pullback"] = state.m15_pullback == pullback
    out["m15_setup"] = bool(out["m15_structure_with"] and out["m15_pullback"])
    out["m5_trigger"] = state.m5_momentum == with_trend
    micro = m1_execution_state(state, direction)
    out["m1_not_volatile"] = micro != "VOLATILE"
    out["m1_not_quiet"] = micro != "QUIET"
    out["m1_not_noisy"] = micro != "NOISY"
    atr, price = state.atr_m15, state.price
    if atr is None or atr <= 0 or price is None:
        return out
    opposing = state.distance_to_resistance if direction > 0 else state.distance_to_support
    out["clearance_ok"] = opposing is None or opposing >= cfg.min_clear_atr * atr
    swing = state.snapshots.get("M5")
    swing_level = None
    if swing is not None:
        swing_level = swing.last_swing_low if direction > 0 else swing.last_swing_high
    spread_price = (state.spread or 0.0) * ctx.spec.point
    quote = ctx.ask if direction > 0 else ctx.bid
    entry = quote if quote is not None else price + direction * spread_price / 2
    stop = compute_stop(direction, entry, swing_level, atr, cfg.levels)
    out["stop_ok"] = stop is not None and stop.distance >= ctx.spec.min_stop_distance()
    if stop is None or not out["stop_ok"]:
        return out
    opposing_level = None if opposing is None else price + direction * opposing
    targets = compute_targets(
        direction,
        entry,
        stop,
        cfg.levels,
        spread=spread_price,
        atr=atr,
        opposing_level=opposing_level,
    )
    out["rr_ok"] = targets is not None
    if targets is None:
        return out
    if ctx.equity is None:
        out["risk_ok"] = True
    else:
        out["risk_ok"] = size_for_risk(
            ctx.equity, cfg.risk_pct, entry, stop.price, ctx.spec
        ).allowed
    return out


def raw_features(state: MarketState) -> dict[str, Any]:
    """The continuous values behind the labels (for forensics only)."""
    m15 = state.snapshots.get("M15")
    m5 = state.snapshots.get("M5")
    h1 = state.snapshots.get("H1")
    return {
        "atr_pct_m15": None if m15 is None else m15.atr_percentile,
        "atr_m15": state.atr_m15,
        "atr_m5": state.atr_m5,
        "spread": state.spread,
        "spread_pct": state.spread_percentile,
        "spread_to_atr_m5": state.spread_to_atr_m5,
        "m15_pve": None if m15 is None else m15.price_vs_ema_atr,
        "m15_trend": None if m15 is None else m15.structure_trend,
        "m15_choch": None if m15 is None else m15.choch_recent,
        "m5_roc": None if m5 is None else m5.roc,
        "m5_rsi": None if m5 is None else m5.rsi,
        "m5_bos": None if m5 is None else m5.bos_recent,
        "m5_body": None if m5 is None else m5.patterns.get("strong_body", 0),
        "h1_close_vs_slow": None if h1 is None or h1.ema_slow is None else h1.close - h1.ema_slow,
        "m1_z": state.volume_zscore_m1,
        "labels": {
            "h4": state.h4_regime,
            "h1": state.h1_trend,
            "m15s": state.m15_structure,
            "m15p": state.m15_pullback,
            "m5": state.m5_momentum,
            "m1": state.m1_micro_state,
            "vol": state.volatility_regime,
            "exec": state.execution_quality,
            "session": state.session,
        },
    }


STAGES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Market & data", ("market_open", "data_ok", "spec_ok")),
    ("Spread & volatility", ("spread_ok", "vol_not_high", "vol_not_low")),
    ("H4 regime", ("h4_regime_ok", "h4_not_against")),
    ("H1 direction", ("h1_directional",)),
    ("M15 setup", ("m15_not_against", "m15_setup")),
    ("M5 trigger", ("m5_trigger",)),
    ("M1 execution", ("m1_not_volatile", "m1_not_quiet", "m1_not_noisy")),
    ("Trade plan", ("clearance_ok", "stop_ok", "rr_ok", "risk_ok")),
)


def stage_report(
    signal: TradingSignal, vector: dict[str, bool | None]
) -> list[dict[str, str | list[str]]]:
    """Ordered PASS / FAIL / NOT_REACHED per stage, consistent with the actual decision."""
    out: list[dict[str, str | list[str]]] = []
    blocked = signal.decision is TradeDecision.WAIT
    stopped = False
    for name, gates in STAGES:
        failed = [g for g in gates if vector.get(g) is False]
        if stopped:
            out.append({"stage": name, "status": "NOT_REACHED", "failed": []})
        elif failed and blocked:
            out.append({"stage": name, "status": "FAIL", "failed": failed})
            stopped = True
        else:
            out.append({"stage": name, "status": "PASS", "failed": []})
    return out
