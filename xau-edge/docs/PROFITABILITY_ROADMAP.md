# XAU EDGE: Profitability Roadmap

Status: **PLAN ONLY. Nothing here has been executed.** Written 2026-10-09 after a read-only forensic
pass over the repository at commit `f9b527d` (working tree clean). No strategy, trading logic, holdout
data, demo or funded flag was touched.

Audience: a new senior engineer or AI coding agent who must execute the programme without guessing, and
the project owner who must make the decisions in section 24.

Language: English for the plan. The owner's summary is in Vietnamese just below.

### Map from the required plan structure to this document

| Required section | Where |
|---|---|
| 1 Executive Summary | 1 |
| 2 Current-State Architecture | 2 |
| 3 Capability Matrix | 3 |
| 4 Research History | 4 |
| 5 Root-Cause Analysis | 5 |
| 6 Profitability Blockers | 6 |
| 7 Data Gaps | 6A |
| 8 Research Thesis | 8, 9.5 |
| 9 Edge Program V2 | 9 |
| 10 Label Strategy | 11 |
| 11 Event Sampling Strategy | 10, 12 |
| 12 Analogue Engine V2 | 14 |
| 13 Statistical Protocol | 13 |
| 14 Robustness Protocol | 21 |
| 15 Machine Learning Plan | 7, 15, 19 |
| 16 Data Acquisition Plan | 16, 17, 18 |
| 17 Execution Calibration Plan | 23.3 |
| 18 Forward Testing Plan | 23.2 |
| 19 Operations Plan | 24.2 |
| 20 FTMO Readiness Plan | 20 |
| 21 Strategy Lifecycle | 23.4, 23.5 |
| 22 Sprint Roadmap | 25 |
| 23 Dependency Graph | 26 |
| 24 Owner Actions | 27 |
| 25 AI Coding Actions | 27 |
| 26 Calendar-Time Actions | 27, 28 |
| 27 Cost Estimate | 28 |
| 28 Stop Conditions | 28 |
| 29 Go / No-Go Tree | 29 |
| 30 Final Recommendation | 31 |
| Red-team, perspectives, rankings | 30, 30.1, 9.5, 31 |

---

## 0. Tóm tắt cho chủ dự án (tiếng Việt)

* **Hiện trạng:** hạ tầng đã gần đầy đủ (nghiên cứu, backtest, risk, bot demo/funded có khóa, web control).
  Thứ **chưa có** là một edge. Mọi kiểm định đã chạy (3 baseline, 1 nghiên cứu analogue, 4 mô hình ML,
  6 giả thuyết / 18 biến thể của Edge Program, tổng cộng 36 lần chạy trên dữ liệu mới) đều FAIL tiêu chí
  đã đăng ký trước. Holdout 2026-05..2026-10 và Test-H 2022-01..2025-04 **chưa bị chạm**.
* **Phát hiện quan trọng của lượt đọc này:**
  1. Thiết kế kiểm định hiện tại **không đủ công suất thống kê** để thấy một edge thực tế (+0,05..+0,10 R
     mỗi lệnh): với K = 21 cần khoảng 2.300 lệnh để thấy +0,10 R và 9.000 lệnh để thấy +0,05 R. Các biến
     thể chỉ có 80..2.700 lệnh. FAIL ở đây **chưa chứng minh không có edge**; nó chỉ chứng minh không có
     edge lớn (≥ +0,2 R) trong các luật đơn giản đã thử.
  2. Có ít nhất ba **nghi vấn về tính hợp lệ** của Edge Program cần xử lý trước khi tin kết quả âm: swap
     hiện hành (-76 điểm/đêm cho lệnh mua) bị áp lên cả 2011-2021; lịch phiên/giờ broker của lịch sử H1 có
     vẻ **đổi cấu trúc quanh 2021** (số bar rơi vào "đóng cửa" tăng gấp đôi 2013-2020 so với 2022-2024); và
     tập H1 lịch sử không qua validator (1.003 bar thiếu mức ERROR).
  3. `gross_pnl` trong danh sách lệnh **đã gồm spread và slippage**, nên chưa ai tách được "không có hướng
     đi" khỏi "chi phí ăn hết".
* **Đề xuất:** một Edge Program V2 hữu hạn (tối đa 8 giả thuyết, 4 + 4), kiểm định hai tầng (event study
  trước, 7 tiêu chí nguyên vẹn sau), Test-H làm tập xác nhận duy nhất, holdout chỉ mở một lần. Việc đầu
  tiên là **sprint P0** (kiểm toán, chưa viết chiến lược). Quyết định cần chủ dự án: Phụ lục A, quyết định D-1.
* **Không hứa lợi nhuận.** Kết luận "không tìm thấy edge" là kết quả hợp lệ (mục 28).

---

## 1. Executive Summary

**Where XAU EDGE is.** About 20,000 lines of source in 21 packages, 1,734 collected tests (not run in
this planning pass), 52 commits, 23 ADRs. The research stack (data, features, structure, regimes,
analogues, outcomes, strategies, backtest, evaluation, experiment registry), the signal engine with an
evidence gate, the risk engine with FTMO profiles, a guarded MT5 executor (demo and funded, both off),
a rollout controller, a Telegram notifier, NSSM installer, a read-only API, a dashboard and a local web
control plane (ADR-0023) all exist in code. **No order has ever been sent by this repository** (no trade
password was supplied; everything on the order path was exercised against fake terminals).

**What is solved.** Software for running a disciplined, fail-closed bot. A pre-registered evaluation
protocol with a locked holdout and a power test showing the pipeline can see a planted edge.

**What is unresolved.** Whether any rule on XAUUSD has positive expectancy after realistic costs. Every
test so far says no, under conditions that (section 5) had limited power and several unresolved validity
questions. The only candidate the repository can currently run on a funded account (H03-c1.0) has
**negative** expected R after pessimistic costs (-0.066 R/trade on Validation-H); it is an execution
plumbing option, not a profit candidate (section 20).

**What this plan does.** It does not add software for its own sake. It (a) closes the validity doubts
cheaply, (b) raises statistical power by testing mechanisms at the event level before simulating
trading, (c) spends a small, counted budget on mechanism-based hypotheses, (d) keeps the strict seven
criteria and the locked holdout, (e) leaves funded compliance, dashboards and automation frozen unless
they unblock research.

---

## 2. Current-State Architecture (what actually exists)

```text
MT5 DEMO terminal (FTMO), read-only for research
   |  scripts/fetch_history.py, market_data/refresh.py (closed bars only)
   v
RawStore (immutable parquet + sidecar hash)  ->  DatasetCatalog (DuckDB, merge, mtime cache)  -> validators (report, never repair)
   v
features/ (EMA, ADX, RSI, MACD, Stoch, ATR, BB, candle geometry, volume, session)   structure/ (swings, HH/HL/LH/LL, BOS, CHoCH, regime)
   v
patterns/ (6-channel ATR-scaled windows, 5 distances, leakage-safe kNN)   outcomes/ (forward return, MFE/MAE, barrier R)
   v
strategies/ (baselines A,B,C; edge_program H01-H06)  ->  backtest/ (bid/ask, spread floor, slippage, swap, 1 position, R-based)
   v
evaluation/ (7 edge criteria, day-block bootstrap, walk-forward folds, prop Monte Carlo)  +  experiments/ (registry, K)
   v
signals/ (decide(), 12 refusal reasons, evidence gate by strategy_id+config+dataset hash)   models/ (LR, RF, XGB, LGBM, calibration)
   v                                                                    (models are NOT in the signal path)
execution/ (state.sqlite, bridge, intent, reconcile, journal, runner/app, guards)  funded/ (rules lock, identity, rollout)
   v
brokers/mt5_demo/ (reader, executor: single order_send call site)  ->  MT5 (never reached with a real order so far)
   v
api/ (read-only + /control when enabled)  ->  apps/dashboard (Next.js)      ops/ (Telegram, NTP, logging)   control/ (web control service)
```

Not in the picture because it does not exist: a live strategy generator for any Edge Program hypothesis
(only Baseline C has a live signal path), a news calendar with data, tick or M1 history, cross-asset
data, a second broker, measured slippage/commission, any forward sample.

---

## 3. Capability Matrix

Legend: DONE, DONE-BUT-UNVERIFIED (code and fake-terminal tests only), RESEARCH-FAILED, BLOCKED,
TIME-BOUND, OWNER-ACTION, NOT-NEEDED. "Profit relevance": H = decides whether there is an edge, M =
needed once an edge exists, L = unrelated to edge.

| Subsystem | Status | Evidence | Real-world validation | Profit relevance |
|---|---|---|---|---|
| Market-data import, store, catalog, validators | DONE | tests; verification report; ADR-0005/0008/0009 | real FTMO demo data, bars match broker's derived bars | H (garbage in) |
| Historical H1 2010-2025 / H4 2004-2025 | DONE-BUT-UNVERIFIED | manifest: H1 fails validator (1,003 missing-bar ERRORs, 2,226 weekend bars); spread field unusable | none: session clock before ~2021 unverified | H |
| M15 history | DONE (short) | 2022-07..2025-04 only, lies inside Test-H | | M |
| M5 history | DONE (short) | 2025-05..now only | real | M |
| Features / structure / regime | DONE | golden tests vs TA-Lib, no-repaint tests | | H (inputs) |
| Pattern analogues | RESEARCH-FAILED | timing statistic -0.158 [-0.299,-0.012] dev; +0.019 [-0.160,+0.180] val | | H |
| Outcome / barrier engine | DONE | tests | | H (label source) |
| Baselines A, B, C | RESEARCH-FAILED | checkpoint-1 | | H |
| ML benchmark (4 models, Platt) | RESEARCH-FAILED | model-evaluation.md; none beats base rate on validation | | H |
| Edge Program H01-H06 | RESEARCH-FAILED (see doubts, section 5) | ledger.md, final-verdict.md (B) | | H |
| Backtest engine and cost model | DONE-BUT-UNVERIFIED | ADR-0015; slippage 3 pts assumed; commission 0 unverified; swap = today's values | no measured fills | H |
| Evaluation protocol (7 criteria) | DONE | planted-edge power test passes | | H |
| Experiment registry / K | DONE (per programme) | K=21 constant in code; baselines K=3 separate; ML K=7..10 separate | | H |
| Signal engine + evidence gate | DONE | tests, mutation checks; strategy registry ADR-0021 | demo dry-run cycles on real data (WAIT) | M |
| Risk engine, FTMO profiles | DONE | tests; prop MC; funded rules lock (13 `must_verify` pending) | none on real orders | M |
| MT5 executor, reconcile, state | DONE-BUT-UNVERIFIED | fake-terminal tests; independent review | **no real order ever sent** | M |
| Dry-run bot on real data | DONE (short) | ~10 live cycles on 2026-10-08 | needs 14-day soak | M |
| Web control plane, dashboard | DONE | Playwright with mocks | | L |
| Telegram, NSSM, NTP, logging | DONE-BUT-UNVERIFIED | unit tests; owner has not created bot/service | | L |
| News calendar | DONE (loader) / OWNER-ACTION (source) | point-in-time loader with `available_at` | no data | M..H (H13) |
| Cross-asset data | NOT-STARTED | none | | M (conditioning only) |
| Tick / M1 data | UNKNOWN | never probed | | M (execution realism) |
| Second-broker data | OWNER-ACTION | none | | M (robustness gate) |
| Forward test | TIME-BOUND | tooling exists, no candidate | | H (final proof) |
| Funded compliance | OWNER-ACTION | `ftmo_funded.yaml`: 13 rules pending | | none (compliance is not alpha) |

---

## 4. Research History (every hypothesis, model and variant)

Costs everywhere: spread (measured M5 in 2025-26; `max(recorded, 30)` points on 2011-2021 history),
slippage 3 points per fill, commission 0 (unverified), swap at today's terminal values, one position at
a time, 0.5% risk, regime SHOCK blocked. Net R = after all of these. "Holdout" = 2026-05-01..2026-10-07
(old Test) untouched in every row.

### 4.1 Programme 0 (2025-05..2026-04, M5 execution, K = 3 for baselines, 7..10 for models)

| Item | Economic idea | Period / TF | Params | Variants | Trades | Dev | Val | Test | PF (dev/val) | Mean net R (dev/val) | Max DD | Rejected because |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Analogue study | similar past windows predict next 20 bars | 2025-05..2026-04, M15 | W30, k20, euclid | 1 (+exploratory not counted) | n/a (3,941 / 1,924 queries) | timing -0.158 | +0.019 | locked | n/a | n/a | n/a | lower bounds not > 0; sign flip |
| Baseline A | H1 trend + M15 pullback + M5 break | same | fixed | 1 | 135 / 63 | FAIL | FAIL | locked | 0.80 / 0.85 | -0.135 / -0.099 | 12.3% / 7.0% | PF, CI, <100 trades on Val |
| Baseline B | EMA stack + RSI | same | fixed | 1 | 782 / 395 | FAIL | FAIL | locked | 1.01 / 0.84 | +0.009 / -0.104 | 20.9% / 25.9% | sign flip, PF, DD |
| Baseline C | analogue direction traded | same | fixed | 1 | 799 / 413 | FAIL | FAIL | locked | 0.81 / 1.04 | -0.105 / +0.027 | 44.1% / 15.4% | sign flip, PF, DD |
| Logistic, RF, XGBoost, LightGBM | 20-bar UP/DOWN/NEUTRAL from 54 scale-free features | same, M15 | fixed modest | 4 models x calibration variants | 418/264, 563/281, 539/317, 561/295 | FAIL (2/7..1/7 criteria) | FAIL | locked | 1.14/0.81, 0.99/0.89, 0.95/0.84, 1.02/0.86 | not reported as R | n/a | only LR beat base-rate log loss on Dev (by 0.003), not on Val |

### 4.2 Programme 1: Edge Program (2011-2021 H1/H4, K = 21, alpha = 0.002381, Test-H and holdout untouched)

Each row: 3 variants of one parameter, Dev-H 2011-2018 and Val-H 2019-2021, pessimistic scenario in the
last column. Best variant by the pre-fixed maximin rule.

| ID | Economic idea | TF | Parameter grid | Trades dev/val (range over variants) | Best pessimistic mean net R, min(dev,val) | PF best base | Rejected because |
|---|---|---|---|---|---|---|---|
| H01 | session-open momentum | H1 | theta {0.3,0.6,0.9} | 729-2,727 / 291-1,091 | -0.093 (theta0.3) | < 1 | negative everywhere |
| H02 | Asia-range breakout at London/NY | H1 | b {0,0.25,0.5} | 1,320-1,714 / 487-640 | -0.074 (b0.0) | < 1 | negative everywhere |
| H03 | volatility compression then breakout | H1 | c {0.8,0.9,1.0} | 83-211 / 35-119 | -0.066 (c1.0) | 1.023 max | c0.9: +0.012 on Val-H but 83 trades and negative on Dev-H |
| H04 | daily trend + EMA pullback | H1 | L {10,20,40} | 1,810-1,861 / 687-703 | -0.144 (L40) | < 1 | clearly negative |
| H05 | fade excess impulse bar | H1 | s {1.5,2.0,2.5} | 22-815 / 6-305 | -0.142 (s1.5) | < 1 (s2.5: 6 trades, no loser) | s2.5 has 22/6 trades |
| H06 | H4 Donchian trend | H4/H1 | N {20,40,80} | 78-142 / 34-71 | -0.428 (N40) | < 1 | few trades, strongly negative on Val-H |

Totals: 36 runs, 3/36 with base mean net R > 0 (H03-c0.9 Val +0.021 on 83 trades; H03-c1.0 Dev +0.0001;
H05-s2.5 Val +0.667 on 6 trades), none passing. Maximum drawdown is not tabulated in the ledger (known
gap, fixed in P1).

### 4.3 Why they failed: root-cause classification

| Cause | Applies to | Evidence | Strength |
|---|---|---|---|
| **Weak or absent effect in simple rules** | all | gross direction not isolated, but 33/36 negative and 3 positives all tiny | likely, not proven |
| **Insufficient sample size / power** | H03, H05, H06, Baseline A; all at K=21 | section 5.1 power table | **proven** (design limit) |
| **Multiple-testing burden** | all | alpha 0.0024 needs +0.21 R at 500 trades | proven (arithmetic) |
| **Bad hypothesis** | H04, H06 (strongly negative both periods) | consistent sign | possible |
| **Cost structure** | long-biased variants | swap -76 points/night applied to 2011-2021 | **suspected bias, unquantified** |
| **Regime instability** | Baselines B, C | sign flip between periods | likely |
| **Parameter instability** | H03 | c0.9 vs c1.0 vs c0.8 inconsistent | likely noise |
| **Dataset limitation** | all H-programme | H1 only, spread unusable, 1,003 missing-bar errors, session clock unverified | real |
| **Label / target problem** | ML | direction of a 20-bar move, every bar an observation | likely (section 7) |
| **Execution-timeframe mismatch** | H01, H02 | session effects execute on H1, entry next-bar open | possible |
| **Feature problem** | ML | 54 features, all functions of OHLCV | likely (no new information) |
| **Implementation limitation** | all | `gross_pnl` includes spread and slippage; stop-first on both-touch | real (blocks attribution) |

---

## 5. Root-Cause Analysis: why has no edge been found?

### 5.1 The tests could not have seen a realistic edge

Minimum detectable mean net R per trade (one-sided, power 80%, i.i.d. approximation, sd(R) = 1.3 R, the
sd observed in baselines; real tests use day-block bootstrap and are slightly worse):

| K (alpha = 0.05/K) | n = 100 | 200 | 500 | 1,000 | 2,000 | 3,000 |
|---|---:|---:|---:|---:|---:|---:|
| 21 (Edge Program) | 0.476 | 0.337 | 0.213 | 0.151 | 0.107 | 0.087 |
| 8 | 0.434 | 0.307 | 0.194 | 0.137 | 0.097 | 0.079 |
| 4 | 0.401 | 0.283 | 0.179 | 0.127 | 0.090 | 0.073 |
| 1 | 0.323 | 0.229 | 0.145 | 0.102 | 0.072 | 0.059 |

Trades needed at K = 21: +0.20 R: 567; +0.15 R: 1,008; **+0.10 R: 2,269; +0.05 R: 9,076**. The
Edge Program variants had 6..2,727 trades per period; ten of eighteen variants had fewer than 700 on
Dev-H. A real but modest edge (+0.05..+0.10 R, which is already generous for gold intraday) was
**undetectable by construction**. The seven criteria were designed to avoid false positives; they were
never sized to avoid false negatives. This is the single most important fact in this document.

Per-trade cost is small next to these thresholds (0.03..0.07 R per trade according to the sprint-9
review), so **power and signal quality, not costs, are the binding constraint**. Costs matter at the
margin and for long-biased rules (swap).

### 5.2 Suspected validity problems in the negative result

1. **Swap anachronism.** `CostModel.swap_long_points = -76.05`, `swap_short_points = -4.2` are today's
   terminal values, applied to every overnight position in 2011-2021. At a 1.5 ATR stop (about $12 per oz
   on H1) a long held one night pays about 0.06 R; a short pays almost nothing. Long-held mean-reverting
   and breakout variants were penalised against a drifting asset. Not quantified yet (P0).
2. **Session clock before ~2021.** On the FTMO H1 history, the number of bars per year that fall inside
   the current calendar's closure windows (daily break 16:50-18:05 New York, weekend) is about 514 in
   2013-2020, about 257 in 2022-2024 and 281/258 in 2021/2022 (measured in this pass, no outcome data
   looked at). A structural change around 2021 means the NY+7 broker clock and daily-break assumption
   probably do **not** hold for 2011-2020. H01 (session-open bars at 09:00 Tokyo, 08:00 London, 08:00 New
   York) and H02 (07..15 UTC window) depend on that clock: they may have been testing the wrong hours for
   part of the sample. Unresolved (P0).
3. **Dataset certificate.** The H1 research dataset failed the validator (`MISSING_BARS` ERROR x 1,003;
   `WEEKEND_BARS` x 2,226) and was used with "reported, not repaired" results. The effect of the gaps on
   ATR, entries (`ENTRY_GAP`) and signals was not bounded.
4. **Cost attribution is impossible today.** `gross_pnl` already includes spread and slippage, so
   "no directional signal" cannot be separated from "costs consumed it". A mid-price gross R column is
   missing.
5. **Programme-level K.** K=21 counts Programme 1 plus three baselines. The analogue study, the ML runs
   (K 7..10), exploratory analogue variants and any informal exploration live in separate counters.
   Dev-H and Val-H have now been used to evaluate 18 designs; any new hypothesis tested on them is **not
   independent** of what was learned. See section 13 for how V2 handles this.
6. **Design of the labels and the trade rules.** Fixed 1.5/3.0 ATR exits, `hold` windows and "first
   signal wins while a position is open" impose a trade-simulation structure on every hypothesis, which
   shrinks sample size and can destroy a real conditional effect (section 11).

### 5.3 What the evidence does NOT say

It does not say XAUUSD is efficient. It says: simple, single-mechanism, fixed-exit rules on one broker's
OHLC bars show no edge **of a size these tests could detect**, with cost and clock caveats above.

---

## 6. Profitability Blockers (ranked)

| Rank | Blocker | Type | Fix |
|---|---|---|---|
| **P0-1** | No hypothesis with positive evidence; tests underpowered for modest edges | research design | Edge Program V2: event-level screening, power stated before each run (sections 9, 11-13) |
| **P0-2** | Validity doubts on the negative result (swap anachronism, session clock, data certificate, no gross-at-mid) | data / cost | P0 forensics, diagnostic-only |
| **P0-3** | No cross-programme K ledger; reused development data | governance | K ledger v2 (section 22) |
| **P1-4** | No measured execution costs (slippage, commission, swap, latency) | calendar-bound | demo calibration (P12), after a candidate exists |
| **P1-5** | No live signal implementation for any non-Baseline-C strategy | engineering | only after a candidate passes Test-H (parity test) |
| **P1-6** | Data resolution: M5 only since 2025-05, no M1/ticks probed | data | probe depth read-only (P0), then decide |
| **P2-7** | News calendar not supplied | owner | scheduled-event calendar is enough for H13 (section 17) |
| **P2-8** | No second broker | owner | needed only at the Broker Robustness gate |
| **P3-9** | Funded compliance (13 `must_verify`, trade password, soak, demo) | compliance | separate track (section 20); does not create edge |

---

## 6A. Data gaps

| Gap | Detail | Consequence | Closing it |
|---|---|---|---|
| M5 history short | only 2025-05-01 onward | fine-resolution research limited to 17 months, all burned | accumulate forward; M1/tick probe |
| M15 history short | 2022-07..2025-04 in research store, lies inside Test-H | cannot be used for design without touching the confirmatory set | keep out of design |
| H1/H4 history validity | H1 fails validator (1,003 missing-bar ERRORs, 2,226 weekend bars); spread field unusable (zero or 5..23 points before 2025) | gaps and cost rules are assumptions | data certificate (P0), `max(spread, 30)` rule, era tables |
| Session clock unverified before ~2021 | closure-bar count doubles in 2013-2020 | session hypotheses may test the wrong hours | clock inference per year (P0) |
| No M1 / tick data probed | never queried | sweeps timing and execution realism unknown | read-only probe (D-2) |
| No news data | loader only | H13 and the news guard idle | scheduled-event calendar |
| No cross-assets | none stored | H14 impossible | same-broker fetch (Batch B) |
| No second broker | none | no broker-robustness evidence | owner demo account (survivors only) |
| No measured costs | slippage 3 points assumed, commission 0 unverified, swap = today's | cost claims unverified | demo calibration (P12) |
| No forward sample | none | nothing out of sample in time | forward paper (P11) |

---

## 7. Do not confuse model failure with market efficiency

The four models failed. Whether they solved the right problem:

| Question | Finding |
|---|---|
| Right label? | They predicted UP/DOWN/NEUTRAL over 20 bars (5 hours) with a 0.5 ATR neutral band. That is a convenient target, not the decision quantity (P(TP before SL), expected R). Barrier outcomes already exist in `outcomes/` and were not the training target. |
| Event-based sampling? | No: every M15 bar is an observation, mostly dull bars. A model must learn "nothing happens" and spends its capacity on the 90% of bars with no structure. |
| Contexts mixed? | Yes: sessions, volatility regimes, news and normal periods share one model; session and regime appear as one-hot features only. |
| Direction vs barrier? | Direction. A 1-sigma move over 20 bars is dominated by noise; barrier outcomes with an asymmetric payoff concentrate information on the part of the path that gets traded. |
| Features independent? | No: returns, EMA distances, ADX/DI, RSI, MACD, stochastic, Bollinger, candle geometry are all smooth functions of the same OHLC path. Little incremental information. |
| Microstructure visible? | No: bar resolution; spread only as a per-bar scalar. |
| History too short? | M5/M15 history was 17 months for models. That is data-limited, not model-limited: 5,800 labelled rows per period with strongly overlapping 20-bar labels (effective n much lower). |
| Verdict | The ML result is **uninformative about efficiency**. It is informative only that generic technical features do not forecast direction on 17 months. |

Hence: no more "predict every bar" models until events and labels (sections 10-12) are in place.

---

## 8. Reframe: mechanism first

Research families must come from a repeatable mechanism, state why it should exist, why it should
persist, when it should work and when it should fail. Families considered (full definitions in sections
9-11):

| Mechanism | Why it might exist | Why it might persist | Works when | Fails when |
|---|---|---|---|---|
| Liquidity acquisition (sweep of obvious levels) | stops and resting orders cluster at prior high/low; market makers and large flow trade into them | structural to order-book markets | clear range, thin liquidity beyond the level | strong trend day, news repricing |
| Acceptance vs rejection at a level | information arrival decides whether a break is accepted | same | trend regimes (accept), range regimes (reject) | transitions |
| Session inventory transfer | Asia range is built on thin flow; London/NY reprice | session structure of the 24h market | stable session clock, ordinary days | holidays, news days |
| Volatility compression / expansion | volatility clusters | very robust empirically, but direction is not | after compression, with a directional context | direction unknown |
| Impulse and pullback | slow information diffusion | uncertain | persistent trends | choppy |
| Structure failure | failed continuation signals exhausted flow | uncertain, definitions subjective | | |
| News repricing | scheduled releases move gold | real catalyst | scheduled events | spreads and slippage explode; FTMO funded restricts news trading |
| Cross-asset confirmation | gold reacts to USD and rates | macro link | rates/USD driven days | decoupled periods |
| Time-of-day liquidity / spread regime | costs and flow vary by hour | structural | | |

---

## 9. Edge Program V2

### 9.1 Budget (finite, counted, not resettable)

* Batch A: **4 hypotheses (H07-H10)**. Batch B: up to **4 more (H11-H14)**, only if Batch A yields no
  Development survivor. **Maximum 8 new hypotheses.**
* Each hypothesis has at most **6 variants** (grid: at most 2 parameters x 3 values, trimmed to 6).
  Batch A: at most 24 variants; whole programme: at most 48.
* **K_V2 starts at the number of V2 variants declared**, counting the whole grid at registration, never
  resetting. Programme 0 (K 3..10) and Programme 1 (K 21) are legacy; their data (2011-2021, 2025-05..
  2026-04) is **burned for confirmation** (section 13).
* Labels, horizons, filters and model families count as variants when they change a trading decision.

### 9.2 Pre-registration template (every hypothesis)

ID; name; economic rationale; mechanism; event definition (causal, objective); required timeframe; data;
entry; invalidation; exit model; prediction target; expected holding horizon; regimes and sessions where
it should work; parameter grid and variant count; **minimum event count and the minimum detectable
effect at the stated K**; predefined rejection criteria. Files go in
`docs/research/edge-program-v2/hypotheses/H07.md ...`, committed **before** any result on the data used.

### 9.3 Batch A (decided)

**H07 Liquidity-sweep reversal.** Events: first H1 bar (or later) whose HIGH exceeds a reference level
(previous-day high, previous-day low, Asia range high, Asia range low) and whose CLOSE is back inside the
level by at least `eps` x ATR within `m` bars (rejection). Direction: against the sweep. Outcome:
barrier (section 13) from the rejection bar close, ATR units. Variants (6): level set {PDH/PDL, Asia
H/L} x `eps` in {0.0, 0.25, 0.5} (m fixed at 3). Expected to work in range regimes and ordinary days,
fail on trend/news days. One event per level per day; no overlapping events within the same level.

**H08 Breakout acceptance / continuation.** Same events and same levels, complementary hypothesis:
the bar after the breach CLOSES beyond the level by at least `eps` x ATR and the next `m` bars hold
outside (acceptance). Direction: with the break. Variants (6) mirror H07. Evaluated on the **same event
set** as H07 so reject and accept are one fork of the same objective event (the fork, not either side
alone, is the object of study). Expected to work in trend regimes.

**H09 Session-transition structure.** Event: close of the last H1 bar before London open (Asia to London)
and before New York open (London to NY), conditioned on the position of price within the completed
session range (tercile) and the H4 trend sign. Direction: continuation if price is in the outer tercile
with the trend, fade if in the opposite tercile against the trend (the direction rule is part of the
registration, not chosen after results). Variants (6): transition {Asia-London, London-NY} x range
tercile threshold {0.2, 0.3, 0.4}. Expected on ordinary days; excluded days with a known scheduled
news event when a calendar exists. **Requires verified session clock for the whole period (P0).**

**H10 Conditional volatility expansion.** Event: H1 volatility compression (ATR14 / mean ATR14 over 120
bars <= c) AND session in {London, London/NY overlap}. Direction by H4 trend sign only (no direction
when H4 trend is flat). Target: signed outcome with **barrier asymmetry 1:2**. Variants (6): c {0.8,
0.9} x H4 trend lookback {20, 50, 100 bars}. Differs from H03 by the session and trend conditioning
(H03 had neither).

### 9.4 Batch B (only if Batch A has no Development survivor)

H11 impulse, pullback, re-expansion; H12 structure failure (HH attempt fails then prior HL breaks);
H13 scheduled-news regime (pre-event, event, post-event; requires scheduled-event calendar, section
17); H14 cross-asset confirmation (only as an incremental filter to a survivor of H07-H13, never a
standalone strategy). Full templates written only when Batch B is opened.

### 9.5 Ranking of research families (1 = highest expected information value)

| Rank | Family | Reason |
|---|---|---|
| 1 | H07/H08 sweep vs acceptance | objective, causal, many events (about 1-4 per day), clear mechanism, a fork that is informative either way |
| 2 | H10 conditional volatility expansion | volatility clustering is the most robust effect in finance; adding session and trend context fixes H03's missing structure |
| 3 | H09 session transition | mechanism plausible; depends on a clock that must be verified; related to the failed H02, so lower prior |
| 4 | H12 structure failure | structure primitives exist; but definitions are subjective; moderate event count |
| 5 | H11 impulse, pullback | overlaps baseline A and H04 which failed; low incremental information |
| 6 | H13 scheduled news | strong catalyst but costs explode around releases and funded rules restrict news trading; high research value, low deployability |
| 7 | H14 cross-asset | cannot work alone; value only as a filter after a base edge |
| 8 | Analogue V2 (conditional similarity) | unconditional analogues failed; expensive; fits only after events exist (section 14) |

---

## 10. Event sampling (replace "every bar")

Principle: observe the market where information concentrates. For each event family: objective,
causal (uses only closed bars), non-repainting, enough occurrences, tied to a mechanism.

| Event | Objective | Causal | Occurrence (H1, 11 y) | Mechanism | Verdict |
|---|---|---|---|---|---|
| PDH / PDL sweep | yes (daily high/low, broker day) | yes after the day closes | 1-2 per day | liquidity | **adopt (H07/H08)** |
| Asia high/low sweep | yes if Asia bars fixed in UTC and clock verified | yes | about 1 per day | liquidity | **adopt (H07/H08)** |
| Failed breakout | derived from the above | yes | | rejection | covered by H07 |
| Breakout acceptance | derived | yes | | acceptance | covered by H08 |
| Volatility compression | yes (ratio) | yes | 10-20% of bars | clustering | **adopt (H10)** |
| Volatility expansion bar | yes | yes | | | context for H10 |
| Large impulse (> k ATR) | yes | yes | 2-5% of bars | impact | Batch B (H11) |
| Structured pullback | partly (swing definitions) | yes (non-repainting swings) | | | Batch B |
| Failed HH/LL, BOS then failure | depends on swing rule | yes | | exhaustion | Batch B (H12) |
| Session open / overlap | yes | yes | 3 per day | participation | context (H09) |
| Post-news impulse | needs calendar | yes | | repricing | Batch B (H13) |

Rule: every detector gets a **repaint test** (truncate future bars; events up to t must be identical)
and a **leak test** (replace future bars with garbage; no change), the same style as the pattern
leakage tests.

---

## 11. Label strategy: predict what the decision needs

| Label | Decision alignment | Use |
|---|---|---|
| Direction over N bars (current) | low: ignores path and payoff | retire as a training target |
| Future ATR-normalised return | medium | descriptive only |
| MFE / MAE | high for stop and target design | descriptive, feeds barrier grid |
| **TP-before-SL (triple barrier) with timeout** | **highest: it is the P&L of the trade** | **primary target** |
| Expected R (net) | direct | reported per event, per variant |
| P(timeout) | informs holding time | reported |
| Time to target | informs holding horizon | reported |
| Breakout continuation / mean reversion | event-specific | encoded by the H07 vs H08 fork |

**Triple barrier, defined once and frozen:** for an event at close `t0` with ATR `a` (ATR14 at `t0`),
entry at the next bar's open (execution cost model applies), barriers `+2a` (target) and `-1a` (stop)
as the **primary** pair (a 1:2 payoff, so a hit rate above one third is break-even before costs).
Secondary pair for continuity with Programme 1: `+3.0a / -1.5a`. Timeout `N` bars (H1: 24). Both barriers
inside one bar: stop first. Reported per event: label in {TP, SL, TIMEOUT}, `r_gross_mid`
(mid-price, no costs), `r_net` (after spread, slippage, swap era-correct), MFE, MAE, bars held.
Barrier pairs and `N` are **frozen constants of the programme**, not parameters. Adding a pair is a new
variant and counts toward K.

---

## 12. Event-level inference vs trade simulation (the power fix)

Programme 1 judged strategies by a one-position-at-a-time backtest: the engine drops signals while a
position is open, which discards events and shrinks n. V2 splits the question:

* **Stage 1: event study** (descriptive, all declustered events, no position constraint). Unit = event,
  one event per (level, day) or (variant, signal day); overlapping outcomes handled by **day-block
  bootstrap** (blocks of one Prague day). Output per variant: n_events, n_effective days, mean
  `r_gross_mid`, mean `r_net`, CI at the alpha chosen in section 13, hit rates, MFE/MAE, by session and
  regime. Purpose: screening at a power that matches the effect sizes we care about.
* **Stage 2: trade simulation** with the existing engine and the **unchanged seven criteria** (section
  13) for variants that survive Stage 1. This is where costs, one-position, risk and drawdown are real.

Stage 1 can reject a mechanism early and cheaply; it cannot confer evidence. Evidence needs Stage 2 on
Test-H.

---

## 13. Statistical protocol

### 13.1 Splits (chronological, never shuffled)

| Name | Dates | Data | Use in V2 | Status |
|---|---|---|---|---|
| Development-2 | 2011-01-01 .. 2018-12-31 | H1/H4 | design, Stage 1 screening, walk-forward inside | burned for confirmation (Programme 1 saw it) |
| Validation-2 | 2019-01-01 .. 2021-12-31 | H1/H4 | Stage 1/2 for pre-registered survivors | burned for confirmation |
| **Test-H** | **2022-01-01 .. 2025-04-30** | H1/H4 (M15 exists, not used) | **confirmation, one run per candidate** | **pristine** |
| **Locked Holdout** | **2026-05-01 .. 2026-10-07** | M5..H4 | final, one candidate, one run | **pristine** |
| Forward | 2026-10-09 onward | live | paper, then demo | accumulating |
| Burned recent | 2025-05-01 .. 2026-04-30 | M5..H4 | used by baselines/ML/analogue; may serve only as extra descriptive data | burned |

Warm-up from earlier data allowed; decisions and outcomes inside the period.

### 13.2 Decisions allowed per stage

| Stage | May | May not |
|---|---|---|
| Development-2 | design events/labels, debug, power calculation, Stage 1 screening | read results of Validation-2/Test-H/holdout |
| Validation-2 | evaluate every pre-registered variant once per cost scenario | change a hypothesis after results |
| Test-H | **one run per candidate that passed Development-2 and Validation-2 at Stage 2** | re-run, tune, add a variant |
| Holdout | one run, one frozen candidate, after independent review | anything iterative |
| Forward | measure, compare to expectation | tune |

### 13.3 Criteria and alpha

* The **seven criteria are unchanged** (>=100 trades, mean net R CI lower bound > 0 at `1 - 0.05/K`,
  PF >= 1.2, max DD <= 15 R, >=3/4 positive folds, positive after removing best 5%, no regime/session
  > 60% of profit) plus the pessimistic-slippage condition added in Programme 1.
* `K` for V2 = number of V2 variants declared (<= 48). The first Stage 2 evaluation uses the Batch A
  declared count (<= 24) **plus Batch B's declared count once Batch B is registered**; opening Batch B
  retroactively tightens nothing already decided, but any later PASS must hold at the full K_V2.
* **Stage 1 alpha** (screening only): Holm-Bonferroni over the variants evaluated in Stage 1, family-wise
  0.10. Rationale: screening may be liberal because it cannot confer evidence; Stage 2 and Test-H do.
  This is an **addition** before Stage 2; it does not alter any of the seven criteria.
* Each pre-registration states n_events and the **MDE** at the stated K. A hypothesis whose expected n
  gives an MDE above +0.20 R at K_V2 is **registered as "underpowered-by-design"** and is either dropped
  or given more data before it spends a variant.

### 13.4 Required outputs for every candidate

Day-block bootstrap (20,000 resamples, seed 7), confidence interval, multiple-testing correction, PF,
max DD, four contiguous walk-forward folds, best-5% removal, regime and session concentration, gross-mid
and net R, trade count, costs assumed, K at the time, dataset ids, commit SHA.

---

## 14. Analogue engine V2 (conditional similarity)

Audit: the unconditional engine found "analogues" at 0.5-0.65 of the median candidate distance in 6xW
dimensions (distance concentration): neighbours are only moderately closer than random windows, and the
study found no timing skill. More distance metrics will not fix that. V2 experiment, **defined now,
run only if an event family shows promise**:

* Candidate pool conditioned on: session, regime label, volatility bucket (ATR percentile tercile), H4
  trend sign, and event type. Query is matched only against compatible states.
* Compare, on identical queries, **unconditional vs conditional** k-NN, on the same barrier label, with
  `k` in {20, 50} (two variants).
* Success definition: conditional beats unconditional by a pre-set margin in **expected R after costs**
  AND the 7 criteria hold at Stage 2. Counts as 2 variants of K_V2.
* Multi-resolution (H1 shape + H4 context) is a Batch B option, not a Batch A item.

---

## 15. Machine learning plan

* ML does **not** start until at least one event family has a Stage 1 survivor.
* Where ML enters: **meta-labelling** (section 19) on a base event strategy, with the barrier label
  and event-level sampling; LR first, then RF / XGBoost / LightGBM, in the existing order, fixed modest
  hyperparameters, no tuning on Validation.
* Where ML does not enter: whole-market direction forecasting, any deep model (LSTM, TCN, Transformer,
  RL). **Rejected** unless a specific statistical reason is written down: current evidence says the
  limit is information and sample size, not model capacity.
* A probability never becomes an order directly (section 32).

---

## 16. Data acquisition plan

| Priority | Data | How | Cost | Why | Gate |
|---|---|---|---|---|---|
| 1 | Same-broker cross-assets (XAGUSD, EURUSD, USDJPY, an index, a USD index if listed) H1/M15 history | existing read-only MT5, `symbols_get` probe then `fetch_history.py` | free | same clock, no alignment problem; conditioning only | Batch B (H14) |
| 2 | Depth of M1 and ticks | read-only probe of `copy_rates_range` M1 and `copy_ticks_range` | free | tells whether fine-resolution research is feasible | P0 probe (owner approves the read-only calls) |
| 3 | **Scheduled-event calendar**: FOMC, CPI, NFP, PCE, Fed speakers, as dates and times | compile from official schedules (BLS, Fed), file with coverage header | free, owner/AI | scheduled events are published in advance: point-in-time safe by construction; no revised "actual" needed for event windows | Batch B (H13), and news guard |
| 4 | Second broker (MT5 demo, different server) | owner opens a demo, read-only fetch with the same tool | free | Broker Robustness gate only | survivors only |
| 5 | Tick data / paid feeds | none | cost | execution realism | **not recommended** before a candidate survives |

Not recommended: paid data purchases because the current result is negative.

---

## 17. News data requirements (research-grade)

Per event: name, category, release timestamp (UTC), impact, currency, `actual`, `forecast`, `previous`,
`available_at`, source provenance. Point-in-time rule: a decision at `t` may use only rows with
`available_at <= t`. Phase 1 needs only **timestamps and categories of scheduled events** (they exist
months ahead, so `available_at` is early by construction); `actual/forecast/previous` are optional for
H13 and must carry the real publication time. The existing loader (`news/pit.py`, `news/update.py`)
already enforces `available_at` and refuses rows later than the decision time; it has no data.
Revisions must never overwrite values seen at the time (append-only). FTMO funded news restrictions are
unverified; do not design a trading rule around news windows before they are known.

---

## 18. Cross-asset architecture (smallest viable)

Optional experiment module `research/cross_asset.py`. Instruments from the same broker; each series is
its own immutable dataset with hash. Timestamp alignment: all in UTC after the broker-clock conversion
used for XAUUSD; join with `join_asof` on closed-bar `available_at` (bar close), never on open time.
Missing data: forward-fill **at most one bar**, otherwise the feature is null and the event is skipped
(logged). Market-hours differences: index CFDs closed when gold trades; features null in closure.
Normalisation: ATR-scaled returns and rolling z-scores computed on past bars only. Each cross-asset
variable must prove **incremental value** over the base event strategy by ablation (section 19);
otherwise it is removed.

---

## 19. Feature governance, meta-labelling, ablations

* **No feature zoo.** A feature enters only with: mechanism, causal timing, version, ablation result.
* Required for candidates: permutation importance on Validation-2, group ablation (remove a feature
  group, re-run), and a **fragility check**: if removing one feature destroys performance, treat it as
  fragility unless the mechanism explains it.
* **Meta-labelling**: base strategy emits candidate trades; a meta model outputs TAKE/SKIP using context
  (regime, session, volatility, spread, distance to levels, HTF alignment, analogue statistics). Compare
  base vs base+meta on **the same events** out of sample. Outcome information must not be reused: the
  meta model trains on past events only, with purged and embargoed folds (embargo >= timeout `N`).

---

## 20. Unvalidated override, FTMO funded track, compliance versus alpha

* The owner-override path (ADR-0020, D2) lets an UNVALIDATED strategy trade a funded account at <=0.25%
  risk, tier <=2. The only strategy it could name, H03-c1.0, has pessimistic mean net R **-0.066** on
  Val-H and no live implementation. **It is not a profitability candidate and must not be recommended as
  one.** It may be used **only for execution-plumbing experiments, only with explicit owner
  authorisation, preferably on demo.**
* Funded compliance is a **separate track** and must not dominate research. Pending in
  `configs/prop/ftmo_funded.yaml` (all `must_verify`, none verified): daily loss limit, max loss limit,
  max loss kind, daily reset, EA/automated trading, AI tools, request definition and limit, news trading
  window, market-close margin, weekend/overnight holding, hedging/opposite positions, funded consistency
  rule, account access/copy trading. Other compliance items: `MT5_TRADE_PASSWORD`, rotation of the demo
  password that was once exposed, Telegram, NSSM install, 14-day soak, 4-week demo, go-live checklist
  signature.
* Compliance makes a bot allowed to run; it creates no edge.

---

## 21. Robustness gates (all additive, apply to every candidate)

| Gate | Test | Pass condition (fixed before use) |
|---|---|---|
| **Cost Stress** | rerun at base, 1.5x and 2.0x spread and slippage; one-bar delayed entry; worse fills (adverse 1 tick extra) | mean net R > 0 at 1.5x and delayed entry; mean net R >= -0.02 R at 2.0x |
| **Parameter stability** | all grid neighbours of the chosen variant | every neighbour mean net R > 0 and >= 50% of the best; a single lucky spike fails |
| **Temporal stability** | by year and by quarter, by regime and session | positive mean R in >= 70% of calendar years; no year > 40% of total profit; reported quarterly |
| **Broker robustness** | same frozen strategy on broker B, no retuning | same sign, mean R >= 50% of broker A, intervals overlap, trade count within 30%, spread-sensitivity reported |
| **Leakage** | repaint and future-garbage tests on the event detector | identical events |
| **Era-correct costs** | swap and spread by era | applied before any claim |

---

## 22. Experiment budget and K ledger v2

* One ledger `docs/research/edge-program-v2/ledger.md`, append-only, owner of K for V2. It contains the
  legacy counters as read-only history: baselines K=3, analogue exploratory, ML K 7..10, Programme 1 K
  21, with their data corpora.
* `K_V2` = declared V2 variants (<= 48). Every run, including failed or abandoned ones, is a row.
* **A diagnostic run on burned data (section 5.2 checks) is Class D**: descriptive, cannot confer
  evidence, cannot be used to reopen a failed hypothesis, **not** counted in K. Any claim of evidence
  must come from Stage 2 on Test-H.
* Changing agents, sprints or branches does not reset K. The programme refuses to start a run if the
  ledger and code disagree (guard in the runner, as for the holdout).
* Hard cap: when `K_V2` reaches its declared cap or all 8 hypotheses are used, the programme stops
  (section 28).

---

## 23. Holdout, forward test, demo calibration, edge decay, lifecycle

### 23.1 Holdout governance

The holdout (2026-05-01..2026-10-07) is an asset. A holdout run requires beforehand: frozen strategy
code, frozen parameters, frozen dataset ids, frozen evaluation rules, the commit SHA, a strategy-registry
entry, a **Test-H PASS**, and an **independent review approval** (a different agent or person: sign-flip,
hand-checked trades from raw bars, gross vs net, leakage and repaint tests). One candidate, one run,
one decision. No iteration.

### 23.2 Forward test (paper) as part of the research

Per candidate compare **expected vs realised**: signal frequency, mean R, MFE, MAE, spread assumed vs
observed, slippage assumed vs observed, fill delay. Report these, not account P&L. Minimum evidence:
>= 100 forward trades (existing guard) **and** realised mean R inside the Stage 2 interval with a
cost-adjusted tolerance; fewer trades means "inconclusive", never "pass".

### 23.3 Demo execution calibration (code readiness is not broker reality)

Separate **code readiness** (done on fakes) from **broker-reality readiness** (nothing yet): one smoke
order, reconciliation, measured spread/slippage/commission/swap, order latency, rejection rate, partial
fills, terminal restart, network loss. Measured values feed `CostModel` and the era tables; the backtest
is re-run on the new costs **as a new Class D diagnostic** (not as evidence). Owner supplies
`MT5_TRADE_PASSWORD`; the smoke script exists.

### 23.4 Edge decay monitoring and demotion

Rolling expectancy (R), profit factor, Sharpe, drawdown, feature drift, regime drift, signal-frequency
drift and cost drift, each against the Stage 2 interval. States: **VALIDATED -> WATCH -> DEGRADED ->
DISABLED -> RESEARCH**. Rules (fixed before deployment): WATCH when rolling-60-trade mean R falls below
the lower bound of the validated interval; DEGRADED after 2 consecutive WATCH windows or a cost drift
above 1.5x; DISABLED by the kill switch policy or when drawdown exceeds the validated DD by 1.5x. A
strategy must be demotable by a command, and promotion back only through a new ledger entry.

### 23.5 Strategy lifecycle

`RESEARCH -> REJECTED | PAPER -> DEMO -> VALIDATED -> FUNDED -> WATCH -> DISABLED -> RETIRED`.
`PAPER` needs Test-H pass and holdout pass; `DEMO` needs the forward sample; `VALIDATED` is an
evidence status (evidence gate), not a promotion by itself; `FUNDED` needs the rollout tiers and the
signed go-live checklist.

---

## 24. Operations, architecture after the edge, deferred work

### 24.1 Product architecture after an edge exists (contracts)

Forecast Engine (outputs calibrated barrier probabilities with `n`, intervals, provenance) -> Edge
Engine (answers "is there validated evidence for this strategy id, config hash, dataset hash?") ->
Decision Engine (BUY/SELL/WAIT with explanation, `evidence_status`) -> Risk Engine (sizing, FTMO limits,
kill switch; independent of the forecast) -> Execution Engine (bridge, intent, executor, reconcile).
Each layer has its own typed contract (already roughly so in code); **a model probability can never
reach the executor except through all four.**

### 24.2 Operations plan (only after a candidate exists)

14-day dry-run soak (needs: Telegram, NSSM, news file, health checks), 4-week demo with signal orders,
reconciliation and cost measurement, then funded rollout tiers (shadow, minimum lot, 0.25%, validated
sizing). Details live in `docs/operations/`.

### 24.3 DEFERRED WORK (frozen unless it unblocks research)

| Item | Why deferred |
|---|---|
| Dashboard polish, animations, extra charts, more web features | no relation to edge |
| New indicator libraries / feature zoo | adds correlated information, raises K |
| Funded automation beyond the existing lock | nothing to automate without an edge |
| Cloud architecture, Docker, additional services | no research value |
| Deep learning | no statistical reason (section 15) |
| Paid data | not justified by a negative result alone |
| Funded rollout work | blocked on owner actions and on a candidate |
| Live implementation of H03-c1.0 | it is not a profit candidate |

---

## 25. Sprint roadmap

Sizes: S (<= 1 day of AI work), M (2-4 days), L (>= 1 week). Priority: P0 must happen first, P1 core,
P2 conditional. "AI" = agent implementation time; calendar time listed separately in section 28.

### P0. Repository, data and research-state audit (M, P0)
* **Objective.** Close the validity doubts of section 5.2 without creating evidence.
* **Why.** A negative result that is partly a cost/clock/data artefact would send the programme the
  wrong way.
* **Files.** new `scripts/forensics_*.py`, `docs/research/edge-program-v2/00-forensics.md`; read-only
  use of `market_data/`, `backtest/costs.py`, `strategies/edge_program.py`.
* **Dependencies.** none.
* **Tasks.** (1) per-year broker-clock inference on H1 (`infer_broker_clock` candidates, closure and
  weekend-bar profile) and per-year daily-break detection; (2) data certificate per split (missing-bar
  fraction, gaps, `ENTRY_GAP` counts) for Dev-2/Val-2/Test-H **without reading prices as outcomes**;
  (3) cost-attribution on the 18 Programme-1 variants, **Class D**: gross-at-mid R, era-correct swap
  sensitivity (swap 0, -20, -76 long), spread-floor sensitivity; (4) read-only probe of M1 and tick
  depth and of the symbol list; (5) reconcile K ledgers into `ledger.md` v2.
* **Tests.** unit tests for each forensic function with fixtures; clock inference regression test on
  synthetic series with a known offset change.
* **Statistical checks.** none that confer evidence; outputs are descriptive tables.
* **Acceptance.** a report that states, per year, the clock/offset and daily break; a swap/spread
  attribution table; a go/no-go on whether H01/H02 and session hypotheses are valid for each year;
  M1/tick depth known.
* **Red-team.** Does a forensic run leak knowledge into design? (Class D rules; no new hypothesis is
  chosen from these tables.)
* **Owner action.** approve the read-only MT5 probes (D-2).
* **DoD.** committed report, ledger v2 skeleton, no change to `edge-criteria.md`.

### P1. Profitability gate v2 and the research harness (M, P0)
* **Objective.** Make tests that can see +0.10 R and say so up front.
* **Files.** `evaluation/power.py` (new), `evaluation/event_study.py` (new), `docs/evals/edge-criteria.md`
  (append V2 appendix only), `experiments/` (K ledger v2 guard).
* **Tasks.** MDE/power calculator wired into pre-registration; day-block event-study inference; gross-mid
  and net R columns in trades/events; era-correct cost model (swap and spread by era) as a **new** cost
  profile, old one kept for reproducibility; Class D marker in the registry; guard that refuses runs on
  Test-H/holdout without the freeze record.
* **Tests.** planted-edge power test at event level (a +0.10 R planted effect is found at n_eff >= 2,300
  and a null is not); guards tested.
* **Acceptance.** `evaluation/power.py` reproduces the table in section 5.1; criteria file diff is
  append-only.
* **Red-team.** Does the event study double count overlapping outcomes? (dedupe and day-block tests.)
* **DoD.** merged, CI green.

### P2. Event framework (M, P0)
* **Objective.** Causal, repaint-free event detectors for PDH/PDL, Asia H/L, compression, session edges.
* **Files.** `events/` (new package), `outcomes/engine.py` (barrier labels), tests.
* **Tasks.** detectors with era-aware sessions, one-event-per-level-per-day rule, barrier label builder
  (frozen constants, section 11), repaint and leak tests.
* **Acceptance.** detector tests pass; event counts per year printed.
* **Red-team.** Do detectors use bar highs/lows that were not yet known at the decision bar close?

### P3. H07/H08 liquidity research (M, P0)
| Field | Content |
|---|---|
| Objective | Test sweep-reject (H07) against break-accept (H08) on one event set |
| Why | highest information value (section 9.5); a fork informative either way |
| Files | `docs/research/edge-program-v2/hypotheses/H07.md, H08.md`, ledger rows, `scripts/run_edge_v2.py`, `events/levels.py` |
| Dependencies | P1, P2 |
| Tasks | pre-register (commit first); Stage 1 on Development-2 for 12 variants; Holm 0.10; write results; no Validation-2 look before Stage 1 is final |
| Tests | detector tests from P2; runner refuses a run with an uncommitted hypothesis file |
| Statistical checks | n_events and MDE stated before; gross-mid vs net; by session and regime; day-block CI |
| Acceptance | every variant has a ledger row; result reported in the pre-registered direction only |
| Red-team | Is the fork direction fixed beforehand? Is the clock valid for every era used? Are events independent across days? |
| DoD | report committed, ledger updated, no criteria changed |
| Owner action | none |

### P4. H09 session-transition research (M, P1)
| Field | Content |
|---|---|
| Objective | Test range-position-conditioned session transitions |
| Why | plausible mechanism; builds on H02's failure with added conditioning |
| Files | `hypotheses/H09.md`, `events/sessions.py` |
| Dependencies | P0 clock certificate for the eras used (hard block), P2 |
| Tasks | restrict to certified eras; pre-register; Stage 1; exclude scheduled news days when a calendar exists |
| Tests | session boundary tests per era; DST edge tests |
| Statistical checks | as P3 plus per-era consistency |
| Acceptance | as P3 |
| Red-team | Are results driven by one era? Does the direction rule depend on the outcome? |
| DoD | as P3 |
| Owner action | none |

### P5. H10 conditional volatility research (M, P1)
| Field | Content |
|---|---|
| Objective | Test volatility compression conditioned on session and H4 trend |
| Why | volatility clustering is the most robust effect; also reports magnitude information usable as a filter |
| Files | `hypotheses/H10.md`, `events/volatility.py` |
| Dependencies | P1, P2 |
| Tasks | pre-register; Stage 1; additionally report the skill of predicting absolute return (descriptive) |
| Tests | ATR ratio causality (only past bars) |
| Statistical checks | as P3 |
| Acceptance | as P3 |
| Red-team | Is this H03 again? What do session and trend add? |
| DoD | as P3 |
| Owner action | none |

### GATE A (after P3-P5): any Stage 1 survivor at Holm 0.10 on Development-2?
No: Batch A stops; Batch B only with a data justification (P7). Yes: P6.

### P6. Validation of survivors (M, P0 if Gate A yes)
| Field | Content |
|---|---|
| Objective | Stage 2 on Validation-2: seven criteria unchanged, all four robustness gates in descriptive mode |
| Why | converts a screen into a testable trading claim |
| Files | `evaluation/edge_program_v2.py`, ledger |
| Dependencies | Gate A yes |
| Tasks | run each surviving pre-registered variant once per cost scenario; produce the full candidate report |
| Tests | criteria unchanged (golden tests from `evaluation/edge.py`) |
| Statistical checks | section 13.4 list; K_V2 as declared |
| Acceptance | verdict per variant; survivors listed with gross and net |
| Red-team | an independent reviewer re-checks every survivor (sign flip, hand-computed trades) |
| DoD | review file committed |
| Owner action | none |

**GATE B**: any Stage 2 survivor? No: stop or P8. Yes: P9.

### P7. Data expansion, only if justified (S to M, P1)
| Field | Content |
|---|---|
| Objective | Add exactly the data a surviving mechanism lacks |
| Why | information, not volume |
| Files | `scripts/fetch_history.py` (read-only), `research/cross_asset.py`, calendar file |
| Dependencies | a written mechanism gap from Gate A or B; D-2 approved |
| Tasks | fetch same-broker cross-assets; compile the scheduled-event calendar; M1 only if probed and executable |
| Tests | alignment and join tests; `available_at` guard tests |
| Statistical checks | each new variable must show incremental value by ablation |
| Acceptance | immutable datasets with hashes; manifest committed before any use |
| Red-team | timestamp leakage; closure handling; is this a way to keep searching after negative results? |
| DoD | manifest and tests merged |
| Owner action | scheduled-event source choice (D-5) |

### P8. Batch B hypotheses H11-H14 (M each, P2)
| Field | Content |
|---|---|
| Objective | Test the second batch only if Batch A found nothing and P7 produced data |
| Why | a finite second chance, not an open search |
| Files | `hypotheses/H11..H14.md` |
| Dependencies | Gate A no, P7 done |
| Tasks | same protocol as Batch A; H14 only as a filter on survivors |
| Tests and checks | as P3 |
| Acceptance | as P3; the stop conditions of section 28 apply after P8 |
| Red-team | budget cap respected? |
| DoD | as P3 |
| Owner action | none |

### P9. Locked Test-H (S, P0 if a candidate exists)
| Field | Content |
|---|---|
| Objective | One confirmatory run per candidate |
| Why | the only unburned historical confirmation set |
| Files | freeze record `docs/research/edge-program-v2/freeze-<id>.md` |
| Dependencies | Gate B yes |
| Tasks | freeze code, params, dataset ids, rules, SHA; run once; Holm across candidates; robustness gates binding |
| Tests | the runner refuses without the freeze record and without a prior Stage 2 pass |
| Statistical checks | seven criteria, cost stress, parameter stability, temporal stability |
| Acceptance | verdict recorded; a failure ends the candidate |
| Red-team | was anything tuned after seeing Validation-2? |
| DoD | verdict committed |
| Owner action | none |

### P10. Holdout review (S, P0 if P9 passes)
| Field | Content |
|---|---|
| Objective | Independent review, then one run on 2026-05-01..2026-10-07 |
| Why | final historical decision |
| Files | `review-<id>.md` |
| Dependencies | P9 pass |
| Tasks | sign flip, hand-checked trades from raw bars, gross vs net, leakage and repaint tests; then run once |
| Tests | holdout guard (existing) plus freeze check |
| Statistical checks | same criteria; compare with the Test-H effect size |
| Acceptance | pass means PAPER; fail ends the candidate |
| Red-team | is the reviewer independent of the author? |
| DoD | decision committed |
| Owner action | approve the single holdout run |

### P11. Forward paper (L, P1, calendar-bound)
| Field | Content |
|---|---|
| Objective | Compare expected with realised on new data |
| Why | live-like evidence without capital |
| Files | live signal implementation for the candidate, parity tests, `scripts/forward_test.py` |
| Dependencies | P10 pass |
| Tasks | implement the live generator behind the strategy registry; parity test between research and live code on identical bars; run daily; report the section 23.2 metrics |
| Tests | parity test on a year of bars: identical signals |
| Statistical checks | at least 100 trades; realised mean R against the Stage 2 interval |
| Acceptance | realised consistent with expected, otherwise the candidate is DEGRADED |
| Red-team | repainting in live versus backtest; clock offsets |
| DoD | report committed |
| Owner action | keep the machine running |

### P12. Demo execution calibration (M plus calendar, P1)
| Field | Content |
|---|---|
| Objective | Measure real costs and the reality of the order path |
| Why | the backtest costs are assumptions |
| Files | `scripts/smoke_demo_order.py` (exists), cost calibration notebook, ADR-0015 update |
| Dependencies | P11 started; the owner supplies `MT5_TRADE_PASSWORD` |
| Tasks | smoke order; measure spread, slippage, commission, swap, latency, rejects, partial fills; terminal restart and network loss drills |
| Tests | calibration math on recorded fills |
| Statistical checks | measured cost against the Cost Stress tolerance |
| Acceptance | reject/UNKNOWN under 2%; costs inside the gate |
| Red-team | demo fills are not live fills |
| DoD | ADR updated |
| Owner action | trade password; run the smoke command |

### P13. Operational soak (calendar, P1)
| Field | Content |
|---|---|
| Objective | 14 days of dry-run with a network cut and a terminal restart, then 4 weeks of demo orders |
| Why | uptime and recovery evidence |
| Files | existing operations runbooks |
| Dependencies | P12; Telegram and NSSM installed by the owner |
| Tasks | run; collect uptime, duplicate bars, recoveries |
| Tests | none new |
| Statistical checks | uptime at least 99% of M15 bars, 0 duplicate bars |
| Acceptance | per `docs/operations/go-live-checklist.md` |
| Red-team | unattended failure modes |
| DoD | checklist items filled |
| Owner action | install services, create the Telegram bot |

### P14. Controlled funded readiness (compliance track, P2, blocked on the owner)
| Field | Content |
|---|---|
| Objective | Allow a VALIDATED strategy through the rollout tiers |
| Why | compliance, not alpha |
| Files | `configs/prop/ftmo_funded.yaml`, `configs/execution/rollout.yaml` |
| Dependencies | a VALIDATED strategy and the signed checklist |
| Tasks | the owner verifies the 13 rules with FTMO and records `verified_official`; tiers 0 to 3 under the lock |
| Tests | the existing authorisation matrix |
| Statistical checks | Monte Carlo risk from the validated trades |
| Acceptance | each tier's exit criteria met |
| Red-team | funded rules change over time |
| DoD | tiers promoted by the owner |
| Owner action | everything that touches FTMO or capital |

---

## 26. Dependency graph

```text
P0 forensics ──┬─> P1 gate v2 ──> P2 events ──> P3 H07/H08 ──┐
               │                                P4 H09 (needs P0 clock cert) ├──> GATE A ─no─> P7? -> P8 (Batch B) -> GATE A'
               └─ M1/tick/symbol probe ──────> P7              P5 H10 ───────┘            └yes> P6 validate -> GATE B -no-> stop/P8
GATE B yes -> P9 Test-H -> P10 holdout -> P11 forward -> P12 demo calibration -> P13 soak -> P14 funded readiness
```

---

## 27. Owner actions, AI actions, calendar-time actions

| Owner only | AI can do | Calendar time |
|---|---|---|
| Approve D-1..D-5 (Appendix A) | all of P0-P6, P8 code and runs | forward paper (weeks), demo (>= 4 weeks), soak (14 days) |
| Approve read-only MT5 probes (M1/tick depth, symbols) | P1-P2 frameworks | edge-decay windows |
| Open a second broker demo (only for survivors) | calendar compilation from official schedules (needs owner source choice) | Test-H and holdout are instant; forward is not |
| Supply `MT5_TRADE_PASSWORD`; rotate the exposed demo password | live parity implementation (after a candidate) | |
| Verify the 13 FTMO rules with FTMO | | |
| Create Telegram bot, install NSSM | | |
| Decide on funded override signing (D2) | | |

## 28. Cost, time and stop conditions

**Engineering effort (AI time, not calendar).** P0 2-4 days, P1 2-4, P2 2-4, P3 2-4, P4 1-3, P5 1-3, P6 1-3,
P7 1-3, P8 each hypothesis 1-3 days, P9-P10 1 day, P11 3-6 days, P12 2-4 days. Whole of Batch A through
Gate A: about 2-3 weeks of AI work. **Data cost:** $0 for everything except an optional second-broker
demo (free) and paid feeds (not recommended). **Infrastructure:** none until a candidate (a VPS for the
soak, order of $20-40 per month, owner-paid). **Calendar time:** forward evidence >= 100 trades at the
observed event rates is **weeks to months** (e.g. H03-style 26-40 trades a year would take years;
event families with 1-4 events per day take weeks); demo 4 weeks; soak 14 days. Do not read any of this
as "validated in days".

**Stop conditions (research stops, honestly).**
1. All 8 V2 hypotheses used with no Stage 2 survivor, or K_V2 at its cap: record **NO EDGE FOUND within
   OHLC bars of one broker**; stop alpha search in this data class.
2. Any pre-registration whose MDE exceeds +0.20 R at K_V2 and cannot be given more data: dropped.
3. A candidate fails Test-H: that candidate ends; no retune.
4. Holdout fails: candidate ends; programme reviewed, not repeated.
5. Evidence of an artefact (clock, cost, leakage) in a candidate: its result is voided.
Reopening after a stop needs a **new data class** (tick/order flow, second broker with different
microstructure, alternative data) and a new budget approved by the owner.

## 29. Go / No-Go tree

```text
P0 finds a material bug/artefact in Programme 1?
   YES -> record, fix, and the affected hypotheses may be RE-REGISTERED as new V2 variants (counted)
   NO  -> continue
Batch A Stage 1 survivor (Holm 0.10)?
   NO  -> data justification for Batch B?  YES -> P7, P8   NO -> STOP (section 28.1)
   YES -> Stage 2 on Validation-2: 7 criteria + gross/net + robustness (descriptive)
          PASS? NO -> candidate REJECTED, next survivor / Gate A'
                YES -> Test-H once
                       PASS? NO -> REJECTED   YES -> independent review -> holdout once
                                            PASS? NO -> REJECTED   YES -> PAPER (forward >= 100 trades)
                                                                   realised ~ expected? NO -> DEGRADED/RESEARCH
                                                                                          YES -> DEMO calibration (reject/UNKNOWN < 2%)
                                                                                                 costs within Stage 2 tolerance? YES -> VALIDATED
                                                                                                 -> funded rollout tiers (owner signs)
```
Capital is never exposed before **VALIDATED + signed checklist + rollout tiers 0-1 clean**.

---

## 30. Red team findings (separate pass, plan revised accordingly)

| # | Question | Finding | Plan change |
|---|---|---|---|
| R1 | Are we overfitting the research process itself? | Dev-2/Val-2 data already informed Programme 1; V2 reuses it for design | Test-H is the only confirmatory set; Dev-2/Val-2 labelled burned; diagnostics Class D |
| R2 | Are hypotheses genuinely different? | H07 vs H08 are two sides of one event set; H10 builds on H03; H09 on H02 | declared; the fork H07/H08 counts as 2 variants x 3; H09/H10 must justify what H02/H03 lacked |
| R3 | Multiple-testing counted correctly? | legacy K split across counters | ledger v2; K_V2 declared up front; cap 48 |
| R4 | Buying more data just because results are negative? | possible | data bought only with a stated mechanism gap; paid data not recommended |
| R5 | Labels aligned with trading outcomes? | direction label was not | barrier labels primary |
| R6 | Broker artefact? | one broker, one spread feed, one clock, one rollover | Broker Robustness gate; second demo for survivors |
| R7 | Could spread destroy everything? | cost per trade 0.03-0.07 R at H1/M15; worse intraday on M5 | stress gate; prefer H1/H4 events; event spreads by hour |
| R8 | Realistic sample size? | section 5.1 | MDE in every pre-registration; underpowered-by-design rule |
| R9 | Session effects as timezone artefacts? | yes, suspected for pre-2021 | P0 clock certificate before any session hypothesis; H09 blocked until then |
| R10 | News look-ahead? | loader forbids it; scheduled-event design avoids revisions | `available_at` guard kept; no `actual` values in Phase 1 |
| R11 | Cross-asset timestamp leakage? | open-time joins would leak | join on bar close; null on closures |
| R12 | Do event detectors repaint? | swing-based ones can | repaint and future-garbage tests mandatory (P2) |
| R13 | HFT-like effects impossible from Python/MT5? | sweeps resolved in seconds are not executable at M15/H1 cadence | restrict to H1+ events; M1/tick only if executable latency is measured |
| R14 | Stage 1 liberal alpha a back door? | it could inflate false survivors | Stage 1 cannot confer evidence; Stage 2 and Test-H unchanged |
| R15 | Is the "no edge" stop honest? | yes but can become a way to quit early | stop only per section 28 and only after Batch A and (if justified) Batch B |
| R16 | Does Class D let us peek? | risk of design leakage | Class D outputs cannot choose new hypotheses; reviewed at P1 |
| R17 | Is the Test-H still pristine? | no code path has read 2022-2025 outcomes; M15 in that window exists but unused | freeze record plus guard; confirm by registry audit in P0 |

### 30.1 Five perspectives

| Perspective | Top concern | Top opportunity | Top rejection reason |
|---|---|---|---|
| Quant researcher | underpowered tests, reused data | event-level screening, barrier labels | any plan that tunes on Dev-2/Val-2 after seeing it again |
| Statistician | K accounting and dependence between overlapping events | Holm screening + day-block bootstrap | declaring survivors from a single lucky parameter |
| Trader | execution realism: swap, spread, news, sessions | H07/H08 on levels traders actually watch | strategies needing sub-minute execution |
| Software architect | adding code with no research value | small harness; strict freeze guards | new services before a candidate exists |
| Risk manager | trading a negative-expectancy override on a funded account | rollout tiers and kill switch exist | any funded exposure before VALIDATED |

Reconciliation: the researcher and statistician want more events and honest K; the trader wants
executable, session-aware ideas; the architect and risk manager want nothing built or exposed ahead of
evidence. The plan satisfies all five: events and power first (researcher, statistician), executable H1+
mechanisms (trader), a small harness (architect), exposure only after VALIDATED (risk).

---

## 31. Final recommendation, choices made

**Next research families (ranked): H07/H08, H10, H09, then (Batch B) H12, H11, H13, H14; analogue V2
last.** **Next data (ranked): same-broker cross-assets (conditioning only, Batch B), M1/tick depth probe
(P0), scheduled-event calendar, second broker (survivors only), no paid data.** **Next engineering
(ranked): event study + power harness, clock/data certificates, era-correct costs and gross-at-mid, K
ledger v2 and freeze guards, live parity only after a candidate.**

**Recommended first sprint: P0** (audit and forensics, no strategy code).

No claim in this document is a promise of profit. A candidate is a candidate; evidence is the seven
criteria on Test-H, one holdout run and a forward sample; "not validated" and "no edge found" are
acceptable outcomes.

---

## Appendix A: owner decisions (referenced from the front matter)

| ID | Decision | Recommended |
|---|---|---|
| **D-1** | Approve Edge Program V2: budget (<= 8 hypotheses, Batch A = H07-H10, <= 48 variants), two-stage inference (Stage 1 Holm screening is additive, the seven criteria unchanged), Test-H as the sole confirmatory set, Dev-2/Val-2 labelled burned, Class D rule | Yes |
| D-2 | Approve **read-only** MT5 probes: M1 and tick depth, symbol list (no orders, no account data printed) | Yes |
| D-3 | Treat funded and web-control work as frozen except bug fixes | Yes |
| D-4 | Do not use the UNVALIDATED override for profit; at most for demo plumbing | Yes |
| D-5 | Provide a scheduled-event calendar source later (not needed before Batch B) | Defer |

## Appendix B: facts used and where to check them

Section 4: `docs/reports/checkpoint-1.md`, `docs/research/model-evaluation.md`,
`docs/reports/sprint-7-report.md`, `docs/research/edge-program/ledger.md`, `final-verdict.md`.
Section 5.1: arithmetic on the normal distribution (z(1-0.05/K) + z(0.8)) x 1.3 / sqrt(n), sd from
checkpoint-1 baselines. Section 5.2.2: closure-bar counts computed in this pass from
`data/research_history` H1 with the NY+7 calendar of `configs/brokers/ftmo_demo.yaml`: 2013-2020 about
514 per year, 2022-2024 about 257. Section 3 test count: `pytest --collect-only -m "not mt5"` = 1,734
(tests not run in this pass). CI state on the remote could not be queried (network timeout), so the
claim "CI green" is **not** made here.
