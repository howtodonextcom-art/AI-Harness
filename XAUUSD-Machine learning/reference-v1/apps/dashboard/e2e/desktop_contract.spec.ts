import { expect, test } from "@playwright/test";
import type { TradeView } from "../lib/trade";
import { mock, view } from "./fixtures/trade";

/**
 * DESKTOP CONTRACT (scope decision 2026-10-12: the owner uses a desktop; phone layouts are frozen).
 * Supported: 1280 to 2560 CSS px wide and browser zoom up to 200% (down to 720x450). In every supported window and
 * state: the action is on the first screen, nothing scrolls sideways, the chart is at least 280 px high, the open
 * button is usable when a BUY/SELL is offered, and NOTHING offers a trade when the action is not BUY/SELL.
 */

const VIEWPORTS = [
  { name: "2560x1440", width: 2560, height: 1440 },
  { name: "1920x1080", width: 1920, height: 1080 },
  { name: "1440x900", width: 1440, height: 900 },
  { name: "1280x720", width: 1280, height: 720 },
  { name: "150% zoom 960x600", width: 960, height: 600 },
  { name: "125% zoom 1152x720", width: 1152, height: 720 },
  { name: "200% zoom 720x450", width: 720, height: 450 },
];

function blockedBuy(): TradeView {
  const v = view("buy");
  v.hero.action = { ...v.hero.action, code: "WAIT", stage: "BLOCKED", blocked_by: { code: "CLOSURE_NEAR", message: "closure" } } as TradeView["hero"]["action"];
  v.actionable = false;
  return v;
}

const OFFER = [
  ["buy", () => view("buy")],
  ["sell", () => view("sell")],
] as const;
const NO_OFFER = [
  ["wait", () => view("wait")],
  ["buyWatch", () => view("buyWatch")],
  ["blocked BUY", blockedBuy],
  ["expired", () => view("expired")],
  ["stale", () => view("stale")],
  ["marketClosed", () => view("marketClosed")],
  ["openPaper", () => view("openPaper")],
  ["closedSl", () => view("closedSl")],
] as const;

for (const vp of VIEWPORTS) {
  test.describe(vp.name, () => {
    test.use({ viewport: { width: vp.width, height: vp.height } });

    for (const [name, make] of [...OFFER, ...NO_OFFER]) {
      test(`${name}: action on the first screen, no sideways scroll, chart >= 280 px`, async ({ page }) => {
        await mock(page, make());
        await page.goto("/trade");
        const word = page.getByTestId("action-word");
        await expect(word).toBeVisible();
        const box = await word.boundingBox();
        expect(box!.y, "the action word is inside the first screen").toBeLessThan(vp.height);
        expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth), "no sideways scroll").toBeLessThanOrEqual(0);
        const chart = await page.getByTestId("trade-chart").boundingBox();
        expect(chart!.height, "chart height").toBeGreaterThanOrEqual(280);
        expect(chart!.width, "chart width").toBeGreaterThan(Math.min(400, vp.width - 120));
      });
    }

    for (const [name, make] of OFFER) {
      test(`${name}: the open button is reachable and enabled`, async ({ page }) => {
        await mock(page, make());
        await page.goto("/trade");
        const open = page.getByTestId("take-paper");
        await open.scrollIntoViewIfNeeded();
        await expect(open).toBeVisible();
        await expect(open).toBeEnabled();
      });
    }

    for (const [name, make] of NO_OFFER) {
      test(`${name}: nothing offers a trade (fail-closed at every supported size)`, async ({ page }) => {
        await mock(page, make());
        await page.goto("/trade");
        await expect(page.getByTestId("take-paper")).toHaveCount(0);
        await expect(page.getByTestId("fs-open")).toHaveCount(0);
        if (name !== "openPaper") await expect(page.getByTestId("system-action-badge")).toHaveCount(0); // HOLD draws its own position badge
        const text = (await page.locator("body").innerText()).replace(/\s+/g, " ");
        expect(text).not.toMatch(/SẴN SÀNG (MUA|BÁN)/);
        expect(text).not.toMatch(/(MUA|BÁN) · R:R/);
        if (name !== "openPaper") await expect(page.getByTestId("system-plan-overlay")).toHaveCount(0);
      });
    }
  });
}
