"""ML V0 features and label, exactly as frozen in ``docs/ml/ml_v0_spec.json`` (task ``rng24.v1``).

Every feature at row ``t`` uses bars ``<= t`` only (the hour/weekday features use the bar's open
time). The label looks 24 bars ahead and is therefore *not* known until the close of bar ``t+24``;
the walk-forward machinery enforces the embargo. No imputation: a row is excluded until every
lookback is complete (``valid_rows``).

ATR here is the SMA of the true range (the frozen spec), NOT Wilder's ATR used by the decision core.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from numpy.typing import NDArray

Floats = NDArray[np.float64]
SPEC_PATH = Path(__file__).resolve().parents[3] / "docs" / "ml" / "ml_v0_spec.json"

FEATURE_NAMES: tuple[str, ...] = (
    "lATR14", "lATR50", "lATR200", "lR24", "lR5", "lRV24", "ar1", "ar5", "lBBW",
    "hour_sin", "hour_cos", "dow_sin", "dow_cos",
)  # fmt: skip
HORIZON = 24
WARMUP_ROWS = 250
EPS = 1e-12
LABEL_VERSION = "rng24.v1"


@dataclass(frozen=True)
class Bars:
    """Closed H1 bars, strictly increasing in time (UTC epoch seconds of the bar OPEN)."""

    open_s: NDArray[np.int64]
    high: Floats
    low: Floats
    close: Floats

    def __post_init__(self) -> None:
        n = self.open_s.size
        if not (self.high.size == self.low.size == self.close.size == n):
            msg = "bar arrays must have the same length"
            raise ValueError(msg)
        if n > 1 and not bool(np.all(np.diff(self.open_s) > 0)):
            msg = "bars must be strictly increasing in time"
            raise ValueError(msg)
        if n and (self.high < self.low).any():
            msg = "high must be >= low"
            raise ValueError(msg)

    @property
    def size(self) -> int:
        return int(self.open_s.size)

    def head(self, rows: int) -> Bars:
        return Bars(self.open_s[:rows], self.high[:rows], self.low[:rows], self.close[:rows])


def _sma(x: Floats, k: int) -> Floats:
    out = np.full(x.size, np.nan)
    if x.size >= k:
        out[k - 1 :] = sliding_window_view(x, k).mean(axis=1)
    return out


def _roll(x: Floats, k: int, fn: str) -> Floats:
    out = np.full(x.size, np.nan)
    if x.size >= k:
        view = sliding_window_view(x, k)
        out[k - 1 :] = getattr(view, fn)(axis=1)
    return out


def _hour_dow(open_s: NDArray[np.int64]) -> tuple[Floats, Floats]:
    days = open_s // 86_400
    hour = ((open_s % 86_400) // 3_600).astype(np.float64)
    dow = ((days + 3) % 7).astype(np.float64)  # 1970-01-01 was a Thursday; Monday = 0
    return hour, dow


def build_features(bars: Bars) -> Floats:
    """The 13-column feature matrix (rows align with ``bars``; NaN while a lookback is incomplete)."""
    h, lo, c = bars.high, bars.low, bars.close
    n = bars.size
    prev_close = np.r_[c[:1], c[:-1]]
    tr = np.maximum(h - lo, np.maximum(np.abs(h - prev_close), np.abs(lo - prev_close)))
    log_ret = np.r_[0.0, np.diff(np.log(c))]
    sma20 = _sma(c, 20)
    sd20 = _roll(c, 20, "std")
    rng24 = _roll(h, 24, "max") - _roll(lo, 24, "min")
    rng5 = _roll(h, 5, "max") - _roll(lo, 5, "min")
    ar5 = np.full(n, np.nan)
    ar5[5:] = np.abs(c[5:] / c[:-5] - 1)
    hour, dow = _hour_dow(bars.open_s)
    with np.errstate(divide="ignore", invalid="ignore"):
        cols = (
            np.log(_sma(tr, 14) / c),
            np.log(_sma(tr, 50) / c),
            np.log(_sma(tr, 200) / c),
            np.log(rng24 / c),
            np.log(rng5 / c),
            np.log(_roll(log_ret, 24, "std") + EPS),
            np.abs(log_ret),
            ar5,
            np.log(4 * sd20 / sma20 + EPS),
            np.sin(2 * np.pi * hour / 24),
            np.cos(2 * np.pi * hour / 24),
            np.sin(2 * np.pi * dow / 7),
            np.cos(2 * np.pi * dow / 7),
        )
    return np.column_stack(cols)


def build_label(bars: Bars) -> Floats:
    """``y[t] = ln((max High[t+1..t+24] - min Low[t+1..t+24]) / Close[t])``; NaN for the last 24 rows."""
    n = bars.size
    y = np.full(n, np.nan)
    if n > HORIZON:
        ahead_hi = sliding_window_view(bars.high[1:], HORIZON).max(axis=1)
        ahead_lo = sliding_window_view(bars.low[1:], HORIZON).min(axis=1)
        m = ahead_hi.size  # rows 0 .. n-1-HORIZON have a full window
        with np.errstate(divide="ignore", invalid="ignore"):
            y[:m] = np.log((ahead_hi - ahead_lo) / bars.close[:m])
    return y


def valid_rows(x: Floats, y: Floats | None = None) -> NDArray[np.bool_]:
    """Rows usable for fitting/evaluation: past the warm-up, every feature (and label) finite."""
    ok = np.isfinite(x).all(axis=1) & (np.arange(x.shape[0]) >= WARMUP_ROWS)
    if y is not None:
        ok &= np.isfinite(y)
    return ok


def spec_features() -> list[dict[str, object]]:
    data = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    return list(data["features"])


def feature_schema_hash() -> str:
    """Hash of the feature contract in the spec (names, versions, normalisation, lookbacks)."""
    text = json.dumps(spec_features(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def live_row(bars: Bars) -> Floats:
    """The feature row for the LAST bar using only a bounded tail (what a live service would hold).

    A live process keeps the newest few hundred bars; this must equal the batch value at that row
    (the replay/live parity criterion).
    """
    tail = bars.size - 260 if bars.size > 260 else 0
    sub = Bars(bars.open_s[tail:], bars.high[tail:], bars.low[tail:], bars.close[tail:])
    return np.asarray(build_features(sub)[-1], dtype=np.float64)
