import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { EMPTY_MARKERS, LAST_OPEN, STEP, barOpen, mock, view } from "./fixtures/trade";

/**
 * Screenshots for docs/reports/TRADING_CHART_ACCEPTANCE.md (run with SCREENSHOTS=1).
 * The data are labelled fixtures shaped like the server objects; there is no account data.
 */
const OUT = path.resolve(process.cwd(), "..", "..", "docs", "reports", "img", "trading-chart");
const enabled = process.env.SCREENSHOTS === "1";

async function shot(page: Page, name: string) {
  await expect(page.getByTestId("trade-chart")).toBeVisible();
  await page.waitForTimeout(600); // let the canvas paint
  await page.screenshot({ path: path.join(OUT, `${name}.png`), fullPage: true });
}

function sellView() {
  const v = view({}, "SELL");
  Object.assign(v.decision, { entry_price: 2100.1, stop_loss: 2105.1, take_profit: 2090.1, take_profit_2: 2085.1 });
  v.explanation = ["SELL: H1 direction is bearish", "M15 setup: pullback in the downtrend"];
  v.timeframes = v.timeframes.map((t) => ({ ...t, state: t.timeframe === "M15" ? "TRIGGERED (DOWN / PULLBACK)" : "BEARISH", bias: -1 }));
  return v;
}

function position() {
  return {
    trade_id: "P-0007", setup_id: "x", status: "OPEN", side: "BUY", created_at: barOpen(4), opened_at: barOpen(4), closed_at: null,
    fill_price: 2100.5, sl: 2095.5, initial_sl: 2095.5, tp: 2110.5, lots: 0.5, risk_pct: 0.25, risk_amount: 25,
    unrealized_pnl: 12.5, unrealized_r: 0.5, current_price: 2103, duration_minutes: 20,
  };
}

const closed = (id: string, back: number, reason: string, pnl: number, r: number, side = "BUY") => ({
  trade_id: id, side, status: "CLOSED", entry_time: barOpen(back + 6), entry_price: 2100.5,
  exit_time: barOpen(back), exit_price: reason === "TAKE_PROFIT" ? 2110.5 : 2095.5, exit_reason: reason, net_pnl: pnl,
  r_multiple: r, duration_minutes: 30, sl: 2095.5, tp: 2110.5,
});

test.describe("screenshots", () => {
  test.skip(!enabled, "set SCREENSHOTS=1 to regenerate the images");

  test("wait", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await mock(page, view({}, "WAIT"));
    await page.goto("/trade");
    await shot(page, "01-wait-desktop");
  });

  test("buy fixture", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    const at = new Date(LAST_OPEN - 1 * STEP).toISOString();
    const markers = { ...EMPTY_MARKERS, signals: [{ at, bar_time: at, setup_id: "abcdef0123456789", side: "BUY", entry: 2100.5, sl: 2095.5, tp1: 2110.5, tp2: 2115.5, rr: 1.9, lots: 0.5, expires_at: null, strategy_version: "1.2.0", taken: false }] };
    await mock(page, view({}, "BUY"), markers);
    await page.goto("/trade");
    await shot(page, "02-buy-desktop");
  });

  test("sell fixture", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    const at = new Date(LAST_OPEN - 1 * STEP).toISOString();
    const markers = { ...EMPTY_MARKERS, signals: [{ at, bar_time: at, setup_id: "abcdef0123456789", side: "SELL", entry: 2100.1, sl: 2105.1, tp1: 2090.1, tp2: 2085.1, rr: 1.9, lots: 0.5, expires_at: null, strategy_version: "1.2.0", taken: false }] };
    await mock(page, sellView(), markers);
    await page.goto("/trade");
    await shot(page, "03-sell-desktop");
  });

  test("open paper trade", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    const v = view({}, "WAIT");
    (v.desk as { position: unknown }).position = position();
    const markers = { ...EMPTY_MARKERS, paper_trades: [{ trade_id: "P-0007", side: "BUY", status: "OPEN", entry_time: barOpen(4), entry_price: 2100.5, exit_time: null, exit_price: null, exit_reason: null, net_pnl: null, r_multiple: null, duration_minutes: null, sl: 2095.5, tp: 2110.5 }] };
    await mock(page, v, markers);
    await page.goto("/trade");
    await shot(page, "04-open-paper-desktop");
  });

  test("closed paper trades with history", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    const markers = { ...EMPTY_MARKERS, paper_trades: [closed("P-0005", 40, "TAKE_PROFIT", 52, 2.1), closed("P-0006", 12, "STOP_LOSS", -27.5, -1.1)] };
    await mock(page, view({}, "WAIT"), markers);
    await page.goto("/trade");
    await page.getByTestId("toggle-history").check();
    await shot(page, "05-closed-history-desktop");
  });

  test("mobile wait and buy", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await mock(page, view({}, "WAIT"));
    await page.goto("/trade");
    await shot(page, "06-wait-mobile");
    await mock(page, view({}, "BUY"));
    await page.goto("/trade");
    await shot(page, "07-buy-mobile");
  });

  test("dark theme buy", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.setViewportSize({ width: 1440, height: 900 });
    await mock(page, view({}, "BUY"));
    await page.goto("/trade");
    await shot(page, "08-buy-dark");
  });
});
