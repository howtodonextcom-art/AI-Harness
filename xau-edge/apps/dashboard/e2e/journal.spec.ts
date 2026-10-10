import { expect, test } from "@playwright/test";
import { journalClosedGolden } from "./fixtures/trade";

/** The paper journal page against the production build; the API serves the real golden journal. */

const fixed = (n: number | null | undefined) => (n ?? 0).toFixed(2);

test("journal lists the real closed trade, labels replay, links to the chart and says it proves nothing", async ({ page }) => {
  const journal = journalClosedGolden();
  const t = journal.trades[0];
  await page.route("**/trade/journal**", (route) => route.fulfill({ json: journal }));
  await page.goto("/journal");
  const row = page.getByTestId("journal-row").first();
  await expect(page.getByTestId("journal-row")).toHaveCount(journal.trades.length);
  await expect(row).toContainText("Chạm TP");
  await expect(row).toContainText(fixed(t.tp));
  await expect(row).toContainText(`v${t.strategy_version}`);
  await expect(page.getByTestId("journal-replay-banner")).toContainText("KHÔNG PHẢI LIVE");
  await expect(page.getByTestId("journal-note")).toContainText("Chưa có bằng chứng");
  await page.getByTestId("journal-detail-toggle").first().click();
  await expect(page.getByTestId("journal-detail")).toContainText("ACCEPTANCE_REPLAY");
  const href = await page.getByTestId("journal-view-on-chart").first().getAttribute("href");
  expect(href).toContain("/trade?focus=");
  expect(href).toContain(`trade=${t.trade_id}`);
});

test("a faulted desk is shown on the journal instead of an empty list", async ({ page }) => {
  const journal = { ...journalClosedGolden(), trades: [], desk_fault: "the paper state and its journal disagree" };
  await page.route("**/trade/journal**", (route) => route.fulfill({ json: journal }));
  await page.goto("/journal");
  await expect(page.getByTestId("journal-desk-fault")).toContainText("PAPER_STATE_ERROR");
});

test("journal API down is an error, not an empty journal", async ({ page }) => {
  await page.route("**/trade/journal**", (route) => route.abort());
  await page.goto("/journal");
  await expect(page.getByText("chưa có dữ liệu")).toBeVisible();
});

test("/journal at 390px has no horizontal page scroll", async ({ page }) => {
  await page.route("**/trade/journal**", (route) => route.fulfill({ json: journalClosedGolden() }));
  await page.setViewportSize({ width: 390, height: 800 });
  await page.goto("/journal");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0);
});
