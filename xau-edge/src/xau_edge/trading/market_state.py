"""Multi-timeframe market state (trading core sections 5, 6, 8).

Responsibility by timeframe, hierarchical (not a vote):

    H4 REGIME -> H1 BIAS -> M30/M15 SETUP -> M5 CONFIRMATION -> M1 EXECUTION QUALITY

``build_market_state`` reads ONLY bars that had closed at ``at`` (``closed_as_of``), so the same
closed bars always give the same state in research, paper and demo. Volume is tick volume unless
verified otherwise (``volume_type``) and is only compared after normalisation inside each
timeframe. Missing timeframes degrade the state explicitly (``UNKNOWN``); nothing is invented.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import polars as pl
from pydantic import BaseModel, ConfigDict, Field

from xau_edge.domain.timeframe import Timeframe
from xau_edge.features import indicators as ind
from xau_edge.features.sessions import session_features
from xau_edge.market_data.broker_clock import BrokerClock
from xau_edge.structure.regime import RegimeConfig, classify_regime
from xau_edge.structure.swings import StructureConfig, analyse_structure
from xau_edge.trading.activity import VolumeType, activity, detect_volume_type
from xau_edge.trading.frames import MultiTfBars
from xau_edge.trading.patterns import detect_patterns

MIN_BARS = 60
UNKNOWN = "UNKNOWN"


class StateConfig(BaseModel):
    """Windows and thresholds of the state engine (versioned with the strategy)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    window: int = Field(default=400, ge=MIN_BARS)
    ema_fast: int = 20
    ema_slow: int = 50
    atr_period: int = 14
    atr_pct_window: int = 200
    swing_left: int = 3
    swing_right: int = 3
    bos_recent_bars: int = 6
    spread_window: int = 300
    stale_bars: int = 3
    """A timeframe is stale when its last closed bar is older than this many bar lengths."""
    wide_spread_percentile: float = 0.9
    max_spread_to_atr: float = 0.15
    abnormal_range_atr: float = 3.0
    low_vol_percentile: float = 0.2
    high_vol_percentile: float = 0.8
    point: float = 0.01


class TfSnapshot(BaseModel):
    """What one timeframe says at its last CLOSED bar."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    timeframe: str
    bar_open: datetime
    bar_closed: datetime
    bars_used: int
    close: float
    atr: float | None
    atr_percentile: float | None
    ema_fast: float | None
    ema_slow: float | None
    ema_slope_atr: float | None
    price_vs_ema_atr: float | None
    adx: float | None
    plus_di: float | None
    minus_di: float | None
    rsi: float | None
    roc: float | None
    structure_trend: int
    bos_recent: int
    choch_recent: int
    last_swing_high: float | None
    last_swing_low: float | None
    support: float | None
    resistance: float | None
    range_percentile: float | None
    patterns: dict[str, int]
    volume_zscore: float | None
    volume_percentile: float | None
    volume_ratio: float | None
    volume_acceleration: float | None
    tick_volume: float | None
    regime: str | None


class MarketState(BaseModel):
    """The hierarchical state the decision engine reads (and the dashboard shows)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

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
    atr_m1: float | None
    atr_m5: float | None
    atr_m15: float | None
    atr_h1: float | None
    tick_volume_m1: float | None
    volume_zscore_m1: float | None
    volume_ratio_m1_m5: float | None
    spread: float | None
    spread_percentile: float | None
    spread_to_atr_m5: float | None
    session: str
    price: float | None
    distance_to_recent_high: float | None
    distance_to_recent_low: float | None
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
    snapshots: dict[str, TfSnapshot] = Field(default_factory=dict)
    pdh: float | None = None
    """Previous broker-day high (server day, from closed H1 bars)."""
    pdl: float | None = None
    nearest_resistance: float | None = None
    nearest_support: float | None = None
    spread_state: str = "UNKNOWN"
    volume_percentile_m1: float | None = None
    volume_acceleration_m1: float | None = None
    relative_volume_m1: float | None = None
    """M1 tick volume against the average of its OWN last 20 bars (no cross-timeframe compare)."""
    volume_state: str = "UNKNOWN"
    market_open: bool = True


def _last(arr: Any) -> float | None:
    value = float(arr[-1]) if len(arr) else math.nan
    return value if math.isfinite(value) else None


def _recent(arr: Any, bars: int) -> int:
    """The most recent non-zero value within the last ``bars`` entries (0 when none)."""
    tail = np.asarray(arr)[-bars:]
    nz = tail[tail != 0]
    return int(nz[-1]) if nz.size else 0


def snapshot(df: pl.DataFrame, timeframe: Timeframe, cfg: StateConfig) -> TfSnapshot | None:
    """Features of one timeframe at its last closed bar, or None with too few bars."""
    if df.height < MIN_BARS:
        return None
    tail = df.tail(cfg.window)
    o, h, lo, c = (tail[k].to_numpy().astype(np.float64) for k in ("open", "high", "low", "close"))
    vol = tail["tick_volume"].to_numpy().astype(np.float64)
    atr = ind.atr(h, lo, c, cfg.atr_period)
    atr_now = _last(atr)
    valid_atr = atr[np.isfinite(atr)][-cfg.atr_pct_window :]
    atr_pct = (
        float(np.mean(valid_atr <= atr_now))
        if atr_now is not None and valid_atr.size >= 20
        else None
    )
    ema_f, ema_s = ind.ema(c, cfg.ema_fast), ind.ema(c, cfg.ema_slow)
    slope = None
    if atr_now and len(ema_f) > 5 and np.isfinite(ema_f[-6]) and np.isfinite(ema_f[-1]):
        slope = float((ema_f[-1] - ema_f[-6]) / (5 * atr_now))
    pve = None
    if atr_now and np.isfinite(ema_f[-1]):
        pve = float((c[-1] - ema_f[-1]) / atr_now)
    adx = ind.adx(h, lo, c, 14)
    structure = analyse_structure(
        h, lo, c, StructureConfig(left=cfg.swing_left, right=cfg.swing_right)
    )
    pats = detect_patterns(o, h, lo, c, atr)
    act = activity(vol)
    rsi = ind.rsi(c, 14)
    roc = float(c[-1] / c[-6] - 1) if len(c) > 5 and c[-6] > 0 else None
    win = slice(-50, None)
    top, bottom = float(np.max(h[win])), float(np.min(lo[win]))
    rng_pct = float((c[-1] - bottom) / (top - bottom)) if top > bottom else None
    regime_arr = classify_regime(
        adx=adx.adx,
        plus_di=adx.plus_di,
        minus_di=adx.minus_di,
        atr=atr,
        high=h,
        low=lo,
        config=RegimeConfig(vol_window=min(200, len(c)), min_history=min(60, len(c))),
    )
    regime = regime_arr[-1] if len(regime_arr) else None
    return TfSnapshot(
        timeframe=timeframe.value,
        bar_open=tail["timestamp"][-1],
        bar_closed=tail["available_at"][-1],
        bars_used=int(tail.height),
        close=float(c[-1]),
        atr=atr_now,
        atr_percentile=atr_pct,
        ema_fast=_last(ema_f),
        ema_slow=_last(ema_s),
        ema_slope_atr=slope,
        price_vs_ema_atr=pve,
        adx=_last(adx.adx),
        plus_di=_last(adx.plus_di),
        minus_di=_last(adx.minus_di),
        rsi=_last(rsi),
        roc=roc,
        structure_trend=int(structure.trend[-1]),
        bos_recent=_recent(structure.bos, cfg.bos_recent_bars),
        choch_recent=_recent(structure.choch, cfg.bos_recent_bars),
        last_swing_high=_last(structure.last_swing_high),
        last_swing_low=_last(structure.last_swing_low),
        support=_last(structure.support),
        resistance=_last(structure.resistance),
        range_percentile=rng_pct,
        patterns={k: int(v[-1]) for k, v in pats.items()},
        volume_zscore=_last(act["zscore"]),
        volume_percentile=_last(act["percentile"]),
        volume_ratio=_last(act["ratio"]),
        volume_acceleration=_last(act["acceleration"]),
        tick_volume=float(vol[-1]),
        regime=None if regime is None else str(regime),
    )


def previous_day_range(
    h1: pl.DataFrame | None, clock: BrokerClock | None
) -> tuple[float | None, float | None]:
    """High and low of the previous BROKER day (server wall-clock date) from closed H1 bars."""
    if h1 is None or h1.height < 48 or clock is None:
        return None, None
    wall = clock.utc_to_server(h1["timestamp"])
    frame = h1.with_columns(wall.dt.date().alias("_day"))
    days = frame["_day"].unique().sort()
    if days.len() < 2:
        return None, None
    previous = days[-2]
    day = frame.filter(pl.col("_day") == previous)
    if day.height == 0:
        return None, None
    return float(day["high"].max()), float(day["low"].min())  # type: ignore[arg-type]


def _volume_label(z: float | None) -> str:
    if z is None:
        return "UNKNOWN"
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
    """Has price pulled back to the fast EMA inside the M15 trend (candidate entry zone)?"""
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


def _m1_state(s: TfSnapshot | None, cfg: StateConfig) -> str:
    if s is None or s.atr is None:
        return UNKNOWN
    last_range_atr = s.patterns.get("range_expansion", 0)
    if last_range_atr and s.volume_zscore is not None and s.volume_zscore > 3.0:
        return "ABNORMAL"
    if s.volume_zscore is not None and s.volume_zscore < -1.0:
        return "QUIET"
    body = s.patterns.get("strong_body", 0)
    if body > 0:
        return "ACTIVE_UP"
    if body < 0:
        return "ACTIVE_DOWN"
    return "NEUTRAL"


def _spread_stats(
    m5: pl.DataFrame | None, spread: float | None, cfg: StateConfig
) -> tuple[float | None, float | None, float | None]:
    """(current spread in points, its percentile in recent M5 spreads, spread/ATR(M5) ratio)."""
    if m5 is None or m5.height == 0:
        return spread, None, None
    recent = m5["spread"].tail(cfg.spread_window).to_numpy().astype(np.float64)
    current = spread if spread is not None else float(recent[-1])
    pct = (
        float((np.sum(recent < current) + 0.5 * np.sum(recent == current)) / recent.size)
        if recent.size >= 30
        else None
    )
    return current, pct, None


def build_market_state(
    bars: MultiTfBars,
    at: datetime,
    *,
    spread_points: float | None = None,
    news_state: str = UNKNOWN,
    symbol: str = "XAUUSD",
    config: StateConfig | None = None,
    broker_clock: BrokerClock | None = None,
    market_open: bool = True,
) -> MarketState:
    """The hierarchical state at ``at`` from closed bars only."""
    cfg = config or StateConfig()
    snaps: dict[Timeframe, TfSnapshot | None] = {}
    frames: dict[Timeframe, pl.DataFrame | None] = {}
    for tf in bars.available():
        closed = bars.as_of(tf, at)
        frames[tf] = closed
        snaps[tf] = None if closed is None else snapshot(closed, tf, cfg)
    s = snaps.get
    m1, m5, m15, m30, h1, h4 = (
        s(Timeframe.M1),
        s(Timeframe.M5),
        s(Timeframe.M15),
        s(Timeframe.M30),
        s(Timeframe.H1),
        s(Timeframe.H4),
    )
    stale: list[str] = []
    for tf, snap in snaps.items():
        if snap is None or at - snap.bar_closed > timedelta(minutes=cfg.stale_bars * tf.minutes):
            stale.append(tf.value)
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
    current_spread, spread_pct, _ = _spread_stats(frames.get(Timeframe.M5), spread_points, cfg)
    atr_m5 = m5.atr if m5 else None
    spread_to_atr = (
        current_spread * cfg.point / atr_m5 if current_spread is not None and atr_m5 else None
    )
    price = None
    for snap in (m1, m5, m15):
        if snap is not None:
            price = snap.close
            break
    ref = m15 or m5 or h1
    atr_pct = ref.atr_percentile if ref else None
    vol_regime = (
        UNKNOWN
        if atr_pct is None
        else "LOW"
        if atr_pct <= cfg.low_vol_percentile
        else "HIGH"
        if atr_pct >= cfg.high_vol_percentile
        else "NORMAL"
    )
    session = UNKNOWN
    if price is not None:
        ts = pl.Series("t", [at], dtype=pl.Datetime("us", "UTC"))
        session = str(session_features(ts)["trading_session"][0])
    swing_ref = m15 or m5
    hi = swing_ref.last_swing_high if swing_ref else None
    lo = swing_ref.last_swing_low if swing_ref else None
    sup = swing_ref.support if swing_ref else None
    res = swing_ref.resistance if swing_ref else None

    def dist(level: float | None) -> float | None:
        return None if level is None or price is None else abs(price - level)

    abnormal = m1 is not None and _m1_state(m1, cfg) == "ABNORMAL"
    exec_quality = (
        UNKNOWN
        if current_spread is None or spread_pct is None
        else "POOR"
        if (spread_pct >= cfg.wide_spread_percentile or abnormal)
        or (spread_to_atr is not None and spread_to_atr > cfg.max_spread_to_atr)
        else "GOOD"
    )
    ratio_m1_m5 = (
        m1.volume_zscore - m5.volume_zscore
        if m1 and m5 and m1.volume_zscore is not None and m5.volume_zscore is not None
        else None
    )
    volume_type = VolumeType.UNKNOWN.value
    base_frame = frames.get(Timeframe.M5)
    if base_frame is None:
        base_frame = frames.get(Timeframe.M15)
    if base_frame is not None and base_frame.height:
        real = base_frame["real_volume"].to_numpy() if "real_volume" in base_frame.columns else None
        volume_type = detect_volume_type(base_frame["tick_volume"].to_numpy(), real).value
    pdh, pdl = previous_day_range(frames.get(Timeframe.H1), broker_clock)
    return MarketState(
        timestamp=at,
        symbol=symbol,
        volume_type=volume_type,
        h4_regime=(h4.regime or UNKNOWN) if h4 else UNKNOWN,
        h1_trend=_h1_trend(h1),
        m30_structure=_structure_label(m30),
        m15_structure=_structure_label(m15),
        m15_pullback=_pullback(m15),
        m5_momentum=_m5_momentum(m5),
        m1_micro_state=_m1_state(m1, cfg),
        atr_m1=m1.atr if m1 else None,
        atr_m5=atr_m5,
        atr_m15=m15.atr if m15 else None,
        atr_h1=h1.atr if h1 else None,
        tick_volume_m1=m1.tick_volume if m1 else None,
        volume_zscore_m1=m1.volume_zscore if m1 else None,
        volume_ratio_m1_m5=ratio_m1_m5,
        spread=current_spread,
        spread_percentile=spread_pct,
        spread_to_atr_m5=spread_to_atr,
        session=session,
        price=price,
        distance_to_recent_high=dist(hi),
        distance_to_recent_low=dist(lo),
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
        nearest_resistance=None if price is None or res is None else res,
        nearest_support=None if price is None or sup is None else sup,
        spread_state=(
            UNKNOWN
            if current_spread is None or spread_pct is None
            else "WIDE"
            if exec_quality == "POOR"
            else "GOOD"
        ),
        volume_percentile_m1=m1.volume_percentile if m1 else None,
        volume_acceleration_m1=m1.volume_acceleration if m1 else None,
        relative_volume_m1=m1.volume_ratio if m1 else None,
        volume_state=_volume_label(m1.volume_zscore if m1 else None),
        market_open=market_open,
    )
