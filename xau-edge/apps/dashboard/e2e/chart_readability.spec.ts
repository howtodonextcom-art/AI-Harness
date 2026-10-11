import { expect, test, type Page } from "@playwright/test";
import { bars, mock, view, type GoldenName } from "./fixtures/trade";

/** Found by comparing /trade with the FTMO web terminal: candles filled 70% of the plot there and 20-30% here. */

const PREFS_KEY = "xau-edge.trade.prefs.v1";

async function withStructure(page: Page) {
  await page.addInitScript((key) => {
    window.localStorage.setItem(key, JSON.stringify({ overlays: { structure: true, keyLevels: false } }));
  }, PREFS_KEY);
}

/** Candle pixels (the project's green/red) of the main canvas: vertical share of the plot and candle pitch. */
async function measure(page: Page) {
  return page.getByTestId("trade-chart").evaluate((host) => {
    const canvases = Array.from(host.querySelectorAll("canvas")).filter((c) => c.height > 200 && c.width > 300);
    const near = (a: number, b: number) => Math.abs(a - b) < 14;
    let best = { span: 0, candles: 0, pitch: 0 };
    for (const c of canvases) {
      const { width: w, height: h } = c;
      const d = c.getContext("2d")!.getImageData(0, 0, w, h).data;
      let minY = 1e9, maxY = -1, minX = 1e9, maxX = -1;
      const cols = new Uint8Array(w);
      for (let y = 0; y < h; y++) {
        for (let x = 0; x < w; x++) {
          const i = (y * w + x) * 4;
          if (d[i + 3] < 200) continue;
          const g = near(d[i], 22) && near(d[i + 1], 163) && near(d[i + 2], 74);
          const r = near(d[i], 220) && near(d[i + 1], 38) && near(d[i + 2], 38);
          if (!g && !r) continue;
          minY = Math.min(minY, y); maxY = Math.max(maxY, y); minX = Math.min(minX, x); maxX = Math.max(maxX, x); cols[x] = 1;
        }
      }
      if (maxY < 0) continue;
      let clusters = 0, prev = 0;
      for (let x = 0; x < w; x++) { if (cols[x] && !prev) clusters++; prev = cols[x]; }
      best = { span: (maxY - minY) / h, candles: clusters, pitch: (maxX - minX) / Math.max(1, clusters - 1) / (window.devicePixelRatio || 1) };
    }
    return best;
  });
}

/** The same view with PDH/PDL far away from the candles, as on the live page (PDL 4131 against candles at 4195). */
function withFarStructure(name: GoldenName) {
  const v = view(name);
  const last = bars(v, "M5").bars.at(-1)!.close;
  v.structure = { ...v.structure!, pdh: last + 70, pdl: last - 70, nearest_resistance: last + 40, nearest_support: last - 40 };
  return v;
}

for (const tf of ["M1", "M5"]) {
  test(`${tf}: far structure levels do not shrink the candles (span >= 40% of the plot) and each candle is readable`, async ({ page }) => {
    await withStructure(page);
    await mock(page, withFarStructure("wait"));
    await page.goto("/trade");
    await page.getByTestId(`chart-tf-${tf}`).click();
    await expect(page.getByTestId("line-PDH")).toBeVisible(); // the far level is still listed
    await page.waitForTimeout(900);
    const m = await measure(page);
    const { from, to, width } = await page.getByTestId("trade-chart").evaluate((e) => {
      const [f, t] = (e.getAttribute("data-range") ?? "0:1").split(":").map(Number);
      return { from: f, to: t, width: e.clientWidth - 64 }; // minus the price axis
    });
    const pitch = width / (to - from);
    expect(m.span, `${tf} candle span ${m.span.toFixed(2)} of the plot`).toBeGreaterThanOrEqual(0.4);
    expect(pitch, `${tf} candle pitch ${pitch.toFixed(1)} px (${(to - from).toFixed(0)} bars)`).toBeGreaterThanOrEqual(6);
  });
}

test("a live plan stays inside the price scale while far context levels do not move it", async ({ page }) => {
  await withStructure(page);
  const v = view("buy");
  const last = bars(v, "M5").bars.at(-1)!.close;
  v.structure = { ...v.structure!, pdh: last + 90, pdl: last - 90 };
  await mock(page, v);
  await page.goto("/trade");
  await expect(page.getByTestId("system-plan-overlay")).toBeVisible();
  const box = await page.getByTestId("trade-chart").boundingBox();
  const ys = await page.getByTestId("system-plan-overlay").evaluate((el) =>
    Object.fromEntries(Array.from(el.querySelectorAll("[data-y]")).map((n) => [(n as HTMLElement).dataset.role, Number((n as HTMLElement).dataset.y)])),
  );
  for (const role of ["entry", "sl", "tp1"]) {
    expect(ys[role], `${role} inside the chart`).toBeGreaterThan(0);
    expect(ys[role], `${role} inside the chart`).toBeLessThan(box!.height);
  }
});

test("the session legend sits above the time axis and never covers its labels", async ({ page }) => {
  await page.addInitScript((key) => {
    window.localStorage.setItem(key, JSON.stringify({ overlays: { sessions: true } }));
  }, PREFS_KEY);
  await mock(page, view("wait"));
  await page.goto("/trade");
  const legend = page.getByTestId("session-legend");
  await expect(legend).toBeVisible();
  const [l, c] = await Promise.all([legend.boundingBox(), page.getByTestId("trade-chart").boundingBox()]);
  expect(c!.y + c!.height - (l!.y + l!.height), "gap between the legend and the bottom of the chart (time axis is about 28 px)").toBeGreaterThanOrEqual(28);
});
