# Sprint 5 - Report

Date: 2026-10-08. Scope: Epics 05 (market structure) and 06 (market regime).

## Delivered

| Item | Module | Notes |
|---|---|---|
| Swings, HH/HL/LH/LL, trend, BOS, CHoCH, support/resistance | `structure/swings.py` | confirmed pivots (visible `right` bars later), close-based breaks, each level breaks once |
| Regime | `structure/regime.py` | SHOCK > HIGH_VOLATILITY > TREND_UP/DOWN > LOW_VOLATILITY > RANGE; unknown during warm-up |
| Frame | `structure/frame.py` | 14 columns aligned to bars with `available_at`; ATR-normalised distances to support/resistance |
| Rules | ADR-0012 | definitions, order of operations per bar, known weaknesses |

## Evidence

* **Tests first:** the hand-built series and its expected pivots, confirmations, BOS/CHoCH bars and
  support/resistance were derived on paper before any implementation; they passed on the first run.
  RED: the structure test module failed at import (module absent).
* **Repainting:** truncation equality for every output on the hand series at every cut, and on
  random walks; mirror symmetry (negated prices give negated trend/BOS/CHoCH and swapped labels)
  on five random walks.
* **Mutation spot-check:** 22 mutants (pivot comparisons, confirmation offset, BOS/CHoCH rules,
  close equality, broken flags, trend rule, support/resistance min/max, label sign, shock boundary,
  previous-ATR use, high/low-vol boundaries, ADX boundary, baseline window, min history, priority
  order, distance sign). 10 survived the first tests; tie, boundary, mirror and nearest-level tests
  were added and every non-equivalent mutant was then killed (one survivor is an equivalent no-op
  mutation I wrote by mistake).
* **Independent review (1 reviewer, quant stance):** no look-ahead or repainting found (40 random
  truncations, future shifted by +50). Findings fixed with tests: a test that could not fail
  (history exclusion) rewritten; equal DI no longer means TREND_DOWN; zero previous ATR cannot cause
  a shock; ADR now documents the per-bar order of operations, that trend changes only at swing
  confirmation, and that labels can be stale; outside-bar case pinned.
* **Real data sanity** (FTMO demo M15, 34,075 bars): 1,686 BOS, 685 CHoCH; regime shares RANGE
  46%, TREND_DOWN 21%, TREND_UP 18%, HIGH_VOL 9%, LOW_VOL 4%, SHOCK 1%. Not evidence of edge.
* Performance at 100k bars: structure 0.6 s, regime 1.6 s.

## Red-team: how could this sprint be wrong?

| Question | Finding | Status |
|---|---|---|
| Structure depends on the pivot window | Different `left/right` give different valid structure | Open; baselines (Sprint 7) must report sensitivity |
| Thresholds arbitrary | ADX 25, ratios 1.5/0.67, shock 3x are conventions | Documented as a priori; any retuning needs unseen data |
| Stale labels | Trend can combine an old high label with a new low label | Documented, pinned by test |
| Regime lag | ADX and ATR median lag turning points | Accepted |
| Gaps | Weekend/holiday gaps treated as consecutive bars | Documented (ADR-0011/0012) |
| Subjective-looking concepts | No order blocks / FVG / liquidity concepts implemented | By design |
| Small real sample | One broker, 17 months | Open |
