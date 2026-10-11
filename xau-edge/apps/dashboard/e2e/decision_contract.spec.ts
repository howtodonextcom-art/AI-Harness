import { expect, test } from "@playwright/test";
import { mock, view } from "./fixtures/trade";

/**
 * Human Decision Contract (V3 report section 3): every state answers WHY and WHAT NEXT on the hero, TP2 and the
 * invalidation rule are never read as active exits, every exit names its reason, and the evidence rung is on the fold.
 * Deterministic goldens: visual correctness only, never live evidence.
 */

// ~20% of live open minutes: H1 leans, the first refusal is not NO_SETUP/NO_TRIGGER, the server sends no bias
for (const [code, why] of [
  ["TIMEFRAME_CONFLICT", "H1 đang tăng nhưng H4 hoặc M15 đang đi ngược hướng"],
  ["TOO_CLOSE_TO_RESISTANCE", "giá quá sát kháng cự kế tiếp"],
  ["SPREAD_TOO_WIDE", "spread đang quá rộng"],
  ["VOLUME_TOO_LOW", "tick volume M1 quá thấp"],
] as const) {
  test(`WAIT with H1 leaning and ${code}: the real reason and the next condition, never "no direction"`, async ({ page }) => {
    const v = view("wait");
    (v.structure as Record<string, unknown>).h1_trend = "BULLISH";
    v.why_wait = { ...v.why_wait!, waiting_for_code: code, blocked_by: [code] };
    await mock(page, v);
    await page.goto("/trade");
    await expect(page.getByTestId("action-word")).toHaveText("CHỜ");
    await expect(page.getByTestId("action-sub")).toContainText(why);
    await expect(page.getByTestId("action-sub")).not.toContainText("Chưa có hướng ưu tiên");
    await expect(page.getByTestId("action-when")).toContainText("Cần xảy ra:");
  });
}

test("BUY: TP 2 and the invalidation rule are reference only; risk and lot sit on the hero", async ({ page }) => {
  await mock(page, view("buy"));
  await page.goto("/trade");
  await expect(page.getByTestId("plan-tp2-note")).toContainText("không chốt ở TP 2");
  await expect(page.getByTestId("plan-invalidation-note")).toContainText("bàn không tự đóng lệnh");
  await expect(page.getByTestId("action-when")).toContainText("chỉ tham khảo, bàn không tự đóng");
  await expect(page.getByTestId("hero-risk")).toContainText("%");
  await expect(page.getByTestId("hero-lot")).not.toHaveText("—");
});

test("HOLD says why it holds and what will force the exit", async ({ page }) => {
  await mock(page, view("openPaper"));
  await page.goto("/trade");
  await expect(page.getByTestId("action-when")).toContainText("Vì sao GIỮ");
  await expect(page.getByTestId("action-when")).toContainText("sàn khẩn cấp");
  await expect(page.getByTestId("action-when")).toContainText("KHÔNG tự đóng");
});

for (const [code, text] of [
  ["DAILY_LOSS_GUARD", "Chạm giới hạn lỗ trong ngày"],
  ["FORCED_FLAT", "Buộc đóng"],
  ["KILL_SWITCH", "kill switch"],
  ["MANUAL_CLOSE", "Đóng tay"],
] as const) {
  test(`EXIT names the reason ${code}, never a bare code`, async ({ page }) => {
    const v = view("closedSl");
    v.desk!.last_exit!.exit_reason = code;
    await mock(page, v);
    await page.goto("/trade");
    await expect(page.getByTestId("action-sub")).toContainText(text);
    await expect(page.getByTestId("action-sub")).not.toContainText(code);
  });
}

test("the evidence rung and its meaning are on the fold; an unknown level falls to UNVALIDATED", async ({ page }) => {
  const v = view("buy");
  v.evidence = { ...v.evidence, level: "EDGE_CONFIRMED" };
  await mock(page, v);
  await page.goto("/trade");
  await expect(page.getByTestId("honesty")).toHaveAttribute("data-level", "UNVALIDATED");
  await expect(page.getByTestId("evidence-copy")).toHaveText("Baseline vận hành. Chưa có bằng chứng kỳ vọng dương.");
});

test("fold screenshots of the contract states (fixtures, not live evidence)", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const wait = view("wait");
  (wait.structure as Record<string, unknown>).h1_trend = "BULLISH";
  wait.why_wait = { ...wait.why_wait!, waiting_for_code: "TIMEFRAME_CONFLICT", blocked_by: ["TIMEFRAME_CONFLICT"] };
  for (const [name, v] of [["wait-conflict", wait], ["buy", view("buy")], ["hold", view("openPaper")], ["exit-sl", view("closedSl")]] as const) {
    await page.unrouteAll();
    await mock(page, v);
    await page.goto("/trade");
    await expect(page.getByTestId("action-word")).toBeVisible();
    await page.screenshot({ path: (process.env.SAVE_DOC_SHOTS ? "../../docs/reports/img/v3-2026-10-11" : "test-results/shots") + `/trade-1440-${name}.png`, fullPage: false });
  }
});

test("Operations is labelled for what it is and kept apart from the trader links", async ({ page }) => {
  await mock(page, view("wait"));
  await page.goto("/trade");
  await expect(page.getByTestId("nav-ops")).toHaveText("Vận hành");
  await expect(page.getByTestId("main-nav")).not.toContainText("System");
});
