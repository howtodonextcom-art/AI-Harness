import { expect, test } from "@playwright/test";
import { mock, view } from "./fixtures/trade";

/** A second market feed is shown as such: the research baseline (FTMO) carries no extra badge, any other source says so. */
test("an FTMO desk shows no source badge", async ({ page }) => {
  const v = view("wait");
  v.market_source = { id: "ftmo", label: "FTMO-Demo", server: "FTMO-Demo", research_baseline: true };
  await mock(page, v);
  await page.goto("/trade");
  await expect(page.getByTestId("market-pill")).toBeVisible();
  await expect(page.getByTestId("market-source-pill")).toHaveCount(0);
});

test("a MetaQuotes desk says the data is not FTMO", async ({ page }) => {
  const v = view("wait");
  v.market_source = { id: "metaquotes", label: "MetaQuotes-Demo", server: "MetaQuotes-Demo", research_baseline: false };
  await mock(page, v);
  await page.goto("/trade");
  await expect(page.getByTestId("market-source-pill")).toContainText("MetaQuotes-Demo");
  await expect(page.getByTestId("market-source-pill")).toContainText("không phải FTMO");
});
