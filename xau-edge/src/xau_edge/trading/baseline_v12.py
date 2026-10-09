"""Baseline v1.2.0 decision (pre-registered in ``docs/trading/BASELINE_V1_2_PREREGISTRATION.md``).

Differences from v1.1.0 and nothing else:

A. setup lifecycle: the M15 setup ARMS, the M5 trigger fires later within a bounded window
   (``setup_machine``) instead of requiring both on the same bar; one signal per pullback;
B. plan geometry in the trigger's time scale: the stop floor, the structure buffer, the maximum
   stop and the target buffer use ATR(M5); the redundant ``clearance`` gate is removed (the
   net-R/R test already covers the room to the opposing M15 level);
C. the LOW / HIGH ATR-percentile labels are context (warning + ``entry_quality`` CAUTION), not
   vetoes. Hard protections stay: spread / abnormal M1, H4 SHOCK or HIGH_VOLATILITY, a volatile M1,
   and the maximum stop.

H1 stays the only source of direction, H4 only blocks, M30 is display only and M1 only blocks.
"""

from __future__ import annotations

from datetime import timedelta

from xau_edge.trading.baseline import (
    BLOCKING_H4,
    BaselineConfig,
    DecisionContext,
    _common,
    _expiry_anchor,
    _gates,
    _volume_state,
    _wait,
    m1_execution_state,
)
from xau_edge.trading.levels import compute_stop, compute_targets
from xau_edge.trading.market_state import MarketState
from xau_edge.trading.schema import (
    EntryType,
    EvidenceLabel,
    Refusal,
    TradeDecision,
    TradingSignal,
    make_signal_id,
)
from xau_edge.trading.setup_machine import SetupLifecycle, SetupPhase
from xau_edge.trading.sizing import size_for_risk


def decide_v12(  # noqa: PLR0911, PLR0912, PLR0915 - one refusal per link of the chain
    state: MarketState, ctx: DecisionContext, cfg: BaselineConfig
) -> TradingSignal:
    """The v1.2.0 baseline decision for ``state`` (deterministic)."""
    lc = ctx.lifecycle
    chain = [
        f"H4:{state.h4_regime}",
        f"H1:{state.h1_trend}",
        f"M30:{state.m30_structure} (context only)",
        f"M15:{state.m15_structure}/{state.m15_pullback}",
        f"SETUP:{'UNKNOWN' if lc is None else lc.phase.value}",
        f"M5:{state.m5_momentum}",
        f"M1:{m1_execution_state(state)}",
        f"SPREAD:{state.execution_quality}",
        f"VOLUME:{_volume_state(state)}({state.volume_type})",
    ]
    # hard gates only: volatility labels are context in v1.2 (warning below)
    hard = (
        cfg.model_copy(update={"block_high_volatility": False, "block_low_volatility": False})
        if cfg.v12_vol_warning
        else cfg
    )
    gates, warnings_t = _gates(state, ctx, hard)
    warnings = list(warnings_t)
    if cfg.v12_vol_warning and state.volatility_regime in ("LOW", "HIGH"):
        warnings.append(
            f"VOLATILITY {state.volatility_regime}: ATR(M15) is in the "
            f"{'bottom' if state.volatility_regime == 'LOW' else 'top'} fifth of its recent range"
        )
    if gates:
        return _wait(state, gates, chain, cfg, ctx, warnings=tuple(warnings))

    def wait(reason: Refusal, extra: str | None = None) -> TradingSignal:
        signal = _wait(
            state, [reason], [*chain, extra] if extra else chain, cfg, ctx, warnings=tuple(warnings)
        )
        if lc is None:
            return signal
        meta = {
            **signal.metadata,
            "setup_phase": lc.phase.value,
            "setup_bars_since_armed": lc.bars_since_armed,
        }
        return signal.model_copy(update={"metadata": meta})

    # 1. DIRECTION from H1 (the only source of direction)
    if state.h1_trend == "BULLISH":
        side, direction = "BUY", 1
    elif state.h1_trend == "BEARISH":
        side, direction = "SELL", -1
    else:
        return wait(Refusal.NO_DIRECTION)
    # 2. REGIME: H4 may veto the direction
    if state.h4_regime == BLOCKING_H4[side]:
        return wait(Refusal.TIMEFRAME_CONFLICT, f"H4 vetoes {side}")
    with_trend, against = ("UP", "DOWN") if direction > 0 else ("DOWN", "UP")
    turned = (
        state.m15_structure in (against, f"REVERSAL_{against}")
        if cfg.version == "1.2.1"
        else state.m15_structure == against
    )
    if turned:
        return wait(Refusal.TIMEFRAME_CONFLICT, "M15 against H1")
    # 3. SETUP lifecycle (M30 is context only)
    if cfg.v12_lifecycle:
        if lc is None:
            return wait(Refusal.UNKNOWN_STATE, "setup lifecycle unavailable")
        if lc.side != direction or lc.phase in (
            SetupPhase.NONE,
            SetupPhase.EXPIRED,
            SetupPhase.INVALIDATED,
        ):
            return wait(Refusal.NO_SETUP, lc.reason)
        if lc.phase is SetupPhase.ARMED:
            return wait(
                Refusal.NO_TRIGGER, f"setup armed {lc.bars_since_armed} M5 bars ago; waiting"
            )
        if not lc.fires:
            return wait(Refusal.NO_SETUP, "this pullback already produced its signal")
    else:  # ablation: v1.1 same-bar confluence
        pullback = "PULLBACK_IN_UPTREND" if direction > 0 else "PULLBACK_IN_DOWNTREND"
        if state.m15_structure != with_trend or state.m15_pullback != pullback:
            return wait(Refusal.NO_SETUP)
        if state.m5_momentum != with_trend:
            return wait(Refusal.NO_TRIGGER)
    # 4. TRIGGER is the lifecycle's TRIGGERED on the newest M5 close (checked above)
    # 5. EXECUTION quality on M1: it may only block
    exec_state = m1_execution_state(state, direction)
    if exec_state == "VOLATILE":
        return wait(Refusal.VOLATILITY_TOO_HIGH, "M1 volatile: range and volume")
    if exec_state == "QUIET" and cfg.block_quiet_m1:
        return wait(Refusal.VOLUME_TOO_LOW, "M1 tick volume far below its own average")
    if exec_state == "NOISY":
        return wait(Refusal.NO_TRIGGER, "M1 candle is strongly against the entry")
    if exec_state == "STALE" and cfg.require_m1:
        return wait(Refusal.STALE_DATA, "M1 feed missing")
    # 6. TRADE PLAN at the trigger's time scale (ATR M5); the room to the M15 level is judged by R/R
    atr = state.atr_m5 if cfg.v12_m5_geometry else state.atr_m15
    price = state.price
    if atr is None or atr <= 0 or price is None:
        return wait(Refusal.UNKNOWN_STATE)
    opposing = state.distance_to_resistance if direction > 0 else state.distance_to_support
    if (
        not cfg.v12_m5_geometry and opposing is not None and opposing < cfg.min_clear_atr * atr
    ):  # ablation: v1.1 clearance gate
        return wait(
            Refusal.TOO_CLOSE_TO_RESISTANCE if direction > 0 else Refusal.TOO_CLOSE_TO_SUPPORT
        )
    swing = state.snapshots.get("M5")
    swing_level = None
    if swing is not None:
        swing_level = swing.last_swing_low if direction > 0 else swing.last_swing_high
    spread_price = (state.spread or 0.0) * ctx.spec.point
    quote = ctx.ask if direction > 0 else ctx.bid
    entry = quote if quote is not None else price + direction * spread_price / 2
    stop = compute_stop(direction, entry, swing_level, atr, cfg.levels)
    if stop is None or stop.distance < ctx.spec.min_stop_distance():
        return wait(Refusal.INVALID_STOP_DISTANCE, "no acceptable stop")
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
    if targets is None:
        return wait(Refusal.RR_TOO_LOW)
    # 7. RISK: size from the broker's specification
    lots: float | None = None
    risk_amount: float | None = None
    if ctx.equity is not None:
        sized = size_for_risk(ctx.equity, cfg.risk_pct, entry, stop.price, ctx.spec)
        if not sized.allowed:
            return wait(Refusal.RISK_LIMIT, ", ".join(sized.reasons))
        lots, risk_amount = sized.lots, sized.risk_amount
    decision = TradeDecision.BUY if direction > 0 else TradeDecision.SELL
    _, trigger_close = _expiry_anchor(state)
    expiry = trigger_close + timedelta(minutes=5 * cfg.expiry_bars_m5)  # type: ignore[operator]
    caution = state.volatility_regime in ("LOW", "HIGH")
    entry_quality = (
        "CAUTION" if caution else "STRONG" if _volume_state(state) == "HIGH" else "ACCEPTABLE"
    )
    reasons = (
        *chain,
        f"setup armed {lc.bars_since_armed if lc else 0} M5 bars before the trigger",
        f"stop={stop.model} {stop.distance:.2f} (ATR M5 {atr:.2f})",
        f"net_rr={targets.net_rr:.2f}",
    )
    key: dict[str, object] = {
        "setup": side,
        "s": state.symbol,
        "armed": None if lc is None else lc.armed_at,
        "trigger": _trigger_key(state, lc, cfg),
        "v": cfg.version,
    }
    if _flags(cfg):
        key["flags"] = _flags(cfg)  # ablations never share an id with the production variant
    identity = make_signal_id(key)
    return TradingSignal(
        signal_id=make_signal_id(
            {
                "t": state.timestamp,
                "s": state.symbol,
                "v": cfg.version,
                "d": decision.value,
                "e": round(entry, 5),
                "sl": round(stop.price, 5),
                "tp": round(targets.tp1, 5),
                **({"flags": _flags(cfg)} if _flags(cfg) else {}),
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
        setup_id=identity,
        invalidation=(
            f"H1 turns {'bearish' if direction > 0 else 'bullish'}, or price closes beyond the stop"
        ),
        warnings=tuple(warnings),
        metadata={
            "gross_rr": targets.gross_rr,
            "capped_by_structure": str(targets.capped_by_structure),
            "setup_phase": "SAME_BAR" if lc is None else lc.phase.value,
            "setup_bars_since_armed": None if lc is None else lc.bars_since_armed,
            "m15_structure": state.m15_structure,
            "variant_flags": _flags(cfg),
        },
        **_common(state, cfg, ctx),
    )


def _flags(cfg: BaselineConfig) -> str:
    """Non-default ablation switches (empty for the production configuration)."""
    off = [
        name
        for name, on in (
            ("lifecycle", cfg.v12_lifecycle),
            ("m5_geometry", cfg.v12_m5_geometry),
            ("vol_warning", cfg.v12_vol_warning),
            ("spread_veto", cfg.spread_veto),
        )
        if not on
    ]
    return ",".join(f"no_{n}" for n in off)


def _trigger_key(state: MarketState, lc: SetupLifecycle | None, cfg: BaselineConfig) -> object:
    """Identity of the trigger bar: the lifecycle's, or (ablation) the M5 bar that triggered."""
    if lc is not None and cfg.v12_lifecycle:
        return lc.trigger_at
    m5 = state.snapshots.get("M5")
    return state.timestamp if m5 is None else m5.bar_open
