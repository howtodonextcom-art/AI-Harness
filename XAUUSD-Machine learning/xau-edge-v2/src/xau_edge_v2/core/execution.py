"""M1 execution intelligence (G10): "is this a good MOMENT to act on an idea the higher timeframes
already support?" It never says which way the market goes.

Ownership (unchanged, and enforced by the tests):

* direction  -> H4 / H1 (the strategy's ``h1_trend``; M1 can only copy it, never flip it);
* setup      -> M15 (the strategy's pullback);
* trigger    -> M5 (the strategy's momentum);
* M1         -> timing: spread, immediate price behaviour, and whether the geometry still pays.

This module is ADVISORY. It reads the strategy's decision and state and never feeds back into
them: the strategy files are pinned byte for byte (``tests/unit/test_strategy_lock.py``).

No new alpha and no new tuned numbers. Every threshold is a constant the strategy already uses:

=================================  ==============================================================
``MIN_NET_RR`` (1.5)               net R:R below this = the idea no longer pays (TOO_LATE)
``min_clear_atr`` (1.0 ATR M15)    room left to the opposing level below this = TOO_LATE
``STRONG_BODY`` (0.6)              a strong body fills >= 60% of the candle (the strategy's pattern)
``HALF`` (0.5)                     a wick of >= half the candle is a rejection (the pin-bar rule)
``FAILED_LOOKBACK`` (10)           the failed-breakout window of the strategy's pattern set
spread percentile >= 0.9 / spread  the strategy's own "spread is wide" gate (POOR execution quality)
/ ATR(M5) > 0.15
=================================  ==============================================================

The PLANNED trade is the one the strategy's own functions give at the last closed M5 bar (the
trigger): entry = that close plus half the spread, stop and targets from ``compute_stop`` /
``compute_targets``. Lateness is then measured against that plan with the live price.

States (applicable once an idea is supported, i.e. the strategy's readiness is at least 3):

TOO_EARLY         setup armed, the M5 trigger is not confirmed yet
WATCH             trigger confirmed, M1 shows nothing in the trade direction yet
FORMING           M1 starts to move with the trade
CONFIRMED         the last closed M1 candle confirms (strong body with, no rejection against)
EXECUTION_WINDOW  CONFIRMED and clean: spread normal, micro-volatility normal, geometry intact
TOO_LATE          the geometry no longer pays (net R:R < 1.5, or no room left) vs the plan
INVALIDATED       price is at/through the planned stop
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from xau_edge_v2.core.decision import Decision
from xau_edge_v2.core.frames import Frame
from xau_edge_v2.core.market_state import MarketState
from xau_edge_v2.core.risk import MIN_NET_RR, SymbolSpec, compute_stop, compute_targets

State = Literal[
    "TOO_EARLY", "WATCH", "FORMING", "CONFIRMED", "EXECUTION_WINDOW", "TOO_LATE", "INVALIDATED"
]
Quality = Literal["GOOD", "CAUTION", "BAD"]
Feature = float | bool | str | None

STRONG_BODY = 0.6
HALF = 0.5
FAILED_LOOKBACK = 10
MIN_CLEAR_ATR = 1.0
WIDE_SPREAD_PERCENTILE = 0.9
MIN_BARS = FAILED_LOOKBACK + 2
SUPPORTED_FROM_LEVEL = 3  # SETUP_ARMED
TRIGGER_LEVEL = 4  # TRIGGER


@dataclass(frozen=True)
class ExecutionAssessment:
    applicable: bool
    reason: str
    """When not applicable: why. When applicable: the one-line summary of the state."""
    direction: int = 0
    """+1 BUY / -1 SELL, COPIED from the strategy's H1 bias (never produced here)."""
    state: State | None = None
    quality: Quality | None = None
    reasons: tuple[str, ...] = ()
    features: dict[str, Feature] = field(default_factory=dict)
    planned_entry: float | None = None
    planned_stop: float | None = None
    planned_target: float | None = None
    net_rr_now: float | None = None
    price_now: float | None = None


def not_applicable(why: str) -> ExecutionAssessment:
    return ExecutionAssessment(applicable=False, reason=why)


def _wick_parts(
    o: float, h: float, lo: float, c: float, side: int
) -> tuple[float, float, float, float]:
    """(body_dir, close_location, favourable_wick, adverse_wick) as fractions of the candle range."""
    rng = h - lo
    if rng <= 0:
        return 0.0, 0.5, 0.0, 0.0
    body_dir = side * (c - o) / rng
    lower = (min(o, c) - lo) / rng
    upper = (h - max(o, c)) / rng
    if side > 0:
        return body_dir, (c - lo) / rng, lower, upper  # a long LOWER wick supports a buy
    return body_dir, (h - c) / rng, upper, lower


def assess_execution(  # noqa: PLR0912, PLR0915 - one branch per documented state
    decision: Decision,
    state: MarketState,
    m1: Frame | None,
    spec: SymbolSpec,
    *,
    bid: float | None = None,
    ask: float | None = None,
) -> ExecutionAssessment:
    """The M1 execution state for the idea the strategy currently supports (or not applicable)."""
    if decision.readiness_level < SUPPORTED_FROM_LEVEL or state.h1_trend not in (
        "BULLISH",
        "BEARISH",
    ):
        return not_applicable("chưa có setup được khung lớn ủng hộ (M1 chỉ xét thời điểm thực thi)")
    side = 1 if state.h1_trend == "BULLISH" else -1
    if "M1" not in state.available_timeframes or "M1" in state.stale_timeframes:
        return not_applicable("nến M1 thiếu hoặc cũ")
    if m1 is None or m1.height < MIN_BARS:
        return not_applicable("chưa đủ nến M1 đã đóng")
    m5 = state.snapshots.get("M5")
    atr = state.atr_m15
    if m5 is None or atr is None or atr <= 0:
        return not_applicable("thiếu dữ liệu M5/ATR để dựng kế hoạch tại thời điểm trigger")

    spread_price = (state.spread or 0.0) * spec.point
    entry_p = m5.close + side * spread_price / 2
    swing = m5.last_swing_low if side > 0 else m5.last_swing_high
    stop = compute_stop(side, entry_p, swing, atr)
    opposing = state.distance_to_resistance if side > 0 else state.distance_to_support
    opposing_level = (
        None if opposing is None or state.price is None else state.price + side * opposing
    )
    targets = (
        None
        if stop is None
        else compute_targets(
            side, entry_p, stop, spread=spread_price, atr=atr, opposing_level=opposing_level
        )
    )
    if stop is None or targets is None:
        return ExecutionAssessment(
            applicable=False,
            reason="kế hoạch tại thời điểm trigger không hợp lệ (SL hoặc R:R ròng không đạt)",
            direction=side,
        )

    last_close = float(m1.close[-1])
    quote = ask if side > 0 else bid
    px = quote if quote is not None else last_close + side * spread_price / 2
    reward_now = side * (targets.tp1 - px)
    risk_now = side * (px - stop.price)
    net_rr_now = (
        (reward_now - spread_price) / (risk_now + spread_price)
        if reward_now > 0 and risk_now + spread_price > 0
        else None
    )
    chase = side * (px - entry_p)
    room_atr = None if opposing_level is None else side * (opposing_level - px) / atr
    o, h, lo, c = (float(a[-1]) for a in (m1.open, m1.high, m1.low, m1.close))
    body_dir, close_loc, fav_wick, adv_wick = _wick_parts(o, h, lo, c, side)
    mom3 = side * (float(m1.close[-1]) - float(m1.close[-4]))
    prior_hi = float(m1.high[-1 - FAILED_LOOKBACK : -1].max())
    prior_lo = float(m1.low[-1 - FAILED_LOOKBACK : -1].min())
    up_fail = h > prior_hi and c <= prior_hi
    down_fail = lo < prior_lo and c >= prior_lo
    failed_adverse = up_fail if side > 0 else down_fail
    failed_favourable = down_fail if side > 0 else up_fail
    stop_closed_through = side * (last_close - stop.price) <= 0
    features: dict[str, Feature] = {
        "spread_points": state.spread,
        "spread_percentile": state.spread_percentile,
        "spread_to_atr_m5": state.spread_to_atr_m5,
        "micro_state": state.m1_micro_state,
        "execution_quality": state.execution_quality,
        "body_dir": round(body_dir, 3),
        "close_location": round(close_loc, 3),
        "favourable_wick": round(fav_wick, 3),
        "adverse_wick": round(adv_wick, 3),
        "momentum_3": round(mom3, 3),
        "failed_breakout_against": failed_adverse,
        "failed_breakout_with": failed_favourable,
        "chase_price": round(chase, 3),
        "chase_atr_m5": None if not state.atr_m5 else round(chase / state.atr_m5, 3),
        "chase_r": round(chase / stop.distance, 3),
        "room_to_opposing_atr_m15": None if room_atr is None else round(room_atr, 3),
        "net_rr_now": None if net_rr_now is None else round(net_rr_now, 3),
        "net_rr_planned": round(targets.net_rr, 3),
    }

    reasons: list[str] = []
    wide = state.execution_quality == "POOR" or (
        state.spread_percentile is not None and state.spread_percentile >= WIDE_SPREAD_PERCENTILE
    )
    verdict: State
    if risk_now <= 0 or stop_closed_through:
        verdict = "INVALIDATED"
        reasons.append(f"giá đã chạm/vượt SL của kế hoạch ({stop.price:.2f})")
    elif (
        net_rr_now is None
        or net_rr_now < MIN_NET_RR
        or (room_atr is not None and room_atr < MIN_CLEAR_ATR)
    ):
        verdict = "TOO_LATE"
        if net_rr_now is None or net_rr_now < MIN_NET_RR:
            shown = "không còn phần thưởng" if net_rr_now is None else f"{net_rr_now:.2f}"
            reasons.append(
                f"R:R ròng hiện tại {shown} < {MIN_NET_RR} "
                f"(kế hoạch lúc trigger: vào {entry_p:.2f}, SL {stop.price:.2f}, TP {targets.tp1:.2f}; "
                f"giá đã đi {chase:+.2f})"
            )
        if room_atr is not None and room_atr < MIN_CLEAR_ATR:
            reasons.append(f"chỉ còn {room_atr:.2f} ATR tới mức đối diện (cần ≥ {MIN_CLEAR_ATR:g})")
    elif decision.readiness_level < TRIGGER_LEVEL:
        verdict = "TOO_EARLY"
        reasons.append("setup đã armed nhưng M5 chưa xác nhận trigger")
    else:
        confirmed = body_dir >= STRONG_BODY and adv_wick < HALF and not failed_adverse
        if confirmed:
            clean = (
                not wide
                and state.m1_micro_state not in ("ABNORMAL", "QUIET")
                and state.execution_quality == "GOOD"
            )
            verdict = "EXECUTION_WINDOW" if clean else "CONFIRMED"
            reasons.append(
                f"nến M1 xác nhận: thân cùng chiều {body_dir:.0%} (≥ {STRONG_BODY:.0%}), "
                f"bấc ngược {adv_wick:.0%} (< {HALF:.0%})"
            )
            reasons.append(f"R:R ròng hiện tại {net_rr_now:.2f} ≥ {MIN_NET_RR}")
            if verdict == "CONFIRMED":
                reasons.append(
                    "chưa sạch: spread rộng/vi biến động bất thường/chất lượng thực thi chưa GOOD "
                    f"({state.execution_quality}, {state.m1_micro_state})"
                )
        elif body_dir > 0 or mom3 > 0:
            verdict = "FORMING"
            reasons.append("M1 bắt đầu đi cùng hướng nhưng chưa đủ xác nhận")
            if adv_wick >= HALF:
                reasons.append(f"bấc ngược {adv_wick:.0%} ≥ {HALF:.0%}: bị từ chối ở vùng vào")
            if failed_adverse:
                reasons.append("phá vỡ giả ngược hướng trên M1")
        else:
            verdict = "WATCH"
            reasons.append("trigger M5 đã xác nhận nhưng M1 chưa đi theo hướng giao dịch")
    if failed_favourable and verdict in ("FORMING", "CONFIRMED", "EXECUTION_WINDOW"):
        reasons.append("phá vỡ giả cùng hướng (hỗ trợ) trên M1")
    if wide:
        reasons.append("spread rộng so với lịch sử gần đây")
    quality: Quality
    if verdict in ("INVALIDATED", "TOO_LATE") or wide:
        quality = "BAD"
    elif verdict == "EXECUTION_WINDOW":
        quality = "GOOD"
    else:
        quality = "CAUTION"
    return ExecutionAssessment(
        applicable=True,
        reason=reasons[0],
        direction=side,
        state=verdict,
        quality=quality,
        reasons=tuple(reasons),
        features=features,
        planned_entry=entry_p,
        planned_stop=stop.price,
        planned_target=targets.tp1,
        net_rr_now=net_rr_now,
        price_now=px,
    )
