import { expect, test } from "@playwright/test";
import { mock, view, type GoldenName } from "./fixtures/trade";

/** Core Web Vitals CLS found by the Chrome DevTools MCP on the live page (0.23 at load): the market bar and the
 * "loading" line changed height when the first decision arrived. The page must not move when data lands. */
for (const name of ["wait", "buy", "marketClosed"] as GoldenName[]) {
  test(`${name}: the page does not shift when the first decision arrives (CLS < 0.1)`, async ({ page }) => {
    await page.addInitScript(() => {
      const w = window as unknown as { __cls: number; __who: string[] };
      w.__cls = 0;
      w.__who = [];
      type Shift = { value: number; hadRecentInput: boolean; sources: { node?: HTMLElement; previousRect: DOMRect; currentRect: DOMRect }[] };
      new PerformanceObserver((list) => {
        for (const e of list.getEntries() as unknown as Shift[]) {
          if (e.hadRecentInput) continue;
          w.__cls += e.value;
          for (const src of e.sources) {
            const id = src.node?.dataset?.testid ?? src.node?.tagName ?? "?";
            w.__who.push(`${id} y ${Math.round(src.previousRect.y)}+${Math.round(src.previousRect.height)} -> ${Math.round(src.currentRect.y)}+${Math.round(src.currentRect.height)}`);
          }
        }
      }).observe({ type: "layout-shift", buffered: true });
    });
    const v = view(name);
    await mock(page, v);
    await page.route("**/trade/decision", async (route) => {
      await new Promise((r) => setTimeout(r, 400)); // the placeholders are on screen first
      await route.fulfill({ json: v });
    });
    await page.goto("/trade");
    await expect(page.getByTestId("hero")).toBeVisible();
    await page.waitForTimeout(1200);
    const { cls, who } = await page.evaluate(() => {
      const w = window as unknown as { __cls: number; __who: string[] };
      return { cls: w.__cls, who: w.__who };
    });
    expect(cls, `CLS ${cls.toFixed(3)}: ${who.join(" | ")}`).toBeLessThan(0.1);
  });
}
