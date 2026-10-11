import collections

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
full = smc.swing_highs_lows(ohlc, swing_length=L)["HighLow"]
kinds = collections.Counter()
examples = []
for t in range(20, n, 3):
    part = smc.swing_highs_lows(ohlc.iloc[: t + 1].reset_index(drop=True), swing_length=L)[
        "HighLow"
    ]
    for i in range(len(part)):
        v = part.iloc[i]
        if pd.isna(v):
            continue
        fv = full.iloc[i]
        if pd.isna(fv):
            kinds["label in a prefix, absent in the full run (vanishes)"] += 1
            if len(examples) < 4:
                examples.append((t, i, v, "NaN"))
        elif fv != v:
            kinds["label flips between high and low"] += 1
            if len(examples) < 4:
                examples.append((t, i, v, fv))
print(dict(kinds))
print("examples (cut t, row i, value in prefix, value in full):", examples)
# how close to the end of the prefix do the vanishing labels sit?
gaps = []
for t in range(20, n, 3):
    part = smc.swing_highs_lows(ohlc.iloc[: t + 1].reset_index(drop=True), swing_length=L)[
        "HighLow"
    ]
    for i in range(len(part)):
        if not pd.isna(part.iloc[i]) and pd.isna(full.iloc[i]):
            gaps.append(t - i)
print(
    "distance from the end of the prefix for vanishing labels: min",
    min(gaps) if gaps else None,
    "max",
    max(gaps) if gaps else None,
    "n",
    len(gaps),
)
