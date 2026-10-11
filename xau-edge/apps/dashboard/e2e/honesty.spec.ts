import { expect, test } from "@playwright/test";
import { coverageIncompleteGolden, mock, view } from "./fixtures/trade";

/**
 * Card B (honesty on the fold): UNVALIDATED + coverage vs the 95% gate beside the action,
 * Entry/SL/TP/R:R even when "—", DỮ LIỆU LIVE, header pill when closed, one-source setup note.
 */

test("honesty and levels sit beside the action; coverage below the 95% gate is said in Vietnamese", async ({ page }) => {
  const v = view("wait");
  v.source_mode = "LIVE";
  const cov = coverageIncompleteGolden();
  v.decision_coverage = cov;
  v.forward_acceptance = { ...v.forward_acceptance, live: true, evidence_complete: false, coverage_pct: cov.coverage_pct };
  await mock(page, v);
  await page.goto("/trade");
  const honesty = page.getByTestId("honesty");
  await expect(honesty).toBeVisible();
  await expect(honesty).toContainText("UNVALIDATED");
  await expect(honesty).toContainText("CHƯA KIỂM CHỨNG");
  await expect(honesty).toContainText("70.4%");
  await expect(honesty).toContainText("95");
  await expect(honesty).toContainText("chưa thấy setup");
  await expect(honesty).toHaveAttribute("data-below-gate", "true");
  await expect(page.getByTestId("hero-levels")).toBeVisible();
  await expect(page.getByTestId("hero-entry")).toHaveText("—");
  await expect(page.getByTestId("hero-sl")).toHaveText("—");
  await expect(page.getByTestId("hero-tp")).toHaveText("—");
  await expect(page.getByTestId("hero-rr")).toHaveText("—");
});

test("a BUY plan puts Entry/SL/TP/R:R on the hero, not only in the ticket", async ({ page }) => {
  await mock(page, view("buy"));
  await page.goto("/trade");
  await expect(page.getByTestId("hero-entry")).toContainText("4236.47");
  await expect(page.getByTestId("hero-sl")).toContainText("4229.45");
  await expect(page.getByTestId("hero-tp")).toContainText("4250.51");
  await expect(page.getByTestId("hero-rr")).not.toHaveText("—");
});

test("closed LIVE market: data badge, header action pill, honesty on the fold", async ({ page }) => {
  const v = view("marketClosed");
  v.source_mode = "LIVE";
  await mock(page, v);
  await page.goto("/trade");
  await expect(page.getByTestId("source-pill")).toContainText("DỮ LIỆU LIVE");
  await expect(page.getByTestId("source-pill")).toContainText("ĐÓNG CỬA");
  await expect(page.getByTestId("header-action-pill")).toContainText("CHỜ");
  await expect(page.getByTestId("header-action-pill")).toContainText("CHƯA KIỂM CHỨNG");
  await expect(page.getByTestId("honesty")).toContainText("UNVALIDATED");
  await expect(page.getByTestId("hero-levels")).toBeVisible();
});

test("M15 PULLBACK is not a setup: one source of truth on the card", async ({ page }) => {
  await mock(page, view("buyWatch"));
  await page.goto("/trade");
  await expect(page.getByTestId("setup-stage")).toContainText("Chưa có");
  await expect(page.getByTestId("setup-truth")).toContainText("chưa có setup");
  await expect(page.getByTestId("setup-truth")).toContainText("vai trò khung");
  await expect(page.getByTestId("action-when")).toContainText("M15 có nhịp pullback");
  await expect(page.getByTestId("action-when")).toContainText("hiện chưa có");
});

test("5-second fold screenshots at 1440 and 1920 (closed LIVE)", async ({ page }) => {
  const v = view("marketClosed");
  v.source_mode = "LIVE";
  const cov = coverageIncompleteGolden();
  v.decision_coverage = cov;
  await mock(page, v);
  await page.goto("/trade");
  await expect(page.getByTestId("honesty")).toBeVisible();
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.screenshot({
    path: "../../docs/reports/img/consolidation-2026-10-11/trade-1440-card-b.png",
    fullPage: false,
  });
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.screenshot({
    path: "../../docs/reports/img/consolidation-2026-10-11/trade-1920-card-b.png",
    fullPage: false,
  });
});
