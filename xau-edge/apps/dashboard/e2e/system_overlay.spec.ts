import { expect, test } from "@playwright/test";
import { mock, view, type GoldenName } from "./fixtures/trade";

const REPLAY_DRAWINGS_KEY = "xau-edge:v3:REPLAY:XAUUSD:drawings";

async function prices(page: import("@playwright/test").Page) {
  return page.getByTestId("system-plan-overlay").evaluate((el) =>
    Object.fromEntries(
      Array.from(el.querySelectorAll("[data-price]")).map((node) => [
        (node as HTMLElement).dataset.role,
        Number((node as HTMLElement).dataset.price),
      ]),
    ) as Record<string, number>,
  );
}

async function ys(page: import("@playwright/test").Page) {
  return page.getByTestId("system-plan-overlay").evaluate((el) =>
    Object.fromEntries(
      Array.from(el.querySelectorAll("[data-y]")).map((node) => [
        (node as HTMLElement).dataset.role,
        Number((node as HTMLElement).dataset.y),
      ]),
    ) as Record<string, number>,
  );
}

test("WAIT and UNAVAILABLE never leave an actionable system trade-plan overlay", async ({ page }) => {
  for (const name of ["wait", "writerConflict", "stale", "expired"] as GoldenName[]) {
    await mock(page, view(name));
    await page.goto("/trade");
    await expect(page.getByTestId("system-plan-overlay")).toHaveCount(0);
    await expect(page.getByTestId("line-BUY-ENTRY")).toHaveCount(0);
    await expect(page.getByTestId("line-SELL-ENTRY")).toHaveCount(0);
  }
});

test("BUY overlay is read-only and uses exact backend plan levels", async ({ page }) => {
  const v = view("buy");
  await mock(page, v);
  await page.goto("/trade");
  await expect(page.getByTestId("system-plan-overlay")).toHaveAttribute("data-mode", "PLAN");
  await expect(page.getByTestId("system-plan-overlay")).toHaveAttribute("data-side", "BUY");
  await expect(page.getByTestId("system-action-badge")).toContainText("MUA");
  await expect(page.getByTestId("system-action-badge")).toContainText("UNVALIDATED");
  await expect(page.getByTestId("system-plan-overlay")).toContainText("NOT A REAL-MONEY SIGNAL");
  expect(await prices(page)).toMatchObject({
    entry: v.trade_plan!.planned_entry,
    sl: v.trade_plan!.sl,
    tp1: v.trade_plan!.tp1,
  });
  const y = await ys(page);
  expect(y.tp1).toBeLessThan(y.entry);
  expect(y.entry).toBeLessThan(y.sl);
  await expect(page.getByTestId("system-plan-overlay")).toHaveCSS("pointer-events", "none");
  expect(await page.evaluate((k) => window.localStorage.getItem(k), REPLAY_DRAWINGS_KEY)).not.toContain("system");
});

test("SELL overlay keeps backend geometry: SL above entry, TP below entry", async ({ page }) => {
  const v = view("sell");
  await mock(page, v);
  await page.goto("/trade");
  await expect(page.getByTestId("system-plan-overlay")).toHaveAttribute("data-side", "SELL");
  await expect(page.getByTestId("system-action-badge")).toContainText("BÁN");
  expect(await prices(page)).toMatchObject({
    entry: v.trade_plan!.planned_entry,
    sl: v.trade_plan!.sl,
    tp1: v.trade_plan!.tp1,
  });
  const y = await ys(page);
  expect(y.sl).toBeLessThan(y.entry);
  expect(y.entry).toBeLessThan(y.tp1);
});

test("HOLD overlay uses actual paper fill, not the planned entry", async ({ page }) => {
  const v = view("openPaper");
  await mock(page, v);
  await page.goto("/trade");
  await expect(page.getByTestId("system-plan-overlay")).toHaveAttribute("data-mode", "POSITION");
  await expect(page.getByTestId("system-action-badge")).toContainText("GIỮ");
  const p = await prices(page);
  expect(p.entry).toBe(v.desk!.position!.fill_price);
  expect(p.entry).not.toBe(v.desk!.position!.planned_entry);
  expect(p.sl).toBe(v.desk!.position!.sl);
  expect(p.tp1).toBe(v.desk!.position!.tp);
});

test("system plan prices are invariant across timeframe and resize", async ({ page }) => {
  const v = view("buy");
  await mock(page, v);
  await page.goto("/trade");
  const before = await prices(page);
  await page.getByTestId("chart-tf-M15").click();
  await expect(page.getByTestId("system-plan-overlay")).toHaveAttribute("data-side", "BUY");
  expect(await prices(page)).toEqual(before);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByTestId("system-plan-overlay")).toBeVisible();
  expect(await prices(page)).toEqual(before);
  const box = await page.getByTestId("system-action-badge").boundingBox();
  expect(box?.x ?? -1).toBeGreaterThanOrEqual(0);
  expect((box?.x ?? 0) + (box?.width ?? 0)).toBeLessThanOrEqual(390);
});
