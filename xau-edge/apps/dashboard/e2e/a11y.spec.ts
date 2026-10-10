import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { journalClosedGolden, markersClosedGolden, mock, view, type GoldenName } from "./fixtures/trade";

/**
 * Automated accessibility audit (axe-core, WCAG 2 A/AA rules) of the trading terminal in light and
 * dark mode, in the states a trader meets, and with each modal open. No serious or critical
 * violation may remain.
 */

async function audit(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(bad.map((v) => `${v.id}: ${v.help} -> ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
}

const STATES: GoldenName[] = ["wait", "buy", "sell", "openPaper", "stale", "marketClosed", "paperCorrupt"];

for (const scheme of ["light", "dark"] as const) {
  for (const state of STATES) {
    test(`${scheme}: ${state} has no serious accessibility violation`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: scheme });
      await mock(page, view(state), { markers: markersClosedGolden(), journal: journalClosedGolden() });
      await page.goto("/trade");
      await expect(page.getByTestId("decision").or(page.getByTestId("api-down-banner"))).toBeVisible();
      await audit(page);
    });
  }

  test(`${scheme}: every workspace tab and the open/close modals are accessible`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: scheme });
    await mock(page, view("buy"), { markers: markersClosedGolden(), journal: journalClosedGolden() });
    await page.goto("/trade");
    for (const tab of ["tab-why", "tab-position", "tab-activity", "tab-system"]) {
      await page.getByTestId(tab).click();
      await audit(page);
    }
    await page.getByTestId("take-paper").click();
    await expect(page.getByTestId("confirm-open-modal")).toBeVisible();
    await audit(page);
  });
}

test("the close modal and the phone layout are accessible", async ({ page }) => {
  await mock(page, view("openPaper"));
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/trade");
  await page.getByTestId("action-bar-close").click();
  await expect(page.getByTestId("confirm-close-modal")).toBeVisible();
  await audit(page);
});
