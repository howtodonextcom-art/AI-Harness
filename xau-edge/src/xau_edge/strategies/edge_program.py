"""Signal generators of the six pre-registered Edge Program hypotheses (H01..H06).

The rules are implemented literally from ``docs/research/edge-program/hypotheses/H0*.md``
(frozen 2026-10-08). Each hypothesis has one parameter with three registered values, so the
registry below holds exactly 18 variants, identified as ``<hypothesis>-<param><value>`` (for
example ``H03-c0.9``). Like the baselines, the generators only emit signals; fills, costs, the
one-position-at-a-time rule and stop-first exits belong to the backtest engine.

Shared conventions (hypotheses README):

* Bars are validated upstream: sorted, unique, tz-aware UTC bar-OPEN timestamps (``check_bars``
  refuses anything else). Gaps are never filled, so rolling windows run over consecutive ROWS
  (ADR-0011); missing or weekend bars are reported by the runner, not repaired here.
* A signal is decided at the close of its bar (``decision_time = available_at``) and enters at the
  open of the next H1 bar.
* ATR is Wilder ATR(14) of the signal timeframe at the decision bar (H05 uses the previous bar's
  ATR for its trigger threshold only, as registered).
* ``max_hold_bars`` is written in H1 execution bars (H06: 30 H4 bars = 120 H1 bars).
* Cooldown: the minimum distance, in signal-timeframe bars, between two emitted signals (the
  baseline convention of ``signals_from_direction``); it counts from the previous emitted signal,
  whether or not the engine later skips that signal because a position is open.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final

import numpy as np
import polars as pl
from numpy.lib.stride_tricks import sliding_window_view
from numpy.typing import NDArray

from xau_edge.domain.timeframe import Timeframe
from xau_edge.features import indicators as ind
from xau_edge.features.feature_set import check_bars
from xau_edge.market_data.broker_clock import BrokerClock
from xau_edge.strategies.baselines import signals_from_direction
from xau_edge.structure.frame import structure_frame

Floats = NDArray[np.float64]
Directions = NDArray[np.int8]

PROGRAM: Final = "edge-program"
ATR_PERIOD: Final = 14
EXECUTION_TIMEFRAME: Final = Timeframe.H1
SERVER_CLOCK: Final = BrokerClock(ny_offset_hours=7)
"""Server day of the broker (NY+7, rollover 17:00 New York) used for the H04 daily bars."""
SESSION_OPENS: Final = (("Asia/Tokyo", 9), ("Europe/London", 8), ("America/New_York", 8))
ASIA_RANGE_HOURS: Final = tuple(range(7))
"""H02: the seven H1 bars opening 00:00..06:00 UTC."""
BREAKOUT_HOURS: Final = tuple(range(7, 16))
"""H02: H1 bars opening 07:00..15:00 UTC are scanned for the breakout."""
RATIO_WINDOW: Final = 120
CHANNEL_WINDOW: Final = 24
EMA_PERIOD: Final = 20
MIN_DAY_BARS: Final = 12


@dataclass(frozen=True)
class HypothesisSpec:
    """The registered constants of one hypothesis and its three-value grid."""

    hypothesis: str
    param: str
    grid: tuple[float | int, ...]
    signal_timeframe: Timeframe
    stop_atr: float
    target_atr: float
    hold_bars: int
    """Holding limit in bars of the signal timeframe, as registered."""
    cooldown_bars: int

    @property
    def hold_execution_bars(self) -> int:
        """Holding limit converted to H1 execution bars."""
        return self.hold_bars * self.signal_timeframe.minutes // EXECUTION_TIMEFRAME.minutes


@dataclass(frozen=True)
class Variant:
    """One grid cell of one hypothesis."""

    variant_id: str
    spec: HypothesisSpec
    value: float | int

    @property
    def hypothesis(self) -> str:
        """The hypothesis id (``H01``..``H06``)."""
        return self.spec.hypothesis

    def params(self) -> dict[str, Any]:
        """Registry identity: the variant and every registered constant it runs with."""
        s = self.spec
        return {
            "program": PROGRAM,
            "variant": self.variant_id,
            "hypothesis": s.hypothesis,
            "param": s.param,
            "value": self.value,
            "signal_timeframe": s.signal_timeframe.value,
            "stop_atr": s.stop_atr,
            "target_atr": s.target_atr,
            "hold_bars": s.hold_bars,
            "hold_execution_bars": s.hold_execution_bars,
            "cooldown_bars": s.cooldown_bars,
        }


SPECS: Final[Mapping[str, HypothesisSpec]] = MappingProxyType(
    {
        "H01": HypothesisSpec("H01", "theta", (0.3, 0.6, 0.9), Timeframe.H1, 1.5, 3.0, 6, 0),
        "H02": HypothesisSpec("H02", "b", (0.0, 0.25, 0.5), Timeframe.H1, 1.5, 3.0, 8, 0),
        "H03": HypothesisSpec("H03", "c", (0.8, 0.9, 1.0), Timeframe.H1, 1.5, 3.0, 24, 12),
        "H04": HypothesisSpec("H04", "L", (10, 20, 40), Timeframe.H1, 1.5, 3.0, 24, 6),
        "H05": HypothesisSpec("H05", "s", (1.5, 2.0, 2.5), Timeframe.H1, 1.5, 1.0, 6, 3),
        "H06": HypothesisSpec("H06", "N", (20, 40, 80), Timeframe.H4, 2.0, 4.0, 30, 6),
    }
)


def _variant_id(spec: HypothesisSpec, value: float | int) -> str:
    return f"{spec.hypothesis}-{spec.param}{value}"


VARIANTS: Final[Mapping[str, Variant]] = MappingProxyType(
    {
        _variant_id(spec, value): Variant(_variant_id(spec, value), spec, value)
        for spec in SPECS.values()
        for value in spec.grid
    }
)


def get_variant(variant_id: str) -> Variant:
    """Look up a registered variant; unknown ids raise with the valid list."""
    if variant_id not in VARIANTS:
        msg = f"unknown variant {variant_id!r}; choose from {list(VARIANTS)}"
        raise ValueError(msg)
    return VARIANTS[variant_id]


def variants_of(hypothesis: str) -> list[Variant]:
    """The three variants of one hypothesis, in grid order."""
    if hypothesis not in SPECS:
        msg = f"unknown hypothesis {hypothesis!r}; choose from {list(SPECS)}"
        raise ValueError(msg)
    return [v for v in VARIANTS.values() if v.hypothesis == hypothesis]


@dataclass(frozen=True)
class SignalContext:
    """Per-timeframe frames shared by all variants (computed once per run).

    ``h1`` / ``h4`` carry ``timestamp, available_at, open, high, low, close, atr_14, regime``;
    ``daily`` holds the H1-derived server-day bars of H04 with their ``available_at``.
    """

    h1: pl.DataFrame
    h4: pl.DataFrame | None
    daily: pl.DataFrame


def _timeframe_context(bars: pl.DataFrame, timeframe: Timeframe) -> pl.DataFrame:
    check_bars(bars)
    h, lo, c = (bars[k].to_numpy() for k in ("high", "low", "close"))
    atr = ind.atr(h, lo, c, ATR_PERIOD)
    regime = structure_frame(bars, timeframe)["regime"]
    return bars.select("timestamp", "open", "high", "low", "close").with_columns(
        pl.col("timestamp").dt.offset_by(f"{timeframe.minutes}m").alias("available_at"),
        pl.Series("atr_14", atr, dtype=pl.Float64, nan_to_null=True),
        regime,
    )


def server_daily_bars(
    h1: pl.DataFrame, clock: BrokerClock = SERVER_CLOCK, *, min_bars: int = MIN_DAY_BARS
) -> pl.DataFrame:
    """H1-derived daily bars by server day; usable from ``available_at`` = last H1 open + 1h.

    Days with fewer than ``min_bars`` H1 bars are dropped, never padded (same grouping as
    ``experiments.history.daily_from_h1``).
    """
    check_bars(h1)
    return (
        h1.select("timestamp", "close")
        .with_columns(clock.utc_to_server(pl.col("timestamp")).dt.date().alias("server_day"))
        .group_by("server_day", maintain_order=True)
        .agg(
            pl.col("timestamp").first(),
            pl.col("timestamp").last().alias("last_open"),
            pl.col("close").last(),
            pl.len().alias("n_bars"),
        )
        .filter(pl.col("n_bars") >= min_bars)
        .with_columns(pl.col("last_open").dt.offset_by("1h").alias("available_at"))
    )


def edge_context(h1: pl.DataFrame, h4: pl.DataFrame | None = None) -> SignalContext:
    """Build the shared context from H1 bars (and H4 bars, needed by H06 only)."""
    return SignalContext(
        h1=_timeframe_context(h1, Timeframe.H1),
        h4=None if h4 is None else _timeframe_context(h4, Timeframe.H4),
        daily=server_daily_bars(h1),
    )


def compression_ratio(atr: Floats, window: int = RATIO_WINDOW) -> Floats:
    """``ratio[t] = atr[t-1] / mean(atr[t-window .. t-1])``; NaN if any input is missing."""
    n = atr.size
    out = np.full(n, np.nan)
    if n > window:
        means = sliding_window_view(atr, window).mean(axis=1)[: n - window]
        prev = atr[window - 1 : n - 1]
        with np.errstate(divide="ignore", invalid="ignore"):
            out[window:] = np.where(means > 0, prev / means, np.nan)
    return out


def prior_channel(high: Floats, low: Floats, window: int) -> tuple[Floats, Floats]:
    """``max(high[t-window .. t-1])`` and ``min(low[t-window .. t-1])``; NaN for t < window."""
    n = high.size
    hh = np.full(n, np.nan)
    ll = np.full(n, np.nan)
    if n > window:
        hh[window:] = sliding_window_view(high, window)[: n - window].max(axis=1)
        ll[window:] = sliding_window_view(low, window)[: n - window].min(axis=1)
    return hh, ll


def _arrays(frame: pl.DataFrame) -> tuple[Floats, Floats, Floats, Floats, Floats]:
    o, h, lo, c = (frame[k].to_numpy().astype(np.float64) for k in ("open", "high", "low", "close"))
    atr = frame["atr_14"].fill_null(np.nan).to_numpy().astype(np.float64)
    return o, h, lo, c, atr


def _breakout(close: Floats, hh: Floats, ll: Floats) -> Directions:
    with np.errstate(invalid="ignore"):
        return np.where(close > hh, 1, np.where(close < ll, -1, 0)).astype(np.int8)


def _h01(ctx: SignalContext, theta: float) -> Directions:
    """Session-open momentum: |body| >= theta x ATR14 on the Tokyo/London/New York open bar."""
    frame = ctx.h1
    o, _, _, c, atr = _arrays(frame)
    ts = frame["timestamp"]
    is_open = np.zeros(frame.height, dtype=bool)
    for zone, hour in SESSION_OPENS:
        local = ts.dt.convert_time_zone(zone)
        is_open |= ((local.dt.hour() == hour) & (local.dt.minute() == 0)).to_numpy()
    body = c - o
    with np.errstate(invalid="ignore"):
        fire = is_open & (np.abs(body) >= theta * atr)
    return np.where(fire, np.sign(body), 0).astype(np.int8)


def _h02(ctx: SignalContext, b: float) -> Directions:
    """Asia range (00:00..06:00 UTC, all 7 bars) broken by a close at 07:00..15:00 UTC."""
    frame = ctx.h1
    ts = pl.col("timestamp")
    rows = frame.select(
        ts.dt.date().alias("day"),
        ts.dt.hour().alias("hour"),
        (ts.dt.minute() == 0).alias("on_hour"),
        "high",
        "low",
        "close",
        "atr_14",
        pl.int_range(pl.len()).alias("_i"),
    )
    asia = (
        rows.filter(pl.col("on_hour") & pl.col("hour").is_in(ASIA_RANGE_HOURS))
        .group_by("day")
        .agg(
            pl.col("hour").n_unique().alias("n"),
            pl.col("high").max().alias("range_high"),
            pl.col("low").min().alias("range_low"),
        )
        .filter(pl.col("n") == len(ASIA_RANGE_HOURS))
    )
    long_ = pl.col("close") > pl.col("range_high") + b * pl.col("atr_14")
    short = pl.col("close") < pl.col("range_low") - b * pl.col("atr_14")
    first = (
        rows.filter(pl.col("on_hour") & pl.col("hour").is_in(BREAKOUT_HOURS))
        .join(asia, on="day", how="inner")
        .with_columns(
            long_.fill_null(value=False).alias("up"), short.fill_null(value=False).alias("dn")
        )
        .filter(pl.col("up") | pl.col("dn"))
        .sort("_i")
        .group_by("day", maintain_order=True)
        .first()
        .filter(~(pl.col("up") & pl.col("dn")))
    )
    out = np.zeros(frame.height, dtype=np.int8)
    idx = first["_i"].to_numpy()
    out[idx] = np.where(first["up"].to_numpy(), 1, -1)
    return out


def _h03(ctx: SignalContext, c_max: float) -> Directions:
    """24-bar channel breakout while ATR14[t-1] / mean(ATR14[t-120..t-1]) <= c."""
    _, h, lo, c, atr = _arrays(ctx.h1)
    ratio = compression_ratio(atr)
    hh, ll = prior_channel(h, lo, CHANNEL_WINDOW)
    with np.errstate(invalid="ignore"):
        compressed = ratio <= c_max
    return np.where(compressed, _breakout(c, hh, ll), 0).astype(np.int8)


def daily_momentum(ctx: SignalContext, lookback: int) -> Floats:
    """``sign(close_D - close_{D-L})`` of the latest daily bar closed at each H1 bar's close."""
    daily = ctx.daily.select(
        pl.col("available_at").alias("_key"),
        (pl.col("close") - pl.col("close").shift(lookback)).sign().alias("m"),
    )
    joined = ctx.h1.select("available_at").join_asof(
        daily, left_on="available_at", right_on="_key", strategy="backward"
    )
    return joined["m"].cast(pl.Float64).fill_null(np.nan).to_numpy()


def _h04(ctx: SignalContext, lookback: float) -> Directions:
    """Daily momentum (L daily bars) + H1 close crossing EMA20 in the trend direction."""
    _, _, _, c, _ = _arrays(ctx.h1)
    m = daily_momentum(ctx, int(lookback))
    ema = ind.ema(c, EMA_PERIOD)
    prev_c = np.concatenate([[np.nan], c[:-1]])
    prev_e = np.concatenate([[np.nan], ema[:-1]])
    with np.errstate(invalid="ignore"):
        up = (m == 1) & (prev_c <= prev_e) & (c > ema)
        down = (m == -1) & (prev_c >= prev_e) & (c < ema)
    return np.where(up, 1, np.where(down, -1, 0)).astype(np.int8)


def _h05(ctx: SignalContext, s: float) -> Directions:
    """Fade: |body_t| >= s x ATR14[t-1] gives the direction opposite to the body."""
    o, _, _, c, atr = _arrays(ctx.h1)
    prev_atr = np.concatenate([[np.nan], atr[:-1]])
    body = c - o
    with np.errstate(invalid="ignore"):
        fire = np.abs(body) >= s * prev_atr
    return np.where(fire, -np.sign(body), 0).astype(np.int8)


def _h06(ctx: SignalContext, n_bars: float) -> Directions:
    """H4 close beyond the high/low of the previous N H4 bars."""
    if ctx.h4 is None:
        msg = "H06 needs H4 bars: build the context with edge_context(h1, h4)"
        raise ValueError(msg)
    _, h, lo, c, _ = _arrays(ctx.h4)
    hh, ll = prior_channel(h, lo, int(n_bars))
    return _breakout(c, hh, ll)


_DIRECTIONS: Final[Mapping[str, Callable[[SignalContext, float], Directions]]] = MappingProxyType(
    {"H01": _h01, "H02": _h02, "H03": _h03, "H04": _h04, "H05": _h05, "H06": _h06}
)


def variant_signals(variant: Variant | str, ctx: SignalContext) -> pl.DataFrame:
    """Signal rows of one variant (``SIGNAL_COLUMNS`` plus ``regime``), over the whole context."""
    v = get_variant(variant) if isinstance(variant, str) else variant
    spec = v.spec
    direction = _DIRECTIONS[spec.hypothesis](ctx, float(v.value))
    frame = ctx.h4 if spec.signal_timeframe is Timeframe.H4 else ctx.h1
    assert frame is not None  # noqa: S101 - _h06 already refused a missing H4 frame
    return signals_from_direction(
        frame,
        pl.Series("direction", direction, dtype=pl.Int8),
        name=v.variant_id,
        stop_atr=spec.stop_atr,
        target_atr=spec.target_atr,
        max_hold_bars=spec.hold_execution_bars,
        cooldown_bars=spec.cooldown_bars,
    )


def generate_signals(
    variant: Variant | str, h1: pl.DataFrame, h4: pl.DataFrame | None = None
) -> pl.DataFrame:
    """Convenience: build the context and return one variant's signals."""
    return variant_signals(variant, edge_context(h1, h4))
