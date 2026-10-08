# ADR-0012: Market structure and regime rules

Status: accepted (2026-10-08). Rules were written down before the implementation and the hand-built
test series (`tests/unit/structure/test_swings_structure.py`) was worked out on paper first.

## Structure (`xau_edge.structure.swings`)

All definitions use only bars up to the current one; nothing is reported before it is knowable.

| Concept | Rule |
|---|---|
| Swing high at bar `i` | `high[i]` > the `left` bars before it, and >= the `right` bars after it; visible from bar `i + right` (confirmation). Ties: the first bar of a plateau wins, no duplicates |
| Swing low | mirror image (`<` on the left, `<=` on the right) |
| HH / LH, HL / LL | label of a new swing versus the previous swing of the same kind; equal gives 0 |
| Trend | +1 if latest high is HH and latest low is HL; -1 if LH and LL; else 0 |
| Break | the CLOSE crosses the latest confirmed, unbroken swing level; each level breaks once |
| BOS | break in the direction of the prior trend, or any break when the prior trend is 0 |
| CHoCH | break against the prior trend (up while -1, down while +1) |
| Support / resistance | within the last `sr_lookback` swings, the highest unbroken swing low below the close / lowest unbroken swing high above it |

**Order of operations on each bar** (pinned by tests): (1) a break is evaluated against the swing
levels that existed BEFORE this bar, and BOS versus CHoCH uses the trend of the PREVIOUS bar;
(2) unbroken/broken flags are updated; (3) swings confirmed on this bar are appended and labels and
trend are recomputed. Consequences: a bar can break a level and confirm a new swing at once; the
trend changes only at swing confirmation, never on a break, so it stays unchanged for a few bars
after a CHoCH; the trend combines the latest high label and the latest low label, either of which
may be old. A pivot bar can be a swing high and a swing low at once (outside bar).

Defaults `left = right = 3`, `sr_lookback = 10` are conventional, not fitted. Smart-Money-style
concepts beyond these (order blocks, fair value gaps, liquidity sweeps) are deliberately not
implemented because they lack objective definitions (brief section 12).

**Why close-based breaks.** A wick through a level is not a confirmed break and would make the label
sensitive to spikes and spread.

**Tests that protect the rules.** Hand-derived series; a mirror-symmetry property (negating prices
must negate trend, BOS, CHoCH and swap high/low labels), checked on random walks; truncation
equality (appending bars never changes earlier output); ties and exact-level closes.

## Regime (`xau_edge.structure.regime`)

First match wins: SHOCK (bar range >= 3 x previous bar's ATR), HIGH_VOLATILITY (ATR / median of the
previous 500 ATR values >= 1.5), TREND_UP / TREND_DOWN (ADX >= 25, direction by +DI vs -DI; equal DI is not a trend),
LOW_VOLATILITY (ratio <= 0.67), RANGE. Unknown (`None`) until the inputs exist and at least 100
earlier ATR values are available. The baseline excludes the current bar.

Thresholds are set a priori and are not tuned. Any change to them is a new rule set that must be
evaluated on data not used to choose them, and reported with the number of variants tried.

## Real-data sanity (not evidence of edge)

FTMO demo data, 2025-05 to 2026-10: regime shares on M15 are RANGE 46%, TREND_DOWN 21%, TREND_UP
18%, HIGH_VOLATILITY 9%, LOW_VOLATILITY 4%, SHOCK 1%; no label dominates absurdly. This only shows
the rules are exercised; it says nothing about predictive value.

## Known weaknesses

* BOS and CHoCH depend on the pivot window; a different window gives a different (equally valid)
  structure. Results using them must state the window and be checked for sensitivity.
* ADX-based trend labelling lags by construction.
* Gaps (weekend, daily break) are treated as ordinary consecutive bars.
