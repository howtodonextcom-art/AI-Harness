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
| 02 | MT5 data connector | `BarSource` interface, MT5 adapter, offline file adapter | 01 | offline path works; MT5 path unit-tested with fake client | **broker time handling unverified live** | M | P0 | 1 (adapters), **2 (live verification)** |
| 03 | Market-data validation | duplicate/order/gap/OHLC/volume/spread/tz/weekend checks; raw store | 02 | every check has a failing-input test; raw data immutable | market-calendar assumptions per broker | M | P0 | 1 (done), 2 (resample + cross-TF checks) |
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

## Recommended Sprint 2

1. **Verify MT5 on a demo account** (owner: needs terminal): script that pulls a week of M5
   XAUUSD, determines the broker timezone empirically (compare to known session opens and DST
   transitions), and records it in config. Until this passes, MT5 data is untrusted.
2. Resampling M5 -> M15/H1/H4 with the same alignment rules as the broker, plus cross-timeframe
   consistency checks (a derived H1 must equal the broker's H1 within tolerance).
3. Dataset catalog: DuckDB over Parquet (`DatasetCatalog.query`), dataset versioning by content hash.
4. Real-data validation report on a real XAUUSD export (all Sprint 1 validators were tested on
   synthetic data only).
5. Confirm broker market hours against real data (default is 17:00 New York, ADR-0007; holidays
   are not modelled) and set `MarketCalendar` accordingly; add Python 3.12/3.13 to CI.

## Testing strategy

* Unit tests for every pure function; synthetic data only for exercising code paths.
* Mutation spot-checks for critical logic (Sprint 1: 10 hand-made mutants; 4 initially
  survived, tests were strengthened, and all 10 are now killed).
* Statistical tests (leakage, calibration, walk-forward) arrive with their epics.
* No MT5 test runs in CI (`-m "not mt5"`).

## Success criteria for the MVP

See section 49 of the project brief. Sprint 1 satisfies items 2 (validation), 11 (no live
trade possible) and part of 12 (critical modules tested); items 1 and 3 are only
partially met (MT5 import untested live; querying arrives in Sprint 2).
