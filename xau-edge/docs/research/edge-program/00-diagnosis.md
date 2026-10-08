# Edge Program Phase 0 Diagnosis

Date: 2026-10-08. Scope: read-only repository/data analysis. No MT5 fetch, no order
submission, no change to `docs/evals/edge-criteria.md`, and no test-period run.

Inputs inspected:

- `docs/evals/edge-criteria.md`
- `docs/reports/checkpoint-1.md`
- `docs/reports/final-status.md`
- `CLAUDE.md`
- `experiments/runs/*.json`
- `data/backtests/trades_baseline_{a,b,c}_{development,validation}.parquet`
- local `data/raw/XAUUSD/{M5,M15,H1,H4}` through `DatasetCatalog`
- `src/xau_edge/{strategies,backtest,evaluation,experiments,signals}`

## 1. Statistical Power

Current strategy family variant count from `ExperimentRegistry.variant_count("backtest")`: **K = 3**.
So the current Bonferroni alpha is `0.05 / 3 = 0.0167`.

The table below estimates the minimum detectable mean net R per trade using the observed trade
standard deviation and an optimistic i.i.d. one-sided lower-bound approximation:

`MDE = z(1 - alpha) * sd(net_R) / sqrt(n)`.

The actual criterion uses day-block bootstrap and six additional edge criteria, so these MDEs are a
best-case lower bound, not a guarantee.

| Strategy | Period | Trades | Mean R | sd(R) | MDE at K=3 | MDE at K=6 | MDE at K=10 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline A | Development | 135 | -0.135 | 1.371 | +0.251R | +0.283R | +0.304R |
| Baseline A | Validation | 63 | -0.099 | 1.358 | +0.364R | +0.410R | +0.441R |
| Baseline B | Development | 782 | +0.009 | 1.398 | +0.106R | +0.120R | +0.129R |
| Baseline B | Validation | 395 | -0.104 | 1.381 | +0.148R | +0.166R | +0.179R |
| Baseline C | Development | 799 | -0.105 | 1.260 | +0.095R | +0.107R | +0.115R |
| Baseline C | Validation | 413 | +0.027 | 1.285 | +0.135R | +0.151R | +0.163R |

Trade-frequency extrapolation from Validation:

| Strategy | Validation trades | Trades / 30 days | Estimated Test trades | Diagnosis |
|---|---:|---:|---:|---|
| Baseline A | 63 | 15.8 | 84.0 | Fails the 100-trade criterion structurally on 4-month Val and likely 5-month Test |
| Baseline B | 395 | 98.8 | 526.7 | Enough sample size, but observed mean is negative on Val |
| Baseline C | 413 | 103.2 | 550.7 | Enough sample size, but edge signal is unstable and weak |

Answer to the practical edge question:

- A realistic intraday XAU edge of **+0.05R/trade** is not detectable in this setup.
- **+0.10R/trade** is detectable only in the best/high-frequency Development cases; it is not
  enough for Validation at K=3 except maybe under assumptions more favorable than the bootstrap.
- **+0.15R/trade** is roughly the lower edge of detectability for Baseline B/C on Validation at K=3,
  and becomes insufficient once K rises to 6-10.
- Low-frequency hypotheses like Baseline A need either a longer validation period, a different
  pre-registered criterion, or must be rejected before consuming Test because criterion 1 blocks them.

## 2. Costs

M5 spread distribution by session, measured from local FTMO demo M5 bars:

| Session | Bars | Median spread | p90 spread | p95 spread |
|---|---:|---:|---:|---:|
| ASIA | 32,628 | 31 pts | 52 pts | 59 pts |
| LONDON | 22,139 | 27 pts | 47 pts | 55 pts |
| LONDON_NY_OVERLAP | 18,111 | 29 pts | 51 pts | 57 pts |
| NEW_YORK | 20,912 | 31 pts | 49 pts | 55 pts |
| OFF_HOURS | 7,499 | 37 pts | 55 pts | 60 pts |

Worst UTC hours by median spread:

| UTC hour | Median spread | p90 spread | Note |
|---:|---:|---:|---|
| 22 | 43 pts | 56 pts | worst hour in local dataset |
| 20 | 36 pts | 55 pts | off-hours / rollover-adjacent risk |
| 23 | 35 pts | 53 pts | off-hours |
| 00-01 | 32 pts | 53-54 pts | Asia early |

Cost/ATR by timeframe, using spread price (`spread_points * 0.01`) divided by ATR(14):

| Timeframe | Median spread/ATR | p75 | p90 | p95 | Median spread |
|---|---:|---:|---:|---:|---:|
| M5 | 7.83% | 10.51% | 13.72% | 16.25% | 31 pts |
| M15 | 4.25% | 5.49% | 6.80% | 7.79% | 29 pts |
| H1 | 2.02% | 2.45% | 2.86% | 3.12% | 27 pts |
| H4 | 0.99% | 1.14% | 1.32% | 1.42% | 26 pts |

Diagnosis:

- M5 is structurally expensive for small-edge intraday strategies: spread alone consumes about
  8-16% of ATR before slippage.
- M15 is materially better but still cost-sensitive.
- H1/H4 are far more cost-efficient, but will likely produce fewer trades and can collide with the
  current 100-trade criterion.
- London hours have the lowest observed median spread; off-hours and UTC 22 are the worst.

## 3. Data Availability

Local `DatasetCatalog` availability:

| Timeframe | Rows | First bar UTC | Last bar UTC | Dataset id |
|---|---:|---|---|---|
| M5 | 101,289 | 2025-05-01 00:00 | 2026-10-08 13:10 | `9a14966ad702d9c9` |
| M15 | 34,127 | 2025-05-01 00:00 | 2026-10-08 13:00 | `c0556aabc439f3d4` |
| H1 | 8,536 | 2025-05-01 00:00 | 2026-10-08 12:00 | `a05ff65eccdb5d84` |
| H4 | 2,232 | 2025-05-01 01:00 | 2026-10-08 09:00 | `7399bc77ab845d5f` |

Raw file counts under `data/raw/XAUUSD`: M5 = 14, M15 = 12, H1 = 6, H4 = 5. These include the
original research range and later demo-bot refresh slices.

Diagnosis:

- The local bar dataset starts on 2025-05-01. That is enough to reproduce the current Dev/Val/Test
  design but is short for detecting modest edge sizes, regime dependence and rare event effects.
- No local D1 folder exists under `data/raw/XAUUSD`; D1 is not part of the implemented MVP dataset.
- No tick data was found locally.
- No second-broker dataset was found locally.
- MT5 read-only history depth beyond the local files was not fetched because Phase 0 forbids MT5
  access until owner approval.

## 4. Strategy Design Diagnosis

Current baselines:

| Strategy | Mechanism actually tested | Economic/market microstructure basis |
|---|---|---|
| A | H1 structure trend + M15 RSI pullback + M5 BOS/CHoCH | Mostly technical trend-following; weak direct XAU-specific economic mechanism |
| B | EMA stack + RSI momentum band | Generic indicator momentum; no explicit gold/USD event/session mechanism |
| C | Historical pattern similarity on M15 | Statistical analogue hypothesis; no causal economic mechanism and probabilities are uncalibrated frequencies |

Untried XAUUSD effects with stronger economic rationale:

| Candidate effect | Rationale | Constraints |
|---|---|---|
| London open / London morning volatility expansion | Liquidity and European macro flow can reprice gold/USD | Needs session-specific rules and cost check; avoid overfitting hour windows |
| New York open / COMEX cash-session behavior | US liquidity and USD/rates reaction often dominate gold intraday | News contamination must be modelled |
| London PM fix / benchmark flow window | Gold-specific benchmark-flow hypothesis | Requires exact fix-time treatment and enough samples |
| High-impact USD news windows | CPI, NFP, FOMC, Fed speakers can dominate XAUUSD | Requires reliable calendar with `available_at`; current absence blocks signals |
| Daily momentum / mean reversion after large prior-day move | Gold can trend on rates shocks or mean-revert after exhaustion | H1/H4/D1 data or longer history needed; trade count may be low |
| Volatility-regime filter | Same signal may work only in non-shock / expanding volatility regimes | Must be pre-registered; avoid selecting after seeing Val |
| Asia range -> London/NY breakout or fade | Session microstructure hypothesis | Needs rules fixed before Val; M5 costs may dominate |
| Rollover/off-hours avoidance | Costs widen materially in off-hours | Mainly a filter; may reduce trades below criterion 1 |

## 5. Infrastructure Barriers

| Barrier | Evidence | Impact |
|---|---|---|
| Signal engine is bound to Baseline C | `signals/engine.py` defines `EVIDENCE_FAMILY = "backtest"` and `evidence_params()` returns `strategy_params("baseline_c")` | A new validated strategy cannot drive BUY/SELL without code/registry refactor |
| Evidence gate requires exact params and all three periods | `signals/evidence.py` requires development, validation and test, same dataset ids, clean code, and pass status | Correct safety behavior, but Phase 5 needs strategy registry and authorization ADR |
| Experiment registry counts variants by params only | `experiments/registry.py` supports variant count by family | Good enough for current baselines, but new hypotheses need explicit ledger/K management |
| Test period is programmatically locked | `scripts/run_backtest.py` requires `--allow-test` and passed Dev/Val records | Good; must keep intact |
| News guard blocks when no calendar exists | `signals/decision.py` emits `NEWS_UNKNOWN` when `news_blocked is None` | Correct fail-closed behavior; needs calendar data before operational signals |

## 6. Criteria Diagnosis

| Criterion | Structural issue? | Evidence |
|---|---|---|
| At least 100 trades per period | Yes for low-frequency strategies | Baseline A has 63 trades on Validation and estimated 84 on Test at the same frequency |
| CI lower bound > 0 at `1 - 0.05/K` | Structurally hard for modest edges | For Baseline B/C Validation, MDE is about +0.135R to +0.148R at K=3; with K=10 this rises to +0.163R to +0.179R |
| PF >= 1.2 | Quality barrier | All baselines are below 1.2; not merely structural |
| Max DD <= 15R | Mixed | Baseline B/C drawdown failures are quality/risk problems; lower-frequency strategies may pass but fail trade count |
| 3/4 positive folds | Quality/stability barrier | Designed to reject sign-flipping noise; current B/C flip sign between periods |
| Remove best 5% still mean > 0 | Quality/robustness barrier | Appropriate but harder for low-N strategies |
| No regime/session supplies >60% profit | Structural if a hypothesis is intentionally session-specific | A London/NY/fix hypothesis may conflict with this unless it is reframed as "not concentrated within the traded session/regime"; report only, do not change without gate |

## 7. Barrier Table

| Rào cản | Bằng chứng | Loại | Có thể gỡ không | Cách gỡ hợp lệ |
|---|---|---|---|---|
| Modest edge not detectable on current Validation at planned K | MDE +0.135R to +0.148R for B/C at K=3; +0.151R to +0.179R at K=6-10 | tiêu chí / dữ liệu | Có, nhưng only before new results | Increase data length/splits for new data, reduce hypothesis budget, or pre-register criteria amendment at Gate 1 |
| Low-frequency strategies fail 100-trade rule | Baseline A Validation = 63 trades, estimated Test = 84 | tiêu chí | Có, but must pre-register | Reject low-frequency hypotheses, extend data, or amend criterion before new experiments |
| M5 costs are high | M5 median spread/ATR 7.83%, p95 16.25% | chi phí | Có | Prefer M15/H1/H4, London session, avoid off-hours/UTC 22, measure slippage/commission |
| Existing baselines are generic technical rules | A/B generic trend/indicator; C analogue statistical only | thiết kế | Có | Pre-register XAU-specific economic hypotheses: session/news/fix/vol regime |
| No news data | final-status and local env/docs; `NEWS_UNKNOWN` fail-closed | dữ liệu | Có | Add reliable calendar with coverage and `available_at`, then pre-register news-window study |
| Short single-broker sample | 2025-05-01 to 2026-10-08, one FTMO demo source | dữ liệu | Có | Add longer history, tick data, second broker; define new splits before seeing results |
| No tick data | no local tick files; only OHLCV bars | dữ liệu | Có | Add tick source or MT5 ticks only after owner approval |
| No second broker | no local second-broker dataset | dữ liệu | Có | Import second broker CSV/Parquet and predefine cross-broker validation |
| Signal engine hard-bound to Baseline C | `signals/engine.py` lines around `evidence_params()` | hạ tầng | Có | Strategy registry + strategy_id/config hash/dataset hash evidence gate (Phase 1) |
| Evidence gate requires Test pass | `signals/evidence.py` requires all periods | hạ tầng / tiêu chí | Keep | Correct protection; integrate only after strict PASS |
| Session-concentration criterion may conflict with session-specific hypotheses | criterion 7 max 60% profit by session/regime | tiêu chí | Có, but only Gate 1 | Clarify criterion for intentionally session-scoped strategies before results |

## 8. Gate 1 Recommendations (do not execute without owner approval)

1. Hypothesis budget: choose **N = 6** initially. This keeps K lower than 10 and preserves some power.
   At K=6, B/C Validation MDE is already about +0.151R to +0.166R. K=10 pushes it to +0.163R to
   +0.179R, making +0.10R strategies unlikely to pass.
2. Data expansion: recommended before Phase 2 if the owner wants realistic discovery odds.
   Minimum useful additions: news calendar with `available_at`, slippage/commission measurement,
   and either longer history or second-broker data. Tick data is useful for execution/cost but not
   mandatory for first hypothesis registration.
3. Splits: if adding materially new historical data, define new splits for that new corpus before
   looking at outcomes. Keep the current Test period as a locked holdout unless the owner explicitly
   adopts a new data program and records why.
4. Criteria amendment candidates to decide before any new result:
   - Whether low-frequency, H1/H4 strategies may use a longer validation/test window instead of the
     100-trade rule on 4-month Validation.
   - How criterion 7 applies to intentionally session-scoped hypotheses.
   - Whether K counts every parameter-cell or every economic hypothesis plus parameter-cell; the
     conservative answer is every run/config variant.
5. Stop rule for state (B): recommended stop after N registered hypotheses or K cumulative variants
   reaches the approved cap, whichever comes first, unless new data is acquired and a new program is
   approved.

Phase 1 should not begin until the owner approves these Gate 1 choices.
