"""Prefix-invariance audit of joshyattridge/smart-money-concepts (third-party, not our code).

For each function: run it on the full series and on every prefix; a label that exists at row i in the
full run must also exist at row i in a prefix run once that prefix could know it. We measure, per
label, the first cut t at which it appears (its real confirmation lag) and any label whose value
CHANGES between a prefix and the full run (repaint).
"""

import sys

import numpy as np
import pandas as pd
from smartmoneyconcepts import smc

rng = np.random.default_rng(5)
n = 400
close = 100 + np.cumsum(rng.normal(0, 0.3, n))
ohlc = pd.DataFrame(
    {
        "open": np.r_[close[0], close[:-1]] + rng.normal(0, 0.05, n),
        "high": close + np.abs(rng.normal(0, 0.15, n)) + 0.05,
        "low": close - np.abs(rng.normal(0, 0.15, n)) - 0.05,
        "close": close,
        "volume": rng.integers(100, 1000, n).astype(float),
    }
)
ohlc["high"] = ohlc[["high", "open", "close"]].max(axis=1)
ohlc["low"] = ohlc[["low", "open", "close"]].min(axis=1)

L = 5
full_sw = smc.swing_highs_lows(ohlc, swing_length=L)
full_fvg = smc.fvg(ohlc)


def first_seen(fn, col):
    """label index -> first prefix end at which that label (same value) is present; plus changes."""
    full = fn(ohlc)[col]
    first, changed = {}, 0
    for t in range(20, n, 3):
        part = fn(ohlc.iloc[: t + 1].reset_index(drop=True))[col]
        for i in range(len(part)):
            v = part.iloc[i]
            if pd.isna(v):
                continue
            fv = full.iloc[i]
            if pd.isna(fv) or fv != v:
                changed += 1
            first.setdefault(i, t)
    return full, first, changed


def report(name, fn, col):
    full, first, changed = first_seen(fn, col)
    labels = [i for i in range(n) if not pd.isna(full.iloc[i])]
    lags = [first[i] - i for i in labels if i in first]
    missing = [i for i in labels if i not in first and i < n - 25]
    print(
        f"{name}: labels in full run {len(labels)}; seen in prefixes {len(lags)}; "
        f"min lag {min(lags) if lags else None} median {np.median(lags) if lags else None} max {max(lags) if lags else None}; "
        f"labels that CHANGED value between a prefix and the full run: {changed}; labels never seen in any prefix: {len(missing)}"
    )
    print(
        f"   labels visible in the full run at row i whose information arrived later than row i: {sum(1 for g in lags if g > 0)} of {len(lags)}"
    )
    return lags


report(
    "swing_highs_lows(swing_length=5)", lambda d: smc.swing_highs_lows(d, swing_length=L), "HighLow"
)
report("fvg", smc.fvg, "FVG")
sys.stdout.flush()
