# BUY/SELL symmetry, signal starvation, and UI roadmap

Date: 2026-10-12. Branch: `main`. Scope: current code -> current git -> current tests -> current decision logs -> current API/runtime -> current UI -> alerts -> Chrome DevTools MCP -> reports.

## 1. Executive verdict

BUY and SELL are both implemented end-to-end in the trading core, API payload, UI ready states, alert dispatcher, and PAPER desk. Synthetic tests can force both terminal decisions. No side-specific algorithm bug was found in the audited code path.

The live morning session did not produce BUY/SELL because the default v1.1 chain is extremely sparse and was mostly blocked by execution gates before setup/trigger authorization. This is signal starvation by design plus possible overfiltering/research questions, not proof of an implementation bug.

One production UI communication bug was found and fixed during this audit: the hero could say `TRUNG TÍNH` while the whole-funnel diagnostic and MTF strip correctly said H1 BUY bias. That made Human interpretation worse even though the algorithm was not neutral.

## 2. Git/runtime reality

`HEAD = origin/main = daf22f6238efe9049e49ae562354455954a66da0` before audit changes. Working tree was clean at start. Live dashboard HTML contained build SHA `daf22f6`, so runtime matched audited source before the UI patch. Recent relevant commit: `daf22f6 feat(ui): bias vs action cards, primary blocker, whole-funnel stepper, execution card, chart bias strip, PAPER_FILLED alert`.

After the audit patch, dashboard was rebuilt and the live stack restarted. Runtime now serves the patched build; Playwright verified hero bias text as `↑ MUA — chỉ là hướng thị trường nghiêng về, không phải lệnh`.

## 3. BUY path

BUY path exists:

H1 BULLISH -> `side="BUY", direction=1` in `baseline.py`; H4 veto only blocks `TREND_DOWN`; M15 requires `UP/PULLBACK_IN_UPTREND`; M5 requires `UP`; M1 may block but cannot reverse; room uses distance to resistance; entry uses ask; stop uses M5 swing low/ATR; target is above entry; `TradeDecision.BUY` gets a setup id, expiry, risk sizing and plan. See `src/xau_edge/trading/baseline.py:278`, `src/xau_edge/trading/baseline.py:315`, `src/xau_edge/trading/baseline.py:365`, `src/xau_edge/trading/levels.py:63`, `src/xau_edge/trading/levels.py:89`.

## 4. SELL path

SELL mirrors BUY:

H1 BEARISH -> `side="SELL", direction=-1`; H4 veto only blocks `TREND_UP`; M15 requires `DOWN/PULLBACK_IN_DOWNTREND`; M5 requires `DOWN`; room uses distance to support; entry uses bid; stop uses M5 swing high/ATR; target is below entry; `TradeDecision.SELL` flows to the same signal/API/UI/PAPER paths.

## 5. Symmetry matrix

| Row | BUY | SELL | Classification |
|---|---|---|---|
| Direction | H1 BULLISH | H1 BEARISH | SYMMETRIC |
| H4 veto | block TREND_DOWN | block TREND_UP | SYMMETRIC |
| M15 structure | UP | DOWN | SYMMETRIC |
| M15 pullback | `PULLBACK_IN_UPTREND` | `PULLBACK_IN_DOWNTREND` | SYMMETRIC |
| M5 trigger | UP | DOWN | SYMMETRIC |
| M1 execution | against-direction active candle blocks | mirrored | SYMMETRIC |
| Structure room | resistance | support | SYMMETRIC |
| Entry quote | ask | bid | INTENTIONAL ASYMMETRY |
| Swing stop | swing low | swing high | SYMMETRIC |
| Target | above entry | below entry | SYMMETRIC |
| R:R | same net formula | same net formula | SYMMETRIC |
| Risk sizing | abs(entry-stop) | abs(entry-stop) | SYMMETRIC |
| Expiry/setup_id | M5 trigger bar | M5 trigger bar | SYMMETRIC |
| Alert | `BUY_SETUP_READY` | `SELL_SETUP_READY` | SYMMETRIC |
| PAPER open | simulated buy | simulated sell | SYMMETRIC |
| PAPER close | bid-side close | ask-side close | INTENTIONAL ASYMMETRY |

## 6. Morning-session diagnostics

Source: `data/trade/decisions-20261012.jsonl`, 2026-10-12 00:00:21 to 05:03:26 UTC, 295 decisions.

Decisions: WAIT 295, BUY 0, SELL 0.

First refusal counts: `SPREAD_TOO_WIDE` 216, `NO_SETUP` 64, `VOLATILITY_TOO_HIGH` 13, `STALE_DATA` 2.

All overlapping refusal counts: `SPREAD_TOO_WIDE` 218, `NO_SETUP` 64, `VOLATILITY_TOO_HIGH` 45, `VOLATILITY_TOO_LOW` 15, `STALE_DATA` 2.

Context: H1 was BULLISH for all 295 rows; H4 RANGE for all 295. M15 was `RANGE/NONE` 173, `UP/NONE` 107, `UP/PULLBACK_IN_UPTREND` 15. M5 was FLAT 201, UP 49, DOWN 45. M1 was SPREAD_WIDE 218, QUIET 39, GOOD 38.

## 7. Signal funnel

Independent, non-overlap prefix funnel for today:

| Stage | Count reaching |
|---|---:|
| MARKET/DATA OK | 293 |
| EXECUTION REGIME OK | 34 |
| H1 DIRECTION | 34 |
| H4 NOT VETO | 34 |
| M15 ALIGNED | 9 |
| M15 SETUP | 0 |
| M5 TRIGGER | 0 |
| M1 EXECUTION | 0 |
| STRUCTURE ROOM | 0 |
| STOP VALID | 0 |
| RR PASS | 0 |
| RISK PASS | 0 |
| BUY/SELL READY | 0 |

The bottleneck was not a missing BUY implementation. The chain almost never got past execution + M15 setup simultaneously.

## 8. BUY near-misses

All 295 rows had BUY bias. Counts within H1 BULLISH rows: M15 aligned 122, M15 pullback/setup 15, M5 UP trigger 49, M1 GOOD 38, structure room pass 295, RR pass 295.

Nearest BUY misses included rows with H1 BULLISH + M15 UP + M5 UP, but spread was WIDE; and rows with execution GOOD but M15 stayed RANGE/NONE and M5 FLAT. No row had execution OK + aligned M15 + M15 pullback + M5 UP together.

## 9. SELL near-misses

There were no H1 BEARISH intervals in the current morning window, so no live SELL opportunity can be inferred from today. This is market-regime absence, not evidence of SELL-side code failure.

Replay/acceptance data does include SELL: v1.1 2025-08-04 to 2025-09-01 had decisions BUY 2 / SELL 3; v1.2.1 same window had BUY 2 / SELL 2; v1.2.1 2025-12-01 to 2025-12-29 had BUY 3 / SELL 1.

## 10. Spread gate

Today spread dominated: 218/295 rows had WIDE spread; first refusal `SPREAD_TOO_WIDE` was 216. Live API snapshot showed spread 46 points, spread percentile about 0.993, spread/ATR M5 0.158 versus threshold 0.15. Later Playwright snapshot showed spread 45 points, percentile 95.7%, spread/ATR M5 0.152.

Classification: INTENDED PROTECTION and POSSIBLE OVERFILTERING. Do not disable without research.

## 11. Volatility gate

Today volatility labels: NORMAL 235, HIGH 45, LOW 15. In v1.1 both LOW and HIGH are vetoes. Previous rally report was reproduced for 2026-10-11 22:10-23:49 UTC: 100 rows, all WAIT, all first refusal `SPREAD_TOO_WIDE`, all also had `VOLATILITY_TOO_LOW`, H1 BULLISH, mostly M15 REVERSAL_DOWN/NONE and M5 FLAT/DOWN.

Classification: BY DESIGN plus RESEARCH QUESTION. The ATR percentile gate can lag short impulse moves.

## 12. M15 setup

H1 was BULLISH all morning, but M15 pullback was present only 15/295 rows. M15 was more often RANGE/NONE or UP/NONE. The band itself is mirrored in `market_state.py`: bullish `-0.3 <= price_vs_ema_atr <= 0.7`, bearish `-0.7 <= price_vs_ema_atr <= 0.3`.

Classification: GOOD for symmetry; OVERFILTERING SUSPECTED for frequency.

## 13. M5 trigger

M5 trigger rules are mirrored: UP requires positive ROC and RSI > 52 with BOS/body support; DOWN requires negative ROC and RSI < 48 with mirrored BOS/body support. Today M5 UP appeared 49 rows and DOWN 45 rows, so no obvious polarity bug.

Classification: GOOD for polarity; same-bar alignment with M15 in v1.1 remains a starvation suspect.

## 14. v1.1 vs v1.2

Default runtime is v1.1. v1.2/1.2.1 are installed but inactive. v1.2 lifecycle arms M15 setup and allows later M5 trigger within a bounded window; v1.2 also treats LOW/HIGH ATR labels as warning/context rather than veto while preserving hard spread/abnormal protections.

Frequency evidence is mixed but useful: v1.1 August replay 5 signals, v1.2.1 August replay 4 signals, v1.2.1 December replay 4 signals. Lifecycle is conceptually useful for timing mismatch, but current evidence does not justify activating it automatically.

## 15. Alert coverage

Implemented: `BUY_SETUP_READY`, `SELL_SETUP_READY`, `SETUP_INVALIDATED`, `PAPER_FILLED`, `PAPER_SL`, `PAPER_TP`, and other PAPER close reasons via `PAPER_<reason>`. Both sides use the same `SetupAlerts.on_decision` dispatcher path in `src/xau_edge/trading/setup_alerts.py:94`.

Missing/recommended: `BIAS_CHANGED` optional, `SETUP_ARMED` mandatory for lifecycle adoption, `WAITING_TRIGGER` useful, `POSITION_FILLED` already covered as `PAPER_FILLED`, `SETUP_EXPIRED` mandatory, `STALE_CRITICAL` mandatory.

Alert coverage estimate: 6 implemented out of 11 desired event families = 55%.

## 16. UI/color audit

Required semantic language:

BUY bias: soft green. BUY ready: strong green. SELL bias: soft red. SELL ready: strong red. WAIT: amber. HOLD: blue. EXIT: neutral/violet-neutral. NEUTRAL/UNAVAILABLE: gray. System error: red-orange/error icon, not SELL styling. Color must never be the only signal.

Current UI mostly follows this in `WaitBriefing.tsx` and ready-state tests. Defect found: hero displayed neutral while diagnostic displayed BUY. Fixed in `apps/dashboard/lib/action.ts`; regression added in `apps/dashboard/e2e/bias_vs_action.spec.ts`.

## 17. Chrome MCP

Chrome DevTools MCP was invoked. The first attempt failed because the MCP Chrome profile was locked and then remained on `about:blank`. A second attempt loaded the additional `evaluate_script` capability, navigated the selected MCP page to `http://127.0.0.1:3000/trade`, waited for live trade text, captured an accessibility snapshot, captured a full-page screenshot, checked network requests, and evaluated the page semantics.

Evidence files:
- `docs/reports/chrome-mcp-live-trade-snapshot.txt`
- `docs/reports/chrome-mcp-live-trade.png`
- legacy failed attempt: `docs/reports/chrome-mcp-live-snapshot.txt`, `docs/reports/chrome-mcp-live.png`

Chrome MCP observations:
- Page title: `XAU EDGE - Terminal giao dịch PAPER (XAUUSD)`.
- URL: `http://127.0.0.1:3000/trade`.
- Network: `/trade` 200 and live API calls to `/trade/decision`, `/trade/markers`, `/trade/signals`, `/trade/journal`, `/trade/setups`, and `/md/XAUUSD/bars` returned 200.
- Console: no console messages found.
- Semantic check: `H1 BIAS: MUA` present; hero BUY bias present; action WAIT / no-entry present; spread blocker present; old neutral contradiction absent.

Classification: CHROME DEVTOOLS MCP = PASS for current live BUY-bias + WAIT + spread-blocked UI coverage. It still does not prove all synthetic UI states visually because the live runtime was only in one market state during this audit.

## 18. Tests

Added backend mirror test proving deterministic BUY and SELL both reach terminal decisions and satisfy geometry:

`tests/unit/trading/test_decision_levels_sizing.py::test_mirrored_buy_and_sell_fixtures_both_reach_terminal_decisions`

Added UI regression in `apps/dashboard/e2e/bias_vs_action.spec.ts`: BUY bias + spread-blocked WAIT must show BUY in hero bias, not neutral.

Ran:

- `python -m pytest tests/unit/trading/test_decision_levels_sizing.py tests/unit/trading/test_baseline_v12.py` -> 80 passed.
- `npm run build` -> passed.
- `npx playwright test e2e/bias_vs_action.spec.ts` -> 24 passed.
- `npm run lint` -> passed when run alone. A parallel run failed once because ESLint tried to scan Playwright `test-results` while Playwright was cleaning it.

## 19. Root causes

1. SIGNAL STARVATION BY DESIGN: v1.1 requires strict same-bar M15 setup + M5 trigger after early gates.
2. POSSIBLE OVERFILTERING: spread and volatility gates dominate live WAIT.
3. RESEARCH QUESTION: low ATR percentile can lag short impulse moves.
4. UI COMMUNICATION BUG: hero bias did not consume diagnostic bias under non-setup blockers. Fixed.
5. ALERTING GAP: setup lifecycle/watch states need more alert events before demo certification.

## 20. Roadmap

NOW:

Goal: lock correctness/symmetry and fix UI contradiction. Files: `baseline.py`, `levels.py`, `schema.py`, `action.ts`, `bias_vs_action.spec.ts`, `test_decision_levels_sizing.py`. Tests: focused unit + Playwright. Exit: BUY/SELL synthetic pass, no neutral hero under directional diagnostic.

NEXT:

Goal: operational diagnostics for last BUY candidate, last SELL candidate, last BUY ready, last SELL ready. Files: `telemetry.py`, `cockpit.py`, `SystemCards.tsx`. Exit: UI/API say “never observed in current session” when absent.

LATER:

Goal: alert completeness and v1.1/v1.2 frequency comparison. Files: `setup_alerts.py`, `engine.py`, replay scripts. Exit: no threshold changes; frequency-only report.

LOCKED:

No spread/ATR/EMA/M15/M5/RR/risk threshold changes until research is pre-registered and run.

## 21. Final verdict

BUY PATH IMPLEMENTED: YES

SELL PATH IMPLEMENTED: YES

BUY/SELL LOGIC SYMMETRY: PASS

BUY SYNTHETIC SIGNAL: PASS

SELL SYNTHETIC SIGNAL: PASS

BUY READY TODAY: 0

SELL READY TODAY: 0

WAIT TODAY: 295

TOP FIRST-REFUSAL: SPREAD_TOO_WIDE

TOP 5 BOTTLENECKS:
1. SPREAD_TOO_WIDE
2. NO_SETUP
3. VOLATILITY_TOO_HIGH
4. VOLATILITY_TOO_LOW
5. STALE_DATA

H1 DIRECTION: GOOD

M15 SETUP: OVERFILTERING SUSPECTED

M5 TRIGGER: GOOD

SPREAD GATE: OVERFILTERING SUSPECTED

VOLATILITY GATE: LAG SUSPECTED

V1.1 SIGNAL STARVATION: YES

V1.2 LIFECYCLE VALUE: RESEARCH NEEDED

BIAS/ACTION UI: PASS after fix

BUY COLOR SEMANTICS: PASS

SELL COLOR SEMANTICS: PASS

ALERT COVERAGE: 55%

CHROME DEVTOOLS MCP: PASS for current live state; PARTIAL for full state matrix

ALGORITHM BUG: NO

ALGORITHM CHANGE NOW: NO

RESEARCH REQUIRED: YES

VALIDATED EDGE: 0%

STATISTICAL DECISION TRUST: 0%

REAL-MONEY READINESS: 0%

NEXT 5 ACTIONS:
1. Add API/UI “last BUY/SELL candidate/ready” operational diagnostics.
2. Add `SETUP_ARMED`, `SETUP_EXPIRED`, `STALE_CRITICAL` alerts.
3. Run frequency-only v1.1 vs v1.2 replay on current protocol.
4. Research spread/ATR percentile lag without changing thresholds.
5. Add fixture-driven UI routes or mocks so Chrome MCP can certify BUY READY, SELL READY, armed, HOLD, and EXIT states without waiting for live market conditions.

OVERALL VERDICT:
XAU EDGE supports both BUY and SELL. The live absence of BUY/SELL this morning is explained by signal starvation and protective gates, not by a missing side implementation. The only production defect found was Human-facing: the hero could describe a directional BUY-bias WAIT as neutral. That UI contradiction is fixed; algorithm thresholds should not be changed until research answers whether the gates are overblocking.
