# Sprint 10 - Report

Date: 2026-10-08. Scope: Epics 11 and 12 (ML benchmark and probability calibration).

## Delivered

Dataset (54 scale-free features, forward direction labels), the four models in the brief's order,
Platt and isotonic calibration with Brier, log loss and reliability scoring, walk-forward with
embargo, model signals, versioned model artifacts, model runner and script; results in
`docs/research/model-evaluation.md`; ADR-0016. The `ml` extra (scikit-learn, XGBoost, LightGBM) is
installed in CI and tested on Python 3.12-3.14.

## Result

No model beats the base rate out of sample and none passes the edge criteria. Logistic regression
looked slightly better than the base rate on Development (log loss 1.0132 vs 1.0159, +19% in the
backtest) and failed on Validation (1.0235 vs 1.0170, -13.7%). Isotonic calibration and no calibration
were worse than Platt. No model is promoted; the test period is locked.

## Evidence and review

* Tests first: calibration maths by hand, planted-signal and pure-noise walk-forward tests (a signal is
  learned, noise is not), per-model shape/determinism/missing-value tests.
* Independent leakage review (real data): features identical when the last 20% of bars is removed;
  predictions for a fold unchanged (max diff 0) when every bar after the fold is rescaled; embargo
  arithmetic verified on a real fold (last fit label window ends before calibration starts, last
  calibration window ends before the first test row). No leakage found.
* Fixed after review: artifacts now include the calibrator and the real per-period pass flags with a
  time-stamped version; the test unlock requires matching dataset ids; the walk-forward test now records
  fitted row indices (the earlier one only counted rows); the vacuous runner assertion was replaced.
* Accepted: label/trade mismatch (ADR-0016), no interval on the base-rate comparison, validation labels
  near the end of April peek at most 20 bars into May for scoring only.

## Red-team

| Question | Finding | Status |
|---|---|---|
| Untuned models | No hyperparameter search | By design; further variants raise K |
| Weak features | Technical features only | Open |
| Small calibration sets | Isotonic overfits | Documented |
| Base rate moves with the regime | Per-fold base rate used | Mitigated |
| K | 10 variants counted across backtest and model families | Stated |
