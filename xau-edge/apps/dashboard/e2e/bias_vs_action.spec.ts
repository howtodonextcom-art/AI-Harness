import { expect, test, type Page } from "@playwright/test";
import type { Diagnostic, TradeView } from "../lib/trade";
import { mock, view } from "./fixtures/trade";

/**
 * BIAS vs ACTION: "the system sees an uptrend" must never read as "BUY is allowed". With H1 bullish and any gate failing the panel
 * shows the bias, the action CHỜ, the primary blocker, what else is missing and what comes next, and offers no trade geometry.
 */
type Row = Diagnostic["rows"][number];
const row = (stage: string, status: Row["status"], timeframe: string, observed: string): Row => ({ stage, status, timeframe, observed });

function diag(over: Partial<Diagnostic> = {}, rows?: Row[]): Diagnostic {
  return {
    bias: { side: "BUY", source: "H1", reading: "BULLISH", reason: "H1 đang tăng" },
    formation: { state: "NO_SETUP", bars_since_armed: null },
    blockers: ["SPREAD_TOO_WIDE", "VOLATILITY_TOO_LOW"],
    execution: {
      spread_points: 46, spread_percentile: 0.95, spread_percentile_limit: 0.9, spread_to_atr_m5: 0.15, spread_to_atr_limit: 0.15,
      volatility_regime: "LOW", atr_m15: 3.77, atr_percentile: 0.045, atr_percentile_min: 0.2, m1_state: "ACTIVE_UP",
    },
    action: "WAIT",
    rows: rows ?? [
      row("Market & data", "PASS", "M5", "market/data"),
      row("Spread & regime", "FAIL", "H4", "WIDE/LOW"),
      row("H1 direction", "PASS", "H1", "H1:BULLISH"),
      row("H4 / M15 alignment", "PASS", "M15", "H4:RANGE M15:RANGE"),
      row("M15 setup", "FAIL", "M15", "M15:RANGE/NONE"),
      row("M5 trigger", "FAIL", "M5", "M5:FLAT"),
      row("M1 execution", "FAIL", "M1", "M1:SPREAD_WIDE"),
      row("Trade plan", "NOT_EVALUATED", "M5", "plan"),
    ],
    required_total: 8, required_passed: 3, primary_blocker: "SPREAD_TOO_WIDE", primary_stage: "Spread & regime",
    also_missing: ["M15 setup", "M5 trigger", "M1 execution"], ...over,
  };
}

function waitWith(d: Diagnostic): TradeView {
  const v = view("wait");
  v.why_wait = { ...(v.why_wait as NonNullable<TradeView["why_wait"]>), diagnostic: d };
  return v;
}

async function expectNoTradeGeometry(page: Page) {
  await expect(page.getByTestId("take-paper")).toHaveCount(0);
  await expect(page.getByTestId("system-plan-overlay")).toHaveCount(0);
  await expect(page.getByTestId("plan-card")).toHaveCount(0);
  const text = (await page.locator("body").innerText()).replace(/\s+/g, " ");
  expect(text).not.toMatch(/SẴN SÀNG (MUA|BÁN)/);
}

const TRIGGER_ROWS: Row[] = [
  row("Market & data", "PASS", "M5", "market/data"), row("Spread & regime", "PASS", "H4", "GOOD/NORMAL"), row("H1 direction", "PASS", "H1", "H1:BULLISH"),
  row("H4 / M15 alignment", "PASS", "M15", "ok"), row("M15 setup", "PASS", "M15", "M15:UP/PULLBACK_IN_UPTREND"), row("M5 trigger", "FAIL", "M5", "M5:FLAT"),
  row("M1 execution", "PASS", "M1", "M1:GOOD"), row("Trade plan", "NOT_EVALUATED", "M5", "plan"),
];
const VOL_ROWS: Row[] = [
  row("Market & data", "PASS", "M5", "market/data"), row("Spread & regime", "FAIL", "H4", "GOOD/LOW"), row("H1 direction", "PASS", "H1", "H1:BULLISH"),
  row("H4 / M15 alignment", "PASS", "M15", "ok"), row("M15 setup", "FAIL", "M15", "M15:RANGE/NONE"), row("M5 trigger", "FAIL", "M5", "M5:FLAT"),
  row("M1 execution", "PASS", "M1", "M1:GOOD"), row("Trade plan", "NOT_EVALUATED", "M5", "plan"),
];

for (const [name, vp] of [["desktop 1440x900", { width: 1440, height: 900 }], ["1152x864", { width: 1152, height: 864 }], ["200% zoom 720x450", { width: 720, height: 450 }]] as const) {
  test.describe(name, () => {
    test.use({ viewport: vp });

    test("BUY bias + spread blocked: bias, CHỜ, primary blocker, other blocker, missing and next are all visible", async ({ page }) => {
      await mock(page, waitWith(diag()));
      await page.goto("/trade");
      await expect(page.getByTestId("bias-side")).toHaveText(/MUA/);
      await expect(page.getByTestId("action-card")).toContainText("CHỜ");
      await expect(page.getByTestId("bias-note")).toContainText("không phải quyền vào lệnh");
      await expect(page.getByTestId("primary-blocker")).toContainText("Spread M1 quá rộng");
      await expect(page.getByTestId("other-blockers")).toContainText("Biến động thấp");
      await expect(page.getByTestId("missing")).toContainText("M15 chưa có pullback");
      await expect(page.getByTestId("missing")).toContainText("M5 chưa kích hoạt");
      await expect(page.getByTestId("next-steps")).toContainText("→");
      await expect(page.getByTestId("stage-H1-direction")).toHaveAttribute("data-status", "PASS");
      await expect(page.getByTestId("stage-M30-context")).toContainText("chỉ tham khảo");
      await expect(page.getByTestId("stages-progress")).toContainText(/\d+ đạt/);
      await expect(page.getByTestId("stages-progress")).not.toContainText("/8");
      await expect(page.getByTestId("execution-card")).toContainText("Execution blocker");
      await expect(page.getByTestId("exec-spread")).toContainText("46");
      await expect(page.getByTestId("exec-vol")).toContainText("4.5%");
      await expect(page.getByTestId("chart-bias-strip")).toContainText("H1 BIAS: MUA");
      await expectNoTradeGeometry(page);
    });

    test("SELL bias + WAIT keeps the bias directional and the action CHỜ", async ({ page }) => {
      await mock(page, waitWith(diag({ bias: { side: "SELL", source: "H1", reading: "BEARISH" } })));
      await page.goto("/trade");
      await expect(page.getByTestId("bias-side")).toHaveText(/BÁN/);
      await expect(page.getByTestId("action-card")).toContainText("CHỜ");
      await expect(page.getByTestId("bias-card")).toHaveClass(/red/);
      await expect(page.getByTestId("chart-bias-strip")).toContainText("H1 BIAS: BÁN");
      await expectNoTradeGeometry(page);
    });

    test("volatility blocked only: the bias is still visible and the spread is not blamed", async ({ page }) => {
      await mock(page, waitWith(diag({ blockers: ["VOLATILITY_TOO_LOW"], primary_blocker: "VOLATILITY_TOO_LOW" }, VOL_ROWS)));
      await page.goto("/trade");
      await expect(page.getByTestId("bias-side")).toHaveText(/MUA/);
      await expect(page.getByTestId("primary-blocker")).toContainText("Biến động thấp");
      await expect(page.getByTestId("other-blockers")).toHaveCount(0);
      await expectNoTradeGeometry(page);
    });

    test("M15 setup present but the M5 trigger is missing", async ({ page }) => {
      await mock(page, waitWith(diag({ blockers: ["NO_TRIGGER"], primary_blocker: "NO_TRIGGER", primary_stage: "M5 trigger", formation: { state: "WAITING_TRIGGER", bars_since_armed: null } }, TRIGGER_ROWS)));
      await page.goto("/trade");
      await expect(page.getByTestId("primary-blocker")).toContainText("M5 chưa kích hoạt");
      await expect(page.getByTestId("formation")).toContainText("chờ M5 trigger");
      await expect(page.getByTestId("stage-M15-setup")).toHaveAttribute("data-status", "PASS");
      await expectNoTradeGeometry(page);
    });

    test("an armed setup says it is forming, its age and that the trigger is awaited", async ({ page }) => {
      await mock(page, waitWith(diag({ blockers: ["NO_TRIGGER"], primary_blocker: "NO_TRIGGER", primary_stage: "M5 trigger", formation: { state: "FORMING", bars_since_armed: 2 } }, TRIGGER_ROWS)));
      await page.goto("/trade");
      await expect(page.getByTestId("formation")).toContainText("SETUP MUA ĐANG HÌNH THÀNH");
      await expect(page.getByTestId("formation")).toContainText("nến 2/");
      await expect(page.getByTestId("formation")).toContainText("chờ M5 trigger");
      await expectNoTradeGeometry(page);
    });

    test("neutral H1 says there is no direction and draws no bias strip", async ({ page }) => {
      await mock(page, waitWith(diag({ bias: { side: "NEUTRAL", source: "H1", reading: "NEUTRAL" }, blockers: ["NO_DIRECTION"], primary_blocker: "NO_DIRECTION" })));
      await page.goto("/trade");
      await expect(page.getByTestId("bias-side")).toHaveText(/TRUNG TÍNH/);
      await expect(page.getByTestId("bias-note")).toContainText("H1 chưa có hướng rõ");
      await expect(page.getByTestId("chart-bias-strip")).toHaveCount(0);
    });

    test("the legend says a direction colour is not permission", async ({ page }) => {
      await mock(page, waitWith(diag()));
      await page.goto("/trade");
      await page.getByTestId("color-legend").locator("summary").click();
      await expect(page.getByTestId("color-legend")).toContainText("Màu hướng không đồng nghĩa được phép vào lệnh");
    });

    test("BUY and SELL ready show the plan and no wait briefing", async ({ page }) => {
      for (const kind of ["buy", "sell"] as const) {
        await mock(page, view(kind));
        await page.goto("/trade");
        await expect(page.getByTestId("take-paper")).toBeVisible();
        await expect(page.getByTestId("wait-briefing")).toHaveCount(0);
        await expect(page.getByTestId("chart-bias-strip")).toHaveCount(0);
      }
    });
  });
}
