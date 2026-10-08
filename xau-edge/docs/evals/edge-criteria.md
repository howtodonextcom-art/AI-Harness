# Evaluation criteria, fixed BEFORE any outcome or backtest is looked at

Written 2026-10-08 (ECC `eval-harness`: define the evals first). Nothing in this file may be changed
after results exist without recording the change, the reason and the number of variants already
tried. The aim is to keep "we found an edge" honest.

## Data splits (chronological, never shuffled)

Data: FTMO demo XAUUSD, 2025-05-01 to 2026-10-07, M5/M15/H1/H4.

| Period | Dates | Use |
|---|---|---|
| Development | 2025-05-01 .. 2025-12-31 | design, debugging, sanity checks, choosing among variants |
| Validation | 2026-01-01 .. 2026-04-30 | compare the finalists chosen on development |
| Test | 2026-05-01 .. 2026-10-07 | touched once per finished candidate; reported whatever it shows |

Warm-up bars before a period may come from earlier periods (indicators need them); decisions and
outcomes must lie inside the period. Pattern search history may use any data strictly before the
query minus the leakage margin (ADR-0013). Walk-forward (Sprint 9) uses anchored expanding training
windows with contiguous monthly test folds inside Validation and Test.

## Pre-specified analogue study (Sprint 7)

One configuration, chosen a priori: M15, window 30, horizon guard 60, `k = 20`, Euclidean distance,
outcome horizon 20 bars, neutral band 0.5 ATR, queries every 4th bar. Question: do the 20 analogues'
outcomes predict the query's own outcome better than the base rate?

* Statistics (both reported, day-block bootstrap 95% intervals, 2,000 resamples, seed 7):
  - total: mean of `sign(analogue mean forward ATR move) * realised forward ATR move`;
  - timing: mean of `(sign_i - mean(sign)) * realised_i`, the part not explained by always leaning
    the same way (gold drifts, so a constant bias would otherwise look like skill).
* Pass: the lower bound of BOTH intervals > 0 on Development AND Validation (amended on 2026-10-08
  before any result existed: the timing statistic was added to the pass rule). Test only after both
  periods pass.
* Alternatives (other windows, methods, k) are exploratory; each is counted in the registry and the
  required interval widens accordingly (see multiple testing).

## Edge criteria for a strategy (Sprint 9 checkpoint)

A strategy "shows an edge" only if ALL hold on Validation and then on Test, net of costs (measured
M5 spread, commission and slippage assumptions from the broker profile):

1. At least 100 trades in the period.
2. Mean net R per trade > 0 with a day-block bootstrap interval whose lower bound > 0 at the level
   `1 - 0.05 / K`, where `K` is the number of strategy variants evaluated so far (from the registry).
3. Net profit factor >= 1.2.
4. Maximum drawdown <= 15 R.
5. Positive mean net R in at least 3 of 4 contiguous walk-forward folds of the period.
6. Removing the best 5% of trades leaves mean net R > 0.
7. No single regime or session supplies more than 60% of net profit.

Failing any criterion is a failure; there is no partial credit and no re-running with new parameters
on the same period. A failed Test period ends that candidate.

## Model criteria (Sprint 10)

A model replaces nothing unless, out of sample on Validation and Test, it (a) beats the best baseline
on the criteria above and (b) has better Brier score and log loss than the base rate and than the
analogue estimate, with calibration error reported. Simpler wins ties.

## Checkpoint rule (after Sprint 9)

* At least one baseline meets all edge criteria: proceed to ML and signal engine on that evidence.
* None does: record "no statistically justified trade found with these baselines" as the result.
  Later components are still built (signal engine, API, dashboard, paper trading) because their
  correct output in that situation is WAIT with the reasons; no component may present a probability
  as an edge it has not demonstrated.

## Reporting rules

Every report states: data period, number of variants tried (registry count), costs assumed, trade
count, intervals, and every criterion with pass/fail. Negative results are published like positive
ones.
