# Trend recognition and alert gap audit (2026-10-12)

Question: "XAU EDGE sees H1 up / M30 up, why no BUY or SELL?" Scope: explanation, bias vs action, funnel, alerts. No threshold, gate or detector was changed. No Test-H / Holdout, no outcome metric, no PnL.

## 1. Executive verdict

**Correct WAIT plus a human-communication defect (class C).** The system did see an H1 uptrend (BULLISH). A BUY needs five more things and the desk had none of them: a normal spread/volatility regime, an M15 pullback inside the trend, an M5 trigger, a clean M1, and a plan with room and R:R. The screen hid this: the funnel stopped at the first failure and marked "H1 direction" as "not reached" while H1 was BULLISH, and the headline "đạt 1/8" read like "the bot sees nothing".

Recommendation: **A (no algorithm change); explanation and alert gaps only.** Done in this round: a whole-funnel diagnostic and a bias-versus-action line. Alerts: gaps listed, not built (needs the owner's choice, section 11).

## 2. Current strategy architecture (verified in code, `baseline.py::decide`, v1.1.0 live)

| Layer | Role | Source |
|---|---|---|
| Gates (market, data, news, spread POOR, volatility LOW/HIGH, H4 blocked regimes, cooldown, limits) | run first | `_gates` |
| H1 | the only source of direction (BULLISH to BUY, BEARISH to SELL, else NO_DIRECTION) | `decide` step 1 |
| H4 | veto only: TREND_DOWN vetoes BUY, TREND_UP vetoes SELL; RANGE never vetoes | `BLOCKING_H4`, step 2 |
| M30 | display only, not in any condition | `chain` text |
| M15 | setup: structure not against H1 and pullback inside the trend | step 3 |
| M5 | trigger: momentum with the trend | step 4 |
| M1 | execution quality, can only block | step 5, `m1_execution_state` |
| Then | room, stop, R:R, risk | levels / sizing |

## 3. Screenshot diagnosis (live API at 00:06 UTC, 2026-10-12)

H4 RANGE, H1 BULLISH, M30 UP, M15 RANGE/NONE, M5 FLAT, M1 SPREAD_WIDE, spread 46 points, volatility LOW. Refusals: SPREAD_TOO_WIDE, VOLATILITY_TOO_LOW. The screenshot matches the API. Backend funnel (`why_wait.stages`): 1/8, "Spread & regime" FAIL, the other six NOT_REACHED.

## 4-7. Direction, setup, trigger, execution

- **H1 direction: GOOD.** Rule `close>EMA50 & EMA20>EMA50 & structure>=0` (`market_state.py`). Existing replay report (`TRADING_CORE_ACCEPTANCE.md`): H1 had a direction in 4056 of 5406 decisions (75%), so H1 is not too often neutral. On the live telemetry (4 days, 405 rows) H1 was BULLISH in all 405 with no flips, so flip rate and neutral duration cannot be judged from this sample; a replay on development data (not opened this round) is needed for that.
- **H4 role: CORRECT.** RANGE does not veto; only the opposite strong trend does (`BLOCKING_H4`, plus the TIMEFRAME_CONFLICT tests). The UI row "H4 / M15 đồng thuận" passes on RANGE.
- **M30: display only.** It is not among the 8 required stages; the checklist denominator has no M30 row.
- **M15 setup:** needs structure UP and PULLBACK_IN_UPTREND (BUY). First-refusal NO_SETUP is the largest bucket in the live telemetry (151 of 405) and 1311 of 5406 in the 2025 replay. Intentionally selective, not a defect; whether the definition is too narrow is a research question (section 14).
- **M5 trigger:** NO_TRIGGER is rare as a first refusal (35 of 405; 245 of 5406) because few decisions reach it.
- **M1 / spread gate:** doing its intended job. At 00:06 UTC the spread was 46 points against a 36-point median and a 44-point p90 of the last 300 M5 bars. The relative percentile rule (p90 and above) fires about one tenth of the time by construction, more in the thin Asian session. Whether it is calibrated to FTMO quotes is a calibration study (section 14), not a bug.

## 8. Current funnel (diagnostic, new, computed on the live decision)

| Stage | Status | Observed |
|---|---|---|
| Market & data | PASS | |
| Spread & regime | FAIL | WIDE / NORMAL |
| H1 direction | PASS | BULLISH |
| H4 / M15 alignment | PASS | H4 RANGE, M15 RANGE |
| M15 setup | FAIL | RANGE/NONE |
| M5 trigger | PASS | M5 up |
| M1 execution | FAIL | SPREAD_WIDE |
| Trade plan | not evaluated | |

4 of 8 required conditions met; primary blocker spread; also missing M15 setup and M1. The runtime still stops at the first failure for authorization; the diagnostic only explains.

## 9. Signal scarcity (no PnL)

Live telemetry, 4 files, 405 decisions, 0 BUY / SELL. First refusals: NO_SETUP 151, SPREAD_TOO_WIDE 131, MARKET_CLOSED 37, TIMEFRAME_CONFLICT 35, NO_TRIGGER 35. 2025 replay: VOLATILITY_TOO_LOW 1465, NO_SETUP 1311, VOLATILITY_TOO_HIGH 1015. **Top 3 bottlenecks: (1) the volatility/spread regime gates, (2) NO_SETUP (M15 pullback), (3) NO_DIRECTION / TIMEFRAME_CONFLICT.** Caveat: "first refusal" hides every later stage, which is why the whole-funnel diagnostic was needed. Scarcity is not a bug.

## 10. Human UX gap

| Check | Before | After this round |
|---|---|---|
| Bias separate from action | only a plain "Xu hướng: TĂNG" line | "Thiên hướng (H1): ▲ MUA · Hành động: CHỜ" with "Thiên hướng không phải quyền vào lệnh" |
| Funnel | H1 and later stages "chưa tới" when spread blocks | every stage judged from the recorded state; "chưa đánh giá" only when it cannot be (neutral H1, closed market, plan) |
| Missing list | first blocker only | primary blocker plus every other unmet stage |
| "1/8" | all eight are required (M30 is not in it); misleading only through "chưa tới" | 4/8 in this state, with the observed value per row |

Defect class: Human Decision UX defect (C), confirmed. The denominator itself is accurate.

## 11. Alert gap (code audit of `setup_alerts.py`, `engine.py`)

| Alert | Status | Evidence |
|---|---|---|
| BUY / SELL ready | IMPLEMENTED | `*_SETUP_READY`: side, entry, SL, TP, R:R, lot at the risk %, expiry, evidence line |
| Setup invalidated | IMPLEMENTED | `SETUP_INVALIDATED` for announced, untaken setups |
| TP / SL / other exits | IMPLEMENTED | `on_paper_close`: `PAPER_TP`, `PAPER_SL`, `PAPER_<reason>` |
| Position filled (paper open) | MISSING | no dispatch on open; a ready alert is not a fill |
| Setup armed | MISSING | the ARMED phase is in the UI only |
| Setup expired | MISSING | expiry only changes the UI |
| Bias emerged | MISSING | informational, optional |
| Stale data / broker failure | PARTIAL | ops monitor, not the trade-alert channel |
| Delivery | PARTIAL | Telegram not configured; file fallback `alerts.jsonl` |

Roadmap: MUST (position filled; critical failure into the same channel), SHOULD (setup armed, expired), OPTIONAL (bias, near TP/SL). No push for informational states by default (alert fatigue). Not built here: each needs a channel and wording decision from the owner.

## 12. Algorithm-change decision

Option A chosen. Criteria: causality (unchanged), interpretability (improved), false-action risk (none added), complexity (low), research contamination (none), information gain (high: shows the real bottleneck). Option B (lifecycle early warning) is partly present (ARMED phase); Option C is not justified by this evidence. No gate was lowered.

## 13-14. Recommended product changes and research-only candidates

Done: `diagnostic_from_signal` and `why_wait.diagnostic` (backend), bias/action line and whole-funnel rows (UI). Naming options for an early-warning label (not built, not a signal): "ĐANG THEO DÕI MUA" (clear, no permission), "THIÊN HƯỚNG MUA · CHƯA SẴN SÀNG" (explicit, long), "MUA? chưa đủ điều kiện" (short, ambiguous; rejected). Research questions only (V4, development data, no PnL): does the percentile spread/volatility gate over-block thin sessions; does the M15 pullback definition leave long stretches of an intact H1 trend without any setup; H1 flip rate and neutral duration.

## 15. MCP findings

Chrome DevTools MCP was **not run this round**. The live API was inspected over HTTP and the UI through Playwright. This is a gap against the brief (eight states at three widths); to be done before the next UI release.

## 16. Test evidence

- Python: `tests/unit/trading/test_diagnostic_funnel.py`, 8 tests (bullish and bearish NO_SETUP, spread block judges later stages, NO_TRIGGER, neutral H1, H4 RANGE vs opposite trend, closed market, ready trade). The function was also run on the real live decision payload (section 8).
- Playwright `e2e/bias_vs_action.spec.ts`: bullish, bearish, neutral at 1440x900 and 720x450; passed together with the terminal, ux_fixes2, trade08 and human_state specs (113 passed). 390 px was not run (phone is frozen by the scope decision).
- The live API (:8000) and dashboard (:3000) still run the previous build: the diagnostic reaches the screen after the next restart (not done while the market is open).

## 17. Roadmap

1. Restart the stack while the market is closed and run the MCP screenshots. 2. Owner choice: which of position-filled / setup-armed / setup-expired to send, and Telegram. 3. Replay study (development data) of the H1 flip rate and the gate calibration, as V4 questions.

## 18. Final verdict

H1 DIRECTION DETECTION: GOOD (75% of decisions have a direction in the 2025 replay; the live sample is too small for flips)
H4 REGIME ROLE: CORRECT
M15 SETUP DETECTION: NEEDS RESEARCH (selective by design; no formal false negative found)
M5 TRIGGER DETECTION: GOOD (rarely reached; no defect seen)
M1 EXECUTION FILTER: GOOD (works as specified; calibration is a study)
CURRENT SCREENSHOT STATE: bullish H1, thin session, wide spread and low volatility block; a correct WAIT, previously explained badly.
WHY NO BUY: spread regime blocked (46 points vs p90 44), M15 has no pullback (RANGE/NONE), M1 spread wide, plan not evaluated.
WHY NO SELL: H1 is BULLISH, so there is no sell direction.
TOP 3 BOTTLENECKS: 1. volatility/spread gates; 2. NO_SETUP; 3. NO_DIRECTION / TIMEFRAME_CONFLICT.
BIAS VS ACTION UX: PASS after this change (was NEEDS IMPROVEMENT)
DIAGNOSTIC FUNNEL: COMPLETE (backend and UI; live after restart)
BUY READY ALERT: COMPLETE
SELL READY ALERT: COMPLETE
SETUP ARMED ALERT: MISSING
POSITION FILLED ALERT: MISSING
TP ALERT: COMPLETE
SL ALERT: COMPLETE
ALGORITHM CHANGE: NO
RECOMMENDED NEXT STEP: restart on a closed market, run the MCP check, then decide which missing alerts you want.
VALIDATED EDGE: 0%
STATISTICAL DECISION TRUST: 0%
REAL-MONEY READINESS: 0%
OVERALL VERDICT: The desk was right to wait. It saw the H1 uptrend, but the spread/volatility regime, the missing M15 pullback and a wide M1 spread each forbade a BUY. The failure was the explanation, now fixed in code and tests; the detectors and gates are unchanged and no edge claim is made.
