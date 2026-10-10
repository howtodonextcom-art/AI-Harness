import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

/**
 * Real-browser acceptance of the Trading Desk. The API is the REAL one (`TradeEngine`, `PaperDesk`,
 * journal, alerts) running over burned FTMO bars with a replay clock; the page is the production
 * build. Provenance of everything below: ACCEPTANCE REPLAY - NOT LIVE (the page says so itself).
 */

const API = "http://127.0.0.1:8100";
const SHOTS = "../../docs/reports/img/trading-desk";

async function load(page: Page, request: APIRequestContext, name: string, path = "/trade") {
  const res = await request.post(`${API}/acceptance/load/${name}`);
  expect(res.ok()).toBeTruthy();
  // the page asks the production API port; the acceptance API answers instead (same routes, same code)
  await page.route("http://127.0.0.1:8000/**", async (route) => {
    const response = await route.fetch({ url: route.request().url().replace(":8000", ":8100") });
    await route.fulfill({ response });
  });
  await page.goto(path);
}

const advance = (request: APIRequestContext, minutes: number) => request.post(`${API}/acceptance/advance?minutes=${minutes}`);
const hero = (page: Page) => page.getByTestId("hero");
const shot = (page: Page, name: string) => page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true });

async function noHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
}

async function openPaper(page: Page) {
  await page.getByTestId("take-paper").click();
  await expect(page.getByTestId("confirm-card")).toBeVisible();
  await page.getByTestId("confirm-paper").click();
  await expect(page.getByTestId("paper-position")).toBeVisible({ timeout: 20_000 });
}

test.describe("replay is always labelled", () => {
  test("WAIT: state, why, waiting-for, clickable stages, status strip", async ({ page, request }) => {
    await load(page, request, "wait");
    await expect(hero(page)).toHaveAttribute("data-hero-state", "WAIT");
    await expect(page.getByTestId("decision")).toHaveText(/WAIT/);
    await expect(page.getByTestId("replay-banner")).toContainText("NOT LIVE");
    await expect(page.getByTestId("waiting-for")).toBeVisible();
    await expect(page.getByTestId("blocked-by")).toBeVisible();
    await expect(page.getByTestId("status-strip")).toContainText("ACTIVE");
    await expect(page.getByTestId("status-strip")).toContainText("LOCKED");
    await expect(page.getByTestId("status-strip")).toContainText("UNVALIDATED");
    await expect(page.getByTestId("take-paper")).toHaveCount(0);
    // a stage row switches the chart to the timeframe that shows it
    const stages = page.getByTestId("stages").getByRole("button");
    const count = await stages.count();
    expect(count).toBeGreaterThan(3);
    for (let i = 0; i < count; i++) {
      const tf = await stages.nth(i).getAttribute("data-timeframe");
      await stages.nth(i).click();
      await expect(page.getByTestId(`chart-tf-${tf}`)).toHaveAttribute("aria-pressed", "true");
    }
    await noHorizontalScroll(page);
    await shot(page, "01-replay-wait");
  });

  test("real BUY setup: plan, chart lines, confirmation, paper position", async ({ page, request }) => {
    await load(page, request, "buy_tp");
    await expect(hero(page)).toHaveAttribute("data-hero-state", "BUY_READY");
    await expect(page.getByTestId("decision")).toHaveText(/BUY READY/);
    await expect(page.getByTestId("replay-banner")).toContainText("NOT LIVE");
    for (const id of ["plan-entry", "plan-sl", "plan-tp", "plan-rr", "plan-lots", "plan-risk", "plan-version"]) {
      await expect(page.getByTestId(id)).not.toContainText("—");
    }
    await expect(page.getByTestId("plan-version")).toContainText("v1.2.1");
    await expect(page.getByTestId("expiry")).toBeVisible();
    await expect(page.getByTestId("chart-legend")).toContainText(/Entry/i);
    await expect(page.getByTestId("chart-legend")).toContainText(/SL/);
    await expect(page.getByTestId("chart-legend")).toContainText(/TP/);
    await expect(page.getByTestId("take-paper")).toBeEnabled();
    await shot(page, "02-replay-buy-ready");
    // confirmation first, nothing opens on the first click
    await page.getByTestId("take-paper").click();
    await expect(page.getByTestId("confirm-card")).toBeVisible();
    await page.getByTestId("cancel-paper").click();
    await expect(page.getByTestId("paper-position")).toHaveCount(0);
    await openPaper(page);
    await expect(hero(page)).toHaveAttribute("data-hero-state", "POSITION_OPEN");
    await expect(page.getByTestId("position-entry")).not.toContainText("—");
    await expect(page.getByTestId("position-levels")).not.toContainText("—");
    await shot(page, "03-replay-paper-open");
  });

  test("real SELL setup", async ({ page, request }) => {
    await load(page, request, "sell_ready");
    await expect(hero(page)).toHaveAttribute("data-hero-state", "SELL_READY");
    await expect(page.getByTestId("decision")).toHaveText(/SELL READY/);
    await expect(page.getByTestId("plan-side")).toHaveText(/SELL/);
    await expect(page.getByTestId("replay-banner")).toContainText("NOT LIVE");
    await shot(page, "04-replay-sell-ready");
  });
});

test.describe("paper lifecycle through the real API", () => {
  test("TAKE_PROFIT exit (BUY): marker, exited hero, journal row", async ({ page, request }) => {
    await load(page, request, "buy_tp");
    await openPaper(page);
    await advance(request, 60);
    await expect(hero(page)).toHaveAttribute("data-hero-state", "EXITED", { timeout: 20_000 });
    await expect(page.getByTestId("paper-history")).toContainText("TAKE_PROFIT");
    await expect(page.getByTestId("chart-markers")).toContainText(/TAKE_PROFIT|TP/i);
    await shot(page, "05-replay-exit-take-profit");
    await page.goto("/journal");
    const row = page.getByTestId("journal-row").first();
    await expect(row).toContainText("BUY");
    await expect(row).toContainText("Chạm TP");
    await expect(page.getByTestId("journal-replay-banner")).toContainText("KHÔNG PHẢI LIVE");
    await page.getByTestId("journal-detail-toggle").first().click();
    await expect(page.getByTestId("journal-detail")).toContainText("ACCEPTANCE_REPLAY");
    await shot(page, "09-replay-journal");
  });

  test("manual close re-reads the quote and closes once", async ({ page, request }) => {
    await load(page, request, "buy_tp");
    await openPaper(page);
    await advance(request, 10);
    await expect(page.getByTestId("position-pnl")).not.toContainText("—", { timeout: 20_000 });
    await page.getByTestId("close-paper").click();
    await expect(hero(page)).toHaveAttribute("data-hero-state", "EXITED", { timeout: 20_000 });
    await expect(page.getByTestId("paper-history")).toContainText("MANUAL_CLOSE");
    await shot(page, "06-replay-manual-close");
    const journal = await (await request.get(`${API}/trade/journal`, { headers: { Host: "127.0.0.1:8100" } })).json();
    expect(journal.trades.filter((t: { exit_reason: string }) => t.exit_reason === "MANUAL_CLOSE")).toHaveLength(1);
  });

  test("STOP_LOSS exit (SELL)", async ({ page, request }) => {
    await load(page, request, "sell_ready");
    await openPaper(page);
    await advance(request, 60);
    await expect(hero(page)).toHaveAttribute("data-hero-state", "EXITED", { timeout: 20_000 });
    await expect(page.getByTestId("paper-history")).toContainText("STOP_LOSS");
    await shot(page, "07-replay-exit-stop-loss");
  });

  test("TAKE_PROFIT exit (SELL, v1.1.0 shown as the active version)", async ({ page, request }) => {
    await load(page, request, "sell_tp");
    await expect(page.getByTestId("strategy-active")).toContainText("1.1.0");
    await openPaper(page);
    await advance(request, 120); // the target is reached ~85 minutes after entry
    await expect(page.getByTestId("paper-history")).toContainText("TAKE_PROFIT", { timeout: 20_000 });
    await expect(page.getByTestId("position-card")).toContainText("Không có lệnh paper đang mở");
  });

  test("TIME_EXIT", async ({ page, request }) => {
    await load(page, request, "buy_time");
    await openPaper(page);
    await advance(request, 180);
    await expect(hero(page)).toHaveAttribute("data-hero-state", "EXITED", { timeout: 20_000 });
    await expect(page.getByTestId("paper-history")).toContainText("TIME_EXIT");
    await shot(page, "08-replay-exit-time");
  });
});

test.describe("failure states are explicit and never a plain WAIT", () => {
  test("stale data hides the plan", async ({ page, request }) => {
    await load(page, request, "stale");
    await expect(hero(page)).toHaveAttribute("data-hero-state", "STALE");
    await expect(page.getByTestId("plan-card")).toHaveCount(0);
    await expect(page.getByTestId("take-paper")).toHaveCount(0);
    await shot(page, "10-replay-stale");
  });

  test("expired setup cannot be opened", async ({ page, request }) => {
    await load(page, request, "expired");
    await expect(page.getByTestId("decision")).toHaveText(/EXPIRED SETUP/);
    await expect(page.getByTestId("take-paper")).toBeDisabled();
    await shot(page, "11-replay-expired");
  });

  test("corrupt paper state fails closed and says so", async ({ page, request }) => {
    await load(page, request, "paper_corrupt");
    await expect(hero(page)).toHaveAttribute("data-hero-state", "UNAVAILABLE");
    await expect(page.getByTestId("conditions")).toContainText("PAPER STATE ERROR");
    await expect(page.getByTestId("take-paper")).toHaveCount(0);
    await shot(page, "12-replay-paper-state-error");
  });

  test("second writer: read-only, no paper action", async ({ page, request }) => {
    await load(page, request, "writer_conflict");
    await expect(hero(page)).toHaveAttribute("data-hero-state", "UNAVAILABLE");
    await expect(page.getByTestId("conditions")).toContainText(/WRITER/i);
    await expect(page.getByTestId("take-paper")).toHaveCount(0); // no plan is offered by a read-only desk
    await shot(page, "13-replay-writer-conflict");
  });

  test("API down is not WAIT", async ({ page, request }) => {
    await load(page, request, "wait");
    await expect(hero(page)).toHaveAttribute("data-hero-state", "WAIT");
    await page.unroute("http://127.0.0.1:8000/**");
    await page.route("http://127.0.0.1:8000/**", (route) => route.abort());
    await expect(page.getByTestId("api-down-banner")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("take-paper")).toHaveCount(0);
    await shot(page, "14-replay-api-down");
  });

  test("market closed", async ({ page, request }) => {
    await load(page, request, "market_closed");
    await expect(hero(page)).toHaveAttribute("data-hero-state", "MARKET_CLOSED");
    await expect(page.getByTestId("decision")).toHaveText(/MARKET CLOSED/);
    await shot(page, "15-replay-market-closed");
  });

  test("closure policy blocks a new entry with its exact reason", async ({ page, request }) => {
    await load(page, request, "buy_closure_near");
    await expect(hero(page)).toHaveAttribute("data-hero-state", "BUY_READY");
    await expect(page.getByTestId("blockers").locator("[data-code='CLOSURE_NEAR']")).toBeVisible();
    await expect(page.getByTestId("take-paper")).toBeDisabled();
    await shot(page, "16-replay-closure-near");
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
  test("mobile 390x844", async ({ page, request }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await load(page, request, "buy_tp");
    await expect(hero(page)).toHaveAttribute("data-hero-state", "BUY_READY");
    await expect(page.getByTestId("take-paper")).toBeVisible();
    await noHorizontalScroll(page);
    await shot(page, "17-replay-mobile-390x844");
  });

  test("200% zoom (720x450 CSS px)", async ({ page, request }) => {
    await page.setViewportSize({ width: 720, height: 450 });
    await load(page, request, "buy_tp");
    await expect(hero(page)).toHaveAttribute("data-hero-state", "BUY_READY");
    await noHorizontalScroll(page);
    await shot(page, "18-replay-zoom-200");
  });
});
