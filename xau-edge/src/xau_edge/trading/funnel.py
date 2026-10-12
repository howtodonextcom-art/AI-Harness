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
from xau_edge.trading.schema import Refusal, TradeDecision, TradingSignal
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


STAGE_NAMES = (
    "Market & data",
    "Spread & regime",
    "H1 direction",
    "H4 / M15 alignment",
    "M15 setup",
    "M5 trigger",
    "M1 execution",
    "Trade plan",
)
_STAGE_OF = {
    Refusal.MARKET_CLOSED: 0,
    Refusal.STALE_DATA: 0,
    Refusal.UNKNOWN_STATE: 0,
    Refusal.BROKER_DISCONNECTED: 0,
    Refusal.NEWS_WINDOW: 0,
    Refusal.NEWS_UNKNOWN: 0,
    Refusal.SPREAD_TOO_WIDE: 1,
    Refusal.VOLATILITY_TOO_HIGH: 1,
    Refusal.VOLATILITY_TOO_LOW: 1,
    Refusal.COOLDOWN: 1,
    Refusal.DAILY_LIMIT: 1,
    Refusal.RISK_LIMIT: 7,
    Refusal.NO_DIRECTION: 2,
    Refusal.TIMEFRAME_CONFLICT: 3,
    Refusal.NO_SETUP: 4,
    Refusal.NO_TRIGGER: 5,
    Refusal.VOLUME_TOO_LOW: 6,
    Refusal.TOO_CLOSE_TO_RESISTANCE: 7,
    Refusal.TOO_CLOSE_TO_SUPPORT: 7,
    Refusal.INVALID_STOP_DISTANCE: 7,
    Refusal.RR_TOO_LOW: 7,
}


STAGE_TIMEFRAME = {
    "Market & data": "M5",
    "Spread & regime": "H4",
    "H1 direction": "H1",
    "H4 / M15 alignment": "M15",
    "M15 setup": "M15",
    "M5 trigger": "M5",
    "M1 execution": "M1",
    "Trade plan": "M5",
}
"""The chart timeframe that best shows each stage (a clicked row switches the chart to it)."""


def stages_from_signal(signal: TradingSignal) -> list[dict[str, str]]:
    """Ordered PASS / FAIL / NOT_REACHED per stage, derived from the REAL decision.

    ``decide`` short-circuits in this exact order, so the first refusal marks the failing stage:
    every earlier stage passed and every later one was not reached. A BUY/SELL passes all stages.
    """
    failing: int | None = None
    if signal.decision is TradeDecision.WAIT and signal.refusal_reasons:
        failing = min(_STAGE_OF.get(r, 0) for r in signal.refusal_reasons)
    out: list[dict[str, str]] = []
    for index, name in enumerate(STAGE_NAMES):
        if failing is None or index < failing:
            status = "PASS"
        elif index == failing:
            status = "FAIL"
        else:
            status = "NOT_REACHED"
        out.append({"stage": name, "status": status, "timeframe": STAGE_TIMEFRAME[name]})
    return out


def waiting_for(signal: TradingSignal) -> str | None:
    """The single next condition for a WAIT (explanatory state, never a forecast)."""
    if signal.decision is not TradeDecision.WAIT or not signal.refusal_reasons:
        return None
    first = signal.refusal_reasons[0]
    side = "bullish" if signal.h1_bias == "BULLISH" else "bearish"
    phase = signal.metadata.get("setup_phase")
    if first is Refusal.NO_TRIGGER and phase == "ARMED":
        age = signal.metadata.get("setup_bars_since_armed")
        return f"M5 {side} trigger (setup armed {age} M5 bars ago)"
    texts = {
        Refusal.NO_DIRECTION: "H1 to establish a bullish or bearish direction",
        Refusal.TIMEFRAME_CONFLICT: "H4 and M15 to stop opposing the H1 direction",
        Refusal.NO_SETUP: "an M15 pullback inside the H1 trend (it then stays armed 6 M5 bars)",
        Refusal.NO_TRIGGER: f"an M5 {side} trigger",
        Refusal.SPREAD_TOO_WIDE: "the spread to return to a normal level",
        Refusal.VOLATILITY_TOO_HIGH: "the abnormal volatility to settle",
        Refusal.VOLATILITY_TOO_LOW: "volatility to pick up",
        Refusal.VOLUME_TOO_LOW: "M1 tick volume to recover",
        Refusal.RR_TOO_LOW: "a plan with 1.5 net risk/reward (not enough room to the next level)",
        Refusal.TOO_CLOSE_TO_RESISTANCE: "more room to the next resistance",
        Refusal.TOO_CLOSE_TO_SUPPORT: "more room to the next support",
        Refusal.INVALID_STOP_DISTANCE: "a valid stop distance",
        Refusal.RISK_LIMIT: "a position size above the broker minimum within the risk limit",
        Refusal.MARKET_CLOSED: "the market to open",
        Refusal.STALE_DATA: "fresh market data",
        Refusal.UNKNOWN_STATE: "all timeframes and the broker specification",
        Refusal.COOLDOWN: "the cooldown to end",
        Refusal.DAILY_LIMIT: "the next trading day",
        Refusal.NEWS_UNKNOWN: "news to be verified",
        Refusal.NEWS_WINDOW: "the news window to pass",
        Refusal.BROKER_DISCONNECTED: "the broker connection",
    }
    return texts.get(first)


_AUTH_STAGE_PLAN = 7
"""Index of the last stage ("Trade plan"): reached only when every earlier stage passed."""


def _bias_of(signal: TradingSignal) -> tuple[str, str]:
    """(BUY | SELL | NEUTRAL, with-trend structure word) from H1, the only source of direction."""
    if signal.h1_bias == "BULLISH":
        return "BUY", "UP"
    if signal.h1_bias == "BEARISH":
        return "SELL", "DOWN"
    return "NEUTRAL", ""


def _diag_rows(signal: TradingSignal, side: str, with_trend: str) -> list[tuple[str, str, str]]:
    """(stage, PASS | FAIL | NOT_EVALUATED, observed) for every stage, from the recorded state."""
    refusals = set(signal.refusal_reasons)
    stage0 = any(_STAGE_OF.get(r, 0) == 0 for r in refusals)
    stage1 = any(_STAGE_OF.get(r, 0) == 1 for r in refusals)
    m15_structure, _, m15_pullback = signal.m15_setup.partition("/")
    skip = "NOT_EVALUATED"
    live = not stage0  # the readings below are meaningless when the market or the data is unusable
    directed = live and side != "NEUTRAL"
    vetoes = {"BUY": "TREND_DOWN", "SELL": "TREND_UP"}
    against = {"UP": "DOWN", "DOWN": "UP"}.get(with_trend, "")
    pullback = {"BUY": "PULLBACK_IN_UPTREND", "SELL": "PULLBACK_IN_DOWNTREND"}.get(side, "")
    align_ok = signal.h4_bias != vetoes.get(side) and m15_structure != against
    plan_ok = signal.decision is not TradeDecision.WAIT
    plan_failed = (
        directed and not plan_ok and any(_STAGE_OF.get(r, 0) == _AUTH_STAGE_PLAN for r in refusals)
    )
    return [
        (STAGE_NAMES[0], "FAIL" if stage0 else "PASS", "market/data"),
        (
            STAGE_NAMES[1],
            skip if not live else "FAIL" if stage1 else "PASS",
            f"{signal.spread_state}/{signal.volatility_regime}",
        ),
        (
            STAGE_NAMES[2],
            skip if not live else "PASS" if side != "NEUTRAL" else "FAIL",
            f"H1:{signal.h1_bias}",
        ),
        (
            STAGE_NAMES[3],
            skip if not directed else "PASS" if align_ok else "FAIL",
            f"H4:{signal.h4_bias} M15:{m15_structure}",
        ),
        (
            STAGE_NAMES[4],
            skip
            if not directed
            else "PASS"
            if m15_structure == with_trend and m15_pullback == pullback
            else "FAIL",
            f"M15:{signal.m15_setup}",
        ),
        (
            STAGE_NAMES[5],
            skip if not directed else "PASS" if signal.m5_trigger == with_trend else "FAIL",
            f"M5:{signal.m5_trigger}",
        ),
        (
            STAGE_NAMES[6],
            skip if not directed else "PASS" if signal.m1_execution_state == "GOOD" else "FAIL",
            f"M1:{signal.m1_execution_state}",
        ),
        (STAGE_NAMES[7], "PASS" if plan_ok else "FAIL" if plan_failed else skip, "plan"),
    ]


def diagnostic_from_signal(signal: TradingSignal) -> dict[str, Any]:
    """The WHOLE funnel for a human: every stage judged from the recorded state.

    This is an explanation, never an authorization: ``decide`` still stops at the first refusal and
    its
    ``refusal_reasons`` remain the only thing that allows or forbids a trade. The bias (H1) is shown
    separately from the action so "the system sees an uptrend" is never read as "BUY is allowed".
    """
    side, with_trend = _bias_of(signal)
    rows = _diag_rows(signal, side, with_trend)
    trade = signal.decision is not TradeDecision.WAIT
    if trade:
        rows = [(n, "PASS", o) for n, _, o in rows]
    first = signal.refusal_reasons[0].value if signal.refusal_reasons and not trade else None
    primary_stage = min((_STAGE_OF.get(r, 0) for r in signal.refusal_reasons), default=None)
    failed = [n for n, s, _ in rows if s == "FAIL"]
    primary_name = None if primary_stage is None or trade else STAGE_NAMES[primary_stage]
    return {
        "bias": {"side": side, "source": "H1", "reading": signal.h1_bias},
        "action": signal.decision.value,
        "rows": [
            {"stage": n, "status": s, "timeframe": STAGE_TIMEFRAME[n], "observed": o}
            for n, s, o in rows
        ],
        "required_total": len(STAGE_NAMES),
        "required_passed": sum(1 for _, s, _ in rows if s == "PASS"),
        "primary_blocker": first,
        "primary_stage": primary_name,
        "also_missing": [n for n in failed if n != primary_name],
    }
