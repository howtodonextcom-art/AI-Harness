import { expect, test } from "@playwright/test";
import { journalClosedGolden, mock, view } from "./fixtures/trade";
import type { TradeView } from "@/lib/trade";

/** Second review round: setup notification, performance breakdown, position distances, zone switch. */

const live = (v: TradeView): TradeView => ({ ...v, source_mode: "LIVE" });

test("a ready setup updates the tab title (LIVE only, once per setup) and the option can be switched off", async ({ page }) => {
  await mock(page, live(view("buy")));
  await page.goto("/trade");
  await expect(page).toHaveTitle(/▲ MUA SẴN SÀNG @ 4236\.47 · XAUUSD/);
  await page.getByTestId("notify-setup").uncheck();
  await expect(page).toHaveTitle(/Terminal giao dịch PAPER/);
  await page.getByTestId("notify-setup").check();
  await expect(page).toHaveTitle(/SẴN SÀNG/);
  await expect(page.getByTestId("notify-sound")).toBeEnabled();
});

test("replay and WAIT never retitle the tab", async ({ page }) => {
  await mock(page, view("buy")); // a replay
  await page.goto("/trade");
  await expect(page.getByTestId("action-word")).toBeVisible();
  await expect(page).toHaveTitle(/Terminal giao dịch PAPER/);
  await mock(page, live(view("wait")));
  await page.reload();
  await expect(page.getByTestId("action-word")).toHaveText("CHỜ");
  await expect(page).toHaveTitle(/Terminal giao dịch PAPER/);
});

test("the waiting panel gives one reason and how far the pipeline got", async ({ page }) => {
  await mock(page, view("wait"));
  await page.goto("/trade");
  await expect(page.getByTestId("stages-progress")).toContainText(/đạt \d\/8/);
  await expect(page.getByTestId("waiting-for")).toBeAttached();
  await expect(page.getByTestId("blocked-by")).toContainText("Mã chặn");
});

test("an open position shows how far SL and TP are, in price and R; the invalidation rule is readable", async ({ page }) => {
  const v = view("openPaper");
  const pos = v.desk!.position!;
  await mock(page, v);
  await page.goto("/trade");
  const d = page.getByTestId("position-distance");
  await expect(d).toContainText(Math.abs(pos.current_price! - pos.sl).toFixed(2));
  await expect(d).toContainText("R");
  await mock(page, view("buy"));
  await page.goto("/trade");
  await expect(page.getByTestId("plan-invalidation")).toContainText("Vô hiệu khi");
});

test("switching the display zone rebuilds the series instead of mixing two time bases", async ({ page }) => {
  await mock(page, view("buy"));
  await page.goto("/trade");
  const chart = page.getByTestId("trade-chart");
  await expect.poll(() => chart.getAttribute("data-bars")).toBe("121");
  await page.getByLabel("Múi giờ hiển thị").selectOption("UTC");
  await expect(page.getByTestId("ohlc-readout")).toContainText("12-05 14:45");
  await expect.poll(() => chart.getAttribute("data-bars")).toBe("121"); // not 121 + the overlap of the old zone
  await page.getByLabel("Múi giờ hiển thị").selectOption("VN");
  await expect.poll(() => chart.getAttribute("data-bars")).toBe("121");
});

test("the journal breaks results down by exit reason and by week and shows provenance as a list, not JSON", async ({ page }) => {
  const base = journalClosedGolden();
  const win = base.trades[0];
  const loss = { ...win, trade_id: "T00002", side: "SELL" as const, net_pnl: -21, r_multiple: -1, exit_reason: "STOP_LOSS", closed_at: new Date(Date.parse(win.closed_at!) + 8 * 86_400_000).toISOString() };
  await page.route("**/trade/journal**", (route) => route.fulfill({ json: { ...base, trades: [win, loss] } }));
  await page.goto("/journal");
  await expect(page.getByTestId("by-reason")).toContainText("Chạm TP");
  await expect(page.getByTestId("by-reason")).toContainText("Chạm SL");
  await expect(page.getByTestId("by-week").locator("tbody tr")).toHaveCount(2);
  await page.getByTestId("journal-detail-toggle").first().click();
  const detail = page.getByTestId("journal-detail");
  await expect(detail).toContainText("Phiên bản mã");
  await expect(detail).toContainText("ACCEPTANCE REPLAY");
  expect(await detail.evaluate((el) => el.tagName)).toBe("DL");
});

test("the CSV export quotes properly, starts with a BOM and neutralises spreadsheet formulas", async ({ page }) => {
  const base = journalClosedGolden();
  const t = { ...base.trades[0], exit_reason: '=HYPERLINK("http://x")', strategy_version: 'a,"b"' };
  await page.route("**/trade/journal**", (route) => route.fulfill({ json: { ...base, trades: [t] } }));
  await page.goto("/journal");
  const download = page.waitForEvent("download");
  await page.getByTestId("export-csv").click();
  const text = await (await import("node:fs/promises")).readFile((await (await download).path())!, "utf-8");
  expect(text.charCodeAt(0)).toBe(0xfeff);
  expect(text).toContain("'=HYPERLINK(");
  expect(text).toContain('"a,""b"""');
});
