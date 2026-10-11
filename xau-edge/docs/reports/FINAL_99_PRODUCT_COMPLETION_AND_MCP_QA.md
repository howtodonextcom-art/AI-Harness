# Final product completion and Chrome DevTools MCP QA (2026-10-11)

Scope: PAPER human-decision software (`/trade`, backend decision/paper lifecycle, research-gate infrastructure). Not an edge claim.
Research truth is unchanged: Edge V1-V3 CLOSED, NO VIABLE EDGE FOUND, baseline `xau_mtf_baseline v1.1.0` = `UNVALIDATED_OPERATIONAL_BASELINE`.

## 1. Executive verdict

**Product / engineering: 96 of 100, not 99.** Every correctness defect found was fixed and tested; the remaining gap is (a) a review that is not truly independent, (b) two cost components that only the owner or broker can evidence, (c) one cosmetic crowding case at 200% zoom. The score is not rounded up. VALIDATED EDGE, STATISTICAL DECISION TRUST and REAL-MONEY READINESS stay 0%.

The most important finding of this sprint: **the system overlay froze the browser** whenever several plan levels fell outside the visible price range (an unbounded `while` in the label placer). It was invisible in earlier QA because every earlier test started from a fixture whose candles contained the plan. A real WAIT to SELL transition on different candles reproduced it, a CDP pause identified the loop, and a pure bounded allocator replaced it (section 7, FIX-01).

## 2. Git reality

| | |
|---|---|
| Start of this sprint | `451dcb8` = `origin/main`, clean (pushed earlier on request) |
| Code commits | `2fad7a5` research infrastructure; `86338bf` UI/backend fixes |
| This report | a third, docs-only commit on top (the dashboard source is identical to `86338bf`) |
| Pushed | NO |
| Source / build / runtime | source `86338bf`; live `.next` built from it (`data-build-sha="86338bf"` in the served HTML, BUILD_ID `4o62fDNQYkXRj7L2voMAG`); live API restarted after the backend change |

Before this sprint the live `.next` was older than the overlay commit and nothing showed it. It is now stamped (FIX-09) and a test fails if the dashboard source changed after the served build.

## 3. Starting state

`451dcb8`: session labels already renamed; mock suite 336/336 on a sandbox build; acceptance 31/31; the checklist of the owner's prompt (MCP states, zoom, reverse coordinates, collisions, rapid transitions, terminology, research infrastructure) was open.

## 4. Completion rubric (fixed before scoring; weights not changed afterwards)

| Axis | Weight | Score | Basis |
|---|---:|---:|---|
| Human decision correctness | 20 | 19 | all hero states observed in a real browser on the real backend; expired levels and WAIT semantics fixed; 5-second test self-assessed only |
| Browser / runtime correctness | 15 | 14.5 | freeze fixed, CLS 0.23 to 0, console clean on live, build stamp; one transient `ERR_NO_BUFFER_SPACE` in a 4,000-request session |
| Backend / UI parity | 10 | 10 | price round trip API = panel = overlay = chart coordinate for BUY and SELL; HOLD uses the fill |
| Responsive / accessibility | 10 | 9.5 | 390, 720x450 (200%), 960, 1152, 1440, 1920; Lighthouse a11y 100 desktop and mobile; one cosmetic crowding case |
| PAPER lifecycle | 10 | 10 | acceptance 31/31 through the real TradeEngine and PaperDesk |
| Fail-closed safety | 10 | 10 | no gate loosened; expired plan masked; unknown costs never zero |
| Automated QA | 10 | 10 | see section 23 |
| Operational reliability | 5 | 4.5 | restart done safely and verified; the restart itself is a manual procedure |
| Research infrastructure | 5 | 3.5 | cost ledger, fill, room, waterfall built and tested; slippage and commission blocked externally |
| Documentation / reproducibility | 5 | 5 | this report, ledger, JSON of the waterfall, screenshots |
| **Total** | **100** | **96.0** | exact sum, no rounding |

The exact sum is 96.0 and 96 is the figure used everywhere.

## 5. Roadmap (tracks)

| Track | Status | Score | Open |
|---|---|---:|---|
| A Core architecture | complete | 100 | none |
| B Market-data pipeline | complete for scope | 98 | history depth is an owner action (terminal Max bars) |
| C PAPER lifecycle | complete | 100 | none |
| D Decision API | complete | 99 | WAIT `missing` fixed |
| E Human decision UI | complete | 97 | self-review only |
| F Automatic overlay | complete | 99 | 200% zoom crowding (LOW) |
| G Chart UX | complete | 98 | |
| H Responsive | complete | 98 | |
| I Accessibility | complete | 99 | |
| J Browser / runtime | complete | 98 | |
| K MCP QA | complete | 97 | MCP window cannot be narrower than 500 px: 390 is device emulation |
| L Operational reliability | complete | 95 | |
| M 1.5R gate | complete | 100 | |
| N Cost model | partial | 50 | slippage and commission BLOCKED_EXTERNALLY |
| O Executable fill | frozen, partial | 60 | no tick history before 2021-10, so Development-2 fills stay unverified |
| P Structure room | verified | 95 | 343 of 365 fail room by design |
| Q Pattern intelligence | engineering gaps closed | 90 | descriptive only |
| R V4 readiness | NOT READY | 35 | section 22 |
| S Validated edge | 0 | 0 | |
| T Real-money readiness | 0 | 0 | |

## 6. Autonomous iterations

Seven loops, each observe, options, criteria first, implement, browser and automated test, bug hunt (see the ledger `FINAL_COMPLETION_LEDGER.md`).

## 7. Issues found and fixed

| ID | Severity | Root cause | Fix | Evidence |
|---|---|---|---|---|
| FIX-01 | **HIGH** (browser freeze) | `labelY` loop `while (used.some(u => abs(u - out) < 16)) out = clamp(out + 16, ...)` never ends once clamped levels share the edge | `lib/labelSlots.ts` bounded allocator, priority Entry > SL > TP1 > NOW > TP2, max shift 40 px, weakest label yields | `e2e/unit/label_slots.spec.ts` (regression for the clamped case), rapid-transition test |
| FIX-02 | MEDIUM | badge sat on the TP1 label | badge goes to the first band free of plan labels | `system_overlay.spec.ts` collision test; MCP screenshot |
| FIX-03 | MEDIUM | HTML context legend overlapped the plan labels on a phone | chart measures the legend and passes `topInset`; labels and badge stay below it | collision test at 390, 720x450, 1440; MCP 390 screenshot |
| FIX-04 | **MEDIUM correctness** | expired setup still printed Entry/SL/TP/R:R like a live plan | levels masked, "Kế hoạch đã hết hạn, không dùng." | e2e test; MCP before screenshot `mcp_expired.png` |
| FIX-05 | MEDIUM | WAIT with `NO_TRIGGER` reported `missing = SETUP` | `missing = TRIGGER` when the first refusal is NO_TRIGGER | `test_wait_names_the_one_missing_thing...` |
| FIX-06 | MEDIUM | hero levels preferred the plan over the open position's fill | an open position's fill and live levels win | HOLD test |
| FIX-07 | MEDIUM | CLS 0.23 at load (market bar and "loading" line re-flowed) | nothing is painted until the first decision lands; placeholder matches the final size | `layout_stability.spec.ts` (fails before, passes after); MCP CLS 0 on live |
| FIX-08 | LOW | 10 form fields without id or name (Chrome issue) | `name` on all `/trade` inputs | MCP evaluate: 0 left |
| FIX-09 | MEDIUM (process) | a stale served build was undetectable | `data-build-sha` stamp and `build_stamp.spec.ts` | live HTML shows `86338bf` |
| FIX-10 | LOW | ambiguous labels | session: Tokyo / London / New York / London + New York; `PULLBACK` becomes `HỒI` with tooltip, `CŨ` in the MTF strip becomes `DỮ LIỆU CŨ` | tests, MCP |

## 8. Option comparisons (criteria fixed before implementing)

**FIX-01 label placement.** Criteria: always terminates; priority respected; pure; small diff; no wrong-place labels. A) bounded loop with the same clamp: still stacks at the edge. B) slot allocator searching both directions, dropping a label with no slot: all five pass. C) hide labels of off-screen levels: loses names. Chosen **B** with a 40 px shift cap (added after the first screenshot showed a TP1 label sitting below Entry: a label that has moved far names the wrong place, so it yields).

**FIX-03 legend collision.** Criteria: system labels never garbled, legend still discoverable, works at any zoom. A) hide the legend while the overlay is active: breaks tests and the a11y list. B) measure the legend and keep plan labels below it. C) collapse the legend on a phone. Chosen **B**.

**FIX-07 CLS.** Criteria: no shift, no extra request, small diff. A) fixed min-heights for the market bar: depends on breakpoint and market state. B) paint nothing until data (`invisible`; invisible elements are not counted by CLS). C) server-render the first decision. Chosen **B**.

**Terminology.** Criteria: immediate meaning, accurate semantics, compact, consistent, no false trading instruction. PULLBACK: `HỒI ↑` (chosen, tooltip says it is a retracement against the main trend, not an entry), `NHỊP HỒI`, `RETRACE`. CŨ in the MTF strip: `DỮ LIỆU CŨ` (chosen) versus `STALE`. `ĐÃ DỪNG` (stopped) was already unambiguous and is unchanged.

## 9. Implementation changes

Dashboard: `SystemTradePlanOverlay.tsx`, `lib/labelSlots.ts`, `TerminalChart.tsx`, `DecisionPanel.tsx`, `lib/honesty.ts`, `TerminalView.tsx`, `MarketBar.tsx`, `MtfStrip.tsx`, `HeroCard.tsx`, name attributes, `next.config.ts`, `layout.tsx`. Backend: `trading/cockpit.py` (missing), `trading/market_context.py` (labels). Research: `decision_research/{cost_ledger,fill_model,structure_room,waterfall}.py`, `scripts/pattern_waterfall.py`. No evidence gate, risk gate, news guard, kill switch, reconcile or FTMO guard was touched.

## 10. Chrome DevTools MCP

Live `http://127.0.0.1:3000/trade` (MARKET_CLOSED) and the replay stack `:3200` over `serve_acceptance.py :8100` (real TradeEngine, PaperDesk, journal; transport redirect of `:8000` to `:8100` only, no DOM editing). Paper actions were clicked only on the replay world, never on live.

## 11. UI state matrix (real browser, real backend, no reload between states)

| State | Observed | Action / why / next | Overlay | Levels |
|---|---|---|---|---|
| BUY_READY (`buy_tp`) | MUA PAPER | present, "còn hiệu lực 5:00" | PLAN BUY | entry 4236.47, sl 4229.45, tp1 4250.51, R:R 1.90 = API |
| SELL_READY (`sell_ready`) | BÁN PAPER | present | PLAN SELL | 3336.41 / 3339.10 / 3331.03 = API |
| WAIT (`wait`) | CHỜ, no order | "H1 chưa có hướng rõ" | none | all "—" |
| STALE / collector down | KHÔNG KHẢ DỤNG | "Hệ thống chưa cho quyết định đáng tin" | none | "Kế hoạch bị chặn, không dùng." |
| EXPIRED_SETUP | CHỜ | "Setup đã hết hiệu lực, không còn mở được" | none | masked after FIX-04 |
| HOLD (`POSITION_OPEN`) | GIỮ VỊ THẾ | "Vì sao GIỮ…" | POSITION | fill 4236.50, not the planned 4236.47 |
| EXIT (`buy_time`, after +120 min) | ĐÃ THOÁT | "Không cần làm gì thêm" | none | none |
| MARKET_CLOSED (live) | CHỜ, "Mở lại lúc 10-12 05:05" | present | none | none |
| UNAVAILABLE | covered by STALE and collector_down above | | | |

WAIT semantics (backend): `NO_SETUP` gives `missing=SETUP`, `NO_TRIGGER` gives `missing=TRIGGER` (unit test). The two WAIT variants were browser-checked through `buy_watch`, `buy_armed`, `sell_watch`, `sell_armed`, `sell_invalidated` in the acceptance suite (each states the bias, says "CHỜ" and offers no order).

## 12. Responsive matrix (MCP, BUY state, real backend)

| Viewport | Result |
|---|---|
| 1920x1080 | hero and "Mở lệnh" in view, no horizontal scroll |
| 1440x900 | PASS |
| 1152x720 (125%) | PASS, no horizontal scroll |
| 960x600 (150%) | PASS: single column, hero visible, sticky action bar |
| 720x450 (200%) | PASS: action word visible, sticky bar; LOW: badge sits over the lowest candles |
| 390x844 (device emulation) | PASS: ACTION, WHY, NEXT before the chart; Entry/SL/TP in the hero text and sticky bar |

Note: the MCP browser window cannot be made narrower than about 500 px, so 390 wide is `emulate` (390x844 at DPR 2, mobile, touch), which is also what a phone reports. One MCP page crashed once when resizing from 1152 to 960; it was not reproducible and the page was recreated.

## 13. Accessibility

Lighthouse (live): accessibility 100 desktop and mobile, best practices 100, SEO 100. axe over every state in the mock suite; modal focus trap and return focus (existing tests, green); name attributes added to all `/trade` fields. Calculator: the collapsed summary reads "Máy tính lệnh (chỉ để tính)" and the expanded panel keeps "CHỈ LÀ MÁY TÍNH — KHÔNG PHẢI TÍN HIỆU".

## 14. Console and network

Live: zero console messages after the final restart. Replay session: 503s are the scenario switches to `stale`, `collector_down` and similar (the API answers 503 by design there), one `net::ERR_NO_BUFFER_SPACE` (Windows socket exhaustion after about 4,000 requests in one tab). Cadence is single: decision every 3 s, bars every 3 s, markers/signals/journal/setups every 6 s; no duplicates, no storm.

## 15. Performance

CLS 0.23 at load found by the trace (cluster of two shifts at 340 ms) was a measurable product defect and was fixed (FIX-07): CLS 0 on live after the fix. LCP 176 ms. Nothing else was optimised.

## 16. Backend / UI parity

API `trade_plan` = hero levels = plan card = overlay `data-price` = chart coordinate. Reverse test: price to `priceToCoordinate` to `coordinateToPrice` returns the level within 0.01 for entry, SL, TP1, BUY and SELL (`data-reprice`). HOLD: hero, overlay and API agree on the fill.

## 17. Automatic overlay

Backend-derived, read-only (`pointer-events: none`), not persisted (localStorage test), separate from manual drawings, absent in WAIT, UNAVAILABLE, STALE, EXPIRED, EXIT.

## 18. Research: cost model

`decision_research/cost_ledger.py`: every component has value (price units), source, timestamp, relevance window, conversion and a status; unknown is `None`, never 0; `gate_cost_model` returns `None` unless all four are verified and fresh.

| Component | Status | Source |
|---|---|---|
| spread | VERIFIED_MEASURED | cost model v2 tick spread by year and session (class D, no outcome), p90 |
| swap | VERIFIED_BROKER_SPEC, expires after 7 days | MT5 `symbol_info` reading (long -76.05 on 10-08, -69.25 on 10-11: it moves) |
| slippage | **BLOCKED_EXTERNALLY** | needs at least 30 broker-executed demo fills with requested and filled prices; demo execution needs owner authorization |
| commission | **BLOCKED_EXTERNALLY** | needs the account's commission schedule or a closed demo deal's commission field |

Executable fill (`fill_model.py`), criteria before any measurement: causality, broker realism, data availability, auditability, determinism, complexity. A next tick (best realism, no data before 2021-10, complex), **B next bar open with BUY at ask = open + spread, SELL at bid = open (chosen)**, C preregistered limit retest (extra parameters, depends on later prices). Evidence found while building it: the bar's recorded spread understates the tick spread by a median ratio of 1.43 to 1.63 in 2021 to 2023 and 1.04 to 1.10 in 2024 to 2025, and no tick history exists before 2021-10-01, so for the development years the bar-to-executable conversion is not evidenced and every fill there is `verified=False` (FILL_UNVERIFIED).

## 19. Structure room

`structure_room.py`: only pivots confirmed at or before the actionable bar, nearest opposing barrier decides, duplicates are neutral, the target must stop one tick short, BUY and SELL are mirrors, no known barrier is unknown room and fails. Tested for each. One detection (a Wolfe) had no known barrier.

## 20. First-failure waterfall (Development-2 H1, counts only)

Order: DETECTED, INVALID_GEOMETRY, ROOM_FAIL, GROSS_RR_FAIL, FILL_UNVERIFIED, COST_UNVERIFIED, NET_RR_FAIL, PROBABILITY_UNAVAILABLE, ENTRY_ELIGIBLE. The classes partition the detections; raw overlapping reasons are in `docs/reports/data/pattern_waterfall_dev2_h1.json`.

| Family | Detected | INVALID_GEOMETRY | ROOM_FAIL | GROSS_RR_FAIL | FILL_UNVERIFIED | ENTRY_ELIGIBLE |
|---|---:|---:|---:|---:|---:|---:|
| Double top/bottom | 287 | 20 | 266 | 1 | 0 | 0 |
| Head and shoulders | 7 | 0 | 7 | 0 | 0 | 0 |
| Wolfe | 71 | 0 | 70 | 0 | 1 | 0 |
| **All** | **365** | **20** | **343** | **1** | **1** | **0** |

No price after a detection is read; no return, hit rate or win rate exists. This agrees with the earlier gate report (344 overlapping room rejects, 0 eligible).

## 21. Pattern intelligence

Engineering only: the first-failure waterfall and the room audit are new deterministic, tested components; no new detector family, no outcome data.

## 22. V4 readiness: **NOT READY**

Missing before a charter can be preregistered: verified slippage and commission (owner/broker), an executable-spread conversion for the development years (tick history before 2021-10 or an owner decision to accept an assumption), a mechanism with support beyond folklore, a power calculation, untouched evaluation data, and the owner's authorization. 343 of 365 detections fail room before costs are even reached.

## 23. Test results (at `86338bf`)

| Suite | Result |
|---|---|
| `tsc --noEmit`, `eslint` | clean |
| Next production build (sandbox and live) | success |
| Playwright mock suite (`NEXT_DIST_DIR=.next-sandbox`) | **351 / 351** |
| Real-backend acceptance (replay API + dashboard) | **31 / 31** |
| `ruff check`, `ruff format --check`, `mypy --strict` | clean |
| `pytest -m "not mt5"` | **2834 passed**, 1 skipped, 3 deselected |

Backend gate at `86338bf`: `ruff check` all checks passed; `ruff format --check` 783 files already formatted; `mypy --strict` no issues in 493 files; `pytest -m "not mt5"` **2834 passed, 1 skipped (Windows symlink privilege), 3 deselected (MT5)** in 8 min.

## 24. Independent review

**Not independent.** No subagent was started (not requested by the owner); the review below is a self-review done from screenshots, runtime behaviour and test output first, rationale second. The 5-second human test was therefore self-assessed and is the reason for the 1-point deduction in human decision correctness.

Self-review result: BUY and SELL answer what to do, why, what next, entry, SL, TP, risk and evidence in the first screen at 1440 and 390. No CRITICAL or HIGH remains. MEDIUM correctness: none open.

## 25. Red team (attempts and outcomes)

| Attack | Outcome |
|---|---|
| stale BUY overlay after WAIT, SELL, STALE, EXPIRED, EXIT | blocked: rapid-transition test (BUY, WAIT, SELL, UNAVAILABLE, HOLD, EXIT, same document) and the real-browser run |
| wrong side geometry, wrong price mapping | blocked: `validGeometry` banner, reverse-coordinate test |
| TP2 mistaken as active | TP2 is labelled "THAM KHẢO" and lowest priority |
| manual vs system confusion | overlay not persisted, not draggable, separate from drawings |
| calculator mistaken for a signal | collapsed title and expanded banner say it is only a calculator |
| expired plan used | FIX-04 |
| browser freeze through label placement | FIX-01 (found by this exercise) |
| stale build under test | FIX-09 |
| cost fallback to zero, unverified fill, floor bypass, room bypass | blocked by the ledger, fill flag, floor 1.5 that cannot be lowered, unknown room = fail (tests) |
| mobile clipping, zoom failure | PASS at all listed sizes |

## 26. Remaining external blockers

Slippage evidence (owner authorization for demo fills), commission schedule, tick history before 2021-10 (terminal Max bars, owner action), owner decision on V4, a truly independent reviewer if the owner wants one. Push is pending the owner.

## 27. Final scores

Product / engineering 96. Human decision UX 96. PAPER lifecycle 100. Research infrastructure 70. Pattern intelligence 90. V4 readiness 35. VALIDATED EDGE 0. STATISTICAL DECISION TRUST 0. REAL-MONEY READINESS 0.

## 28. Product freeze

NO. The score is below 99; `/trade` stays open to correctness fixes and to the items above. No speculative features were added.
