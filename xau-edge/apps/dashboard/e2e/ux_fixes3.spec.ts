import { expect, test } from "@playwright/test";
import { journalClosedGolden, markersClosedGolden, mock, setupsGolden, signalsGolden, view } from "./fixtures/trade";

/** Third review round: what the engine did while nobody watched, the last trade, alerting, confirmation drift. */

test("the activity feed lists the setups the engine armed and how each ended, including those that expired unseen", async ({ page }) => {
  const setups = setupsGolden();
  expect(setups.setups.some((s) => s.outcome === "EXPIRED")).toBe(true); // real replay data
  await mock(page, view("closedPaper"), { setups, journal: journalClosedGolden(), markers: markersClosedGolden(), signals: signalsGolden() });
  await page.goto("/trade");
  await page.getByTestId("tab-activity").click();
  await page.getByRole("button", { name: "Setup đã hình thành", exact: true }).click();
  const rows = page.getByTestId("activity-row");
  await expect(rows).toHaveCount(setups.setups.length);
  await expect(page.getByTestId("activity-feed")).toContainText("HẾT HẠN khi chưa ai mở");
  await expect(page.getByTestId("activity-feed")).toContainText("đã kích hoạt");
});

test("the last closed trade stays on screen after the exit message is gone", async ({ page }) => {
  await mock(page, view("closedPaper"));
  await page.goto("/trade");
  const card = page.getByTestId("last-exit");
  await expect(card).toContainText("Lệnh đóng gần nhất");
  await expect(card).toContainText("Chạm TP");
  await expect(card).toContainText("R");
  await mock(page, view("wait"));
  await page.reload();
  await expect(page.getByTestId("last-exit")).toHaveCount(0); // no trade yet in that golden
});

test("when Telegram is not configured the page says that alerts will not reach you with the browser closed", async ({ page }) => {
  const v = { ...view("wait"), source_mode: "LIVE" as const };
  expect(v.alerts?.telegram_configured).toBe(false);
  await mock(page, v);
  await page.goto("/trade");
  await expect(page.getByTestId("alert-channel-notice")).toContainText("CHƯA BẬT");
  const on = { ...v, alerts: { ...v.alerts!, telegram_configured: true, delivery: "TELEGRAM" as const } };
  await mock(page, on);
  await page.reload();
  await expect(page.getByTestId("alert-channel-notice")).toHaveCount(0);
});

test("the confirmation shows TP 2 as reference only and warns how far the price moved, in R", async ({ page }) => {
  const v = view("buy");
  const plan = v.trade_plan!;
  await mock(page, v);
  await page.goto("/trade");
  await page.getByTestId("take-paper").click();
  await expect(page.getByTestId("confirm-open-modal")).toContainText("TP 2 (chỉ tham khảo)");
  await expect(page.getByTestId("confirm-open-modal")).toContainText("lệnh thoát tại đây");
  await expect(page.getByTestId("confirm-drift")).toHaveCount(0); // price has not moved
  await page.keyboard.press("Escape");
  // the market moves while the trader reads: the plan (and its entry) is the same setup, the quote is not
  const moved = view("buy");
  moved.trade_plan!.planned_entry = (plan.planned_entry ?? 0) + 2;
  await page.route("**/trade/decision", (route) => route.fulfill({ json: moved }));
  await page.getByTestId("take-paper").click();
  await page.waitForTimeout(3500);
  await expect(page.getByTestId("confirm-drift")).toContainText("đã dịch +2.00");
  await expect(page.getByTestId("confirm-drift")).toContainText("R");
});

test("the validity countdown turns urgent in its last minute and says what expiry means", async ({ page }) => {
  const v = view("buy");
  const soon = new Date(Date.parse(v.served_at!) + 45_000).toISOString();
  v.trade_plan!.expires_at = soon;
  v.trade_plan!.seconds_to_expiry = 45;
  await mock(page, v);
  await page.goto("/trade");
  const e = page.getByTestId("expiry");
  await expect(e).toHaveAttribute("data-urgent", "true");
  await expect(e).toContainText("sắp hết hạn");
});

test("fullscreen keeps the actions: open from the chart summary", async ({ page }) => {
  await mock(page, view("buy"));
  await page.goto("/trade");
  await expect(page.getByTestId("decision")).toBeVisible();
  await page.getByTestId("chart-fullscreen").click();
  await page.getByTestId("fs-open").click();
  await expect(page.getByTestId("confirm-open-modal")).toBeVisible();
  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");
  await mock(page, view("openPaper"));
  await page.reload();
  await page.getByTestId("chart-fullscreen").click();
  await expect(page.getByTestId("fs-close")).toBeVisible();
});
