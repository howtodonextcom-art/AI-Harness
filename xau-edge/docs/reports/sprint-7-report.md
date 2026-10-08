# Sprint 7 - Report

Date: 2026-10-08. Scope: Epics 08 (historical outcomes) and 09 (baseline strategies), the
experiment registry (brief section 39), and the pre-registered evaluation protocol.

## Delivered

| Item | Module |
|---|---|
| Outcome engine: forward return, MFE/MAE (ATR units), direction, barrier results and R for both sides | `outcomes/engine.py` |
| Outcome statistics: probabilities with Wilson intervals, percentiles, expected R | `outcomes/summary.py` |
| Experiment registry (write-once, content-addressed, variant counting, NaN-safe) | `experiments/registry.py` |
| Cross-timeframe alignment without look-ahead; per-timeframe context | `strategies/context.py` |
| Baselines A, B, C (signals only) | `strategies/baselines.py`, `strategies/pattern.py` |
| Day-block bootstrap, pre-registered periods, protocol as code (Bonferroni alpha, pass rule, test-period lock) | `evaluation/` |
| Pre-registration | `docs/evals/edge-criteria.md` (written before any result), ADR-0014 |

## The result: the pre-specified analogue study does not show predictive skill

Configuration fixed in advance (M15, window 30, k = 20, Euclidean, 20-bar outcomes, every 4th bar).
Measure: does the direction suggested by the 20 analogues predict the query's own next-20-bar move?

| Period | Queries | Total (ATR) | Timing (ATR) | Rule |
|---|---|---|---|---|
| Development 2025-05..2025-12 | 3,941 | -0.138 [-0.279, +0.010] | -0.158 [-0.299, -0.012] | FAIL |
| Validation 2026-01..2026-04 | 1,924 | +0.050 [-0.149, +0.252] | +0.019 [-0.160, +0.180] | FAIL |
| Test | not run (locked: needs both earlier periods to pass) | | | |

Reading: nothing in Validation; Development is, if anything, slightly the wrong way round and did
not replicate. Gold drifted up (+0.31 ATR per 20 bars in Development, +0.10 in Validation), and the
analogues lean long about as often as that would suggest; the timing statistic removes that effect.
Baseline C therefore has no support from the study. Rules for post-hoc ideas (for example fading the
analogues) are in ADR-0014: they count as new variants and need fresh data.

Baselines A and B were built and tested (signals only) but were not evaluated: they need the
cost-aware backtest of Sprints 8-9, which is where the edge criteria apply.

## Evidence

* **Tests first:** outcome-engine expectations were worked out by hand; failing import (RED) before
  the code. 718 tests, 97% coverage; ruff and `mypy --strict` clean.
* **Mutation spot-check:** 25 mutants (direction boundaries, barrier tie-break, window offsets,
  end-close index, clamps, short-side mirroring, Wilson centre, registry idempotence and tamper
  check, variant counting, baseline thresholds, cooldown, fresh-entry rule, alignment strategy,
  edge threshold, step). 4 survived the first tests (falling-market excursions, idempotent
  `created_at`, inclusive `min_matches`, float rounding of the edge); tests added; all killed.
* **Independent review (1 reviewer, adversarial):** no look-ahead in the outcome engine (all columns
  identical when bars after `e + h` were perturbed), baselines/alignment (byte-identical signals after
  truncation) or the study. Fixed with tests: registry corrupted itself on NaN metrics (now rejected);
  the Bonferroni alpha, the pass rule and the test-period lock were convention only (now code in
  `evaluation/protocol.py`, periods read-only); realised outcomes could read the next period's bars
  (now clipped to the period). Re-ran both periods after the fixes (numbers above).
  Accepted and noted: the study scores the sign of the analogue mean while Baseline C trades on a
  thresholded `p_up - p_down` (the `edge` column is stored so a strategy-consistent test can be
  added); the timing bootstrap holds `mean(sign)` fixed (slightly narrow); outcome windows count
  bars, so a Friday anchor spans the weekend gap; cooldown counts rows.

## Red-team: how could this sprint be wrong?

| Question | Finding | Status |
|---|---|---|
| Null result from a weak configuration | One window, method and k were tested; others might behave differently | Open; any further variant is counted and must pass on unseen data |
| Low power | 1,924 validation queries, strongly overlapping outcomes; small true effects are undetectable | Open; the criteria need trade counts >= 100 anyway |
| Overlapping outcomes | Day-block bootstrap handles dependence within days, not across days | Accepted |
| Neutral band and horizon arbitrary | 0.5 ATR and 20 bars are conventions | Documented |
| Gross, not net | No costs yet; a gross null becomes worse net | Sprint 8 |
| Dev vs validation inconsistency | -0.16 then +0.02 timing: noise-level instability, not a finding | Recorded |
| Registry counts variants by parameters only | Code changes with the same parameters are separate records but one variant | Accepted |
