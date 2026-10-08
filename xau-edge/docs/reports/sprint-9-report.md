# Sprint 9 - Report

Date: 2026-10-08. Scope: Epic 10 part 2 (metrics, walk-forward folds, breakdowns), the edge criteria as
code, running baselines A, B, C on Development and Validation, and Checkpoint 1
(`docs/reports/checkpoint-1.md`).

## Delivered

| Item | Module |
|---|---|
| All brief section 25 metrics; undefined ratios are `None`; return by session and by regime | `backtest/metrics.py` |
| The seven edge criteria, four contiguous folds, Bonferroni alpha | `evaluation/edge.py` |
| Strategy runner (signals, M5 execution, session labels, prop feasibility from the equity curve) | `evaluation/runner.py`, `scripts/run_backtest.py` |
| Power test: a planted edge passes, the null fails | `tests/statistical/test_pipeline_power.py` |
| Registry records of every run | `experiments/runs` (local, git-ignored) |

## Result

All three baselines FAIL both periods; the test period was never touched (Checkpoint 1).

## Evidence and review

* **Tests first**, hand-computed metrics and criteria; 860+ tests, ruff and `mypy --strict` clean.
* **Independent review (adversarial, false-negative focus):** no bug explains the failures (direction
  flip, gross vs net, hand-checked trades, alignment, regime labels, bootstrap, folds). Fixed:
  research runs also opened the per-day risk throttles (they had thinned B's sample by about 30%);
  the test-period lock now needs the LATEST development and validation records to pass and refuses a
  second test run; the weak runner test now asserts signals exist. Noted: no-loss strategies get
  `profit_factor = None`, treated as a pass by the criterion; `gross_pnl` in trades already contains
  spread and slippage (it is not pre-cost P&L); the variant count K only counts backtest parameter
  sets (analogue-study records and informal exploration are not in K).
* **Known limit:** baseline A cannot reach 100 trades on a 4-month period (about 16 trades a month).

## Red-team: how could this sprint be wrong?

| Question | Finding | Status |
|---|---|---|
| False negatives | Planted-edge test and reviewer checks found none | Mitigated |
| Fixed parameters | Only one parameter set per baseline was tried; other sets might behave differently | Open; every further variant counts toward K |
| Cost assumptions | Slippage 3 points and zero commission are assumptions; they would have to be very wrong to flip all six results | Open |
| No news calendar | News spikes are in the data but not guarded | Open |
| One broker, 17 months, gold up 32% then 7% | A trending sample favours long-biased rules; none emerged | Open |
| Research limits | Prop buffers and per-day throttles were opened; prop feasibility is scanned separately | By design, stated |
| Multiple periods | Development and Validation were both inspected; Test untouched | Mitigated |
