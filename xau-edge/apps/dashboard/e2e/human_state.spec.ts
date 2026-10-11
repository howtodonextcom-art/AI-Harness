import { expect, test, type Page } from "@playwright/test";
import { SURFACES, humanState, humanSurface } from "../lib/humanState";
import type { TradeView } from "../lib/trade";
import { clone, mock, view } from "./fixtures/trade";

/**
 * MCP QA round 3 (2026-10-11), defects H-01, M-01, M-02, M-03, M-04: the Human must never get two instructions on one
 * screen. Every surface follows the server-authorized action (`hero.action`), never `hero.state` or the plan alone.
 * These fixtures deliberately carry the CONFLICTING inputs (a complete plan next to a blocked action; a plan next to
 * an open position): the earlier tests passed because their fixture omitted one side of the conflict.
 */

const BLOCK = { code: "CLOSURE_NEAR", message: "PAPER ENTRY BLOCKED: the weekly market close is approaching" };

function blocked(side: "BUY" | "SELL"): TradeView {
  const v = view(side === "BUY" ? "buy" : "sell");
  // what the real engine sends for a READY setup the desk refuses: hero.state stays *_READY, the action is WAIT/BLOCKED
  v.hero.action = { ...v.hero.action, code: "WAIT", stage: "BLOCKED", blocked_by: BLOCK } as TradeView["hero"]["action"];
  v.actionable = false;
  v.entry_blockers = [{ code: BLOCK.code, message: BLOCK.message }];
  expect(v.hero.state).toBe(`${side}_READY`);
  expect(v.trade_plan?.complete, "the fixture must carry a complete plan").toBe(true);
  return v;
}

async function expectNoPermissionLook(page: Page, side: "BUY" | "SELL", action: "WAIT" | "EXIT" = "WAIT") {
  await expect(page.getByTestId("system-plan-overlay")).toHaveCount(0);
  await expect(page.getByTestId("system-action-badge")).toHaveCount(0);
  await expect(page.getByTestId(`line-${side}-ENTRY`)).toHaveCount(0);
  await expect(page.getByTestId("take-paper")).toHaveCount(0);
  await expect(page.getByTestId("mobile-action-bar")).toHaveCount(0);
  await expect(page.getByTestId("fs-open")).toHaveCount(0);
  await expect(page.getByTestId("hero")).toHaveAttribute("data-action", action);
  const text = (await page.locator("body").innerText()).replace(/\s+/g, " ");
  expect(text).not.toMatch(/SẴN SÀNG (MUA|BÁN)/);
  expect(text).not.toMatch(/(MUA|BÁN) · R:R/);
}

for (const side of ["BUY", "SELL"] as const) {
  test(`H-01 ${side}: a blocked READY setup looks like CHỜ everywhere (desktop)`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await mock(page, blocked(side));
    await page.goto("/trade");
    await expect(page.getByTestId("hero")).toHaveAttribute("data-hero-state", "SETUP_BLOCKED");
    await expectNoPermissionLook(page, side);
    // the numbers survive only as a folded, labelled reference, neutral and after the label
    const ref = page.getByTestId("blocked-reference");
    await expect(ref).toContainText("SETUP BỊ CHẶN — KHÔNG ĐƯỢC VÀO LỆNH");
    await expect(page.getByTestId("hero-levels")).toHaveAttribute("data-blocked", "true");
    for (const id of ["hero-entry", "hero-sl", "hero-tp"]) await expect(page.getByTestId(id)).toHaveText("—");
  });

  test(`H-01 ${side}: ...and on a phone, where M-01 requires the reason without opening details`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await mock(page, blocked(side));
    await page.goto("/trade");
    await expectNoPermissionLook(page, side);
    const hero = page.getByTestId("hero");
    await expect(hero).toContainText("CHỜ");
    // M-01: the actual blocker, visible (not display:none, not inside a closed <details>)
    const reason = hero.getByText("Gần giờ thị trường đóng cửa", { exact: false }).first();
    await expect(reason).toBeVisible();
    await expect(page.getByTestId("action-when")).toContainText("Chờ lý do chặn hết");
  });
}

test("H-01 red team: every blocker code keeps the READY look away (duplicate, cooldown, risk, daily, open position, stale quote)", async ({ page }) => {
  for (const code of ["DUPLICATE_SETUP", "COOLDOWN", "RISK_LIMIT", "DAILY_LIMIT", "OPEN_POSITION", "QUOTE_STALE", "PAPER_STATE_ERROR"]) {
    const v = blocked("BUY");
    v.hero.action = { ...v.hero.action, blocked_by: { code, message: code } } as TradeView["hero"]["action"];
    await mock(page, v);
    await page.goto("/trade");
    await expectNoPermissionLook(page, "BUY");
  }
});

test("M-02: a manual close shows ĐÃ THOÁT with reason, P&L, R and duration even though the setup is consumed", async ({ page }) => {
  const v = view("closedPaper");
  v.trade_plan = clone(view("buy").trade_plan); // the old setup is still on the signal: the conflicting input
  v.desk!.last_exit = { ...v.desk!.last_exit!, exit_reason: "MANUAL_CLOSE", net_pnl: -0.9, r_multiple: -0.04, duration_minutes: 7 };
  await mock(page, v);
  await page.goto("/trade");
  await expect(page.getByTestId("action-word")).toHaveText("ĐÃ THOÁT");
  await expect(page.getByTestId("action-sub")).toContainText("-$0.90");
  await expect(page.getByTestId("action-sub")).toContainText("-0.04R");
  await expect(page.getByTestId("action-sub")).toContainText("7 phút");
  await expectNoPermissionLook(page, "BUY", "EXIT");
  for (const id of ["hero-entry", "hero-sl", "hero-tp", "hero-rr"]) await expect(page.getByTestId(id), "an exited trade shows no Entry/SL/TP").toHaveText("—");
});

test("M-03: while HOLDing, every current-entry surface shows the actual fill, the plan entry never", async ({ page }) => {
  const v = view("openPaper");
  v.trade_plan = clone(view("buy").trade_plan); // BOTH inputs present
  v.trade_plan!.planned_entry = 4236.47;
  v.desk!.position!.fill_price = 4236.5;
  expect(v.trade_plan!.complete).toBe(true);
  await mock(page, v);
  await page.goto("/trade");
  await expect(page.getByTestId("hero")).toHaveAttribute("data-action", "HOLD");
  await expect(page.getByTestId("hero-entry")).toHaveText("4236.50");
  const panel = page.getByTestId("paper-position");
  const panelText = (await panel.innerText()).replace(/\s+/g, " ");
  expect(panelText).toMatch(/Giá vào \(khớp\) ?4236\.50/);
  expect(panelText).not.toMatch(/Giá vào \(khớp\) ?4236\.47/);
  expect(panelText).toMatch(/Giá kế hoạch ?4236\.47/); // the plan may appear only as secondary context, labelled
  const entry = await page.getByTestId("system-plan-overlay").evaluate((el) => Number((el.querySelector("[data-role=entry]") as HTMLElement).dataset.price));
  expect(entry).toBe(4236.5);
  await expect(page.getByTestId("system-plan-overlay")).toHaveAttribute("data-mode", "POSITION");
  await expect(page.getByTestId("hero-entry")).not.toHaveText("4236.47");
});

test("M-04: no contradictory or internal wording in blocked, expired and waiting states", async ({ page }) => {
  const cases: [string, TradeView][] = [["blocked", blocked("BUY")], ["expired", view("expired")], ["wait", view("wait")], ["buyWatch", view("buyWatch")]];
  for (const [name, v] of cases) {
    await mock(page, v);
    await page.goto("/trade");
    await expect(page.getByTestId("hero")).toBeVisible();
    const text = (await page.getByTestId("hero").innerText()).replace(/\s+/g, " ");
    expect(text, name).not.toContain("Một nguồn sự thật");
    const hasSetup = /Có setup (mua|bán)|đã đủ điều kiện kỹ thuật/.test(text);
    const noSetup = /chưa có setup/i.test(text);
    expect(hasSetup && noSetup, `${name}: "có setup" and "chưa có setup" together in: ${text.slice(0, 300)}`).toBe(false);
  }
});

test("the Human-state table: only a complete READY plan carries a BUY/SELL surface; everything else is inert or reference-only", () => {
  for (const [id, s] of Object.entries(SURFACES)) {
    const permission = s.overlay === "PLAN" || s.stickyBar === "OPEN" || s.ticket || s.heroLevels === "PLAN" || s.planLines;
    expect(permission, id).toBe(id === "BUY_READY" || id === "SELL_READY");
  }
  expect(SURFACES.WAIT_BLOCKED.referencePlan).toBe(true);
  expect(SURFACES.HOLD).toMatchObject({ overlay: "POSITION", stickyBar: "CLOSE", heroLevels: "FILL" });
  const buy = view("buy");
  const ctx = { expiredNow: false, offline: false };
  expect(humanState(buy, ctx)).toBe("BUY_READY");
  expect(humanState(buy, { ...ctx, expiredNow: true })).toBe("EXPIRED");
  expect(humanState(buy, { ...ctx, offline: true })).toBe("UNAVAILABLE");
  expect(humanState(blocked("SELL"), ctx)).toBe("WAIT_BLOCKED");
  expect(humanState(view("openPaper"), ctx)).toBe("HOLD");
  expect(humanState(view("closedSl"), ctx)).toBe("EXIT");
  expect(humanState(view("marketClosed"), ctx)).toBe("MARKET_CLOSED");
  expect(humanState(view("stale"), ctx)).toBe("UNAVAILABLE");
  expect(humanState(view("buyArmed"), ctx)).toBe("WAIT_NO_TRIGGER");
  expect(humanState(view("buyWatch"), ctx)).toBe("WAIT_NO_SETUP");
  expect(humanState(view("sellInvalidated"), ctx)).toBe("INVALIDATED");
  const noPlan = view("buy");
  noPlan.trade_plan = null;
  expect(humanState(noPlan, ctx), "a BUY action without a plan is never a permission look").toBe("WAIT_NO_SETUP");
  expect(humanSurface(buy, ctx)).toMatchObject({ overlay: "PLAN", stickyBar: "OPEN", ticket: true });
});

// ---- the LOW defects of the same QA round -----------------------------------------------------------------------

test("L-01: opening one popover or dialog closes the others (only one on screen)", async ({ page }) => {
  await mock(page, view("wait"));
  await page.goto("/trade");
  await page.getByTestId("drawing-manager-btn").click();
  await expect(page.getByTestId("drawing-manager")).toBeVisible();
  await page.getByTestId("tool-alert").click();
  await expect(page.getByTestId("alert-popover")).toBeVisible();
  await expect(page.getByTestId("drawing-manager")).toHaveCount(0);
  await page.getByTestId("shortcut-help").click();
  await expect(page.getByTestId("shortcut-modal")).toBeVisible();
  await expect(page.getByTestId("alert-popover")).toHaveCount(0);
  expect(await page.locator("[role=dialog]").count(), "one dialog at a time").toBe(1);
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("shortcut-modal")).toHaveCount(0);
  expect(await page.locator("[role=dialog]").count()).toBe(0);
});

test("L-02: alerts and horizontal lines are listed and removable from their own panels", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("xau-edge:v3:REPLAY:XAUUSD:levels", JSON.stringify([{ id: "l1", price: 4204.12, label: "Đường" }]));
    window.localStorage.setItem("xau-edge:v3:REPLAY:XAUUSD:alerts", JSON.stringify([{ id: "a1", price: 4190, direction: "DOWN", createdAt: "2025-12-05T14:00:00Z", firedAt: null }]));
  });
  await mock(page, view("wait"));
  await page.goto("/trade");
  await page.getByTestId("tool-alert").click();
  await page.getByTestId("alert-delete").click();
  await expect(page.getByTestId("alert-list")).toHaveCount(0);
  await page.getByTestId("drawing-manager-btn").click();
  await page.getByTestId("manager-level-delete").click();
  await expect(page.getByTestId("manager-levels")).toHaveCount(0);
  const stored = await page.evaluate(() => [window.localStorage.getItem("xau-edge:v3:REPLAY:XAUUSD:levels"), window.localStorage.getItem("xau-edge:v3:REPLAY:XAUUSD:alerts")]);
  expect(stored).toEqual(["[]", "[]"]);
});

test("L-03: a closed market labels M1 as ĐÓNG CỬA, an open market with stale bars keeps DỮ LIỆU CŨ", async ({ page }) => {
  const closed = view("marketClosed");
  closed.timeframes = (closed.timeframes ?? []).map((r) => (r.timeframe === "M1" ? { ...r, state: "STALE" } : r));
  await mock(page, closed);
  await page.goto("/trade");
  await expect(page.getByTestId("matrix-M1")).toContainText("ĐÓNG CỬA");
  await expect(page.getByTestId("matrix-M1")).not.toContainText("DỮ LIỆU CŨ");
  const open = view("wait");
  open.timeframes = (open.timeframes ?? []).map((r) => (r.timeframe === "M1" ? { ...r, state: "STALE" } : r));
  await mock(page, open);
  await page.goto("/trade");
  await expect(page.getByTestId("matrix-M1")).toContainText("DỮ LIỆU CŨ");
});

test("L-04: at 200% zoom (720x450) the chart is at least 280 px high, with the hero and controls still visible", async ({ page }) => {
  await page.setViewportSize({ width: 720, height: 450 });
  await mock(page, view("buy"));
  await page.goto("/trade");
  const box = await page.getByTestId("trade-chart").boundingBox();
  expect(box!.height).toBeGreaterThanOrEqual(280);
  await expect(page.getByTestId("action-word")).toBeVisible();
  await expect(page.getByTestId("chart-tf-M5")).toBeVisible();
});

test("L-05, L-06, L-07: shortcut note, loss-limit explanation, and a labelled reopening time", async ({ page }) => {
  await mock(page, view("marketClosed"));
  await page.goto("/trade");
  await expect(page.getByTestId("reopen-at")).toContainText("(GMT+7)");
  await expect(page.getByTestId("loss-limits-note")).toContainText("3,5%");
  await expect(page.getByTestId("loss-limits-note")).toContainText("chặn lệnh mới");
  await page.getByTestId("shortcut-help").click();
  await expect(page.getByTestId("shortcut-note")).toContainText("2 = M15");
});

test("independent review finding: the BUY/SELL signal marker of a blocked setup is a grey 'bị chặn' dot, not an offer-looking arrow", async ({ page }) => {
  for (const side of ["BUY", "SELL"] as const) {
    const v = blocked(side);
    const markers = {
      simulated: true,
      source_mode: v.source_mode,
      paper_trades: [],
      signals: [{ at: v.served_at, bar_time: v.served_at, setup_id: v.trade_plan!.setup_id, side, entry: v.trade_plan!.planned_entry, sl: v.trade_plan!.sl, tp1: v.trade_plan!.tp1, tp2: v.trade_plan!.tp2, rr: v.trade_plan!.rr_net, lots: 0.03, expires_at: v.trade_plan!.expires_at, taken: false, strategy_version: "1.2.1" }],
    };
    await mock(page, v, { markers: markers as never });
    await page.goto("/trade");
    await expect(page.getByTestId("trade-chart")).toHaveAttribute("data-blocked-markers", "1");
    // and a READY (not blocked) setup keeps its normal arrow
    const ready = view(side === "BUY" ? "buy" : "sell");
    await mock(page, ready, { markers: { ...markers, signals: markers.signals.map((s) => ({ ...s, setup_id: ready.trade_plan!.setup_id })) } as never });
    await page.goto("/trade");
    await expect(page.getByTestId("trade-chart")).toHaveAttribute("data-blocked-markers", "0");
  }
});

test("independent review finding: the stale quote and the data age never contradict (GIÁ CŨ 2 phút next to dữ liệu: 0s)", async ({ page }) => {
  const v = view("stale");
  await mock(page, v);
  await page.goto("/trade");
  await expect(page.getByTestId("price-stale")).toContainText("GIÁ CŨ");
  const stale = (await page.getByTestId("price-stale").innerText()).replace(/\s+/g, " ");
  const age = (await page.getByTestId("data-age").innerText()).replace(/\s+/g, " ");
  expect(stale).toContain("GIÁ CŨ");
  expect(age, `data age must not claim fresh data while the quote is stale: "${age}" vs "${stale}"`).not.toMatch(/: 0 giây/);
});

test("independent review finding: the phone bar carries the entry price, and the chart expiry label uses the trader's zone", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mock(page, view("buy"));
  await page.goto("/trade");
  await expect(page.getByTestId("mobile-action-bar")).toContainText("@ 4236.47");
  await expect(page.getByTestId("system-plan-overlay")).toContainText("GMT+7");
  await expect(page.getByTestId("system-plan-overlay")).not.toContainText(" UTC");
});
