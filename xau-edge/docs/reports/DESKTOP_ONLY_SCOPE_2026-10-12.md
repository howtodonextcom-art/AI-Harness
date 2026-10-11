# Desktop-only scope (2026-10-12)

Decision of the owner: "I only use a desktop computer; mobile UI is not needed for now." This is a scope change, not a feature. No strategy, risk, gate, detector, news guard, research or backend code was touched.

## 1. Supported and frozen

| | Scope |
|---|---|
| Supported | desktop windows 1280 to 2560 CSS px wide, browser zoom up to 200% (down to 720x450) |
| Frozen (not deleted) | phone layouts under 640 px: no features, no polish, no new tests that gate |
| Never frozen | fail-closed safety: nothing may offer a BUY/SELL (no open button, no "SẴN SÀNG MUA/BÁN", no overlay badge, no plan lines) unless the server-authorized action is BUY/SELL; this holds at every width |

## 2. Inventory (evidence from the code)

| Item | Where | Class | Decision |
|---|---|---|---|
| sticky action bar `mobile-action-bar`, class `lg:hidden` | `TerminalView.tsx` | **shared**: it shows below 1024 px, i.e. at 150% and 200% desktop zoom (960x600, 720x450), not only on phones | keep |
| chart legend folds context levels (`COMPACT_LEGEND_PX = 520`) | `TerminalChart.tsx` | **shared**: at 200% zoom the chart is about 404 px wide, so it folds there too | keep |
| `short:` and `roomy:` layout variants | `globals.css`, components | **shared** (wide but short windows: zoom 200%, landscape) | keep |
| `sm:` (640 px) hidden/visible text variants | components | phone-only in the below-640 branch only | frozen |
| humanSurface table, blocked/expired/stale rules, open-button gating | `lib/humanState.ts`, `DecisionPanel`, `TerminalView` | **safety**, width-independent | keep, tested at every width |
| layout tests at 390 or phone landscape | `lifecycle`, `terminal`, `a11y`, `chart_readability`, `journal`, `market`, `qa_2026_10_11`, `research`, `human_state`, acceptance `desk` | phone-only layout | tagged `@mobile` |
| tests that mix a phone width with a desktop invariant | `system_overlay` (badge/legend collisions, resize invariance) | desktop invariants | the 390 width replaced by 720x450 |

Finding that decided the option: the "mobile" bar and legend fold are also what a desktop user at 150-200% zoom sees. Deleting phone code (option B) would have damaged the supported zoom range.

## 3. Options and choice (criteria fixed first)

Criteria: does not break desktop or 200% zoom; keeps the fail-closed invariants; reduces CI and maintenance load; reversible; verifiable by tests; adds no new surface that can be wrong.

- **A. Freeze (chosen).** Keep the code, tag phone layout tests `@mobile`, exclude them from the gate, run them on purpose with `XAU_E2E_MOBILE=1`, document the scope.
- B. Delete phone-only code: the shared code above cannot be cleanly separated; high regression risk; not reversible cheaply.
- C. Hard lock below 640 px with a notice: adds a new surface and a decision (what to show on a phone) the owner declined.

## 4. Changes

- `playwright.config.ts` and `playwright.acceptance.config.ts`: `grepInvert: /@mobile/` by default; `XAU_E2E_MOBILE=1` runs only the `@mobile` tests. The same edit raised `timeout` to 45 s and `expect.timeout` to 10 s: with about 500 tests on a loaded desktop (live stack, MT5, editor) single tests failed intermittently at 30 s and 5 s without any product fault; each rerun alone passed.
- phone layout tests tagged `@mobile` (37 mock tests and 2 acceptance tests when the loops expand); the phone variant of H-01 was split: the "a 390 px window never shows an offer for a blocked setup" test **still gates**, the "reason is readable on a phone" test is `@mobile`.
- New `e2e/desktop_contract.spec.ts`: 7 windows (2560x1440, 1920x1080, 1440x900, 1280x720, 125% 1152x720, 150% 960x600, 200% 720x450) times 10 states: action word on the first screen, no sideways scroll, chart at least 280 px, open button reachable and enabled for BUY/SELL, nothing offers a trade for WAIT, watch, blocked, expired, stale, market closed, HOLD and EXIT. 140 tests.
- `e2e/build_stamp.spec.ts`: tests and Playwright configs no longer make a build count as stale (a docs or test commit does not force a rebuild); `execFileSync` with argument array (no shell quoting).
- `CLAUDE.md` section 1b and the dashboard `README.md`: the scope.

## 5. Verification

| Check | Result |
|---|---|
| `tsc`, `eslint` | clean |
| Playwright mock suite (default, `@mobile` excluded) | **486 / 486** |
| Playwright mock, `XAU_E2E_MOBILE=1` | 37 / 37 (the frozen set still passes) |
| Real-backend acceptance (default) | **30 / 30**; with `XAU_E2E_MOBILE=1`: 2 / 2 |
| Backend gate | not needed: no Python file changed |
| Chrome DevTools MCP (sandbox replay for interaction, nothing touched on LIVE) | 2560x1440 (buy and blocked), 1280x720 (buy), 720x450 (buy and blocked): action word on the first screen, no sideways scroll, chart 608 / 496 / 282 px, blocked shows CHỜ with no overlay, no open button, no badge. 1440x900 and 1920x1080 unchanged since the previous MCP round (same product code, 16 states already captured in `human-state-closure-2026-10-11/`) |
| Console | only 503 during scenario loading on the replay API |

Screenshots: `docs/reports/img/desktop-scope-2026-10-12/` (`blocked_2560x1440.png`, `buy_1280x720.png`, `blocked_720x450.png`).

Bridge reminder: `emulate` reloads the page and drops the fetch-rewrite `initScript`; emulate first, then navigate with the init script, then confirm the source pill reads "REPLAY · NOT LIVE".

## 6. Observations (not changed, outside this task)

- At 2560x1440 the app is capped at 1800 px wide and the chart is 608 px high, so a large screen shows empty margins and space below the chart.
- At 1280x720 the "Mở lệnh PAPER" button is below the first screen (the action word and plan are visible; the button needs a scroll).

Both are layout polish for large or short desktop windows; say if you want them handled.

## 7. Bringing mobile back later

Run `XAU_E2E_MOBILE=1` (mock and acceptance) to see what changed; remove the `@mobile` tags and the `grepInvert` line to make those tests gate again; the code is unchanged.
