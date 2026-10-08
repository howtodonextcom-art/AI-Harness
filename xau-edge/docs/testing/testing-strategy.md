# Testing strategy

Brief section 40. Run everything with `.\scripts\dev.ps1 check` (ruff, ruff format, `mypy --strict`,
pytest with coverage). CI runs the same on Ubuntu and Windows for Python 3.12, 3.13 and 3.14.

## Layers

| Layer | Where | What it proves | Status |
|---|---|---|---|
| Unit | `tests/unit/` | pure functions: validators, calendar, clock, resampling, store, catalog, settings, indicators, logging | 400+ tests, 98% coverage |
| Integration | `tests/integration/` (`-m integration`) | file -> validation path end to end; MT5 tests are marked `mt5` and never run in CI | file path done; MT5 manual (needs a terminal) |
| Regression | `tests/regression/` | results that must not change silently (pinned hashes now; indicator outputs and backtests later) | started |
| Statistical | `tests/statistical/` | leakage, calibration, walk-forward consistency | arrives with Epics 07, 10-12 |
| Golden | `tests/unit/features/test_indicators_golden.py` | indicators equal TA-Lib output recorded in `tests/fixtures/talib_golden.json` | done |

## Rules

1. **Test first.** A failing test (RED output) exists before the code; the sprint report records it.
2. **Synthetic data is for code paths only.** It carries no market information; never draw research
   conclusions from it. Real-data findings are recorded in reports, not asserted in tests.
3. **No look-ahead, by test.** Every indicator has a repainting test: appending future bars must not
   change any past value. Pattern and outcome code will get the same plus overlap and self-match tests.
4. **Warm-up is explicit.** Outputs are `NaN` before the first valid index; golden tests compare the
   warm-up mask, not just the values.
5. **Mutation spot-checks** for critical logic before closing a sprint (hand-made mutants; all must
   be killed). Sprint 3: 15 mutants over indicators and log redaction.
6. **Property tests** (hypothesis) for invariants such as RSI in [0, 100].
7. **Coverage** target 95%+ for data, risk and signal code; 80% is the floor.
8. **No test needs the network, a broker, or credentials.** `.env` is never read by tests.
9. **Red-team section** (brief section 52): every sprint report ends with "how could this be wrong?"
   covering data errors, leakage, timestamps, repainting, overfitting, unrealistic fills, cost
   assumptions, sample size, regime dependence and model instability, with a status per item.
10. **Overfitting checklist** (brief section 26) for any result that claims an edge: look-ahead, data
    leakage, feature leakage, curve fitting, parameter mining, repainting, over-optimisation, poor
    regime generalisation. Edge claims also need `santa-method` and pre-defined `eval-harness` evals.

## Golden fixture provenance

`tests/fixtures/talib_golden.json` holds a seeded synthetic random walk (400 bars) and the output of
TA-Lib (Python wrapper 0.8.1 over the C library) for EMA 9/20/50/200, SMA 20, RSI 14, true range,
ATR 14, ADX/+DI/-DI 14, MACD 12/26/9, slow stochastic 14/3/3 and Bollinger 20/2. TA-Lib is not a
dependency; to regenerate, install it in a scratch environment and rerun the generator described in
ADR-0010. TA-Lib trims MACD and stochastic outputs to a common start; the tests check our own
documented first valid index and compare values wherever TA-Lib reports one.

## Known gaps

* No test exercises a real MT5 terminal in CI (by design).
* Golden values come from one implementation (TA-Lib); a second independent source would reduce the
  shared-convention risk, but TA-Lib is the de facto reference.
* Indicator performance on 100k+ bars is untested (Python loops in the Wilder recursions).
