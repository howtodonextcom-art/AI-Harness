import { expect, test } from "@playwright/test";
import type { Diagnostic, TradeView } from "../lib/trade";
import { mock, view } from "./fixtures/trade";

/**
 * BIAS vs ACTION: "the system sees an uptrend" must never read as "BUY is allowed". With H1 bullish and a spread block the
 * panel shows the bias, the action CHỜ, and every unmet stage, not only the first.
 */
function diag(over: Partial<Diagnostic> = {}): Diagnostic {
  const rows: Diagnostic["rows"] = [
    { stage: "Market & data", status: "PASS", timeframe: "M5", observed: "market/data" },
    { stage: "Spread & regime", status: "FAIL", timeframe: "H4", observed: "WIDE/LOW" },
    { stage: "H1 direction", status: "PASS", timeframe: "H1", observed: "H1:BULLISH" },
    { stage: "H4 / M15 alignment", status: "PASS", timeframe: "M15", observed: "H4:RANGE M15:RANGE" },
    { stage: "M15 setup", status: "FAIL", timeframe: "M15", observed: "M15:RANGE/NONE" },
    { stage: "M5 trigger", status: "FAIL", timeframe: "M5", observed: "M5:FLAT" },
    { stage: "M1 execution", status: "FAIL", timeframe: "M1", observed: "M1:SPREAD_WIDE" },
    { stage: "Trade plan", status: "NOT_EVALUATED", timeframe: "M5", observed: "plan" },
  ];
  return {
    bias: { side: "BUY", source: "H1", reading: "BULLISH" }, action: "WAIT", rows, required_total: 8, required_passed: 3,
    primary_blocker: "SPREAD_TOO_WIDE", primary_stage: "Spread & regime", also_missing: ["M15 setup", "M5 trigger", "M1 execution"], ...over,
  };
}

function waitWith(d: Diagnostic): TradeView {
  const v = view("wait");
  v.why_wait = { ...(v.why_wait as NonNullable<TradeView["why_wait"]>), diagnostic: d };
  return v;
}

for (const [name, vp] of [["desktop", { width: 1440, height: 900 }], ["200% zoom", { width: 720, height: 450 }]] as const) {
  test.describe(name, () => {
    test.use({ viewport: vp });

    test("bullish bias + WAIT: bias, action and every unmet stage are visible; no trade is offered", async ({ page }) => {
      await mock(page, waitWith(diag()));
      await page.goto("/trade");
      await expect(page.getByTestId("bias-side")).toHaveText(/MUA/);
      await expect(page.getByTestId("bias-action")).toContainText("CHỜ");
      await expect(page.getByTestId("bias-note")).toContainText("không phải quyền vào lệnh");
      await expect(page.getByTestId("bias-note")).toContainText("Setup M15");
      await expect(page.getByTestId("bias-note")).toContainText("Kích hoạt M5");
      await expect(page.getByTestId("stage-H1-direction")).toHaveAttribute("data-status", "PASS"); // not "chưa tới" any more
      await expect(page.getByTestId("take-paper")).toHaveCount(0);
      const text = (await page.locator("body").innerText()).replace(/\s+/g, " ");
      expect(text).not.toMatch(/SẴN SÀNG (MUA|BÁN)/);
    });

    test("bearish bias + WAIT keeps the bias directional", async ({ page }) => {
      await mock(page, waitWith(diag({ bias: { side: "SELL", source: "H1", reading: "BEARISH" } })));
      await page.goto("/trade");
      await expect(page.getByTestId("bias-side")).toHaveText(/BÁN/);
      await expect(page.getByTestId("bias-action")).toContainText("CHỜ");
    });

    test("neutral H1 says there is no direction", async ({ page }) => {
      await mock(page, waitWith(diag({ bias: { side: "NEUTRAL", source: "H1", reading: "NEUTRAL" } })));
      await page.goto("/trade");
      await expect(page.getByTestId("bias-side")).toHaveText(/TRUNG TÍNH/);
      await expect(page.getByTestId("bias-note")).toContainText("H1 chưa có hướng rõ");
    });
  });
}
