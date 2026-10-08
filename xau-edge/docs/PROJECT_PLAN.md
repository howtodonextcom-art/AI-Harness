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
| 04 | Feature engine | returns, EMA, ADX, RSI/MACD/Stoch, ATR/BB, candle geometry, volume, session | 03 | golden tests vs independent reference; deterministic output | indicator convention mismatch (Wilder) | M | P0 | 3-4 |
| 05 | Market structure | swings, HH/HL/LH/LL, BOS, CHoCH, S/R | 04 | machine-testable definitions; no repainting test | subjective definitions | L | P0 | 5 |
| 06 | Market regime | TREND_UP/DOWN, RANGE, HIGH/LOW_VOL, SHOCK, documented rules | 04, 05 | each rule documented and unit-tested | threshold fitting on test data | M | P1 | 5 |
| 07 | Pattern similarity | normalisation; Pearson, Euclid, cosine, DTW, Matrix Profile, kNN; unified interface | 04 | leakage tests (future, overlap, self-match) pass | **look-ahead via overlapping windows** | L | P0 | 6 |
| 08 | Historical outcomes | forward return, MFE, MAE, direction, time-to-target/stop; distribution stats | 07 | UP/DOWN/NEUTRAL stats with percentiles; no contamination of inputs | small samples, regime dependence | M | P0 | 7 |
| 09 | Baseline strategies | A (H1 trend + M15 pullback + M5 BOS), B (EMA+RSI+ATR), C (pattern only) | 05, 08 | deterministic signals; documented | overfitting while tuning | M | P1 | 7 |
| 10 | Backtesting | engine, spread/commission/slippage/swap, SL/TP, sizing, metrics, walk-forward | 09 | costs included; reproducible; regression-pinned results; outputs equity curve, drawdown curve, trade list, monthly, regime and session summaries | unrealistic fills | L | P0 | 8-9 |
| 11 | ML benchmark | logistic, RF, XGBoost, LightGBM vs baselines, chronological splits | 10 | beats a baseline OOS or is rejected; deep learning (LSTM, Transformer, RL) is excluded from the MVP unless benchmark evidence shows a clear need | leakage, instability | L | P1 | 10 |
| 12 | Probability calibration | calibration curves, Brier, log loss, Platt/isotonic | 11 | calibration report per model | overconfidence | M | P1 | 10 |
| 13 | Signal engine | schema, EV after costs, BUY/SELL/WAIT, explanations | 08, 10, 12 | every signal explainable and reproducible; NO TRADE conditions covered | explanations that mislead | M | P1 | 11 |
| 14 | Risk engine | risk per trade, max concurrent trades, max exposure, daily risk budget, consecutive-loss guard, drawdown guard, kill switch, spread/vol/news guards, account-state validation, prop profiles (`configs/prop/`, rules verified against official sources before shipping) | 10 | independent of forecasting; limits in config not code | stale prop-firm rules | M | P1 | 8-9 |
| 15 | FastAPI | read-only endpoints; `POST /paper/orders` arrives with Sprint 13 and only reaches `PaperExecutionBroker`; no live order endpoints | 13 | contract tests; a test proves no route can reach a real broker | accidental write endpoints | S | P2 | 12 |
| 16 | Dashboard | Next.js, regime/bias/probabilities/analogue overlay | 15 | 1440x900 + mobile layout | chart misuse implying certainty | L | P2 | 12 |
| 17 | Paper trading | `PaperExecutionBroker`, same signal schema as future live | 13, 14 | simulated SL/TP/spread/slippage/limits | divergence from live fills | M | P2 | 13 |
| 18 | Forward testing | run paper mode live, compare to backtest | 17 | documented out-of-sample comparison | too short a sample to conclude | M | P2 | 14+ |

| 19 | News risk layer (added 2026-10-08, brief section 27) | economic-calendar interface, high-impact categories, configurable windows 5-60 min, backtest of the window (not assumed); data source chosen with `search-first`, or interface only with the limitation stated | 10, 14 | window backtested; news guard feeds the risk engine | no reliable free calendar data | M | P2 | 8-9 |

Auto-execution (phases 12-13) was deliberately not an epic through Sprint 14. ADR-0019 opens a
separate **demo-only** execution track for operational testing on an MT5 demo account; it does not
authorize live trading or any bypass of the evidence gate. The Sprint column follows the
"Roadmap to a complete application" table, which is authoritative. Gaps against the brief and
proposed epic 19 (news risk) are tracked in `docs/ROADMAP_TRACEABILITY.md`.

## Demo-only execution extension (requires owner gates)

This extension follows `docs/reports/gap-audit.md` and ADR-0019. Each row is a separate owner-gated
work package; do not merge them into one large coding turn.

| Lượt | Scope | Key outputs | Acceptance | Must not do |
|---|---|---|---|---|
| 1 | Safety alignment and design lock | ADR-0019, `AGENTS.md`, `.env.example`, this plan, repo-aware gap audit updates, safe demo settings | Existing tests pass; demo disabled by default; dry-run default; no broker APIs added | No broker adapter, no `order_send`, no write API route |
| 2 | Persistent state and signal bridge | state store, persistent kill switch, order intent, idempotency, signal-to-order bridge reusing risk/safety/evidence | restart keeps kill switch/idempotency; corrupt state fails closed; `WAIT`/risk/safety/evidence refusals never reach a broker | No MT5 real send |
| 3 | Demo broker adapter, reconciliation and runner | `src/xau_edge/brokers/mt5_demo/`, fake MT5 tests, reconciliation, M15 runner dry-run, CLI kill switch | broker APIs appear only in demo broker package; unknown order state trips kill switch; dry-run runner works | No arbitrary order API, no live account |
| 4 | Web app observability | read-only bot status API, dashboard panels, journal/reconciliation/status views | dashboard build passes; no UI for arbitrary trade params; write routes unchanged unless a new ADR/auth/test set is accepted | No unauthenticated kill-switch route |

Required deferred or parallel work before calling the bot "operationally complete": news data source
and news-window study, measured demo costs/slippage, alerting/heartbeat, chaos tests, FTMO automation
rule verification, and forward runtime evidence. Without real demo/manual evidence, report the system
as dry-run/fake-tested only.

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
| 8 | Python 3.12 and 3.13 tested; CI workflow (ubuntu + windows x 3.12-3.14), actions pinned by SHA | done (CI passed 6/6 jobs on GitHub for the Sprint 2 commit) |

## ECC delivery loop (applies to every epic from Sprint 3)

Derived from ECC's `rules/common/development-workflow.md` and the `orch-*` pipeline. Each step
names the ECC component that performs it; "gate" means work stops until the owner approves.

| Step | What | ECC component | Evidence required |
|---|---|---|---|
| E0 Research & reuse | search existing libraries/code before writing | `search-first`, `documentation-lookup` | short note in the plan; licence check (ADR-0006) |
| E1 Plan | requirements, files, order, risks, success criteria | `/plan` (agent `planner`; `architect` for structural choices) | plan section in this file |
| **Gate A** | **owner approves the plan** | - | explicit "OK" |
| E2 Tests first | failing tests that encode the acceptance criteria | `tdd-workflow` (agent `tdd-guide`) | RED output saved in the report |
| E3 Implement | smallest change to GREEN, then refactor | `tdd-workflow` | tests pass |
| E4 Review | fresh-context reviews before any commit | `/code-review` (`code-reviewer`), `/python-review` (`python-reviewer`), `security-reviewer` when a security trigger applies | findings list with file:line; CRITICAL/HIGH fixed |
| E5 Verify | build, types, lint, tests >= 80% (target 95%+ for data/risk code), secret grep, diff review; mutation spot-check; red-team | `verification-loop` | `scripts/dev.ps1 check` output, mutants killed |
| **Gate B** | **owner confirms the commit** | - | explicit "OK" |
| E6 Commit | author/committer `howtodonext.com`, straight to `main` | - | pushed SHA |
| E7 Record | ADR for decisions, sprint report, handoff | `architecture-decision-records`, `unified-memory` (`ecc memory`) | files committed |

Extra gates by epic type: results that claim an *edge* (backtest, ML) need `santa-method` (two
independent reviewers with one rubric, both must pass) and `eval-harness` evals defined before
the experiment; ambiguous design choices use `council`; anything touching signals, risk or
execution needs `security-reviewer` and a fail-safe default of WAIT. Live execution is not part of
this roadmap.

## Roadmap to a complete application

Sizes: S <= 2 days, M 3-5 days, L 1-2 weeks of focused work. Each row is one sprint unless noted.

| Sprint | Epic(s) | ECC focus | Acceptance (measurable) | Main risk | Size |
|---|---|---|---|---|---|
| 3 | Housekeeping from the ECC audit; 04 Feature engine (part 1) | planner, tdd-guide, python-reviewer | audit findings fixed; indicators match an independent reference within stated tolerance (EMA, RSI, ATR, ADX, MACD, Stochastic, Bollinger) | Wilder smoothing conventions | M |
| 4 (**done**) | 04 (part 2: candle geometry, volume, sessions; holiday calendar moved to Sprint 8) | tdd-guide, code-reviewer | versioned feature set keyed by dataset id; same input gives byte-identical output; no feature uses data after its bar closes | feature leakage | M |
| 5 (**done**) | 05 Market structure; 06 Regime | planner, council (rule definitions), tdd-guide | swing/BOS/CHoCH rules documented and unit-tested; repainting test: appending future bars never changes past labels | subjective definitions | L |
| 6 (**done**) | 07 Pattern similarity | architect, tdd-guide, **statistical leakage tests written first**, code-reviewer | no overlap or self-match across train/outcome windows (tests prove it); unified interface for Pearson, Euclid, cosine, DTW, Matrix Profile, kNN; benchmark vs plain NumPy search | look-ahead through overlapping windows | L |
| 7 (**done**) | 08 Historical outcomes; 09 Baseline strategies; experiment registry (brief section 39) | tdd-guide, eval-harness (define evals first) | UP/DOWN/NEUTRAL stats with distributions; three deterministic baselines; no tuning on the test period | small samples, regime dependence | M |
| 8 (**done**) | 14 Risk engine (core, prop profiles); 10 Backtest engine (part 1: costs, fills, sizing); 19 News risk (interface) | architect, security-reviewer, tdd-guide | spread/commission/slippage/swap modelled from measured M5 spread and the broker profile; risk limits live in config, never in code; kill switch tested | unrealistic fills, stale limits | L |
| 9 (**done**) | 10 Backtest (part 2: metrics, walk-forward, regime/session breakdown) | eval-harness, santa-method | reproducible results with pinned dataset id; every required metric in the brief; regression-pinned run | overfitting, multiple testing | L |
| **Checkpoint 1 (done: no baseline shows an edge; see docs/reports/checkpoint-1.md)** | After sprint 9: do the baselines show an edge after costs, out of sample? | council + santa-method | written decision: continue to ML, or stop and conclude "no statistically justified trade" | wishful reading of results | - |
| 10 (**done**) | 11 ML benchmark; 12 Calibration | mle-reviewer, eval-harness, tdd-guide | each model beats a baseline out of sample, else rejected; Brier/log-loss/calibration curves reported | leakage, instability | L |
| 11 (**done**) | 13 Signal engine | code-reviewer, security-reviewer, santa-method | every signal explainable and reproducible; all NO TRADE conditions covered; EV computed after costs | misleading explanations | M |
| 12 (**done**) | 15 FastAPI (read-only); 16 Dashboard | api-design, e2e-runner, browser-qa | no write/order endpoints (test enforces); 1440x900 and mobile layouts; analogue overlay never feeds model inputs | UI implying certainty | L |
| 13 (**done**) | 17 Paper trading; `POST /paper/orders` | tdd-guide, security-reviewer | `PaperExecutionBroker` uses the same signal schema as any future broker; SL/TP/spread/slippage/limits simulated; the paper endpoint cannot reach a live broker (test) | divergence from live fills | M |
| 14+ (**tooling done; evidence collection pending**) | 18 Forward testing (calendar-time bound, weeks) | eval-harness, santa-method | documented out-of-sample comparison against backtest; no claims without a sufficient sample | too short a sample | - |

Critical path: 04 -> 05 -> 07 -> 08 -> 09 -> 10 -> checkpoint -> (11, 12) -> 13 -> 17 -> 18.
The checkpoint is a real fork: if no baseline survives costs out of sample, the correct outcome
is to stop building predictors and report that, consistent with the brief's principle.

### Sprint 3 scope (steps 1-3 done in 270e484; roadmap debt and step 4 in the commit that follows)

Order matters: remediation first, features second. See `docs/ECC_ALIGNMENT_AUDIT.md` for the
finding IDs.

1. Install the missing ECC workflow components (dry-run first, `--no-hooks`): 8 skills for the
   workflow and the `security` capability (21 files).
2. Fix, test-first, in this order: F-01 (HIGH: cap on closure length), F-02 (settings guard),
   F-03 (DEMO guard inside `Mt5BarSource`), F-04 (allowlist proxy for the MT5 module),
   F-05 (drop forming bar in the adapter), F-06 (verify content in `DatasetCatalog.load`),
   F-07 (`.gitignore`), F-08 and F-09 (`cross_check`), V-01 (version bump), V-02 (sdist excludes
   `.claude`, data, `.env.example`); then the remaining MEDIUM and LOW items.
3. Run `code-reviewer`, `python-reviewer` and `security-reviewer` again on the fixes (Gate B).
4. Epic 04 part 1: `features/indicators.py` (EMA, SMA, RSI, ATR, ADX, MACD, Stochastic, Bollinger,
   simple/log/rolling returns, rolling volatility) as pure NumPy functions; golden tests against
   recorded TA-Lib output; repainting, validation and property tests. ADR-0010.
5. Roadmap debt from `docs/ROADMAP_TRACEABILITY.md` that was due now: structured logging
   (`observability.py`, G-1), brief copy (`docs/BRIEF.md`), `data-flow.md` and `testing-strategy.md`
   (G-5), `tests/regression` and `tests/statistical` (G-6), `.pre-commit-config.yaml` config only (G-8).

**Sprint closing criteria (added 2026-10-08, brief sections 26 and 52).** Every sprint report must
contain a written red-team section ("how could this be wrong?", each item with a status) and, for
any result that claims an edge, the overfitting checklist in `docs/testing/testing-strategy.md`.
## Run-ladder: when does the system "run for real"?

Full detail and the brief-to-plan matrix: `docs/ROADMAP_TRACEABILITY.md`. No level involves real money.

| Level | Meaning | Exit evidence | Sprint |
|---|---|---|---|
| L0 | Foundation | CI green | 1 (done) |
| L1 | Trustworthy real data | demo MT5 import, validation, dataset id | 2 (done) - **current** |
| L2 | Offline research on real data | features, structure, regime, patterns, outcomes; leakage tests pass | 3-7 |
| L3 | Costed backtest | reproducible report, walk-forward; **Checkpoint** (edge after costs, out of sample?) | 8-9 |
| L4a | Offline signals | ML + calibration + signal engine + API/dashboard | 10-12 |
| L4b | Paper trading | `PaperExecutionBroker` on live demo data | 13 |
| L4c | Forward test | weeks of paper vs backtest | 14+ |
| L5 | Live trading | out of scope; needs a separate decision | - |

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
