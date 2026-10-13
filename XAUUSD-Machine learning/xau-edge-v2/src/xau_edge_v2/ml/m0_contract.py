"""ML M0 / M1 infrastructure (RESEARCH ONLY): data schema, causal features, label contract, leakage guards.

No model is trained or deployed here and nothing in this module can influence a trade (authority
NONE). It defines WHAT a future model may learn and how to prove it learned from the past only.

Labels (no PnL, no price-outcome of a trade; both are properties of the market's own structure):

* ``vol_expansion_12.v1``: y_t = 1 when any of the next 12 bars has range >= 1.5 x ATR14_t.
  Known at the CLOSE of bar t+12 (``label_known_idx = t + 12``).
* ``break_failed_3.v1``: for every BOS/CHoCH event bar j, y = 1 when the broken level is lost again
  by a close within 3 bars. Known at the close of bar j+3.

Features (all computed from bars <= t, each with its provenance; see ``FEATURES``). Every feature
row is known at the close of its own bar. Splits are purged: a training row is dropped when its
label window (t .. label_known_idx) reaches into the test block or its embargo.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from numpy.typing import NDArray

from xau_edge_v2.core import indicators as ind
from xau_edge_v2.core import structure as st
from xau_edge_v2.core.frames import Frame
from xau_edge_v2.core.intelligence import structure_events as se

Floats = NDArray[np.float64]
SCHEMA_VERSION = "m0-1"
HORIZON_VOL = 12
EXPANSION_ATR = 1.5
FAIL_HORIZON = se.FAIL_WINDOW


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    source: str
    lookback: int
    causal: bool = True


FEATURES: tuple[FeatureSpec, ...] = (
    FeatureSpec("atr14_rel", "Wilder ATR(14) / close", 14),
    FeatureSpec(
        "atr_ratio", "ATR14 / median of the previous 100 ATR values (current excluded)", 115
    ),
    FeatureSpec("recent_range_atr", "mean(high-low) of the last 6 bars / ATR14", 20),
    FeatureSpec("last_range_atr", "(high-low) of the bar / ATR14", 14),
    FeatureSpec("body_share", "|close-open| / (high-low)", 1),
    FeatureSpec("close_pos", "(close-low) / (high-low)", 1),
    FeatureSpec("ema_dist_atr", "(close - EMA20) / ATR14", 40),
    FeatureSpec("adx14", "ADX(14)", 28),
    FeatureSpec("spread_atr", "bar spread (price) / ATR14", 14),
    FeatureSpec("hour_sin", "sin of the bar's UTC open hour", 1),
    FeatureSpec("hour_cos", "cos of the bar's UTC open hour", 1),
    FeatureSpec("regime_code", "control regime label as an integer", 260),
)
FEATURE_NAMES = tuple(f.name for f in FEATURES)
WARMUP = 260
_REGIMES = ("RANGE", "LOW_VOLATILITY", "TREND_UP", "TREND_DOWN", "HIGH_VOLATILITY", "SHOCK")


def build_features(frame: Frame) -> tuple[Floats, NDArray[np.bool_]]:
    """(X [n, k], valid [n]): row t uses bars <= t only; rows inside the warm-up are invalid."""
    n = frame.height
    o, h, lo, c = frame.open, frame.high, frame.low, frame.close
    atr = ind.atr(h, lo, c, 14)
    rng = h - lo
    with np.errstate(divide="ignore", invalid="ignore"):
        prev_atr_med = np.full(n, np.nan)
        if n > 101:
            win = sliding_window_view(atr, 100)  # window j covers bars j..j+99
            med = np.nanmedian(win, axis=1)
            prev_atr_med[100:] = med[: n - 100]  # for bar t: the 100 ATR values before t
        recent = np.full(n, np.nan)
        if n >= 6:
            recent[5:] = sliding_window_view(rng, 6).mean(axis=1)
        ema = ind.ema(c, 20)
        adx = ind.adx(h, lo, c, 14).adx
        hours = (frame.open_us // 3_600_000_000) % 24
        regime = st.classify_regime(
            adx=ind.adx(h, lo, c, 14).adx,
            plus_di=ind.adx(h, lo, c, 14).plus_di,
            minus_di=ind.adx(h, lo, c, 14).minus_di,
            atr=atr,
            high=h,
            low=lo,
            vol_window=min(200, n),
            min_history=min(60, n),
        )
        code = np.array(
            [_REGIMES.index(x) if x in _REGIMES else np.nan for x in regime], dtype=np.float64
        )
        cols = [
            atr / c,
            atr / prev_atr_med,
            recent / atr,
            rng / atr,
            np.abs(c - o) / np.where(rng > 0, rng, np.nan),
            (c - lo) / np.where(rng > 0, rng, np.nan),
            (c - ema) / atr,
            adx,
            frame.spread * 0.01 / atr,
            np.sin(2 * np.pi * hours / 24),
            np.cos(2 * np.pi * hours / 24),
            code,
        ]
    x = np.column_stack(cols).astype(np.float64)
    valid = np.isfinite(x).all(axis=1)
    valid[:WARMUP] = False
    return x, valid


def label_vol_expansion(frame: Frame) -> tuple[Floats, NDArray[np.int64]]:
    """(y, label_known_idx): y_t = 1 when any of the next 12 bars is >= 1.5 ATR14_t wide (NaN when unknown)."""
    n = frame.height
    atr = ind.atr(frame.high, frame.low, frame.close, 14)
    rng = frame.high - frame.low
    y = np.full(n, np.nan)
    known = np.arange(n, dtype=np.int64) + HORIZON_VOL
    if n > HORIZON_VOL:
        ahead = sliding_window_view(rng[1:], HORIZON_VOL).max(axis=1)  # max over t+1 .. t+12
        m = ahead.size
        with np.errstate(invalid="ignore"):
            y[:m] = (ahead >= EXPANSION_ATR * atr[:m]).astype(np.float64)
        y[:m][~np.isfinite(atr[:m])] = np.nan
    return y, known


def label_break_failed(frame: Frame) -> tuple[NDArray[np.int64], Floats, NDArray[np.int64]]:
    """(event bar index, y, label_known_idx) for every BOS/CHoCH whose outcome is already knowable."""
    events = se.structure_events(frame)
    lost: dict[tuple[str, float | None], list[int]] = {}
    for e in events:
        if e.kind.startswith("FAILED_BREAK"):
            lost.setdefault((e.kind[-2:].strip("_"), e.level), []).append(e.index)
    idx, ys, known = [], [], []
    for e in events:
        if not e.kind.startswith(("BOS", "CHOCH")):
            continue
        end = e.index + FAIL_HORIZON
        if end >= frame.height:
            continue  # the outcome of the label is not yet known at the end of the data
        side = "UP" if e.kind.endswith("UP") else "DOWN"
        failed = any(e.index < k <= end for k in lost.get((side, e.level), []))
        idx.append(e.index)
        ys.append(1.0 if failed else 0.0)
        known.append(end)
    return (
        np.array(idx, dtype=np.int64),
        np.array(ys, dtype=np.float64),
        np.array(known, dtype=np.int64),
    )


def purged_train_index(
    n: int,
    label_known_idx: NDArray[np.int64],
    test_start: int,
    test_end: int,
    embargo: int,
    *,
    walk_forward: bool = True,
) -> NDArray[np.int64]:
    """Training rows for the test block [test_start, test_end): rows whose label window ended before
    the block minus the embargo; unless ``walk_forward``, also rows that start after the block plus
    the embargo (purged k-fold)."""
    rows = np.arange(n)
    mask = (label_known_idx < test_start - embargo) & (rows < test_start)
    if not walk_forward:
        mask = mask | (rows >= test_end + embargo)
    return rows[mask]


def dataset_manifest(
    frame: Frame, x: Floats, y: Floats, valid: NDArray[np.bool_], label: str
) -> dict[str, object]:
    digest = hashlib.sha256()
    for arr in (frame.open_us, x[valid], y[valid]):
        digest.update(np.ascontiguousarray(arr).tobytes())
    return {
        "schema_version": SCHEMA_VERSION,
        "label": label,
        "features": [f.__dict__ for f in FEATURES],
        "rows": int(valid.sum()),
        "timeframe": frame.timeframe.value,
        "first_open_us": int(frame.open_us[0]),
        "last_open_us": int(frame.open_us[-1]),
        "sha256": digest.hexdigest(),
        "authority": "NONE",
        "pnl_in_labels": False,
    }


__all__ = [
    "FEATURES",
    "FEATURE_NAMES",
    "build_features",
    "dataset_manifest",
    "label_break_failed",
    "label_vol_expansion",
    "purged_train_index",
]
