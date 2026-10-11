# FINAL PRODUCT CLOSURE — XAUUSD Discipline & Research Terminal

Date: 2026-10-11 · Branch: `main` · Scope: product, deployment and operations closure. **No edge research was run.**

Product description (binding): **XAUUSD Discipline & Research Terminal** — a PAPER-only decision-support and discipline desk with a research
harness. It is **not** a validated signal engine. Evidence ladder: UNVALIDATED.

## 1. Research closure (verified once, not re-run)

| Item | State | Evidence |
|---|---|---|
| Programme V3 | **CLOSED, NO VIABLE EDGE FOUND** | `docs/research/edge-program-v3/ledger.md`, `results/F1_stage1.json`, `results/F3_stage1.json` |
| F1 Stage 1 | FAIL (red-team confirmed, `a988a6b`) | `F1_stage1.json` |
| F3 Stage 1 | FAIL, family closed (`8da3b87`) | `F3_stage1.json` |
| F2 | deferred, never run | ledger |
| Test-H (2022-01-01..2025-04-30) | **UNTOUCHED** | ledger line 9; no result file references it |
| Holdout (2026-05-01..2026-10-07) | **UNTOUCHED** | same |
| Trial count | K_V3 = 3 (V2 cap 24, used 20); K_total for locked splits = 44 (21 + 20 + 3) | ledger |

Nothing in the research tree was edited in this closure. Test-H/Holdout were re-checked at the end (section 14): still untouched.

## 2. Git state

Local `main` is ahead of `origin/main`. Nothing was pushed (project rule: push only on owner request).
Commits made in this closure, in the requested order, history not rewritten:

1. `0ea0069` fix(dashboard): UNAVAILABLE blanks plan levels; merge stale bars and stale quote into one line (+ 6-state × 3-viewport spec, acceptance expectation)
2. `e710d2f` fix(dashboard): modal returns focus to the real opener; remove focus debug logging (+ regression test)
3. ECC audit docs commit (documentation only; no ECC install was performed)
4. this report

Working tree was clean before this report. The only debug artefact (`.cursor/debug-e0800b.log`, a log written by my own focus instrumentation) was deleted.
Exact push command, for the owner: `git push origin main`.

## 3. UI fixes

| # | Defect | Fix | Test |
|---|---|---|---|
| 1 | UNAVAILABLE still showed plan numbers/Risk/Lot | Entry/SL/TP/R:R render "—", Risk/Lot hidden, copy "Kế hoạch bị chặn, không dùng." | `qa_2026_10_11.spec.ts` |
| 2 | Modal focus did not return to the opener (mouse-open) | opener captured once at mount, restored on cleanup; survives React double effect | `terminal.spec.ts` "focus returns to the button the mouse opened…" |
| 3 | Two lines for stale bars + stale quote | one human line "Dữ liệu giá và báo giá đã quá cũ…", both codes (`DATA_STALE`, `QUOTE_STALE`) in technical details | `terminal.spec.ts`, acceptance `desk.spec.ts` |

## 4. Debug cleanup

All `// #region agent log` fetch instrumentation was removed from `Modal.tsx` before the first commit of that file; none ever reached git history.
`grep` for `7345`/`agent log` in `apps/dashboard` is empty. Verified by clean `tsc`, `eslint`, production build.

## 5. Browser acceptance (mock/fixture)

- Playwright mock suite: **331 passed** (built from the current source, no stale `.next`).
- Six states WAIT/BUY/SELL/HOLD/EXIT/UNAVAILABLE × 1440×900, 1920×1080, 390×844 (matrix spec + visual montage review): no overlap, no clipping, no horizontal overflow, hero above the fold, no scroll trap, technical details reachable, PAPER and UNVALIDATED labels present, Risk/Lot only when a sized plan exists, `take-paper` only for BUY/SELL, no console errors.
- Dark-mode axe contrast fixed earlier (label opacity removed).

## 6. Real-backend acceptance

`playwright.acceptance.config.ts` (replay API :8100 + dashboard :3200, real TradeEngine and journal): **31 passed**.
One failure appeared in an intermediate run: `stale data hides the plan` asserted the old two-line wording. Classification: **TEST BUG** (expectation not updated for the deliberate fix #3). Fixed in `desk.spec.ts`; clean rerun 31/31.

## 7. Production deployment

Deployed while the market was **CLOSED** (Sun 2026-10-11 07:55 UTC; reopens Mon 2026-10-12 05:05 GMT+7).

- Source: `HEAD` = `9f93a56` at deploy time (UI source identical to commits `0ea0069`/`e710d2f`); build id `GVKSmYhIdi2GAsV1sba8f`, built from source after removing the old `.next`.
- Stack stopped, rebuilt, restarted with `scripts\start_market_stack.ps1 -Dashboard`.
- :8000 → 200, :3000/trade → 200. `source_mode = LIVE`. Supervisor: collector, news, api, dashboard all alive, 0 restarts.
- `/trade/decision`: action WAIT / `MARKET_CLOSED`; `data_ages.collector_heartbeat` FRESH; MT5 "FTMO-Demo, read-only".
- Screenshots (1440, 390): PAPER label, UNVALIDATED label, coverage "48.6% / 95%", plan levels "—", no overflow.
- The build id is not exposed by the API/UI; it is recorded here from `.next/BUILD_ID`. (Listed in section 11.)

## 8. Watchdog verification

Implementation: `ChildSpec.heartbeat` + `stale_after=300 s`, `Supervisor._kill_if_hung`, `last_restart_reason`, `hung_kills` (commit `fe7aaa4`).

- Unit tests: `tests/unit/ops` **41 passed** (fake clock).
- Sandbox simulation with **real processes in a temp dir** (not the live collector): a child that heartbeats then hangs, `stale_after = 4 s`, plus a healthy control child, 30 s run.
  Result: hung child killed **twice** (`hung_kills=2`), reason recorded `HUNG heartbeat 4s old`, exactly one live copy at the end (no duplicate process), exponential backoff prevented a restart storm, control child never touched (`hung_kills=0`, one PID), no leftover processes. **PASS.**
- Data integrity: the watchdog kills only the process tree; collector writes are the existing atomic/append paths. Parity monitor unchanged.

Outage classes: **A** collector reconnect hang → code-fixable, fixed by the watchdog. **B** Windows session ended / sleep / power → **environmental**; the watchdog cannot fix it (it dies with the session).

## 9. Windows session and power analysis (facts, read-only)

| Fact | Value |
|---|---|
| Task "XAU-EDGE Market Stack" | principal `Kieu Oanh`, **LogonType Interactive** (runs only while logged on), RunLevel Limited |
| Trigger | At logon only |
| Task settings | WakeToRun False; ExecutionTimeLimit PT10M (moot: the task is a ~30 s launcher that starts the supervisor detached); restart 3 × 1 min; IgnoreNew |
| Sleep | AC: **never**; battery (DC): sleep after 600 s; hibernate never; display off AC never / DC 180 s |
| Sleep states | S3 standby available |
| Last boot / session | 2026-10-11 08:44, console session 1 active |
| Sleep events in last 7 days | none found |

Consequences: the stack survives as long as the user stays logged on and the machine is on AC. A logoff, reboot without auto-logon, or running on battery stops or sleeps it. No credentials or power settings were changed.

### Host-persistence options

Criteria defined first: **reliability, security, credential impact, maintenance, cost, complexity.**

| Option | Reliability | Security | Credential impact | Maintenance | Cost | Complexity |
|---|---|---|---|---|---|---|
| A. Current: interactive logon task | medium (needs logon + AC) | best (no stored password) | none | low | 0 | low |
| B. Persistent Task Scheduler ("run whether user is logged on or not") | high across logoff/reboot | medium (Windows stores the password; MT5 terminal GUI may not run without a session) | **requires the Windows password** | medium | 0 | medium |
| C. Always-on host (mini-PC or small Windows VPS) | highest | medium (new attack surface; broker-demo login on a second machine) | new credentials on a new host | medium–high | monthly or hardware | high |

**Recommendation: stay on A with discipline (AC power, no logoff, auto-logon is the owner's call) until the operational-forward need is confirmed; if 15 continuous trading days are wanted, move to C.** B is weaker than it looks because the MT5 terminal is a GUI process.

**OWNER ACTION REQUIRED** for B or C (credentials / host decision). Not executed.
**HARD EXTERNAL BLOCKER** for unattended operation: Windows session/power dependency.

## 10. Operational forward

Not a research gate. Decision coverage is **48.6% vs the 95% gate**; reaching it needs ~15 market-open trading days of continuous running, only if the owner wants it. Cannot be accelerated or faked.
No live trade lifecycle occurred during this closure (market closed), so none was captured. None was fabricated.

## 11. Final test matrix

| Check | Result |
|---|---|
| Python full (`pytest -m "not mt5"`) | **2635 passed, 1 skipped (symlink privileges on Windows), 3 deselected (mt5)** |
| Python coverage | 90% total |
| Research / ops / trading / schema / goldens | included in the full run, all green |
| Watchdog unit tests | 41 passed (`tests/unit/ops`) |
| Watchdog sandbox simulation | PASS |
| `ruff check` / `ruff format --check` | clean / 711 files formatted |
| `mypy --strict` | 456 files, no issues |
| `tsc --noEmit`, `eslint .` | clean |
| `next build` (production) | PASS |
| Playwright mock | 331 / 331 |
| Real-backend acceptance | 31 / 31 |

Flaky classification: nothing flaky in the final runs. Past incidents: 308 Playwright failures "Executable doesn't exist" = **ENVIRONMENT** (browser cache removed; `playwright install chromium`); NEWS-01 CI red = **TEST BUG** (old 3-state vocabulary); dark-mode axe = **REAL BUG** (fixed); acceptance stale-line failure = **TEST BUG**; tests writing tracked screenshots = **TEST BUG** (gated by `SAVE_DOC_SHOTS`).

## 12. Remaining limitations (LOW, documented, not blocking)

Layout shift (CLS) on first paint; one 503 on a polled endpoint during startup; a table cell missing header association flagged by axe in a non-critical table; build id not exposed in the UI; `canonical-brain.md` has minor drift; `FINAL_COMPLETION_AND_POST_TERMINAL_AUDIT.md` referenced in the brief does not exist; ECC install (Phase 3) not run, awaiting owner choices C1–C6.

## 13. Archived research state

V3 CLOSED: F1 FAIL, F3 FAIL, F2 deferred, red-team reviews committed, ledger K_V3=3 / K_total=44, Test-H and Holdout protected and unused. Freeze guard is procedural (`research_v2/guards.py`).

Future ideas (**documentation only — POST-HOC, NOT VALIDATED, NOT AUTHORIZED**): observing the F1 opposite direction. Any use would be a new hypothesis with its own pre-registration and K accounting. **NEW EDGE RESEARCH: NOT AUTHORIZED.**

## 14. Boundaries re-verified at the end

No F1 reverse, no F1b/F3b, no new hypothesis, no Test-H, no Holdout, no baseline retune, no indicators, no ML, no BE/trailing/partial, no Demo, no Funded, no broker order, no credential or password change. Test-H/Holdout untouched (ledger and result files; no CRITICAL).

## 15. Final scores (separate, not averaged)

| Dimension | Score | Basis |
|---|---|---|
| Research programme | COMPLETE (terminal: no viable edge) | section 1 |
| Codebase engineering | 96% | all gates green; LOW items in section 12 |
| Human decision UI | 95% | 6 states × 3 viewports clean; CLS/axe LOWs |
| Production deployment | COMPLETE | section 7 |
| Real-backend acceptance | PASS 31/31 | section 6 |
| Operational reliability | PARTIAL | watchdog fixes class A; class B external |
| Forward coverage | 48.6% / 95% | needs trading days |
| Validated edge | 0% | |
| Demo readiness | LOCKED | |
| Real-money readiness | NO | |

## Closure verdict

PROJECT CLOSURE: **COMPLETE EXCEPT EXTERNAL OWNER-CONTROLLED BLOCKER** (Windows session/power dependency and the optional forward-coverage run).

```
RESEARCH PROGRAM: COMPLETE
RESEARCH TERMINAL STATE: NO VIABLE EDGE FOUND
CODEBASE ENGINEERING: 96% COMPLETE
HUMAN DECISION UI: 95% COMPLETE
MOCK/FIXTURE ACCEPTANCE: PASS (331/331)
REAL-BACKEND ACCEPTANCE: PASS (31/31)
LIVE DEPLOYMENT: PASS (new build, source_mode LIVE, deployed while market closed)
WATCHDOG: PASS (unit 41/41 + real-process sandbox simulation; fixes outage class A only)
WINDOWS SESSION RELIABILITY: EXTERNAL LIMITATION (interactive logon + AC power; OWNER ACTION REQUIRED for persistence)
OPERATIONAL FORWARD: NOT STARTED (coverage 48.6% / 95%; needs trading days, optional)
VALIDATED EDGE: 0%
TEST-H: UNTOUCHED
HOLDOUT: UNTOUCHED
DEMO: LOCKED
FUNDED: LOCKED
REAL-MONEY SUPPORT: NO
BLOCKING BUGS: NONE
BLOCKING OPS ISSUES: Windows session/power dependency (external, owner-controlled)
PROJECT CLOSURE: COMPLETE EXCEPT EXTERNAL BLOCKER
NEXT OWNER ACTION: choose host persistence (stay on AC + logged on, or an always-on host), then decide on push (git push origin main)
NEW EDGE RESEARCH: NOT AUTHORIZED
```
