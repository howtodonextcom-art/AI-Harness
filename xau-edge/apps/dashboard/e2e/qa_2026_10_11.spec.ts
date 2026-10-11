import { expect, test } from "@playwright/test";
import { mock, view, type GoldenName } from "./fixtures/trade";

/** Regressions from the MCP trade QA of 2026-10-11 and the six-state viewport matrix. */

test.use({ viewport: { width: 1440, height: 900 } });

test("UNAVAILABLE never shows a usable plan: levels blanked, no risk or lot (QA #1)", async ({ page }) => {
  await mock(page, view("writerConflict"));
  await page.goto("/trade");
  const hero = page.getByTestId("hero");
  await expect(hero).toHaveAttribute("data-action", "UNAVAILABLE");
  await expect(page.getByTestId("hero-levels")).toHaveAttribute("data-blocked", "true");
  await expect(page.getByTestId("hero-levels-blocked")).toHaveText("Kế hoạch bị chặn, không dùng.");
  for (const id of ["hero-entry", "hero-sl", "hero-tp", "hero-rr"]) await expect(page.getByTestId(id)).toHaveText("—");
  await expect(page.getByTestId("hero-risk")).toHaveCount(0);
  await expect(page.getByTestId("hero-lot")).toHaveCount(0);
  await expect(page.getByTestId("take-paper")).toHaveCount(0);
});

test("a tradable plan keeps its levels", async ({ page }) => {
  const v = view("buy");
  await mock(page, v);
  await page.goto("/trade");
  await expect(page.getByTestId("hero-levels")).toHaveAttribute("data-blocked", "false");
  await expect(page.getByTestId("hero-sl")).toHaveText(v.trade_plan!.sl!.toFixed(2));
});

test("stale bars and a stale quote are one problem line, both codes kept in the detail (QA #3)", async ({ page }) => {
  await mock(page, view("stale"));
  await page.goto("/trade");
  const items = page.getByTestId("hero-problems").locator("li");
  await expect(items.filter({ hasText: "quá cũ" })).toHaveCount(1);
  await expect(items.first()).toContainText("Dữ liệu giá và báo giá đã quá cũ");
});

const STATES: [GoldenName, string][] = [
  ["wait", "WAIT"],
  ["buy", "BUY"],
  ["sell", "SELL"],
  ["openPaper", "HOLD"],
  ["closedPaper", "EXIT"],
  ["writerConflict", "UNAVAILABLE"],
];
const VIEWPORTS = [
  { width: 1440, height: 900 },
  { width: 1920, height: 1080 },
  { width: 390, height: 844 },
];

for (const vp of VIEWPORTS) {
  test.describe(`${vp.width}x${vp.height}${vp.width < 640 ? " @mobile" : ""}`, () => {
    test.use({ viewport: vp });
    for (const [name, action] of STATES) {
      test(`${name}: the action is the first thing on screen, nothing overflows, no console error`, async ({ page }) => {
        const errors: string[] = [];
        page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
        page.on("pageerror", (e) => errors.push(e.message));
        await mock(page, view(name));
        await page.goto("/trade");
        const hero = page.getByTestId("hero");
        await expect(hero).toHaveAttribute("data-action", action);
        const box = await hero.boundingBox();
        expect(box, "hero has a box").not.toBeNull();
        expect(box!.y).toBeLessThan(vp.height * 0.6);
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
        expect(overflow).toBeLessThanOrEqual(0);
        if (action !== "BUY" && action !== "SELL") await expect(page.getByTestId("take-paper")).toHaveCount(0);
        expect(errors).toEqual([]);
      });
    }
  });
}
