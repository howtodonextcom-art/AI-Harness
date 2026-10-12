import { test } from "@playwright/test";
import { mock, view } from "./fixtures/trade";

/** Evidence screenshots for docs/reports/VISUAL_BIAS_ACTION_EDUCATION_UI_AND_ALERTS.md. Run on purpose: XAU_SHOTS=1. */
const OUT = "../../docs/reports/img/visual-bias-action-2026-10-12";
const STATES = ["wait", "buyWatch", "buyArmed", "buy", "sell", "openPaper", "closedSl", "stale", "expired"] as const;

test.skip(process.env.XAU_SHOTS !== "1", "evidence screenshots only on request");

for (const [name, vp] of [["1440x900", { width: 1440, height: 900 }], ["1152x864", { width: 1152, height: 864 }], ["720x450", { width: 720, height: 450 }]] as const) {
  for (const state of STATES) {
    test(`shot ${state} ${name}`, async ({ page }) => {
      await page.setViewportSize(vp);
      await mock(page, view(state));
      await page.goto("/trade");
      await page.getByTestId("hero").waitFor();
      await page.screenshot({ path: `${OUT}/mock_${state}_${name}.png`, fullPage: true });
    });
  }
}
