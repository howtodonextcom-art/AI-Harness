import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

/**
 * Real-browser acceptance of the trading terminal. The API is the REAL one (`TradeEngine`,
 * `PaperDesk`, journal, alerts) running over burned FTMO bars with a replay clock; the page is the
 * production build. Provenance of everything below: ACCEPTANCE REPLAY - NOT LIVE (the page says so).
 */

const API = "http://127.0.0.1:8100";
const SHOTS = "../../docs/reports/img/trading-ui/after";

async function load(page: Page, request: APIRequestContext, name: string, path = "/trade") {
  const res = await request.post(`${API}/acceptance/load/${name}`);
  expect(res.ok()).toBeTruthy();
  // the page asks the production API port; the acceptance API answers instead (same routes, same code)
  await page.route("http://127.0.0.1:8000/**", async (route) => {
    const response = await route.fetch({ url: route.request().url().replace(":8000", ":8100") });
    await route.fulfill({ response });
  });
  await page.goto(path);
  await expect(page.getByTestId("hero").or(page.getByTestId("api-down-banner"))).toBeVisible({ timeout: 30_000 });
}

const advance = (request: APIRequestContext, minutes: number) => request.post(`${API}/acceptance/advance?minutes=${minutes}`);
const hero = (page: Page) => page.getByTestId("hero");
const shot = async (page: Page, name: string, full = false) => {
  await page.evaluate(() => window.scrollTo(0, 0)); // every screenshot starts at the top: the price and the decision
  await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: full });
};

async function noHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
}

async function openPaper(page: Page) {
  await page.getByTestId("take-paper").click();
  await expect(page.getByTestId("confirm-open-modal")).toBeVisible();
  await page.getByTestId("confirm-paper").click();
  await expect(page.getByTestId("paper-position")).toBeVisible({ timeout: 20_000 });
}

test.describe("replay is always labelled", () => {
  test("WAIT: market bar, pipeline, what is awaited, clickable stages", async ({ page, request }) => {
    await load(page, request, "wait");
    await expect(hero(page)).toHaveAttribute("data-hero-state", "WAIT");
    await expect(page.getByTestId("action-word")).toHaveText("CHỜ");
    await expect(page.getByTestId("replay-banner")).toContainText("KHÔNG PHẢI LIVE");
    await expect(page.getByTestId("source-pill")).toContainText("NOT LIVE");
    await expect(page.getByTestId("price-bid")).not.toHaveText("—");
    await expect(page.getByTestId("day-change")).not.toHaveText("—");
    await expect(page.getByTestId("session")).not.toHaveText("—");
    await expect(page.getByTestId("countdown")).toContainText("đóng sau");
    await expect(page.getByTestId("waiting-for")).toBeAttached();
    await expect(page.getByTestId("blocked-by")).toBeAttached();
    await expect(page.getByTestId("take-paper")).toHaveCount(0);
    await expect(page.getByTestId("status-strip")).toHaveCount(0); // engineering status is in the System tab
    const stages = page.getByTestId("stages").getByRole("button");
    const count = await stages.count();
    expect(count).toBeGreaterThan(3);
    for (let i = 0; i < count; i++) {
      const tf = await stages.nth(i).getAttribute("data-timeframe");
      await stages.nth(i).click();
      await expect(page.getByTestId(`chart-tf-${tf}`)).toHaveAttribute("aria-pressed", "true");
    }
    await page.getByTestId("tab-system").click();
    await expect(page.getByTestId("status-strip")).toContainText("LOCKED");
    await expect(page.getByTestId("status-strip")).toContainText("UNVALIDATED");
    await noHorizontalScroll(page);
    await page.getByTestId("tab-overview").click();
    await shot(page, "01-replay-wait");
  });

  test("real BUY setup: plan, chart lines, confirmation, paper position", async ({ page, request }) => {
    await load(page, request, "buy_tp");
    await expect(hero(page)).toHaveAttribute("data-hero-state", "BUY_READY");
    await expect(page.getByTestId("hero")).toHaveAttribute("data-hero-state", "BUY_READY");
    for (const id of ["plan-entry", "plan-sl", "plan-tp", "plan-rr", "plan-lots", "plan-risk", "plan-version"]) {
      await expect(page.getByTestId(id)).not.toContainText("—");
    }
    await expect(page.getByTestId("plan-version")).toContainText("v1.2.1");
    await expect(page.getByTestId("expiry")).toBeVisible();
    await expect(page.getByTestId("chart-legend")).toContainText(/ENTRY/);
    await expect(page.getByTestId("chart-legend")).toContainText(/SL/);
    await expect(page.getByTestId("chart-legend")).toContainText(/TP/);
    await expect(page.getByTestId("rr-ruler")).toBeVisible();
    await expect(page.getByTestId("take-paper")).toBeEnabled();
    await shot(page, "02-replay-buy-ready");
    // confirmation first, nothing opens on the first click
    await page.getByTestId("take-paper").click();
    await expect(page.getByTestId("confirm-open-modal")).toBeVisible();
    await shot(page, "03-replay-confirm-open");
    await page.getByTestId("cancel-paper").click();
    await expect(page.getByTestId("paper-position")).toHaveCount(0);
    await openPaper(page);
    await expect(hero(page)).toHaveAttribute("data-hero-state", "POSITION_OPEN");
    await expect(page.getByTestId("plan-card")).toHaveCount(0);
    await expect(page.getByTestId("position-entry")).not.toContainText("—");
    await expect(page.getByTestId("position-levels")).not.toContainText("—");
    await shot(page, "04-replay-paper-open");
  });

  test("real SELL setup", async ({ page, request }) => {
    await load(page, request, "sell_ready");
    await expect(hero(page)).toHaveAttribute("data-hero-state", "SELL_READY");
    await expect(page.getByTestId("hero")).toHaveAttribute("data-hero-state", "SELL_READY");
    await expect(page.getByTestId("plan-side")).toContainText("BÁN");
    await expect(page.getByTestId("replay-banner")).toContainText("KHÔNG PHẢI LIVE");
    await shot(page, "05-replay-sell-ready");
  });
});

test.describe("the real chart", () => {
  test("crosshair readout, marker details, fullscreen, timeframe switch and the sessions overlay on real bars", async ({ page, request }) => {
    await load(page, request, "buy_tp");
    await openPaper(page);
    await advance(request, 60);
    await expect(hero(page)).toHaveAttribute("data-hero-state", "EXITED", { timeout: 20_000 });
    await page.getByTestId("overlay-menu").click();
    await page.getByTestId("toggle-history").check();
    await page.getByTestId("toggle-sessions").check();
    await page.getByTestId("overlay-menu").click();
    const box = (await page.getByTestId("trade-chart").boundingBox())!;
    const readout = page.getByTestId("ohlc-readout");
    const before = await readout.innerText();
    await page.mouse.move(box.x + box.width * 0.35, box.y + box.height * 0.5);
    await expect.poll(async () => readout.innerText()).not.toBe(before);
    // the BUY made at 14:45 sits on the M5 trigger bar 14:40 and, on M1, on the bar closed at 14:45
    const buy = page.getByTestId("chart-markers").locator('li[data-kind="BUY"]');
    await expect(buy).toHaveAttribute("data-bar-time", "2025-12-05T14:40:00.000Z");
    await page.getByTestId("chart-tf-M1").click();
    await expect(buy).toHaveAttribute("data-bar-time", "2025-12-05T14:44:00.000Z");
    await page.getByTestId("chart-tf-M5").click();
    await expect(page.getByTestId("chart-markers").locator('li[data-kind="EXIT"]')).toContainText("TAKE_PROFIT");
    await buy.getByRole("button", { name: "Xem chi tiết" }).focus();
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("marker-popover")).toContainText("Tín hiệu MUA");
    await expect(page.getByTestId("marker-popover")).toContainText("REPLAY (không phải live)");
    await shot(page, "06-replay-marker-details");
    await page.getByRole("button", { name: "Đóng chi tiết" }).click();
    await page.getByTestId("chart-fullscreen").click();
    await expect(page.getByTestId("fullscreen-summary")).toBeVisible();
    await shot(page, "07-replay-fullscreen");
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("fullscreen-summary")).toHaveCount(0);
  });
});

test.describe("paper lifecycle through the real API", () => {
  test("TAKE_PROFIT exit (BUY): marker, exited hero, activity feed and journal row", async ({ page, request }) => {
    await load(page, request, "buy_tp");
    await openPaper(page);
    await advance(request, 60);
    await expect(hero(page)).toHaveAttribute("data-hero-state", "EXITED", { timeout: 20_000 });
    await page.getByTestId("tab-position").click();
    await expect(page.getByTestId("paper-history")).toContainText("TAKE_PROFIT");
    await page.getByTestId("tab-activity").click();
    await expect(page.getByTestId("activity-feed")).toContainText("Chạm TP");
    await expect(page.getByTestId("chart-markers")).toContainText(/TAKE_PROFIT/);
    await shot(page, "08-replay-exit-take-profit");
    await page.goto("/journal");
    const row = page.getByTestId("journal-row").first();
    await expect(row).toContainText("BUY");
    await expect(row).toContainText("Chạm TP");
    await expect(page.getByTestId("journal-replay-banner")).toContainText("KHÔNG PHẢI LIVE");
    await page.getByTestId("journal-detail-toggle").first().click();
    await expect(page.getByTestId("journal-detail")).toContainText("ACCEPTANCE_REPLAY");
    await shot(page, "12-replay-journal", true);
    // journal -> chart: the link lands on the trade, on the right timeframe, with its markers
    await page.getByTestId("journal-view-on-chart").first().click();
    await expect(page).toHaveURL(/\/trade\?focus=/);
    await expect(page.getByTestId("chart-tf-M5")).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("chart-markers").locator('li[data-kind="EXIT"]')).toHaveCount(1);
    await shot(page, "13-replay-journal-to-chart");
  });

  test("manual close shows the latest price and P&L first, then closes once", async ({ page, request }) => {
    await load(page, request, "buy_tp");
    await openPaper(page);
    await advance(request, 10);
    await expect(page.getByTestId("position-pnl")).not.toContainText("—", { timeout: 20_000 });
    await page.getByTestId("close-paper").click();
    await expect(page.getByTestId("close-price")).not.toHaveText("—");
    await shot(page, "09-replay-confirm-close");
    await page.getByTestId("confirm-close").click();
    await expect(hero(page)).toHaveAttribute("data-hero-state", "EXITED", { timeout: 20_000 });
    await page.getByTestId("tab-position").click();
    await expect(page.getByTestId("paper-history")).toContainText("MANUAL_CLOSE");
    const journal = await (await request.get(`${API}/trade/journal`)).json();
    expect(journal.trades.filter((t: { exit_reason: string }) => t.exit_reason === "MANUAL_CLOSE")).toHaveLength(1);
  });

  test("a setup that was already taken and closed is WAIT (blocked), never a green BUY (red team)", async ({ page, request }) => {
    await load(page, request, "buy_tp");
    await openPaper(page);
    await page.getByTestId("close-paper").click();
    await page.getByTestId("confirm-close").click();
    await expect(page.getByTestId("paper-position")).toHaveCount(0, { timeout: 20_000 });
    await expect(hero(page)).toHaveAttribute("data-action", "WAIT", { timeout: 20_000 });
    await expect(page.getByTestId("action-sub")).toContainText("không mở được");
    await expect(page.getByTestId("take-paper")).toBeDisabled();
  });

  test("API down: the hero stops saying BUY and says UNAVAILABLE (red team)", async ({ page, request }) => {
    await load(page, request, "buy_tp");
    await expect(hero(page)).toHaveAttribute("data-action", "BUY");
    await page.unroute("http://127.0.0.1:8000/**");
    await page.route("http://127.0.0.1:8000/**", (route) => route.abort());
    await expect(hero(page)).toHaveAttribute("data-action", "UNAVAILABLE", { timeout: 30_000 });
    await expect(page.getByTestId("action-sub")).toContainText("Mất kết nối API");
  });

  test("STOP_LOSS exit (SELL)", async ({ page, request }) => {
    await load(page, request, "sell_ready");
    await openPaper(page);
    await advance(request, 60);
    await expect(hero(page)).toHaveAttribute("data-hero-state", "EXITED", { timeout: 20_000 });
    await page.getByTestId("tab-position").click();
    await expect(page.getByTestId("paper-history")).toContainText("STOP_LOSS");
    await shot(page, "10-replay-exit-stop-loss");
  });

  test("TAKE_PROFIT exit (SELL, v1.1.0 shown as the active version)", async ({ page, request }) => {
    await load(page, request, "sell_tp");
    await page.getByTestId("tab-system").click();
    await expect(page.getByTestId("strategy-active")).toContainText("1.1.0");
    await page.getByTestId("tab-overview").click();
    await openPaper(page);
    await advance(request, 120); // the target is reached ~85 minutes after entry
    await page.getByTestId("tab-position").click();
    await expect(page.getByTestId("paper-history")).toContainText("TAKE_PROFIT", { timeout: 20_000 });
    await expect(page.getByTestId("position-card")).toContainText("Không có lệnh paper đang mở");
  });

  test("TIME_EXIT", async ({ page, request }) => {
    await load(page, request, "buy_time");
    await openPaper(page);
    await advance(request, 180);
    await expect(hero(page)).toHaveAttribute("data-hero-state", "EXITED", { timeout: 20_000 });
    await page.getByTestId("tab-position").click();
    await expect(page.getByTestId("paper-history")).toContainText("TIME_EXIT");
    await shot(page, "11-replay-exit-time");
  });
});

test.describe("failure states are explicit and never a plain WAIT", () => {
  test("stale data hides the plan", async ({ page, request }) => {
    await load(page, request, "stale");
    await expect(hero(page)).toHaveAttribute("data-hero-state", "STALE");
    await expect(page.getByTestId("hero-problems")).toContainText("Dữ liệu giá đã quá cũ");
    await expect(page.getByTestId("plan-card")).toHaveCount(0);
    await expect(page.getByTestId("take-paper")).toHaveCount(0);
    await shot(page, "14-replay-stale");
  });

  test("expired setup cannot be opened", async ({ page, request }) => {
    await load(page, request, "expired");
    await expect(page.getByTestId("hero")).toHaveAttribute("data-hero-state", "EXPIRED_SETUP");
    await expect(page.getByTestId("take-paper")).toHaveCount(0);
    await shot(page, "15-replay-expired");
  });

  test("corrupt paper state fails closed and says so", async ({ page, request }) => {
    await load(page, request, "paper_corrupt");
    await expect(hero(page)).toHaveAttribute("data-hero-state", "UNAVAILABLE");
    await expect(page.getByTestId("hero-problems")).toContainText("PAPER_STATE_ERROR");
    await expect(page.getByTestId("take-paper")).toHaveCount(0);
    await shot(page, "16-replay-paper-state-error");
  });

  test("second writer: read-only, no paper action", async ({ page, request }) => {
    await load(page, request, "writer_conflict");
    await expect(hero(page)).toHaveAttribute("data-hero-state", "UNAVAILABLE");
    await expect(page.getByTestId("conditions")).toContainText(/WRITER_LOCK/);
    await expect(page.getByTestId("take-paper")).toHaveCount(0);
    await shot(page, "17-replay-writer-conflict");
  });

  test("API down is not WAIT", async ({ page, request }) => {
    await load(page, request, "wait");
    await expect(hero(page)).toHaveAttribute("data-hero-state", "WAIT");
    await page.unroute("http://127.0.0.1:8000/**");
    await page.route("http://127.0.0.1:8000/**", (route) => route.abort());
    await expect(page.getByTestId("api-down-banner")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("take-paper")).toHaveCount(0);
    await shot(page, "18-replay-api-down");
  });

  test("market closed", async ({ page, request }) => {
    await load(page, request, "market_closed");
    await expect(hero(page)).toHaveAttribute("data-hero-state", "MARKET_CLOSED");
    await expect(page.getByTestId("hero")).toHaveAttribute("data-hero-state", "MARKET_CLOSED");
    await expect(page.getByTestId("session")).toHaveText("Ngoài giờ giao dịch");
    await expect(page.getByTestId("reopen-at")).toContainText("mở lại lúc");
    await expect(page.getByTestId("countdown")).toContainText("Mở lại lúc");
    await shot(page, "19-replay-market-closed");
  });

  test("closure policy blocks a new entry with its exact reason", async ({ page, request }) => {
    await load(page, request, "buy_closure_near");
    await expect(hero(page)).toHaveAttribute("data-hero-state", "BUY_READY");
    await expect(page.getByTestId("blockers").locator("[data-code='CLOSURE_NEAR']")).toContainText("Gần giờ thị trường đóng cửa");
    await expect(page.getByTestId("take-paper")).toBeDisabled();
    await shot(page, "20-replay-closure-near");
  });

  test("missing spec and dead collector are errors, not WAIT", async ({ page, request }) => {
    await load(page, request, "no_spec");
    await expect(hero(page)).toHaveAttribute("data-hero-state", "UNAVAILABLE");
    await request.post(`${API}/acceptance/load/collector_down`);
    await page.reload();
    await expect(hero(page)).toHaveAttribute("data-hero-state", "STALE");
  });
});

test.describe("layouts", () => {
  test("1920x1080", async ({ page, request }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await load(page, request, "buy_tp");
    await expect(hero(page)).toHaveAttribute("data-hero-state", "BUY_READY");
    await noHorizontalScroll(page);
    await shot(page, "21-replay-1920x1080");
  });

  test("mobile 390x844: chart on the first screen and a sticky action bar", async ({ page, request }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await load(page, request, "buy_tp");
    await expect(hero(page)).toHaveAttribute("data-hero-state", "BUY_READY");
    await expect(page.getByTestId("mobile-action-bar")).toBeVisible();
    expect((await page.getByTestId("trade-chart").boundingBox())!.y).toBeLessThan(700);
    await noHorizontalScroll(page);
    await shot(page, "22-replay-mobile-390x844");
    await shot(page, "23-replay-mobile-390x844-full", true);
  });

  test("phone with an open position, on every workspace tab: no horizontal scroll (red team)", async ({ page, request }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await load(page, request, "buy_tp");
    await openPaper(page);
    for (const tab of ["overview", "why", "position", "activity", "system"]) {
      await page.getByTestId(`tab-${tab}`).click();
      await noHorizontalScroll(page);
    }
  });

  test("200% zoom (720x450 CSS px)", async ({ page, request }) => {
    await page.setViewportSize({ width: 720, height: 450 });
    await load(page, request, "buy_tp");
    await expect(hero(page)).toHaveAttribute("data-hero-state", "BUY_READY");
    await noHorizontalScroll(page);
    await shot(page, "24-replay-zoom-200");
  });

  test("dark mode", async ({ page, request }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await load(page, request, "buy_tp");
    await expect(hero(page)).toHaveAttribute("data-hero-state", "BUY_READY");
    await shot(page, "25-replay-dark");
    await page.setViewportSize({ width: 390, height: 844 });
    await shot(page, "26-replay-dark-mobile");
  });
});

test.describe("action lifecycle through the real API: WAIT, WATCH, READY, HOLD, EXIT", () => {
  const WATCHES: [string, string][] = [
    ["buy_watch", "BUY"],
    ["buy_armed", "BUY"],
    ["sell_watch", "SELL"],
    ["sell_armed", "SELL"],
  ];
  for (const [scenario, bias] of WATCHES) {
    test(`${scenario}: the bias is ${bias} but the action is CHỜ, it says when and offers no order`, async ({ page, request }) => {
      await load(page, request, scenario);
      await expect(hero(page)).toHaveAttribute("data-action", "WAIT");
      await expect(hero(page)).toHaveAttribute("data-bias", bias);
      await expect(page.getByTestId("action-word")).toHaveText("CHỜ");
      await expect(page.getByTestId("no-entry")).toBeVisible();
      await expect(page.getByTestId("action-when")).toContainText(`Chỉ ${bias === "BUY" ? "MUA" : "BÁN"} khi:`);
      await expect(page.getByTestId("take-paper")).toHaveCount(0);
      await noHorizontalScroll(page);
      await shot(page, `lifecycle-${scenario}`);
    });
  }

  test("sell_invalidated: the dead setup is not an order, the engine waits", async ({ page, request }) => {
    await load(page, request, "sell_invalidated");
    await expect(hero(page)).toHaveAttribute("data-action", "WAIT");
    await expect(page.getByTestId("take-paper")).toHaveCount(0);
  });

  test("BUY READY -> HOLD -> EXIT (TIME) with the action word following each step", async ({ page, request }) => {
    await load(page, request, "buy_time");
    await expect(hero(page)).toHaveAttribute("data-action", "BUY");
    await openPaper(page);
    await expect(hero(page)).toHaveAttribute("data-action", "HOLD");
    await expect(page.getByTestId("action-word")).toHaveText("GIỮ VỊ THẾ");
    await advance(request, 110);
    await advance(request, 15); // past max hold, still inside the 30-minute EXIT banner
    await expect(hero(page)).toHaveAttribute("data-action", "EXIT", { timeout: 30_000 });
    await expect(page.getByTestId("action-sub")).toContainText("Hết thời gian giữ");
  });
});
