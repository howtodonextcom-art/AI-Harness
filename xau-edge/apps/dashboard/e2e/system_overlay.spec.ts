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
  await page.setViewportSize({ width: 720, height: 450 }); // the narrowest supported desktop view (200% zoom)
  await expect(page.getByTestId("system-plan-overlay")).toBeVisible();
  expect(await prices(page)).toEqual(before);
  const box = await page.getByTestId("system-action-badge").boundingBox();
  expect(box?.x ?? -1).toBeGreaterThanOrEqual(0);
  expect((box?.x ?? 0) + (box?.width ?? 0)).toBeLessThanOrEqual(390);
});

test("reverse coordinate parity: price -> y -> price returns the backend level within one tick (BUY and SELL)", async ({ page }) => {
  for (const name of ["buy", "sell"] as GoldenName[]) {
    const v = view(name);
    await mock(page, v);
    await page.goto("/trade");
    await expect(page.getByTestId("system-plan-overlay")).toHaveAttribute("data-mode", "PLAN");
    const rows = await page.getByTestId("system-plan-overlay").evaluate((el) =>
      Array.from(el.querySelectorAll("[data-reprice]")).map((n) => ({
        role: (n as HTMLElement).dataset.role,
        price: Number((n as HTMLElement).dataset.price),
        reprice: Number((n as HTMLElement).dataset.reprice),
      })),
    );
    const byRole = Object.fromEntries(rows.map((r) => [r.role, r]));
    for (const role of ["entry", "sl", "tp1"]) {
      expect(byRole[role], `${name} ${role} has a reverse price`).toBeTruthy();
      expect(Math.abs(byRole[role].reprice - byRole[role].price), `${name} ${role}`).toBeLessThanOrEqual(0.01);
    }
    expect(byRole.entry.price).toBe(v.trade_plan!.planned_entry);
  }
});

test("rapid transitions BUY -> WAIT -> SELL -> UNAVAILABLE -> HOLD -> EXIT without a reload leave no stale plan", async ({ page }) => {
  const steps: { name: GoldenName; overlay: "PLAN" | "POSITION" | null; side?: string }[] = [
    { name: "buy", overlay: "PLAN", side: "BUY" },
    { name: "wait", overlay: null },
    { name: "sell", overlay: "PLAN", side: "SELL" },
    { name: "writerConflict", overlay: null },
    { name: "openPaper", overlay: "POSITION" },
    { name: "closedTime", overlay: null },
  ];
  await mock(page, view(steps[0].name));
  await page.goto("/trade");
  const overlay = page.getByTestId("system-plan-overlay");
  await page.evaluate(() => { (window as unknown as { __noReload: number }).__noReload = 1; });
  for (const step of steps) {
    const v = view(step.name);
    await mock(page, v); // later routes win: the decision AND the candles follow the new state, no reload
    if (step.overlay === null) {
      await expect(overlay).toHaveCount(0, { timeout: 8000 });
      await expect(page.getByTestId("line-BUY-ENTRY")).toHaveCount(0);
      await expect(page.getByTestId("line-SELL-ENTRY")).toHaveCount(0);
      await expect(page.getByTestId("system-action-badge")).toHaveCount(0);
      await expect(page.getByTestId("take-paper")).toHaveCount(0);
    } else {
      await expect(overlay, step.name).toHaveAttribute("data-mode", step.overlay, { timeout: 8000 });
      if (step.side) await expect(overlay).toHaveAttribute("data-side", step.side);
      const p = await prices(page);
      const expected = step.overlay === "POSITION" ? v.desk!.position!.fill_price : v.trade_plan!.planned_entry;
      expect(p.entry).toBe(expected);
    }
  }
  expect(await page.evaluate(() => (window as unknown as { __noReload?: number }).__noReload)).toBe(1); // same document: nothing reloaded
});

test("collision: the action badge never covers a Entry/SL/TP label of the system plan (desktop and 200% zoom)", async ({ page }) => {
  for (const size of [{ width: 1440, height: 900 }, { width: 720, height: 450 }]) {
    await page.setViewportSize(size);
    for (const name of ["buy", "sell", "openPaper"] as GoldenName[]) {
      await mock(page, view(name));
      await page.goto("/trade");
      await expect(page.getByTestId("system-plan-overlay")).toBeVisible();
      const overlaps = await page.getByTestId("system-plan-overlay").evaluate((svg) => {
        const badge = svg.querySelector("[data-testid=system-action-badge]")!.getBoundingClientRect();
        const hit: string[] = [];
        svg.querySelectorAll("text").forEach((t) => {
          if (t.closest("[data-testid=system-action-badge]")) return;
          const r = t.getBoundingClientRect();
          const x = r.left < badge.right && r.right > badge.left;
          const y = r.top < badge.bottom && r.bottom > badge.top;
          if (x && y && /ENTRY|SL|TP|ACTUAL|NOW/.test(t.textContent ?? "")) hit.push(t.textContent ?? "");
        });
        return hit;
      });
      expect(overlaps, `${name} @ ${size.width}`).toEqual([]);
    }
  }
});

test("an expired setup never shows live-looking Entry/SL/TP figures in the hero", async ({ page }) => {
  await mock(page, view("expired"));
  await page.goto("/trade");
  await expect(page.getByTestId("hero")).toHaveAttribute("data-hero-state", "EXPIRED_SETUP");
  await expect(page.getByTestId("hero-levels")).toHaveAttribute("data-blocked", "true");
  await expect(page.getByTestId("hero-levels-blocked")).toHaveText("Kế hoạch đã hết hạn, không dùng.");
  for (const id of ["hero-entry", "hero-sl", "hero-tp", "hero-rr"]) await expect(page.getByTestId(id)).toHaveText("—");
  await expect(page.getByTestId("take-paper")).toHaveCount(0);
});

test("HOLD: hero levels, plan overlay and API agree on the actual fill, not the planned entry", async ({ page }) => {
  const v = view("openPaper");
  await mock(page, v);
  await page.goto("/trade");
  await expect(page.getByTestId("hero")).toHaveAttribute("data-hero-state", "POSITION_OPEN");
  await expect(page.getByTestId("hero-entry")).toHaveText(v.desk!.position!.fill_price.toFixed(2));
  await expect(page.getByTestId("hero-sl")).toHaveText(v.desk!.position!.sl.toFixed(2));
  expect((await prices(page)).entry).toBe(v.desk!.position!.fill_price);
});

test("collision: system plan labels and badge never overlap the chart's context legend (200% zoom, desktop)", async ({ page }) => {
  for (const size of [{ width: 720, height: 450 }, { width: 1440, height: 900 }]) {
    await page.setViewportSize(size);
    await mock(page, view("buy"));
    await page.goto("/trade");
    await expect(page.getByTestId("system-plan-overlay")).toBeVisible();
    await page.waitForTimeout(400); // the legend is measured after layout
    const hits = await page.evaluate(() => {
      const legend = document.querySelector("[data-testid=chart-legend]")!.getBoundingClientRect();
      const svg = document.querySelector("[data-testid=system-plan-overlay]")!;
      const out: string[] = [];
      svg.querySelectorAll("text").forEach((t) => {
        const r = t.getBoundingClientRect();
        if (r.left < legend.right && r.right > legend.left && r.top < legend.bottom && r.bottom > legend.top) out.push(t.textContent ?? "");
      });
      return out;
    });
    expect(hits, `${size.width}x${size.height}`).toEqual([]);
  }
});
