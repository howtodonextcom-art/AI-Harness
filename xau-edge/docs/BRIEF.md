# XAU EDGE - original project brief (condensed copy kept for traceability)

Source: the owner's original request. Section numbers are the brief's own and are referenced by `ROADMAP_TRACEABILITY.md`. Text is condensed in places; the owner's conversation remains the authority.

PROJECT TITLE: XAU EDGE - Probabilistic Decision Support & Research Platform for XAUUSD
PROJECT TYPE: AI-Assisted Quantitative Trading Research Platform
PRIMARY TARGET: XAUUSD / Gold Spot CFD. TARGET PLATFORM: MetaTrader 5.
INITIAL TRADING ENVIRONMENT: FTMO Demo / Research Environment
CURRENT PRIORITY: Research + Backtesting + Signal Decision Support
DO NOT enable autonomous live trading in the initial implementation.

## 0. YOUR ROLE
Lead AI Coding Agent acting simultaneously as: Principal Software Architect, Senior Python Engineer, Quantitative Developer, Time-Series Researcher, Machine Learning Engineer, MetaTrader 5 Integration Engineer, Backend Engineer, Frontend Engineer, QA Engineer, Security Reviewer, Trading Risk Engineer, DevOps Engineer, Technical Documentation Writer.
Responsible for: RESEARCH -> ARCHITECTURE -> IMPLEMENTATION -> TESTING -> VALIDATION -> DOCUMENTATION -> DELIVERY.

## 1. PROJECT MISSION
Build an explainable probabilistic decision-support system for XAUUSD. The system must answer, given the current XAUUSD market state:
1. What is the current market regime?
2. What is the higher-timeframe directional bias?
3. Are there historical market structures similar to the current structure?
4. What happened after those historical analogues?
5. What is the estimated probability of: price moving up; price moving down; price remaining neutral?
6. What is the expected move?
7. Is there sufficient statistical edge after transaction costs?
8. Should the system recommend: BUY / SELL / WAIT
The system must treat WAIT / NO TRADE as a fully valid output.
The project must NOT be designed as "AI predicts gold price." It must be designed as a Probabilistic Market Decision Support System.

## 2. FUNDAMENTAL DESIGN PRINCIPLE
Strictly separate FORECASTING from TRADING DECISION.
Architecture: Market Data -> Feature Extraction -> Historical Pattern Analysis -> Forecast Model -> Probability Calibration -> Expected Value -> Market Context -> Entry Quality -> Risk Engine -> Trade Decision.
Never implement Prediction -> Automatic Order without the intermediate validation layers.

## 3. PROJECT PHASES (incremental; the AI coding agent MUST NOT skip phases)
PHASE 0 Research & Technical Due Diligence
PHASE 1 Market Data Platform
PHASE 2 Feature Engine
PHASE 3 Market Structure Engine
PHASE 4 Historical Pattern Similarity Engine
PHASE 5 Outcome Statistics Engine
PHASE 6 Rule-Based Signal Engine
PHASE 7 Backtesting Framework
PHASE 8 Machine Learning Benchmark
PHASE 9 Probabilistic Signal Engine
PHASE 10 Dashboard
PHASE 11 Paper Trading
PHASE 12 Semi-Automatic Trading
PHASE 13 Controlled Automated Execution

## 4. QUALITY-GATE POLICY
Each phase requires an acceptance gate. A later phase may begin only when the previous phase: builds successfully; passes automated tests; produces reproducible output; has no critical defects; has documentation; satisfies the acceptance criteria. If a gate fails, do not hide it: report failure, likely cause, affected components, recommended fix, whether development should continue.

## 5. RESEARCH BEFORE CODING
Before implementing major components, inspect current open-source projects and official documentation. Research at minimum: MetaTrader 5 Python API, TA-Lib, STUMPY, tslearn, vectorbt, backtesting.py, scikit-learn, XGBoost, LightGBM, DuckDB, Polars, PyArrow/Parquet, FastAPI, Next.js, TradingView Lightweight Charts, QuantConnect LEAN, FinRL, Freqtrade. Do not blindly fork. For each candidate determine: role; license; maintenance status; last meaningful update; maturity; performance; API stability; security concerns; adopt / wrap / avoid. Produce docs/research/dependency-review.md.

## 6. HIGH-LEVEL SYSTEM ARCHITECTURE
MetaTrader 5 -> Market Data Layer -> (M5, M15, H1/H4) -> Feature Engine -> (Technical Indicators, Market Structure Engine, Session/Regime Engine) -> Pattern Similarity Engine (Matrix Profile, DTW) -> Outcome Engine -> ML Predictor -> Probability Calibration -> Signal Engine -> Risk Engine -> BUY / WAIT / SELL.

## 7. REPOSITORY ARCHITECTURE
xau-edge/ with: apps/{api,dashboard}; packages/{core,config,shared}; data/{raw,processed,features,patterns,backtests}; src/{market_data/{mt5,importers,validators,resampling}, features/{indicators,candles,volatility,sessions,temporal}, structure/{swings,trend,bos,choch,support_resistance}, patterns/{normalization,matrix_profile,dtw,nearest_neighbors,outcomes}, regimes/{trend,volatility,sessions}, models/{baseline,logistic,random_forest,xgboost,lightgbm,calibration}, signals/{forecast.py,probability.py,expected_value.py,decision.py}, risk/{position_sizing.py,exposure.py,drawdown.py,prop_rules.py,kill_switch.py}, backtest/{engine,execution,costs,metrics,walk_forward}, paper/, execution/{interface,mt5,safety}, news/}; notebooks/; tests/{unit,integration,regression,statistical}; configs/; scripts/; docs/{architecture,research,decisions,operations}; .env.example; pyproject.toml; README.md; CHANGELOG.md; AGENTS.md.

## 8. TECHNOLOGY STACK
Backend/Quant: Python 3.12+; numpy; pandas or polars; scipy; scikit-learn; xgboost; lightgbm; TA-Lib; STUMPY; tslearn; vectorbt; pydantic; FastAPI; DuckDB; PyArrow. Storage: Parquet; query engine DuckDB; do not introduce PostgreSQL unless justified. Frontend: Next.js; TypeScript strict; Tailwind CSS; charting TradingView Lightweight Charts. API: FastAPI. Testing: pytest. Static quality: ruff; mypy. Optional: pre-commit. Containerization: Docker where useful. Do not over-engineer infrastructure during MVP.

## 9. MARKET DATA REQUIREMENTS
Instrument XAUUSD; timeframes M5, M15, H1, H4. Fields: timestamp, open, high, low, close, tick_volume, spread, real_volume if available. Ingestion supports MetaTrader 5 and offline CSV/Parquet import. Raw market data MUST be immutable (data/raw/); never modify source data in place. Deterministic pipelines: RAW -> CLEAN -> RESAMPLED -> FEATURES.

## 10. DATA VALIDATION
Validators for: duplicate timestamps; missing bars; incorrect OHLC relationships; negative volume; invalid spread; timezone issues; weekend anomalies; out-of-order timestamps. OHLC rule: low <= open <= high; low <= close <= high. Validation results must be logged.

## 11. FEATURE ENGINE
PRICE: returns, log returns, rolling returns. TREND: EMA 9/20/50/200, ADX. MOMENTUM: RSI, MACD, Stochastic. VOLATILITY: ATR, Bollinger Bands, rolling volatility, range/ATR. CANDLE GEOMETRY: body_size, upper_wick, lower_wick, body/range, body/ATR, wick/ATR. VOLUME: tick_volume, volume_zscore, volume_change. TEMPORAL: hour, day_of_week, trading_session (ASIA, LONDON, NEW_YORK, LONDON_NY_OVERLAP). Only include features that can be objectively calculated.

## 12. MARKET STRUCTURE ENGINE
Deterministic detection of: swing highs, swing lows, higher high, higher low, lower high, lower low, trend state, Break of Structure, Change of Character, support, resistance. Avoid subjective Smart Money Concepts unless definitions are explicit. All structural rules machine-testable and backtestable.

## 13. MARKET REGIME ENGINE
States: TREND_UP, TREND_DOWN, RANGE, HIGH_VOLATILITY, LOW_VOLATILITY, SHOCK. Avoid hidden hand-crafted labels. Document each classification rule.

## 14. PATTERN SIMILARITY ENGINE (core innovation)
Given the current N-bar XAUUSD sequence, find historically similar sequences. Window sizes 20, 30, 50, 100 bars. Do NOT compare absolute prices; normalize. Representations: returns, ATR-normalized returns, candle body/ATR, range/ATR, upper wick/ATR, lower wick/ATR, volume z-score. Implement and benchmark: Pearson correlation; Euclidean distance; cosine similarity; Dynamic Time Warping; Matrix Profile; K-nearest-neighbor search. Each method exposes a unified interface.

## 15. PATTERN MATCHING SAFETY
Strictly prevent future leakage. The comparison window must end BEFORE the outcome window begins. Do not allow overlapping pattern/outcome leakage. Add tests detecting: future leakage; look-ahead bias; self-match contamination.

## 16. HISTORICAL OUTCOME ENGINE
For each matched historical pattern calculate outcomes after 5, 10, 20, 30, 60 bars. Metrics: forward return; maximum favorable excursion (MFE); maximum adverse excursion (MAE); direction; time-to-target; time-to-stop. Classification UP / DOWN / NEUTRAL (neutral threshold configurable). Do not stop at percentages: calculate expected return, median return, distribution, percentiles, expected R.

## 17. BASELINE STRATEGIES
Before ML build transparent baselines. Baseline A: H1 trend + M15 pullback + M5 break of structure. Baseline B: EMA trend + RSI + ATR stop. Baseline C: historical pattern similarity only. Every ML model must beat at least one meaningful baseline out-of-sample to justify additional complexity.

## 18. MACHINE LEARNING ROADMAP
Order: 1 Logistic Regression; 2 Random Forest; 3 XGBoost; 4 LightGBM; only after these 5 temporal deep-learning models. Do NOT implement LSTM, Transformer, Reinforcement Learning during MVP unless benchmark evidence demonstrates a clear need. Targets: P(up), P(down), P(neutral) or future_return distribution.

## 19. TIME-SERIES VALIDATION
NEVER randomly shuffle financial time-series data. Required: chronological train/validation/test and walk-forward analysis (e.g. train 2021-2023, validate 2024, test 2025, then roll forward). No model may be considered successful based only on in-sample performance.

## 20. PROBABILITY CALIBRATION
A model producing 0.70 must be statistically evaluated for calibration. Implement calibration curves, Brier Score, Log Loss. Methods: Platt scaling, Isotonic Regression. Do not expose arbitrary "confidence percentages."

## 21. SIGNAL ENGINE
Returns BUY / SELL / WAIT. Signal schema: symbol, timestamp, timeframe, direction, prob_up, prob_down, prob_neutral, expected_return, expected_R, market_regime, higher_timeframe_bias, entry_zone, stop_loss, take_profit_1, take_profit_2, risk_reward, signal_expiry, explanation, historical_matches_count, similarity_quality. Must support NO TRADE when: probability edge insufficient; expected value <= threshold; risk/reward poor; market regime unsupported; news risk excessive; spread excessive; data invalid; model uncertainty excessive.

## 22. SIGNAL EXPLAINABILITY
Every signal must be explainable (e.g. SELL: H1 trend bearish, M15 lower high, M5 BOS down, pattern similarity bearish, historical analogue 63% DOWN, expected return negative, ATR expanding). Do not output unexplained signals.

## 23. EXPECTED VALUE ENGINE
EV = P(win) x AvgWin - P(loss) x AvgLoss - Costs. Costs include spread, commission, slippage, swap when applicable. The system must reject trades with negative expected value.

## 24. BACKTEST ENGINE
Simulate spread, commission, slippage, swap, order delay if applicable, stop loss, take profit, position sizing. Avoid fill-at-perfect-price assumptions. Generate equity curve, drawdown curve, trade list, monthly summary, regime summary, session summary.

## 25. REQUIRED PERFORMANCE METRICS
Net Profit, Profit Factor, Sharpe, Sortino, Max Drawdown, Calmar, Win Rate, Average Win, Average Loss, Average R, Expectancy, Trade Count, Longest Losing Streak, Exposure, Return by session, Return by regime. Do not optimize only for win rate.

## 26. OVERFITTING PROTECTION
Explicitly test for look-ahead bias, data leakage, feature leakage, curve fitting, parameter mining, repainting indicators, over-optimization, poor regime generalization. Prefer simpler models when performance is comparable.

## 27. NEWS RISK LAYER
Design an optional economic calendar interface. High-impact categories: CPI, NFP, FOMC, Fed rate decisions, major central-bank speeches, major geopolitical shock events when data is available. Configurable windows 5, 10, 15, 30, 60 minutes before/after news. Do NOT assume the optimal window; backtest it.

## 28. RISK ENGINE
Independent from forecasting logic. Implement: risk per trade; maximum concurrent trades; maximum exposure; daily risk budget; consecutive loss guard; drawdown guard; kill switch; spread guard; volatility guard; news guard; account-state validation.

## 29. PROP-FIRM RULE ENGINE
Do not hard-code FTMO limits into trading logic. Use configuration profiles (configs/prop/ftmo_2step.yaml, configs/prop/ftmo_1step.yaml). Fields: daily_loss_limit, maximum_loss_limit, minimum_days if relevant, trading restrictions, EA restrictions, execution rules. Verify current official rules before shipping any configuration.

## 30. PAPER TRADING
Before automated execution implement paper trading simulating entry, exit, SL, TP, spread, slippage, position sizing, risk limits. Paper-trade records use the same signal schema as future live execution.

## 31. EXECUTION ABSTRACTION
Interface ExecutionBroker with get_account(), get_positions(), submit_order(), cancel_order(), close_position(), modify_position(). Implement PaperExecutionBroker first; later MT5ExecutionBroker. Do not tightly couple trading logic to MetaTrader 5.

## 32. LIVE-EXECUTION SAFETY
Live execution DISABLED by default. Required controls: ENABLE_LIVE_TRADING=false; kill switch; maximum lot size; maximum order count; account whitelist; symbol whitelist; environment confirmation; dry-run mode. A production execution request must require multiple safety checks.

## 33. API DESIGN
FastAPI endpoints may include: GET /health, /market/{symbol}, /features/{symbol}, /regime/{symbol}, /patterns/{symbol}, /signals/{symbol}, /backtests, /backtests/{id}, /models, /risk/status; POST /paper/orders. Do not expose live order endpoints during MVP.

## 34. DASHBOARD
Desktop-first (1440x900), responsive on mobile. Main XAUUSD screen: Current Price, Market Regime, H4 Bias, H1 Bias, M15 Setup, M5 Trigger, Signal BUY/SELL/WAIT, Probability UP/DOWN/NEUTRAL, Expected Return, Expected R, Pattern Matches, Historical Outcome, Risk Status, News Risk, Signal Explanation.

## 35. HISTORICAL ANALOGUE VISUALIZATION
Visual component: CURRENT PATTERN versus TOP HISTORICAL MATCHES, normalized for shape comparison. Show Top 5/10/20 analogues. Show subsequent outcome without contaminating model input.

## 36. DASHBOARD DECISION CARD
Example: XAUUSD; Market Regime; H4/H1/M15/M5 states; Historical Matches; P Up/Down/Neutral; Expected R; Signal; Trade Decision (e.g. WAIT, reason: entry too close to support).

## 37. LOGGING & OBSERVABILITY
Log: data ingestion; validation errors; feature generation; model version; signal generation; backtests; paper trades; risk events; execution decisions; kill-switch events. Every generated signal must be reproducible.

## 38. MODEL VERSIONING
Every model stores: model name; version; training period; feature version; hyperparameters; evaluation metrics; training timestamp; git commit hash. Artifact format documented.

## 39. REPRODUCIBILITY
Every experiment records: dataset version; feature set; parameters; code version; random seeds; result metrics. Create experiments/ or a lightweight experiment registry. Avoid complex MLOps platforms unless justified.

## 40. TESTING STRATEGY
UNIT: indicators, features, risk formulas, structure rules, pattern normalization, statistics. INTEGRATION: MT5 data ingestion, data->feature pipeline, signal pipeline, paper execution. STATISTICAL: future leakage detection, probability calibration, walk-forward consistency. REGRESSION: previous known backtest results.

## 41. SECURITY
Never commit MT5 passwords, broker credentials, API keys, account numbers, secrets. Use .env with .env.example. No trading credentials in frontend code.

## 42. CODING QUALITY
Type hints; docstrings where meaningful; clean interfaces; small composable modules; Pydantic schemas where appropriate; no giant monolithic script; avoid premature abstraction; readable over clever.

## 43. DOCUMENTATION
Required: README.md; docs/architecture/system.md; docs/architecture/data-flow.md; docs/research/dependency-review.md; docs/research/pattern-similarity.md; docs/research/model-evaluation.md; docs/risk/risk-engine.md; docs/testing/testing-strategy.md; docs/operations/paper-trading.md; docs/decisions/ (ADRs where useful).

## 44. AGENTS.md
For future AI coding agents: mission, architecture, coding rules, safety boundaries, testing commands, folder ownership, definition of done, forbidden behaviours (enabling live trading automatically; changing risk limits silently; removing safety gates; claiming profitability without evidence).

## 45. DEVELOPMENT COMMANDS
make setup, make lint, make typecheck, make test, make test-integration, make backtest, make api, make dashboard, make research (or equivalent scripts). Onboarding takes minutes, not hours.

## 46. IMPLEMENTATION PLAN
Before substantial code create docs/PROJECT_PLAN.md with Epic, Task, Dependencies, Acceptance Criteria, Risk, Estimated Complexity, Priority, suggested implementation sequence.

## 47. INITIAL EPICS
01 Repository Bootstrap; 02 MT5 Data Connector; 03 Market Data Validation; 04 Feature Engine; 05 Market Structure; 06 Market Regime; 07 Pattern Similarity; 08 Historical Outcome Engine; 09 Baseline Strategies; 10 Backtesting; 11 ML Benchmark; 12 Probability Calibration; 13 Signal Engine; 14 Risk Engine; 15 FastAPI; 16 Dashboard; 17 Paper Trading; 18 Forward Testing. Do not implement auto execution as part of these initial epics.

## 48. PHASE-1 IMPLEMENTATION SCOPE
Start with only: XAUUSD; M5/M15/H1/H4; MT5 historical data; Parquet storage; DuckDB querying; technical features; market structure; historical pattern search; outcome statistics; rule-based BUY/SELL/WAIT; backtesting; simple API; simple dashboard. No ML until the deterministic research pipeline works.

## 49. MVP ACCEPTANCE CRITERIA
1. Import XAUUSD history from MT5.
2. Data validation succeeds.
3. M5/M15/H1/H4 datasets can be queried.
4. Feature engine runs reproducibly.
5. Market structure classifies HH, HL, LH, LL, BOS, CHoCH.
6. Pattern engine retrieves historical analogues.
7. Outcome engine calculates UP/DOWN/NEUTRAL probabilities.
8. Backtester can simulate a baseline strategy.
9. Costs are included.
10. Dashboard shows market regime, multi-timeframe context, historical analogues, probabilities, BUY/SELL/WAIT.
11. No live trade can be sent.
12. All critical modules have tests.

## 50. AI AGENT WORKING PROCEDURE (every cycle)
1 Inspect repository status. 2 Read AGENTS.md, PROJECT_PLAN.md, relevant architecture docs. 3 State the task. 4 Inspect existing code before modifying. 5 Implement smallest coherent change. 6 Run lint, typecheck, unit tests, relevant integration tests. 7 Fix failures. 8 Update docs. 9 Report: files changed, tests run, results, remaining issues, next recommended task.

## 51. DO NOT DO
Do not: claim guaranteed profitability; generate fake backtest results; invent live trading performance; use future information; silently drop losing trades; optimize against test data; randomly shuffle time series; hide transaction costs; enable live trading; commit secrets; blindly trust indicator libraries; add Deep Learning for marketing value; build unnecessary microservices; rewrite proven libraries without cause.

## 52. RED-TEAM REQUIREMENT
At the end of each major phase ask: how could this result be wrong? Check data errors, future leakage, incorrect timestamps, repainting, overfitting, unrealistic fills, transaction-cost assumptions, small sample size, regime dependence, model instability. Document findings.

## 53. DEFINITION OF DONE
Code implemented; types valid; tests pass; documentation exists; acceptance criteria satisfied; no known critical bug; feature reproducible.

## 54. DELIVERY FORMAT
Do not dump hundreds of files. Deliver first: A repository audit if repo exists; B architecture proposal; C dependency decisions; D PROJECT_PLAN.md; E Sprint 1 implementation plan. Then implement Sprint 1. After Sprint 1 run all applicable tests, report results, continue sequentially.

## 55. FIRST EXECUTION TASK
1 Inspect repo. 2 Do not destroy existing functionality. 3 Create/update AGENTS.md, docs/PROJECT_PLAN.md, docs/architecture/system.md, docs/research/dependency-review.md. 4 Bootstrap Python project. 5 Establish linting, typing, testing, configuration. 6 Implement market-data domain models. 7 Create an MT5 data-source interface. 8 Create an offline CSV/Parquet adapter. 9 Add validation tests. 10 Do NOT implement trading execution. Stop after Sprint 1. Return IMPLEMENTATION REPORT: files created, files modified, architecture decisions, dependencies, tests, known limitations, risks, recommended Sprint 2.

## 56. FINAL ENGINEERING PRINCIPLE
The goal is not to build a bot that trades frequently. The goal is a system capable of saying "There is no statistically justified trade." A high-quality NO TRADE is more valuable than a low-quality BUY or SELL. Protect statistical integrity first. Protect capital second. Automate execution last.
