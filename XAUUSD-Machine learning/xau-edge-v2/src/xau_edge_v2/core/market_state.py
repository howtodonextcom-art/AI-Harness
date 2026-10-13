"""Hierarchical market state: H4 REGIME -> H1 BIAS -> M15 SETUP -> M5 TRIGGER -> M1 EXECUTION.

Rewritten from V1's behaviour (``trading/market_state.py``); golden parity against V1 is proven by
``scripts/parity/golden_core.py``. ``build_market_state`` reads ONLY bars that had closed at ``at``
(``MultiFrames.as_of``), so the same closed bars always give the same state. Volume is TICK volume
and is only compared inside each timeframe. A missing timeframe degrades the state to ``UNKNOWN``;
nothing is invented. No strategy tuning: every constant equals the one V1 used.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
from numpy.typing import NDArray

from xau_edge_v2.core import indicators as ind
from xau_edge_v2.core import structure as st
from xau_edge_v2.core.frames import Frame, MultiFrames, from_micros
from xau_edge_v2.domain.contract import Timeframe
from xau_edge_v2.domain.market import BrokerClock

MIN_BARS = 60
UNKNOWN = "UNKNOWN"
WINDOW = 400
EMA_FAST = 20
EMA_SLOW = 50
ATR_PERIOD = 14
ATR_PCT_WINDOW = 200
BOS_RECENT_BARS = 6
SPREAD_WINDOW = 300
STALE_BARS = 3
WIDE_SPREAD_PERCENTILE = 0.9
MAX_SPREAD_TO_ATR = 0.15
LOW_VOL_PERCENTILE = 0.2
HIGH_VOL_PERCENTILE = 0.8
POINT = 0.01
PREV_DAY_BARS = 240
"""Last H1 bars scanned for the previous broker day (about ten trading days)."""

_SESSION_ZONES = (
    ("asia", "Asia/Tokyo", 9 * 60, 18 * 60),
    ("london", "Europe/London", 8 * 60, 17 * 60),
    ("new_york", "America/New_York", 8 * 60, 17 * 60),
)


@dataclass(frozen=True)
class TfSnapshot:
    """What one timeframe says at its last CLOSED bar."""

    timeframe: str
    bar_open: datetime
    bar_closed: datetime
    bars_used: int
    close: float
    atr: float | None
    atr_percentile: float | None
    ema_fast: float | None
    ema_slow: float | None
    price_vs_ema_atr: float | None
    rsi: float | None
    roc: float | None
    structure_trend: int
    bos_recent: int
    choch_recent: int
    last_swing_high: float | None
    last_swing_low: float | None
    support: float | None
    resistance: float | None
    patterns: dict[str, int]
    volume_zscore: float | None
    tick_volume: float
    regime: str | None


@dataclass(frozen=True)
class MarketState:
    timestamp: datetime
    symbol: str
    volume_type: str
    h4_regime: str
    h1_trend: str
    m30_structure: str
    m15_structure: str
    m15_pullback: str
    m5_momentum: str
    m1_micro_state: str
    atr_m5: float | None
    atr_m15: float | None
    volume_zscore_m1: float | None
    spread: float | None
    spread_percentile: float | None
    spread_to_atr_m5: float | None
    session: str
    price: float | None
    distance_to_support: float | None
    distance_to_resistance: float | None
    recent_swing_high: float | None
    recent_swing_low: float | None
    bos_state: str
    choch_state: str
    volatility_regime: str
    data_quality: str
    news_state: str
    execution_quality: str
    available_timeframes: tuple[str, ...]
    stale_timeframes: tuple[str, ...]
    snapshots: dict[str, TfSnapshot] = field(default_factory=dict)
    pdh: float | None = None
    pdl: float | None = None
    spread_state: str = UNKNOWN
    volume_state: str = UNKNOWN
    market_open: bool = True


def _last(arr: NDArray[np.float64]) -> float | None:
    value = float(arr[-1]) if len(arr) else math.nan
    return value if math.isfinite(value) else None


def _recent(arr: NDArray[np.int8], bars: int) -> int:
    tail = np.asarray(arr)[-bars:]
    nz = tail[tail != 0]
    return int(nz[-1]) if nz.size else 0


def snapshot(frame: Frame) -> TfSnapshot | None:
    """Features of one timeframe at its last closed bar (None with too few bars)."""
    if frame.height < MIN_BARS:
        return None
    t = frame.tail(WINDOW)
    o, h, lo, c, vol = t.open, t.high, t.low, t.close, t.tick_volume
    atr = ind.atr(h, lo, c, ATR_PERIOD)
    atr_now = _last(atr)
    valid_atr = atr[np.isfinite(atr)][-ATR_PCT_WINDOW:]
    atr_pct = (
        float(np.mean(valid_atr <= atr_now))
        if atr_now is not None and valid_atr.size >= 20
        else None
    )
    ema_f, ema_s = ind.ema(c, EMA_FAST), ind.ema(c, EMA_SLOW)
    pve = None
    if atr_now and np.isfinite(ema_f[-1]):
        pve = float((c[-1] - ema_f[-1]) / atr_now)
    adx = ind.adx(h, lo, c, 14)
    structure = st.analyse_structure(h, lo, c)
    z = ind.volume_zscore(vol, 20)
    rsi = ind.rsi(c, 14)
    roc = float(c[-1] / c[-6] - 1) if len(c) > 5 and c[-6] > 0 else None
    regime_arr = st.classify_regime(
        adx=adx.adx,
        plus_di=adx.plus_di,
        minus_di=adx.minus_di,
        atr=atr,
        high=h,
        low=lo,
        vol_window=min(200, len(c)),
        min_history=min(60, len(c)),
    )
    regime = regime_arr[-1] if len(regime_arr) else None
    return TfSnapshot(
        timeframe=t.timeframe.value,
        bar_open=from_micros(int(t.open_us[-1])),
        bar_closed=from_micros(int(t.available_us[-1])),
        bars_used=t.height,
        close=float(c[-1]),
        atr=atr_now,
        atr_percentile=atr_pct,
        ema_fast=_last(ema_f),
        ema_slow=_last(ema_s),
        price_vs_ema_atr=pve,
        rsi=_last(rsi),
        roc=roc,
        structure_trend=int(structure.trend[-1]),
        bos_recent=_recent(structure.bos, BOS_RECENT_BARS),
        choch_recent=_recent(structure.choch, BOS_RECENT_BARS),
        last_swing_high=_last(structure.last_swing_high),
        last_swing_low=_last(structure.last_swing_low),
        support=_last(structure.support),
        resistance=_last(structure.resistance),
        patterns={
            "strong_body": int(st.strong_body(o, h, lo, c)[-1]),
            "range_expansion": int(st.range_expansion(h, lo, atr)[-1]),
        },
        volume_zscore=_last(z),
        tick_volume=float(vol[-1]),
        regime=None if regime is None else str(regime),
    )


class SnapshotMemo:
    """Per-(timeframe, last bar) cache: a closed bar's snapshot never changes."""

    def __init__(self, limit: int = 4096) -> None:
        self._data: dict[tuple[str, int, float], TfSnapshot | None] = {}
        self._limit = limit

    def get(self, frame: Frame) -> TfSnapshot | None:
        if frame.height == 0:
            return None
        key = (frame.timeframe.value, int(frame.open_us[-1]), float(frame.close[-1]))
        if key not in self._data:
            if len(self._data) >= self._limit:
                self._data.clear()
            self._data[key] = snapshot(frame)
        return self._data[key]


def previous_day_range(
    h1: Frame | None, clock: BrokerClock | None, at: datetime
) -> tuple[float | None, float | None]:
    """High and low of the previous BROKER day (server wall-clock date) from closed H1 bars."""
    if h1 is None or h1.height < 48 or clock is None:
        return None, None
    t = h1.tail(PREV_DAY_BARS)
    days = [clock.to_server_wall(from_micros(int(us))).date() for us in t.open_us]
    today = clock.to_server_wall(at).date()
    earlier = sorted({d for d in days if d < today})
    if not earlier:
        return None, None
    mask = np.array([d == earlier[-1] for d in days])
    if not mask.any():
        return None, None
    return float(t.high[mask].max()), float(t.low[mask].min())


def trading_session(at: datetime) -> str:
    """ASIA / LONDON / NEW_YORK / LONDON_NY_OVERLAP / OFF_HOURS from local exchange hours."""
    active: dict[str, bool] = {}
    for name, zone, start, end in _SESSION_ZONES:
        local = at.astimezone(ZoneInfo(zone))
        minutes = local.hour * 60 + local.minute
        active[name] = start <= minutes < end
    if active["london"] and active["new_york"]:
        return "LONDON_NY_OVERLAP"
    if active["london"]:
        return "LONDON"
    if active["new_york"]:
        return "NEW_YORK"
    if active["asia"]:
        return "ASIA"
    return "OFF_HOURS"


def _volume_label(z: float | None) -> str:
    if z is None:
        return UNKNOWN
    return "HIGH" if z >= 1.0 else "LOW" if z <= -1.0 else "NORMAL"


def _direction_label(trend: int, up: str, down: str, flat: str) -> str:
    return up if trend > 0 else down if trend < 0 else flat


def _h1_trend(s: TfSnapshot | None) -> str:
    if s is None or s.ema_fast is None or s.ema_slow is None:
        return UNKNOWN
    if s.close > s.ema_slow and s.ema_fast > s.ema_slow and s.structure_trend >= 0:
        return "BULLISH"
    if s.close < s.ema_slow and s.ema_fast < s.ema_slow and s.structure_trend <= 0:
        return "BEARISH"
    return "NEUTRAL"


def _structure_label(s: TfSnapshot | None) -> str:
    if s is None:
        return UNKNOWN
    if s.choch_recent != 0:
        return "REVERSAL_UP" if s.choch_recent > 0 else "REVERSAL_DOWN"
    return _direction_label(s.structure_trend, "UP", "DOWN", "RANGE")


def _pullback(s: TfSnapshot | None) -> str:
    if s is None or s.price_vs_ema_atr is None:
        return UNKNOWN
    if s.structure_trend > 0 and -0.3 <= s.price_vs_ema_atr <= 0.7:
        return "PULLBACK_IN_UPTREND"
    if s.structure_trend < 0 and -0.7 <= s.price_vs_ema_atr <= 0.3:
        return "PULLBACK_IN_DOWNTREND"
    return "NONE"


def _m5_momentum(s: TfSnapshot | None) -> str:
    if s is None or s.roc is None or s.rsi is None:
        return UNKNOWN
    body = s.patterns.get("strong_body", 0)
    if (s.roc > 0 and s.rsi > 52 and (s.bos_recent > 0 or body > 0)) or (
        s.bos_recent > 0 and s.roc > 0
    ):
        return "UP"
    if (s.roc < 0 and s.rsi < 48 and (s.bos_recent < 0 or body < 0)) or (
        s.bos_recent < 0 and s.roc < 0
    ):
        return "DOWN"
    return "FLAT"


def _m1_state(s: TfSnapshot | None) -> str:
    if s is None or s.atr is None:
        return UNKNOWN
    if s.patterns.get("range_expansion", 0) and s.volume_zscore is not None and s.volume_zscore > 3:
        return "ABNORMAL"
    if s.volume_zscore is not None and s.volume_zscore < -1.0:
        return "QUIET"
    body = s.patterns.get("strong_body", 0)
    if body > 0:
        return "ACTIVE_UP"
    if body < 0:
        return "ACTIVE_DOWN"
    return "NEUTRAL"


def _spread_stats(m5: Frame | None, spread: float | None) -> tuple[float | None, float | None]:
    """(current spread in points, its percentile among the recent M5 spreads)."""
    if m5 is None or m5.height == 0:
        return spread, None
    recent = m5.spread[-SPREAD_WINDOW:]
    current = spread if spread is not None else float(recent[-1])
    pct = (
        float((np.sum(recent < current) + 0.5 * np.sum(recent == current)) / recent.size)
        if recent.size >= 30
        else None
    )
    return current, pct


def volume_type(frame: Frame | None) -> str:
    """TICK_VOLUME when the feed has no real volume at all; otherwise UNKNOWN (never REAL)."""
    if frame is None or frame.height == 0:
        return UNKNOWN
    ticks = frame.tick_volume
    if ticks.size < 50 or not np.isfinite(ticks).all() or (ticks <= 0).all():
        return UNKNOWN
    real = frame.real_volume
    if real is None:
        return "TICK_VOLUME"
    real = real[np.isfinite(real)]
    if real.size == 0 or float(np.abs(real).sum()) == 0.0:
        return "TICK_VOLUME"
    return UNKNOWN


def build_market_state(
    frames: MultiFrames,
    at: datetime,
    *,
    spread_points: float | None = None,
    news_state: str = UNKNOWN,
    symbol: str = "XAUUSD",
    broker_clock: BrokerClock | None = None,
    market_open: bool = True,
    memo: SnapshotMemo | None = None,
) -> MarketState:
    """The hierarchical state at ``at`` from closed bars only."""
    closed: dict[Timeframe, Frame | None] = {}
    snaps: dict[Timeframe, TfSnapshot | None] = {}
    for tf in frames.available():
        frame = frames.as_of(tf, at)
        closed[tf] = frame
        snaps[tf] = (
            None if frame is None else memo.get(frame) if memo is not None else snapshot(frame)
        )
    m1, m5, m15, m30, h1, h4 = (
        snaps.get(Timeframe.M1),
        snaps.get(Timeframe.M5),
        snaps.get(Timeframe.M15),
        snaps.get(Timeframe.M30),
        snaps.get(Timeframe.H1),
        snaps.get(Timeframe.H4),
    )
    stale = [
        tf.value
        for tf, snap in snaps.items()
        if snap is None or at - snap.bar_closed > timedelta(seconds=STALE_BARS * tf.seconds)
    ]
    available = tuple(tf.value for tf, snap in snaps.items() if snap is not None)
    entry_tf_ok = any(tf in available for tf in ("M5", "M15"))
    quality = (
        UNKNOWN
        if not entry_tf_ok
        else "STALE"
        if "M5" in stale or ("M5" not in available and "M15" in stale)
        else "OK"
        if "H1" in available and "H4" in available
        else "DEGRADED"
    )
    current_spread, spread_pct = _spread_stats(closed.get(Timeframe.M5), spread_points)
    atr_m5 = m5.atr if m5 else None
    spread_to_atr = (
        current_spread * POINT / atr_m5 if current_spread is not None and atr_m5 else None
    )
    price = next((s.close for s in (m1, m5, m15) if s is not None), None)
    ref = m15 or m5 or h1
    atr_pct = ref.atr_percentile if ref else None
    vol_regime = (
        UNKNOWN
        if atr_pct is None
        else "LOW"
        if atr_pct <= LOW_VOL_PERCENTILE
        else "HIGH"
        if atr_pct >= HIGH_VOL_PERCENTILE
        else "NORMAL"
    )
    swing_ref = m15 or m5
    hi = swing_ref.last_swing_high if swing_ref else None
    lo = swing_ref.last_swing_low if swing_ref else None
    sup = swing_ref.support if swing_ref else None
    res = swing_ref.resistance if swing_ref else None

    def dist(level: float | None) -> float | None:
        return None if level is None or price is None else abs(price - level)

    abnormal = m1 is not None and _m1_state(m1) == "ABNORMAL"
    exec_quality = (
        UNKNOWN
        if current_spread is None or spread_pct is None
        else "POOR"
        if (spread_pct >= WIDE_SPREAD_PERCENTILE or abnormal)
        or (spread_to_atr is not None and spread_to_atr > MAX_SPREAD_TO_ATR)
        else "GOOD"
    )
    base = closed.get(Timeframe.M5)
    if base is None:
        base = closed.get(Timeframe.M15)
    pdh, pdl = previous_day_range(closed.get(Timeframe.H1), broker_clock, at)
    return MarketState(
        timestamp=at,
        symbol=symbol,
        volume_type=volume_type(base),
        h4_regime=(h4.regime or UNKNOWN) if h4 else UNKNOWN,
        h1_trend=_h1_trend(h1),
        m30_structure=_structure_label(m30),
        m15_structure=_structure_label(m15),
        m15_pullback=_pullback(m15),
        m5_momentum=_m5_momentum(m5),
        m1_micro_state=_m1_state(m1),
        atr_m5=atr_m5,
        atr_m15=m15.atr if m15 else None,
        volume_zscore_m1=m1.volume_zscore if m1 else None,
        spread=current_spread,
        spread_percentile=spread_pct,
        spread_to_atr_m5=spread_to_atr,
        session=trading_session(at) if price is not None else UNKNOWN,
        price=price,
        distance_to_support=dist(sup),
        distance_to_resistance=dist(res),
        recent_swing_high=hi,
        recent_swing_low=lo,
        bos_state=_direction_label(m5.bos_recent if m5 else 0, "BOS_UP", "BOS_DOWN", "NONE"),
        choch_state=_direction_label(
            m15.choch_recent if m15 else 0, "CHOCH_UP", "CHOCH_DOWN", "NONE"
        ),
        volatility_regime=vol_regime,
        data_quality=quality,
        news_state=news_state,
        execution_quality=exec_quality,
        available_timeframes=available,
        stale_timeframes=tuple(stale),
        snapshots={tf.value: sn for tf, sn in snaps.items() if sn is not None},
        pdh=pdh,
        pdl=pdl,
        spread_state=(
            UNKNOWN
            if current_spread is None or spread_pct is None
            else "WIDE"
            if exec_quality == "POOR"
            else "GOOD"
        ),
        volume_state=_volume_label(m1.volume_zscore if m1 else None),
        market_open=market_open,
    )
