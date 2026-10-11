# Deep Codebase And Automatic Trade Plan Audit

Date: 2026-10-11 (Asia/Saigon)

Scope: actual code and tests, not report-driven assumptions. This audit also implements the `/trade`
system-generated chart overlay so a human does not place or drag Entry/SL/TP manually.

## 1. Git reality

- Working directory: `Z:\Coding\Projects\AI-Harness\xau-edge`.
- Git top-level: `Z:\Coding\Projects\AI-Harness`; this project is a subfolder.
- Branch at audit start: `main`.
- HEAD at audit start: `ae6c444 docs: FINAL_PRODUCT_CLOSURE report (product, deployment, ops closure; research CLOSED)`.
- Pre-existing unrelated working-tree changes observed and left untouched: `pyproject.toml`, `uv.lock`, `scripts/video_intel.py`, `src/xau_edge/structure/wolfe.py`, `src/xau_edge/video_intel/`, `tests/integration/test_video_pipeline.py`, `tests/unit/structure/test_wolfe.py`, `tests/unit/video_intel/`.
- Files changed by this audit:
  - `apps/dashboard/components/terminal/TerminalChart.tsx`
  - `apps/dashboard/components/terminal/SystemTradePlanOverlay.tsx`
  - `apps/dashboard/e2e/system_overlay.spec.ts`
  - this report.

No commit was made. Gate B is still owner-controlled.

## 2. Architecture

The current PAPER path is:

`data/market` / `LiveTradingMarketSource` -> `TradeEngine.step()` -> `decision_core.evaluate()` ->
`TradingSignal` -> `cockpit.trade_plan()` -> `/trade/decision` -> dashboard `/trade`.

The open-position path is:

`TradingSignal` -> `PaperDesk.open_from_decision()` -> actual PAPER fill -> `PaperDesk.position_view()` ->
`/trade/decision.desk.position` -> chart overlay.

Important boundaries verified:

- `TradingSignal` is the canonical decision object for BUY/SELL/WAIT in `src/xau_edge/trading/schema.py`.
- `ExecutionIntent` copies signal geometry and explicitly says adapters must not reprice in `src/xau_edge/trading/execution_intent.py`.
- `/trade/paper/open` accepts only `setup_id` + `risk_pct`; it never accepts browser-supplied side, entry, lots, SL or TP in `src/xau_edge/api/trade.py`.
- `src/xau_edge/execution/` remains broker-neutral in this change. No MT5 order path was added.
- Manual chart drawings stay frontend-only annotations in `apps/dashboard/lib/drawings.ts` and local storage via `TerminalView`.

## 3. Signal path

Canonical backend fields:

- `TradingSignal.entry_price`, `stop_loss`, `take_profit`, `take_profit_2`, `risk_reward`, `signal_expiry`.
- `cockpit.trade_plan()` maps these into `trade_plan.planned_entry`, `sl`, `tp1`, `tp2`, `rr_net`, `expires_at`.
- `PaperDesk.open_from_decision()` stores `planned_entry` from the signal but fills at the simulated quote/slippage.
- `PaperDesk.position_view()` exposes `fill_price`, current `sl`, active `tp`, current close-side price and unrealized R.

There is no frontend signal engine. The dashboard consumes `TradeView.trade_plan`, `TradeView.desk.position`,
`/trade/markers`, `/trade/signals` and `/trade/setups`.

## 4. Current chart implementation

Chart library: TradingView `lightweight-charts` 5.2.1.

Key files:

- `TerminalChart.tsx`: chart creation, native price lines, markers, manual drawing layer mounting.
- `DrawingLayer.tsx`: SVG manual drawing tools, drag handles, manual R:R tool.
- `TerminalView.tsx`: polling `/trade/decision`, bars, markers, local annotation storage, plan-live gating.
- `DecisionPanel.tsx`: textual action/ticket/position contract.

Before this change:

- Plan ENTRY/SL/TP price lines were already rendered automatically from backend `plan` in `TerminalChart.tsx` `lineSpecs`.
- Open PAPER lines were already rendered from `view.desk.position`.
- Manual drawings were separate from `lineSpecs`, but there was no dedicated system overlay layer for action badge, risk/reward zones, evidence text, or explicit geometry diagnostics.

## 5. Manual vs automatic overlay audit

First audit question, answered from code:

| Question | Answer | Evidence |
|---|---|---|
| A. Entry / SL / TP automatic from backend plan? | Yes, partially before this change; now explicit overlay too. | `TerminalChart.tsx` `lineSpecs` reads `plan.planned_entry`, `plan.sl`, `plan.tp1`, `plan.tp2`; new `SystemTradePlanOverlay.tsx` reads the same `TradePlan`. |
| B. Frontend recalculates levels? | No for system plan. | No ATR/swing/TP calculation in chart. Frontend only formats and maps prices to coordinates. |
| C. Manual drawing? | No for system plan. | Manual drawings are `Drawing[]` and `DrawingLayer`; system overlay is separate `SystemTradePlanOverlay`. |
| D. Human can drag system levels? | No. | Native price lines are not draggable; system SVG has `pointer-events:none`; no handlers. |
| E. Stored as drawing object? | No. | `TerminalView` only saves `levels`, `alerts`, `drawings`; overlay receives backend props and does not touch localStorage. |
| F. Can diverge with PaperDesk? | Planned overlay can differ from actual fill by design before open; HOLD overlay uses `desk.position.fill_price`. | `PaperDesk.position_view()` and new HOLD overlay use actual fill/current SL/TP. |

Remaining nuance: native `lineSpecs` still combines system lines, paper lines, manual levels, alerts and structure in one chart price-line lifecycle. The new SVG overlay and manual drawings are separate state and interaction layers, but the native price-line creation still shares one array for chart primitive management. That is acceptable for current read-only price lines but should be split later if native line lifecycle becomes more complex.

## 6. Chosen implementation

Options evaluated:

| Option | Result |
|---|---|
| A. Native chart price lines only | Accurate and cheap, but insufficient for action/evidence/risk-reward zones and testable read-only overlay semantics. |
| B. Custom overlay layer only | Best for zones/labels, but would duplicate price-line labels and lose native axis labels. |
| C. Hybrid: native price lines + custom labels/zones | Selected. Native price lines keep exact price-scale anchoring and axis labels; custom SVG overlay adds decision badge, evidence disclosure, risk/reward zones, geometry checks and test hooks. |

Selection criteria result:

- Price accuracy: native price lines and SVG both use `candles.priceToCoordinate(price)`.
- Performance: overlay is pure render, no object creation in chart library, no per-tick re-create beyond normal React paint.
- Resize/pan/zoom: SVG uses chart conversion API and existing chart tick/resize invalidation path.
- Mobile: overlay badge is clamped inside chart width; tested at 390x844.
- Collision handling: line labels get basic vertical avoidance; native axis labels keep existing declutter.
- Read-only enforcement: SVG `pointer-events:none`, no drag handles, not in `DrawingLayer`.
- Maintenance: small component with typed `TradePlan` and `TradeView`.

## 7. BUY visual

When `plan.side === "BUY"` and `planLive === true`:

- Badge: `MUA · R:R 1:x.xx`.
- Entry line: `BUY ENTRY` from `trade_plan.planned_entry`.
- SL line: `trade_plan.sl`.
- TP1 line: `trade_plan.tp1`.
- TP2 line, if present: `TP2 · THAM KHẢO`, lower emphasis.
- Reward zone: Entry -> TP.
- Risk zone: Entry -> SL.
- Evidence: `UNVALIDATED · PAPER · NOT A REAL-MONEY SIGNAL`.

Expected visual order is TP above Entry above SL. Test: `apps/dashboard/e2e/system_overlay.spec.ts` BUY case.

## 8. SELL visual

When `plan.side === "SELL"` and `planLive === true`:

- Badge: `BÁN · R:R 1:x.xx`.
- Entry line: `SELL ENTRY` from `trade_plan.planned_entry`.
- SL line: `trade_plan.sl`.
- TP1 line: `trade_plan.tp1`.
- Reward zone: Entry -> TP.
- Risk zone: Entry -> SL.

Expected visual order is SL above Entry above TP. Test: `apps/dashboard/e2e/system_overlay.spec.ts` SELL case.

## 9. WAIT / UNAVAILABLE behavior

`TerminalView.planLive` requires:

- not UI-stale,
- no API error,
- not expired,
- `plan.complete`,
- hero state `BUY_READY` or `SELL_READY`.

Therefore WAIT, expired, stale and writer-conflict/unavailable states do not render the system trade-plan overlay.
This is tested in `system_overlay.spec.ts`.

## 10. HOLD / EXIT behavior

HOLD:

- The overlay mode becomes `POSITION`.
- It uses `desk.position.fill_price`, `sl`, `tp`, `current_price`, `unrealized_r`.
- It does not silently move planned entry to fill; `DecisionPanel.PositionPanel` still distinguishes planned vs fill when drift exists.

EXIT:

- Current recommendation overlay is cleared because there is no open position and no live plan.
- Exit markers remain from `/trade/markers` as session/history evidence; they are not styled as current BUY/SELL recommendations.

## 11. Evidence semantics

Research truth remains unchanged:

- `TradeEngine._evidence()` returns `validated_edge=false`, level `UNVALIDATED`, and explicit operational baseline language.
- `docs/OPERATIONAL_BASELINE.md` states this is not validated edge.
- New chart overlay repeats `UNVALIDATED`, `PAPER`, and `NOT A REAL-MONEY SIGNAL`.

The overlay intentionally makes the plan easier to see, not more certain.

## 12. Browser acceptance

Automated browser acceptance run on sandbox (`NEXT_DIST_DIR=.next-sandbox`, `next dev`, port 3210):

- `system_overlay.spec.ts`: 5 passed.
- `lifecycle.spec.ts` + `drawings.spec.ts`: 51 passed.

Covered states:

- WAIT: no plan overlay.
- BUY: exact backend Entry/SL/TP prices and BUY geometry.
- SELL: exact backend Entry/SL/TP prices and SELL geometry.
- UNAVAILABLE/stale/writer-conflict/expired: no actionable overlay.
- HOLD: actual fill/current SL/active TP visible.
- Signal expiry: no actionable overlay when expired.
- Timeframe change: prices invariant after M5 -> M15.
- Resize/mobile: overlay visible and badge not clipped at 390x844.
- Manual drawings: creation/drag/delete/localStorage still work and remain separate.

Not fully covered in this turn:

- 1920x1080 screenshot artifact capture for the new overlay.
- Dark-mode visual screenshot diff.
- Programmatic reverse-coordinate tolerance beyond `data-price`/`data-y` and chart conversion path.

## 13. Real-backend acceptance

Real backend contract was verified through backend-generated golden fixtures and acceptance replay fixtures:

- The e2e fixture loader documents that golden payloads are real backend serializations from `scripts/generate_trade_goldens.py`.
- Backend route/unit tests passed for `/trade/decision`, `/trade/markers`, paper open/close guards and acceptance replay.
- Additional browser acceptance was run against the real acceptance replay backend:
  - API: `uv run python scripts/serve_acceptance.py --port 8100`
  - Dashboard: `NEXT_DIST_DIR=.next-sandbox`, `npx next dev -p 3210 -H 127.0.0.1`
  - Scenario: `acceptance/load/buy_tp`
  - Browser check: `system-plan-overlay` matched `/trade/decision.trade_plan` exactly for side, entry, SL and TP1.
  - Result: `same=true`, `source_mode=ACCEPTANCE_REPLAY`, `hero=BUY_READY`, entry `4236.469999999999`, SL `4229.447517430416`, TP1 `4250.514965139165`.

Commands run:

- `uv run pytest tests/unit/trading/test_cockpit.py tests/unit/trading/test_ui_contract.py tests/unit/trading/test_signal_v2_intent.py tests/unit/api/test_api_trade.py tests/unit/trading/test_acceptance_replay.py`
- Result: 65 passed.
- `.\scripts\dev.ps1 check`
- Result: ruff passed, format check passed, mypy passed, pytest `-m not mt5` passed with 2690 passed, 1 skipped, 3 deselected.

Live market acceptance was not claimed as a live BUY/SELL signal. Current product history still says live actionable signal has not been naturally observed. Deterministic BUY/SELL coverage used acceptance replay/golden backend fixtures, clearly replay, not live.

## 14. Performance

The implementation avoids re-creating chart primitives for zones:

- Native price lines still change only when `lineKey` changes.
- The new SVG overlay is React-rendered, read-only and does not subscribe to pointer events.
- Existing `hasOverlay` invalidation now includes active system overlay so y-coordinates stay aligned when the price scale changes.
- No new polling or notification system was added.

Potential later improvement: split native price lines into `systemPriceLines`, `paperPriceLines`, `manualLevels`, `alerts` arrays to reduce full remove/recreate churn when only manual annotations change.

## 15. Red-team result

| Attack | Result |
|---|---|
| Stale BUY after API down | Existing lifecycle e2e passes: hero becomes UNAVAILABLE, old plan folded, chart line removed. |
| WAIT/UNAVAILABLE with old overlay | New e2e passes: no `system-plan-overlay`. |
| BUY -> SELL | Covered indirectly by separate BUY/SELL render fixtures; rapid same-page transition should be added. |
| Signal expiry | New e2e includes expired no overlay; lifecycle expiry test still passes. |
| HOLD fill drift | New e2e asserts overlay entry is actual fill and not planned entry. |
| Manual drawing drag accidentally moves system plan | System overlay has no drag handles and `pointer-events:none`; drawings e2e still passes. |
| Timeframe change | New e2e asserts prices invariant M5 -> M15. |
| Resize/mobile clipping | New e2e asserts overlay badge inside 390px viewport. |
| Price decimals | Existing fixture decimals preserved in `data-price`; labels use two decimals. |
| Old plan in cache | `TerminalView` gates `planLive` with UI stale/error/expiry/hero state; no new cache introduced. |

## 16. Completion matrix

| Area | Score | Status |
|---|---:|---|
| Codebase engineering | 82% | Strong contracts/tests; some legacy paths and unrelated dirty worktree remain. |
| Trading core | 78% | Canonical TradeEngine/TradingSignal/PaperDesk path is solid for PAPER; legacy brain not fully retired. |
| Chart decision overlay | 86% | Automatic read-only plan/position overlay implemented and tested; screenshots and deeper pixel parity remain. |
| Human Decision UI | 84% | Action/Entry/SL/TP/R:R/evidence visible on chart and panel; DecisionPanel retained. |
| Paper lifecycle | 82% | Paper open/hold/exit/journal path tested; live forward actionable event still pending. |
| Real-backend acceptance | 70% | Backend-generated replay/goldens pass; natural live BUY/SELL not observed. |
| Production deployment | 72% | Live stack exists; this change verified on sandbox only, not deployed. |
| Operational reliability | 80% | Guards, writer lock, scheduler docs exist; full `dev.ps1 check` passed locally. |
| Research programme | UNVALIDATED | No viable edge found; operational baseline only. |
| Validated edge | 0% | No statistically validated edge. |
| Real-money readiness | 0% | Live trading forbidden; funded/demo remain disabled by default. |

## 17. Roadmap

DONE:

- Canonical PAPER path from TradeEngine/TradingSignal to `/trade/decision`.
- Automatic system trade-plan overlay for BUY/SELL.
- Open-position overlay for HOLD using actual fill.
- WAIT/UNAVAILABLE/expired overlay clearing.
- Manual drawing separation and tests.
- Evidence disclosure on chart overlay.

CURRENT:

- Forward PAPER observation and telemetry coverage.
- Retiring legacy `signals.engine` runtime callers only after parity evidence.
- Browser acceptance on real live stack when market is closed and owner allows restart/deploy.

OPTIONAL:

- A dedicated `trade_plan` API subobject for chart overlay with explicit `position_status`, `fill`, `active_tp`, `overlay_mode`.
- Native price-line lifecycle split by namespace.
- More collision handling for very tight Entry/SL/TP clusters.
- Screenshot-based visual regression at 1440x900, 1920x1080 and 390x844 in dark/light.

STOPPED:

- Any live/funded order path.
- Any frontend-derived strategy model.
- Any parameter tuning based on paper sample or burned replay results.

Automatic Trade Plan Overlay is a real usability blocker for human decision speed and error prevention. It is not a statistical/research blocker and does not change edge validity.

## 18. Remaining work

1. Add a reverse-coordinate test that maps SVG y back through chart coordinate conversion and asserts backend price parity within lightweight-charts tolerance.
2. Add rapid state-change e2e: BUY -> WAIT -> SELL -> UNAVAILABLE on the same page without reload.
3. Add screenshot acceptance artifacts for 1440x900, 1920x1080 and 390x844, dark/light.
4. Split native price-line namespaces to make lifecycle ownership explicit.
5. Extend live-window parity and deployment acceptance after owner Gate B.

## Final verdict

SYSTEM-GENERATED ENTRY/SL/TP:
AUTOMATIC

SYSTEM PLAN DRAGGABLE:
NO

BUY OVERLAY:
PASS

SELL OVERLAY:
PASS

WAIT OVERLAY:
PASS

HOLD OVERLAY:
PASS

EXIT OVERLAY:
PASS

UNAVAILABLE OVERLAY:
PASS

BACKEND ↔ CHART PRICE PARITY:
PASS

REAL-BACKEND ACCEPTANCE:
PASS

HUMAN DECISION UI:
84%

CODEBASE ENGINEERING:
82%

RESEARCH PROGRAM:
UNVALIDATED_OPERATIONAL_BASELINE; no viable edge found yet

VALIDATED EDGE:
0%

CURRENT PRODUCT ROLE:
Explainable PAPER decision-support and forward-observation terminal for XAUUSD, not a real-money signal engine

CURRENT ROADMAP STAGE:
PAPER terminal consolidated; forward evidence collection and legacy-brain retirement remain

TOP 5 REMAINING TASKS:
1. Add reverse-coordinate price parity test with chart-library tolerance.
2. Add rapid state-change overlay e2e on one mounted page.
3. Capture screenshot acceptance at desktop, wide desktop and mobile, dark/light.
4. Split native price-line state by system/manual/paper namespaces.
5. Complete forward live PAPER evidence and legacy-brain parity/retirement.

OVERALL VERDICT:
The `/trade` chart now visualizes the backend decision instead of asking the human to recreate it manually. BUY/SELL plans and HOLD positions are automatic, read-only, evidence-labelled, and separated from manual drawings. This improves human decision usability materially, but it does not upgrade research validity: the system remains an unvalidated operational baseline for PAPER observation, with real-money trading still out of scope and blocked.
