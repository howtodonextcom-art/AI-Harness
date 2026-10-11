# Human-state consistency and MCP closure (2026-10-11)

Scope: close the defects of MCP QA round 3 (`MCP_TRADE_QA_ROUND3_2026-10-11.md`, kept as evidence) and the FIX-06 erratum in `FINAL_99_PRODUCT_COMPLETION_AND_MCP_QA.md` (kept). No strategy, entry, SL, TP, R:R, risk, detector, news guard, research gate, cost model, V4, Test-H or Holdout was touched.

## 1. Git reality

| | |
|---|---|
| Start | `66b900b` = `origin/main`; `66b900b`, `ab2ec75`, `c0edd71`, `d4351b4`, `86338bf`, `bca9e4b` all verified as ancestors of `origin/main`; tree clean; runtime stamp `d4351b4` |
| Commits of this sprint (local, not pushed) | `1c96422` fix, `9a43e4c` tests, `134905f` fix (independent review), `a62f66b` tests, `c8bd9fb` fix (second review), `1a0e5d5` tests, plus the docs commit that carries this report |
| Runtime | live rebuilt and restarted while the market was CLOSED (before: build id `bORnjz7vuz8HxihXMbjLV`, source `1a0e5d5`): `data-build-sha="1a0e5d5"`, API and dashboard healthy; the later docs-only commit does not change the dashboard |

## 2. The principle and the design decision

One source of truth: the server-authorized Human action (`hero.action`). A BUY/SELL surface (chart overlay, sticky open bar, ticket, Entry/SL/TP in the hero, plan price lines) may exist only when `action.code` is BUY/SELL, `stage` is READY, the plan is complete, and nothing is stale or expired. This is code, not prose: `lib/humanState.ts` holds the table `SURFACES` and `humanState()`, every surface asks it, and `e2e/human_state.spec.ts` pins it.

Blocked-plan options, criteria fixed before choosing (Human ambiguity, safety, information retention, phone clarity, complexity, testability):

- A. hide everything: lowest ambiguity, loses what the setup was.
- B. keep the geometry, rename it "BỊ CHẶN": the lines on the chart still look like an offer; fails safety.
- C. hide overlay, bar, ticket, plan lines and hero levels, and keep the numbers in a **folded, neutral block labelled "SETUP BỊ CHẶN — KHÔNG ĐƯỢC VÀO LỆNH (chỉ tham khảo)"** that states the reason first: lowest ambiguity and keeps the information.

Chosen **C**. The signal marker of a blocked setup became a grey "bị chặn" dot (independent review finding).

## 3. Human state matrix

| State | Action | Why (what the Human reads) | Next | Plan visible | Overlay | Phone sticky bar | Entry source | Expected Human action |
|---|---|---|---|---|---|---|---|---|
| WAIT_NO_SETUP | CHỜ | "H1 chưa có hướng rõ", "Hiện chưa có setup" | wait for the condition named | no | none | none | none | do nothing |
| WAIT_NO_TRIGGER | CHỜ | "Setup đã hình thành, chưa có trigger" | next M5 close confirming the trigger (candles left) | no | none | none | none | do nothing |
| WAIT_BLOCKED | CHỜ | "Setup mua đã đủ điều kiện kỹ thuật nhưng đang bị chặn: <reason>" | block lifts or a new setup | folded reference only | none (marker is a grey dot) | none | none | do nothing |
| BUY_READY / SELL_READY | MUA / BÁN PAPER | confirmed signal, complete plan | open (confirm modal) before expiry | yes (hero, ticket) | PLAN | "SẴN SÀNG MUA/BÁN @ entry, SL, TP, R/R" | plan | open or skip |
| HOLD | GIỮ VỊ THẾ | "Vì sao GIỮ", exits listed (SL, TP, time, 3.5% floor) | exit rules | position panel | POSITION | "đóng lệnh" | **position.fill_price** (plan price only as "Giá kế hoạch") | hold |
| EXIT | ĐÃ THOÁT | reason, P&L, R, duration | wait for the next setup | none (dashes) | none | none | none | nothing |
| EXPIRED | CHỜ / BỎ QUA | "Setup đã hết hiệu lực" | new setup | none ("Kế hoạch đã hết hạn, không dùng") | none | none | none | nothing |
| STALE / UNAVAILABLE | KHÔNG KHẢ DỤNG | reason named | system recovers | none | none | none | none | do not trade, check the system |
| MARKET_CLOSED | CHỜ | "Thị trường đóng cửa" | reopening time with its zone | none | none | none | none | nothing |

Exit priority (formalised in `cockpit.hero_state`, tested): fault > unknown > stale > market closed > open position (HOLD) > a READY setup nothing blocks > a recent exit (within `EXIT_BANNER_MINUTES`) over every setup that cannot be acted on (blocked, expired, incomplete) > armed > WAIT. A fresh valid READY is still offered right after an exit (a new setup is not a consumed one).

## 4. Defect table

| ID | Original | Root cause | Fix | Playwright evidence | MCP evidence | Status |
|---|---|---|---|---|---|---|
| H-01 | High | overlay, bar and ticket decided from `hero.state === *_READY` / plan presence, while the action was WAIT/BLOCKED | `humanSurface` drives overlay (`holdLive`, `planLive`), bar, ticket, plan lines, hero levels; reference block; grey marker | `human_state.spec` H-01 BUY/SELL desktop and phone, red-team over 7 blocker codes, marker test (12 failed on the old build) | `blocked_buy_desktop.png`, `blocked_buy_390.png`: CHỜ, reason, no badge, no "SẴN SÀNG", no overlay, no open control | **PASS** |
| M-01 | Medium | reason line `display:none` on phone, generic "Đừng mở lệnh..." | reason in the sub line (visible on phone) and in the folded reference | phone test: reason `toBeVisible` | `blocked_buy_390.png` | **PASS** |
| M-02 | Medium | `hero_state` returned READY (blocked as duplicate) before the recent exit | `blocked` input and priority above; engine passes `bool(entry_blockers)`; hero levels masked in EXIT | `test_a_recent_exit_outranks...` (Python), acceptance "manual close shows ĐÃ THOÁT", mock M-02 incl. dashes | `manual_exit.png`: ĐÃ THOÁT, Đóng tay, -$0.90, -0.04R, 0 phút, no levels | **PASS** |
| M-03 | Medium | `heroLevels` preferred the plan (the FIX-06 edit had silently not applied) | position facts first | `human_state.spec` M-03 with BOTH `trade_plan` (4236.47) and `position.fill_price` (4236.50) | `hold_actual_fill.png`: hero 4236.50, overlay 4236.5, panel "Giá vào (khớp) 4236.50", plan only as "Giá kế hoạch" | **PASS** |
| M-04 | Medium | setup row said "Chưa có" in blocked/expired states; "Một nguồn sự thật" jargon | state-dependent copy in `lib/action.ts`; jargon removed | M-04 test (blocked, expired, wait, watch) | `expired.png`, `blocked_buy_desktop.png`, `wait_no_setup.png` | **PASS** |
| L-01 | Low | popovers of different components did not know each other | `lib/popovers.ts` (one at a time) | L-01 test | n/a | closed |
| L-02 | Low | alerts and lines deletable only in the Overview tab | listed with delete in the alert popover and in the drawing manager | L-02 test | n/a | closed |
| L-03 | Low | M1 "DỮ LIỆU CŨ" while the market is closed | "ĐÓNG CỬA" only when closed; stale kept while open | L-03 test | n/a | closed |
| L-04 | Low | 274 px chart at 720x450 | `100dvh-10.5rem` | L-04 test (>= 280) | chart 282 px (`ready_720x450.png`) | closed |
| L-05 | Low | shortcut mapping surprising | kept (muscle memory, tests), explained in the dialog | L-05 test | n/a | closed (explained, not changed) |
| L-06 | Low | 2% vs 3.5% unexplained | one line next to the loss meter | L-06 test | `manual_exit.png` shows the line | closed |
| L-07 | Low | reopening time not labelled | zone label; the default was already VN and remembered (the broker zone seen in QA was a stored choice) | L-07 test | live `Mở lại lúc ... (NY+7)` | closed |

LOW closed: 7/7.

Independent review findings (see section 8) fixed in `134905f`: grey marker on blocked setups, `dữ liệu` age no longer younger than the quote age (stale screen said "GIÁ CŨ · 2 phút" beside "dữ liệu: 0s"), the phone bar shows the entry, the chart expiry label uses the display zone, the block reason is said once.

## 5. Option comparison for the single-popover rule

A. a shared event (`lib/popovers.ts`): small, no prop drilling, testable. B. lift every popover state to `TerminalView`: bigger change. C. close on outside click only: leaves stacked dialogs. Chosen A.

## 6. Test results (final source `1a0e5d5`)

| Suite | Result |
|---|---|
| `tsc`, `eslint` | clean |
| Playwright mock suite | **380 / 380** (includes 18 new tests in `human_state.spec.ts`) |
| Real-backend acceptance | **32 / 32** (two old expectations encoded the defects and were corrected: manual close now ends in EXIT; closure-near now reads SETUP_BLOCKED with no ticket) |
| Backend gate | `ruff` and `mypy --strict` clean; `pytest -m "not mt5"` **2835 passed**, 1 skipped, 3 deselected (run on the backend as committed; only frontend files changed after) |
| Mutation check | with the old components and libs restored, 12 of the 14 first-wave tests failed; the two that passed are the pure table test and the M-02 mock test (M-02's old behaviour is a backend priority, covered by the Python test and by acceptance) |

## 7. Chrome DevTools MCP

Sandbox = replay stack (`serve_acceptance.py :8100`, dashboard `:3200`, `NEXT_DIST_DIR=.next-sandbox`); LIVE was only observed. Bridge discipline that works reliably: `emulate` first (it reloads), then `navigate_page` with the `initScript` that rewrites fetch `:8000` to `:8100` and defines helpers, then confirm "REPLAY · NOT LIVE" in the source pill, then test; every later `emulate` needs a new navigate with the init script. Screenshots: `docs/reports/img/human-state-closure-2026-10-11/`.

Required states (16): wait_no_setup, wait_no_trigger, buy_ready, sell_ready, blocked_buy_desktop (closure near), blocked duplicate (a taken setup now resolves to EXIT by design: observed as `manual_exit`), hold_actual_fill (mixed plan + position), manual_exit, tp_exit, sl_exit, time_exit, expired, stale, market_closed, blocked_buy_390, ready_720x450: **16 / 16 observed and looked at**. A SELL blocked state has no replay scenario that stays blocked (a SELL setup expires before its exit window ends), so the SELL blocked case is covered by the mock tests only.

Live after the final restart (`1a0e5d5`): console empty, 0 failed requests, one poll per endpoint (decision about every 3 s, side data every 6 s), CLS 0.0002, one 70 ms long task during the first hydration and none after, Lighthouse accessibility 100 (best practices 100, SEO 100), no drawings, alerts or levels left, "Số lệnh hôm nay 0 / 6". Sandbox 503s appear only during scenario loads and the deliberately failing scenarios.

## 8. Independent review

A fresh reviewer (a subagent that did not write the fixes) received only the 15 screenshots, no code, no reports, no rationale. First pass: no CRITICAL; HIGH: green MUA arrow on blocked screens, stale age contradiction, phone bar without entry; MEDIUM: R:R 1.90 vs 2.0 unexplained, UTC labels beside a GMT+7 clock, block reason repeated 3 to 4 times, empty dash grid after an exit; LOW: jargon. All HIGH items and the UTC, repetition and age items were fixed (`134905f`) and re-captured.

Second pass (same reviewer resumed with the four re-captured screenshots, still images only): HIGH 1 (green arrow on blocked screens) **RESOLVED**; HIGH 3 (stale "0s" beside "GIÁ CŨ") **RESOLVED** as a contradiction, with two leftovers that were then fixed in `c8bd9fb`/`1a0e5d5` (the M1 candle countdown no longer ticks while the quote is stale; the dimmed-price suggestion was tried and dropped because axe rejected the lower contrast, so the price keeps its grayscale and the red "GIÁ CŨ" pill); HIGH 4 (phone bar without the entry) **PARTLY RESOLVED**: the bar now shows "@ 4236.47" with SL, TP, R/R, but at 720x450 it still covers the risk and lot grid, which stays as a LOW. No new contradiction was reported. The reviewer has not seen the final build after `c8bd9fb`, so this is a real but not a final-build independent review.

## 9. Red team

| Attack | Result |
|---|---|
| READY + closure near, duplicate, cooldown, risk, daily limit, open position, quote stale, paper state error | no overlay, badge, bar, ticket, plan lines or "SẴN SÀNG" (test over 7 codes, SELL mirrored) |
| manual close, TP, SL, time exit | each ends in ĐÃ THOÁT with reason, P&L, R and duration; no old plan visible |
| planned_entry != fill_price | every current-entry surface shows the fill; the plan only as "Giá kế hoạch" |
| expired plan, stale, writer conflict, paper corruption, no spec, collector down | no permission look (existing and new tests, MCP) |
| copy contradictions | none of "có setup" with "chưa có setup", no "Một nguồn sự thật" in blocked, expired, wait, watch |
| popovers | one at a time; Escape closes the one open |

## 10. Remaining (LOW, documented)

R:R is shown after spread and risk is the target risk, not explained on the card; at 720x450 the phone bar still covers the risk and lot grid; the stale price keeps full contrast by design (axe), only the red pill and the stopped countdown mark it; some jargon ("PHỦ", "+N mức ngữ cảnh", PWH/PWL) is unexplained; "Bid (giá bán ra)" may read backwards to some; the expired replay scenario shows a headline price that is a few minutes ahead of the last candle (a replay artefact); a SELL blocked state has no replay scenario.

## 11. Score (same rubric and weights as the final 99 report, recomputed)

Human decision correctness 19/20 (review MEDIUM wording left), browser/runtime 14.5/15, backend/UI parity 10/10, responsive and accessibility 10/10, PAPER lifecycle 10/10, fail-closed 10/10, automated QA 10/10, operational reliability 4.5/5, research infrastructure 3.5/5 (external blockers unchanged), documentation 5/5. **Total 96.5.** Not 99: the gap is 1.5 research infrastructure (slippage and commission evidence need the owner or broker), 1 point of wording the reviewer still found confusing, 1 point of margin I do not claim without a reviewer pass on the final build. VALIDATED EDGE, STATISTICAL DECISION TRUST and REAL-MONEY READINESS stay 0%.
