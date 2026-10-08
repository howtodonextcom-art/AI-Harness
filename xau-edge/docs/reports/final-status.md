# XAU EDGE: final status against the brief (2026-10-08)

Written for the project owner. It states what exists, what the evidence says, and what is not done.

## One-paragraph answer

XAU EDGE is built end to end: market data, features, structure, regimes, pattern analogues, outcome
statistics, a cost-aware backtest, a risk engine, four ML models with calibration, a signal engine, a
read-only API, a dashboard and a paper broker. Every component is tested and independently reviewed.
The research finding is negative: three pre-specified baselines and four models did not beat a
pre-registered, multiple-testing-adjusted bar after realistic costs, so the system's honest output is
**WAIT**, and it says so with reasons. The test period was never touched. No component can place a
real order.

## MVP acceptance criteria (brief section 49)

| # | Criterion | Status |
|---|---|---|
| 1 | Import XAUUSD history from MT5 | done (FTMO demo, read-only, DEMO-guarded) |
| 2 | Data validation succeeds | done (16 issue codes; real data passes with documented warnings) |
| 3 | M5/M15/H1/H4 queryable | done (DuckDB catalog) |
| 4 | Feature engine runs reproducibly | done (versioned feature set, hash-pinned regression) |
| 5 | Structure classifies HH, HL, LH, LL, BOS, CHoCH | done (non-repainting, mirror-symmetry tested) |
| 6 | Pattern engine retrieves analogues | done (5 measures, leakage-safe) |
| 7 | Outcome engine gives UP/DOWN/NEUTRAL probabilities | done (with intervals, MFE/MAE, expected R) |
| 8 | Backtester simulates a baseline | done (3 baselines) |
| 9 | Costs included | done (measured spread, slippage, commission, swap) |
| 10 | Dashboard shows regime, multi-timeframe context, analogues, probabilities, BUY/SELL/WAIT | done (checked at 1440x900 and 390 px on real data) |
| 11 | No live trade can be sent | done (no broker order API anywhere; tests scan for it) |
| 12 | All critical modules have tests | done (1,030+ tests, 97% coverage, mutation spot-checks each sprint) |

## Run-ladder (docs/ROADMAP_TRACEABILITY.md section 5)

L0 foundation, L1 real data, L2 offline research, L3 costed backtest, L4a offline signals and
dashboard, L4b paper trading: all reached. L4c (weeks of forward paper trading on new data) has the
tooling (`scripts/forward_test.py`, `compare_paper_to_backtest` with a 100-trade guard) but has not
run: it is calendar-time bound and there is no validated candidate to forward-test. L5 (real money) is
out of scope by decision.

## What the evidence says

* Analogue-direction study: no skill on Development or Validation.
* Baselines A, B, C: all FAIL both periods; results flip sign between periods (noise signature).
* Models: none beats the base rate out of sample; calibration matters (Platt best, isotonic and
  uncalibrated worse) but does not rescue them.
* The pipeline is able to see an edge: a planted edge passes all seven criteria, the same market
  without it fails.
* Not a proof that no edge exists: one broker, one symbol, 17 months, simple pre-specified rules.

## Not done, and why

| Item | Reason |
|---|---|
| Forward test with new data | needs weeks of calendar time and a candidate that passed validation |
| News calendar data and the news-window backtest | no data source in the project; the guard fails closed (NEWS_UNKNOWN forces WAIT) |
| Holiday calendar | only reclassifies validator warnings; nothing consumes it |
| Live execution, `MT5ExecutionBroker` | out of scope by decision (ADR-0018) |
| Wednesday triple swap, partial fills, latency, margin | not modelled (ADR-0015) |
| Dashboard browser tests in CI | type-check, lint and build run in CI; screenshots were inspected manually |
| Persistent kill switch | needed only when an executor exists |
| Docker, STUMPY/tslearn dependencies | not justified; numba support does not cover the Python matrix |

## Assumptions that would have to be checked before relying on any number

Slippage 3 points per fill (not measured), commission 0 (unverified for the account type), swap
values read once on 2026-10-08, no news guard in the research backtests, FTMO rules verified on
2026-10-08 (they change), restrictions on automated trading not stated on the objectives page.

## If the owner wants to continue

In order of expected value: (1) run the forward replay daily on newly fetched bars to start the
calendar-time sample; (2) add a verified economic calendar and rerun the pre-registered news-window
study; (3) gather tick data and a second broker to test whether the null is data-limited; (4) any new
strategy or model idea goes through `docs/evals/edge-criteria.md` as a counted variant, with the test
period still locked.
