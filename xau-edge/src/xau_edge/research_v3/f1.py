"""F1-USDRES-z2.0 (docs/research/edge-program-v3/F1_gold_usd_residual.md), frozen 2026-10-11.

Readings of the preregistration fixed here BEFORE any outcome was computed:

* An hourly return exists only when the symbol's previous H1 bar opened exactly one hour earlier;
  hours missing a return in any of XAU/EURUSD/USDJPY are dropped (no interpolation). The rolling
  window is the 500 previous rows of that joined series. Residual sigma = sqrt(SSR / (500 - 2)).
* "First bar of the week" and "bar after a gap > 1 h" have no one-hour return, so they cannot be
  events; both are counted.
* Entry "open of H1 bar t+1" is the XAU H1 bar opening exactly one hour after the event bar, priced
  at the first M1 bar inside that hour (the daily reopen bar has no M1 bar at :00). No such H1 bar,
  or no M1 bar inside it: ``dropped_missing_bar`` (COMMON_PROTOCOL).
* Timeout: the open of the 25th XAU H1 bar counting the entry bar as the first, priced at the first
  M1 bar inside that hour. Only a trade that actually reaches the timeout without an M1 bar there is
  dropped (``dropped_missing_bar``); a barrier exit before it stands. Because every event carries
  six paths (long/short x gross/base/pessimistic) on one event set, the event is dropped if any of
  them cannot be priced (expected to be vanishingly rare; counted in ``dropped_missing_bar``).
* One position at a time is decided on the base-cost path; gross, pessimistic and the placebo's
  opposite side reuse the same event set. A stop/target exit occupies its whole minute.
* Swap: current MT5 values at each 17:00 New York Monday..Friday rollover held through, no triple
  Wednesday (CostModel). Triple Wednesday and zero swap are reported as non-gating sensitivities
  (2026 swap applied to 2011-2018 is a documented pessimistic anachronism).

Review 2026-10-11 (before any outcome): reopen-hour M1 lookup, 17:00 New York rollover, literal
alpha 0.0333, trading-calendar bootstrap blocks, same-minute re-entry.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import numpy as np
import polars as pl
from numpy.typing import NDArray

from xau_edge.features import indicators as ind
from xau_edge.research_v3.execution import (
    GROSS,
    M1,
    POINT,
    Fill,
    rollovers,
    scenarios_for_year,
    simulate,
    swap_r,
)

LOOKBACK = 500
Z_STAR = 2.0
ATR_PERIOD = 14
SL_ATR = 1.0
TP_ATR = 2.0
TIMEOUT_BARS = 24
HOUR_US = 3_600_000_000


def hourly_returns(df: pl.DataFrame, name: str) -> pl.DataFrame:
    """``timestamp, r_<name>``: log close-to-close where the previous bar is exactly 1 h earlier."""
    return (
        df.select("timestamp", "close")
        .with_columns(
            (pl.col("close") / pl.col("close").shift(1)).log().alias(f"r_{name}"),
            (pl.col("timestamp") - pl.col("timestamp").shift(1)).alias("dt"),
        )
        .filter(pl.col("dt") == timedelta(hours=1))
        .select("timestamp", f"r_{name}")
    )


def joined_returns(xau: pl.DataFrame, eur: pl.DataFrame, jpy: pl.DataFrame) -> pl.DataFrame:
    j = (
        hourly_returns(xau, "xau")
        .join(hourly_returns(eur, "eur"), on="timestamp", how="inner")
        .join(hourly_returns(jpy, "jpy"), on="timestamp", how="inner")
        .sort("timestamp")
    )
    return j.with_columns((0.5 * (pl.col("r_jpy") - pl.col("r_eur"))).alias("u"))


def rolling_z(
    y: NDArray[np.float64], u: NDArray[np.float64], chunk: int = 4096
) -> NDArray[np.float64]:
    """z_i from OLS of y on u over rows i-500..i-1 (NaN for the first 500 rows). Vectorized."""
    n = y.size
    z = np.full(n, np.nan)
    if n <= LOOKBACK:
        return z
    wy = np.lib.stride_tricks.sliding_window_view(y[:-1], LOOKBACK)
    wu = np.lib.stride_tricks.sliding_window_view(u[:-1], LOOKBACK)
    for a in range(0, wy.shape[0], chunk):
        yy, uu = wy[a : a + chunk], wu[a : a + chunk]
        um, ym = uu.mean(axis=1, keepdims=True), yy.mean(axis=1, keepdims=True)
        du, dy = uu - um, yy - ym
        beta = (du * dy).sum(axis=1) / (du * du).sum(axis=1)
        alpha = ym[:, 0] - beta * um[:, 0]
        resid = yy - (alpha[:, None] + beta[:, None] * uu)
        sigma = np.sqrt((resid * resid).sum(axis=1) / (LOOKBACK - 2))
        i = np.arange(a, a + yy.shape[0]) + LOOKBACK
        z[i] = (y[i] - (alpha + beta * u[i])) / sigma
    return z


def reference_z(y: NDArray[np.float64], u: NDArray[np.float64], i: int) -> float:
    """Oracle: explicit least squares on one window (independent code path)."""
    x = np.column_stack([np.ones(LOOKBACK), u[i - LOOKBACK : i]])
    coef, *_ = np.linalg.lstsq(x, y[i - LOOKBACK : i], rcond=None)
    resid = y[i - LOOKBACK : i] - x @ coef
    sigma = float(np.sqrt(resid @ resid / (LOOKBACK - 2)))
    return float((y[i] - (coef[0] + coef[1] * u[i])) / sigma)


@dataclass(frozen=True)
class Inputs:
    xau_h1: pl.DataFrame
    eur_h1: pl.DataFrame
    jpy_h1: pl.DataFrame
    xau_m1: pl.DataFrame


def m1_arrays(df: pl.DataFrame) -> M1:
    return M1(
        t=df["timestamp"].dt.epoch("us").to_numpy().astype(np.int64),
        o=df["open"].to_numpy().astype(np.float64),
        h=df["high"].to_numpy().astype(np.float64),
        low=df["low"].to_numpy().astype(np.float64),
        spread=df["spread"].to_numpy().astype(np.float64),
    )


def _exact(t: NDArray[np.int64], value: int) -> int | None:
    k = int(np.searchsorted(t, value))
    return k if k < t.size and t[k] == value else None


def first_in_hour(t: NDArray[np.int64], hour_us: int) -> tuple[int, bool]:
    """Index of the first M1 bar at or after ``hour_us`` and whether it lies inside that hour."""
    k = int(np.searchsorted(t, hour_us))
    return k, k < t.size and t[k] < hour_us + HOUR_US


def trading_day(us: int) -> int:
    """FX trading day of an instant (17:00 New York opens the next day), as days since the epoch.

    The Sunday-evening session belongs to Monday, so every key is a Monday..Friday.
    """
    from zoneinfo import ZoneInfo  # noqa: PLC0415

    ny = datetime.fromtimestamp(us / 1e6, tz=UTC).astimezone(ZoneInfo("America/New_York"))
    return ((ny.replace(tzinfo=None) + timedelta(hours=7)).date() - date(1970, 1, 1)).days


def run(inp: Inputs, start: datetime, end: datetime) -> dict[str, Any]:
    """Events with decision time in [start, end) and their outcomes on every cost path."""
    j = joined_returns(inp.xau_h1, inp.eur_h1, inp.jpy_h1)
    y, u = j["r_xau"].to_numpy(), j["u"].to_numpy()
    z = rolling_z(y, u)
    jt = j["timestamp"].dt.epoch("us").to_numpy().astype(np.int64)

    xh = inp.xau_h1
    ht = xh["timestamp"].dt.epoch("us").to_numpy().astype(np.int64)
    atr = np.asarray(
        ind.atr(xh["high"].to_numpy(), xh["low"].to_numpy(), xh["close"].to_numpy(), ATR_PERIOD),
        dtype=np.float64,
    )
    m1 = m1_arrays(inp.xau_m1)
    s_us, e_us = int(start.timestamp() * 1e6), int(end.timestamp() * 1e6)

    counts = {
        "rows_in_window": 0,
        "events_raw": 0,
        "dropped_missing_bar": 0,
        "skipped_position_open": 0,
    }
    trades: list[dict[str, Any]] = []
    last_exit = -1
    for i in np.flatnonzero((jt >= s_us) & (jt < e_us)):
        counts["rows_in_window"] += 1
        if not np.isfinite(z[i]) or abs(z[i]) < Z_STAR:
            continue
        counts["events_raw"] += 1
        t = int(jt[i])
        k = _exact(ht, t)
        if (
            k is None
            or k + 1 + TIMEOUT_BARS >= ht.size
            or ht[k + 1] != t + HOUR_US
            or not np.isfinite(atr[k])
        ):
            counts["dropped_missing_bar"] += 1
            continue
        e, e_ok = first_in_hour(m1.t, int(ht[k + 1]))
        x, x_ok = first_in_hour(m1.t, int(ht[k + 1 + TIMEOUT_BARS]))
        if not e_ok:
            counts["dropped_missing_bar"] += 1
            continue
        if m1.t[e] < last_exit:
            counts["skipped_position_open"] += 1
            continue
        trade = _trade(m1, e, x, x_ok, int(-np.sign(z[i])), float(atr[k]), t, float(z[i]))
        if trade is None:
            counts["dropped_missing_bar"] += 1
            continue
        last_exit = trade["exit_us"] + (0 if trade["reason"] == "TIME_EXIT" else 60_000_000)
        trades.append(trade)
    return {"counts": counts, "trades": trades}


def _trade(  # noqa: PLR0917
    m1: M1, e: int, x: int, x_ok: bool, direction: int, a: float, t: int, zval: float
) -> dict[str, Any] | None:
    year = datetime.fromtimestamp(t / 1e6, tz=UTC).year
    base_sc, pess_sc = scenarios_for_year(year)
    out: dict[str, Any] = {
        "decision_us": t,
        "z": zval,
        "direction": direction,
        "atr": a,
        "year": year,
    }
    sides: dict[int, dict[str, float]] = {}
    base_fill: dict[int, Fill] = {}
    for d in (1, -1):
        fills = [
            simulate(m1, e, x, d, a, SL_ATR * a, TP_ATR * a, sc, x_exists=x_ok)
            for sc in (GROSS, base_sc, pess_sc)
        ]
        g, b, p = fills
        if g is None or b is None or p is None:
            return None
        nb = rollovers(int(m1.t[e]), int(m1.t[b.exit_i]))
        np_ = rollovers(int(m1.t[e]), int(m1.t[p.exit_i]))
        n3 = rollovers(int(m1.t[e]), int(m1.t[b.exit_i]), triple_wednesday=True)
        base_fill[d] = b
        sides[d] = {
            "gross": g.r,
            "base": b.r + swap_r(d, nb, a),
            "pess": p.r + swap_r(d, np_, a),
            "base_triple_wed": b.r + swap_r(d, n3, a),
            "base_zero_swap": b.r,
            "slip_r": 2 * base_sc.slip_points * POINT / a,
            "swap_r": swap_r(d, nb, a),
            "nights": nb,
        }
    me = sides[direction]
    bf = base_fill[direction]
    out |= {
        "entry_us": int(m1.t[e]),
        "exit_us": int(m1.t[bf.exit_i]),
        "base_zero_swap_r": me["base_zero_swap"],
        "entry_px": bf.entry_px,
        "exit_px": bf.exit_px,
        "reason": bf.reason,
        "gross_r": me["gross"],
        "base_r": me["base"],
        "pess_r": me["pess"],
        "base_triple_wed_r": me["base_triple_wed"],
        "slip_r": me["slip_r"],
        "swap_r": me["swap_r"],
        "nights": int(me["nights"]),
        "long_base_r": sides[1]["base"],
        "short_base_r": sides[-1]["base"],
        "day": trading_day(int(m1.t[e])),
    }
    return out


def reference_trade(  # noqa: PLR0917
    bars: list[tuple[int, float, float, float, float]],
    entry_us: int,
    timeout_hour_us: int,
    direction: int,
    a: float,
    spread_mult: float,
    slip_points: float,
) -> tuple[int, str, float] | None:
    """Oracle: (exit_us, reason, R before swap), walking M1 tuples (t, o, h, l, spread)."""
    by_t = {b[0]: b for b in bars}
    eb = by_t[entry_us]

    def ask_add(b: tuple[int, float, float, float, float]) -> float:
        return b[4] * POINT * spread_mult

    entry = eb[1] + (ask_add(eb) if direction == 1 else 0.0)
    sl = entry - a if direction == 1 else entry + a
    tp = entry + 2 * a if direction == 1 else entry - 2 * a
    slip = 2 * slip_points * POINT / a
    for b in sorted(x for x in bars if entry_us <= x[0] < timeout_hour_us):
        if direction == 1:
            o, h, lo = b[1], b[2], b[3]
            if lo <= sl:
                px = o if (b[0] != entry_us and o <= sl) else sl
                return b[0], "STOP_LOSS", (px - entry) / a - slip
            if h >= tp:
                return b[0], "TAKE_PROFIT", (tp - entry) / a - slip
        else:
            add = ask_add(b)
            o, h, lo = b[1] + add, b[2] + add, b[3] + add
            if h >= sl:
                px = o if (b[0] != entry_us and o >= sl) else sl
                return b[0], "STOP_LOSS", (entry - px) / a - slip
            if lo <= tp:
                return b[0], "TAKE_PROFIT", (entry - tp) / a - slip
    inside = sorted(x for x in bars if timeout_hour_us <= x[0] < timeout_hour_us + HOUR_US)
    if not inside:
        return None
    xb = inside[0]
    px = xb[1] + (0.0 if direction == 1 else ask_add(xb))
    return xb[0], "TIME_EXIT", direction * (px - entry) / a - slip
