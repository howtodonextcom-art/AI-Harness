import { expect, test } from "@playwright/test";
import { journalClosedGolden, mock, view } from "./fixtures/trade";

/** Findings of the independent trader review that were in scope (account, reopening, journal analytics). */

test("the paper account is always visible: equity, floating, today and the daily loss limit", async ({ page }) => {
  const v = view("openPaper");
  await mock(page, v);
  await page.goto("/trade");
  const strip = page.getByTestId("account-strip");
  await expect(strip).toBeVisible();
  await expect(page.getByTestId("acct-equity")).toContainText("$");
  await expect(page.getByTestId("acct-today")).toContainText("R");
  const limits = v.desk!.limits;
  await expect(page.getByTestId("acct-limit")).toContainText(`giới hạn ${limits.daily_loss_stop_pct}%`);
  await expect(strip.getByRole("progressbar")).toHaveAttribute("aria-valuemax", "100");
});

test("while the market is closed the terminal says when it reopens (server computed)", async ({ page }) => {
  const v = view("marketClosed");
  await mock(page, v);
  await page.goto("/trade");
  expect(v.market_context!.next_open).toBeTruthy();
  await expect(page.getByTestId("countdown")).toContainText("Mở lại lúc");
  await expect(page.getByTestId("reopen-at")).toContainText("Thị trường mở lại lúc");
});

test("the journal has filters, win rate, average R, a cumulative-R curve and a CSV export", async ({ page }) => {
  const base = journalClosedGolden();
  const win = base.trades[0];
  const loss = { ...win, trade_id: "T00002", side: "SELL" as const, net_pnl: -21, r_multiple: -1, exit_reason: "STOP_LOSS", closed_at: new Date(Date.parse(win.closed_at!) + 3600_000).toISOString() };
  const journal = { ...base, trades: [win, loss] };
  await page.route("**/trade/journal**", (route) => route.fulfill({ json: journal }));
  await page.goto("/journal");
  await expect(page.getByTestId("stat-n")).toHaveText("2");
  await expect(page.getByTestId("stat-winrate")).toHaveText("50%");
  await expect(page.getByTestId("r-curve").locator("polyline")).toHaveCount(1);
  await page.getByTestId("filter-loss").click();
  await expect(page.getByTestId("journal-row")).toHaveCount(1);
  await expect(page.getByTestId("stat-n")).toHaveText("1");
  await expect(page.getByTestId("stat-winrate")).toHaveText("0%");
  await page.getByTestId("filter-BUY").click();
  await expect(page.getByTestId("journal-row")).toHaveCount(1);
  await page.getByTestId("filter-all").click();
  const download = page.waitForEvent("download");
  await page.getByTestId("export-csv").click();
  const file = await download;
  expect(file.suggestedFilename()).toMatch(/^paper-journal-\d{4}-\d{2}-\d{2}\.csv$/);
  const text = await (await import("node:fs/promises")).readFile((await file.path())!, "utf-8");
  expect(text.split("\n")[0]).toContain("trade_id,setup_id,side");
  expect(text).toContain("T00002");
  expect(text).not.toMatch(/token|password|secret/i);
});
