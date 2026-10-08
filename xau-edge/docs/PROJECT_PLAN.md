# Project plan

Format follows ECC's `planner` agent: requirements, architecture changes, phased steps with
dependencies and risks, testing strategy, success criteria. Phases may not be skipped; each
needs a passed quality gate (build, tests, reproducible output, docs, no critical defect).

## Overview

Build XAU EDGE, a research-only probabilistic decision-support platform for XAUUSD, in the
13 phases defined in the project brief. Live trading is out of scope for every epic below.

## Epics

Complexity: S (<=2 days), M (3-5), L (1-2 weeks). Priority: P0 blocks later phases, P1 needed
for MVP, P2 after MVP.

| # | Epic | Key tasks | Depends on | Acceptance criteria | Main risk | Cx | Pri | Sprint |
|---|---|---|---|---|---|---|---|---|
| 01 | Repository bootstrap | package, lint, types, tests, config, AGENTS.md, docs | - | `dev.ps1 check` green; docs exist | tooling drift across OS | S | P0 | **1 (done)** |
| 02 | MT5 data connector | `BarSource` interface, MT5 adapter, offline file adapter | 01 | offline path works; MT5 path unit-tested with fake client | terminal truncates deep history silently (handled, ADR-0009) | M | P0 | 1 (adapters), **2 (verified on FTMO demo)** |
| 03 | Market-data validation | duplicate/order/gap/OHLC/volume/spread/tz/weekend checks; raw store | 02 | every check has a failing-input test; raw data immutable | holiday schedules not modelled | M | P0 | 1-2 (done) |
| 04 | Feature engine | returns, EMA, ADX, RSI/MACD/Stoch, ATR/BB, candle geometry, volume, session | 03 | golden tests vs independent reference; deterministic output | indicator convention mismatch (Wilder) | M | P0 | 3 |
| 05 | Market structure | swings, HH/HL/LH/LL, BOS, CHoCH, S/R | 04 | machine-testable definitions; no repainting test | subjective definitions | L | P0 | 4 |
| 06 | Market regime | TREND_UP/DOWN, RANGE, HIGH/LOW_VOL, SHOCK, documented rules | 04, 05 | each rule documented and unit-tested | threshold fitting on test data | M | P1 | 4 |
| 07 | Pattern similarity | normalisation; Pearson, Euclid, cosine, DTW, Matrix Profile, kNN; unified interface | 04 | leakage tests (future, overlap, self-match) pass | **look-ahead via overlapping windows** | L | P0 | 5 |
| 08 | Historical outcomes | forward return, MFE, MAE, direction, time-to-target/stop; distribution stats | 07 | UP/DOWN/NEUTRAL stats with percentiles; no contamination of inputs | small samples, regime dependence | M | P0 | 5-6 |
| 09 | Baseline strategies | A (H1 trend + M15 pullback + M5 BOS), B (EMA+RSI+ATR), C (pattern only) | 05, 08 | deterministic signals; documented | overfitting while tuning | M | P1 | 6 |
| 10 | Backtesting | engine, spread/commission/slippage/swap, SL/TP, sizing, metrics, walk-forward | 09 | costs included; reproducible; regression-pinned results | unrealistic fills | L | P0 | 6-7 |
| 11 | ML benchmark | logistic, RF, XGBoost, LightGBM vs baselines, chronological splits | 10 | beats a baseline OOS or is rejected | leakage, instability | L | P1 | 8 |
| 12 | Probability calibration | calibration curves, Brier, log loss, Platt/isotonic | 11 | calibration report per model | overconfidence | M | P1 | 8 |
| 13 | Signal engine | schema, EV after costs, BUY/SELL/WAIT, explanations | 08, 10, 12 | every signal explainable and reproducible; NO TRADE conditions covered | explanations that mislead | M | P1 | 9 |
| 14 | Risk engine | sizing, exposure, drawdown, kill switch, spread/vol/news guards, prop profiles | 10 | independent of forecasting; limits in config not code | stale prop-firm rules | M | P1 | 7-9 |
| 15 | FastAPI | read-only endpoints, no live order endpoints | 13 | contract tests | accidental write endpoints | S | P2 | 10 |
| 16 | Dashboard | Next.js, regime/bias/probabilities/analogue overlay | 15 | 1440x900 + mobile layout | chart misuse implying certainty | L | P2 | 10 |
| 17 | Paper trading | `PaperExecutionBroker`, same signal schema as future live | 13, 14 | simulated SL/TP/spread/slippage/limits | divergence from live fills | M | P2 | 11 |
| 18 | Forward testing | run paper mode live, compare to backtest | 17 | documented out-of-sample comparison | too short a sample to conclude | M | P2 | 11+ |

Auto-execution (phases 12-13) is deliberately not an epic here.

## Sprint 1 (completed 2026-10-08)

Goal: foundation for trustworthy market data.

| Step | Output | Status |
|---|---|---|
| 1 | Dependency review (`docs/research/dependency-review.md`) | done |
| 2 | Project bootstrap: `pyproject.toml`, ruff, mypy strict, pytest, Makefile and `dev.ps1`, `.env.example` | done |
| 3 | Domain models: `Timeframe`, `Instrument`, bar schema, `Bar`, `BarRequest` | done |
| 4 | `BarSource` interface; MT5 adapter (read-only); CSV/Parquet adapter incl. MetaTrader exports | done |
| 5 | Immutable raw store | done |
| 6 | Validators (14 issue codes) | done |
| 7 | Config with live trading hard-disabled | done |
| 8 | Docs: AGENTS.md, architecture, ADRs, this plan, sprint report | done |

## Sprint 2 (completed 2026-10-08)

Goal: make the data layer trustworthy against a real broker feed.

| Step | Output | Status |
|---|---|---|
| 1 | Live MT5 verification on the FTMO **demo** terminal (`scripts/verify_mt5.py`, read-only, demo-only guard); findings in `docs/reports/mt5-verification.md` | done |
| 2 | `BrokerClock` (`NY+7` or IANA), `infer_broker_clock`; ADR-0008 | done |
| 3 | Resampling M5 -> M15/H1/H4 on server-clock boundaries, calendar-aware completeness; derived bars equal the broker's (0 differences on 44,000+ compared bars) | done |
| 4 | `cross_check` of derived vs broker bars | done |
| 5 | `DatasetCatalog`: merge of raw fetches (newest wins), content-hash dataset id, read-only SQL via DuckDB | done |
| 6 | Broker profile loader and `configs/brokers/ftmo_demo.yaml` with measured values | done |
| 7 | Validator fixes found with real data: span-aware closures, closure vs data loss, `check_coverage`; ADR-0007/0009 | done |
| 8 | Python 3.12 and 3.13 tested; CI workflow (ubuntu + windows x 3.12-3.14), actions pinned by SHA | done (CI not yet run on GitHub) |

## Recommended Sprint 3 (Epic 04, features)

1. Indicator interface with golden tests against an independent reference implementation
   (EMA, RSI, ATR, ADX, MACD, Stochastic, Bollinger), pinning Wilder smoothing conventions.
2. Candle geometry, volume z-score, temporal and session features using the broker profile's
   calendar and clock; versioned feature sets keyed by dataset id.
3. Tick/spread cost inputs for the cost model from M5 spread (derived higher-timeframe spread
   does not reproduce the broker's).
4. A holiday/early-close calendar so closures stop appearing as warnings, and a decision on raising
   the terminal's bar limit so a single fetch covers the whole history.
5. Run the CI workflow on GitHub and fix any platform differences.
## Testing strategy

* Unit tests for every pure function; synthetic data only for exercising code paths.
* Mutation spot-checks for critical logic (Sprint 1: 10 hand-made mutants, 4 initially survived;
  Sprint 2: 12 more, all killed on the first full pass after two boundary tests were added).
* Statistical tests (leakage, calibration, walk-forward) arrive with their epics.
* No MT5 test runs in CI (`-m "not mt5"`).

## Success criteria for the MVP

See section 49 of the project brief. After Sprint 2: items 1 (MT5 import, verified on a demo
terminal), 2 (validation), 3 (M5/M15/H1/H4 datasets queryable through `DatasetCatalog`), 11 (no live
trade possible) and part of 12 (critical modules tested) are met. Items 4-10 (features, structure,
patterns, outcomes, backtest, dashboard) are not started.
