import { expect, test, type Page } from "@playwright/test";
import { anchorMs, mock, view } from "./fixtures/trade";

/** DRAW-01: the trader's own drawings (annotations only): create, edit, persist per source, never touch a decision. */

const REPLAY_KEY = "xau-edge:v3:REPLAY:XAUUSD:drawings";
const LIVE_KEY = "xau-edge:v3:LIVE:XAUUSD:drawings";

async function box(page: Page) {
  const b = await page.getByTestId("trade-chart").boundingBox();
  if (!b) throw new Error("no chart");
  return b;
}

async function twoClicks(page: Page, tool: string, from: [number, number], to: [number, number]) {
  const b = await box(page);
  await page.getByTestId("draw-menu").click();
  await page.getByTestId(`tool-${tool}`).click();
  await page.mouse.click(b.x + b.width * from[0], b.y + b.height * from[1]);
  await page.mouse.move(b.x + b.width * to[0], b.y + b.height * to[1], { steps: 4 });
  await page.mouse.click(b.x + b.width * to[0], b.y + b.height * to[1]);
}

const stored = (page: Page, key: string) =>
  page.evaluate((k) => JSON.parse(window.localStorage.getItem(k) ?? "[]") as { kind: string; a: { t: number; p: number }; b: { t: number; p: number }; label: string; locked: boolean; rr?: number }[], key);

test.beforeEach(async ({ page }) => {
  await mock(page, view("wait"));
  await page.goto("/trade");
  await expect(page.getByTestId("trade-chart")).toHaveAttribute("data-bars", /\d+/);
});

test("a trendline is two clicks, shows on the chart, and is kept per source across reload, timeframe and display zone", async ({ page }) => {
  await twoClicks(page, "trend", [0.3, 0.6], [0.7, 0.3]);
  await expect(page.locator("[data-testid^='drawing-'][data-kind='trend']")).toHaveCount(1);
  await expect(page.getByTestId("drawing-manager-btn")).toContainText("(1)");
  const [saved] = await stored(page, REPLAY_KEY);
  expect(saved.kind).toBe("trend");
  expect(saved.a.t).toBeLessThan(saved.b.t);
  expect(saved.a.p).toBeLessThan(saved.b.p);
  expect(await stored(page, LIVE_KEY)).toHaveLength(0); // a REPLAY drawing never lands in the LIVE scope

  await page.getByTestId("chart-tf-M15").click(); // another timeframe: same drawing, same instants and prices
  await expect(page.locator("[data-kind='trend']")).toHaveCount(1);
  await page.reload();
  await expect(page.locator("[data-kind='trend']")).toHaveCount(1);
  const [after] = await stored(page, REPLAY_KEY);
  expect(after.a).toEqual(saved.a);
  expect(after.b).toEqual(saved.b);
});

test("the drawing is anchored to real instants: changing the display zone moves nothing in storage", async ({ page }) => {
  await twoClicks(page, "rect", [0.3, 0.4], [0.6, 0.7]);
  const [before] = await stored(page, REPLAY_KEY);
  await page.getByLabel("Múi giờ hiển thị").selectOption("UTC");
  await expect(page.locator("[data-kind='rect']")).toHaveCount(1);
  const [after] = await stored(page, REPLAY_KEY);
  expect(after.a).toEqual(before.a);
  expect(after.b).toEqual(before.b);
});

test("a vertical line is one click; a zone shows its price range; Fibonacci draws all seven levels", async ({ page }) => {
  const b = await box(page);
  await page.getByTestId("draw-menu").click();
  await page.getByTestId("tool-vline").click();
  await page.mouse.click(b.x + b.width * 0.5, b.y + b.height * 0.5);
  await expect(page.locator("[data-kind='vline']")).toHaveCount(1);
  await twoClicks(page, "rect", [0.2, 0.3], [0.4, 0.5]);
  await expect(page.locator("[data-kind='rect']")).toContainText(/\d{4}\.\d{2} – \d{4}\.\d{2}/);
  await twoClicks(page, "fib", [0.5, 0.7], [0.8, 0.3]);
  const fib = page.locator("[data-kind='fib']");
  await expect(fib).toContainText("0.618");
  await expect(fib).toContainText("0.236");
  expect((await fib.locator("text").allTextContents()).filter((t) => /^\d(\.\d+)? · /.test(t))).toHaveLength(7);
});

test("the risk-reward tool is labelled a manual analysis tool, never a signal, and shows risk, reward and R:R", async ({ page }) => {
  await twoClicks(page, "rr", [0.4, 0.5], [0.6, 0.65]);
  const rr = page.locator("[data-kind='rr']");
  await expect(rr.getByTestId("rr-disclaimer")).toHaveText("PHÂN TÍCH THỦ CÔNG — KHÔNG PHẢI TÍN HIỆU");
  await expect(rr).toContainText("ENTRY");
  await expect(rr).toContainText("SL");
  await expect(rr).toContainText("R:R 1:2");
  const [saved] = await stored(page, REPLAY_KEY);
  expect(saved.kind).toBe("rr");
  expect(saved.b.p).toBeLessThan(saved.a.p); // the stop below the entry: a long idea
  // the tool never reaches the desk: no order, no ticket, the decision card is unchanged
  await expect(page.getByTestId("take-paper")).toHaveCount(0);
  await expect(page.getByTestId("decision-card")).not.toContainText("MUA NGAY");
});

test("the object manager lists, renames, locks, deletes and clears; a locked drawing cannot be deleted by accident", async ({ page }) => {
  await twoClicks(page, "trend", [0.2, 0.6], [0.4, 0.4]);
  await twoClicks(page, "ray", [0.5, 0.6], [0.7, 0.5]);
  await page.getByTestId("drawing-manager-btn").click();
  await expect(page.getByTestId("drawing-scope")).toContainText("REPLAY");
  const rows = page.locator("[data-testid^='manager-row-']");
  await expect(rows).toHaveCount(2);
  await rows.first().getByTestId("manager-label").fill("Kháng cự H1");
  expect((await stored(page, REPLAY_KEY))[0].label).toBe("Kháng cự H1");
  await rows.first().getByTestId("manager-lock").click();
  await expect(rows.first().getByTestId("manager-delete")).toBeDisabled();
  expect((await stored(page, REPLAY_KEY))[0].locked).toBe(true);
  await page.getByTestId("manager-clear").click();
  await page.getByTestId("manager-clear-confirm").click();
  await expect(rows).toHaveCount(1); // only the locked one stays
  await rows.first().getByTestId("manager-lock").click();
  await rows.first().getByTestId("manager-delete").click();
  await expect(rows).toHaveCount(0);
  expect(await stored(page, REPLAY_KEY)).toHaveLength(0);
});

test("dragging a handle edits the anchor, Delete removes the selection, Esc cancels a half-drawn line", async ({ page }) => {
  await twoClicks(page, "trend", [0.3, 0.6], [0.6, 0.4]);
  const before = (await stored(page, REPLAY_KEY))[0];
  const handle = page.getByTestId("drawing-handle-b");
  await expect(handle).toBeVisible(); // a new drawing is selected
  const hb = (await handle.boundingBox())!;
  await page.mouse.move(hb.x + hb.width / 2, hb.y + hb.height / 2);
  await page.mouse.down();
  await page.mouse.move(hb.x + hb.width / 2 + 60, hb.y + hb.height / 2 + 40, { steps: 6 });
  await page.mouse.up();
  const moved = (await stored(page, REPLAY_KEY))[0];
  expect(moved.b.p).not.toBe(before.b.p);
  expect(moved.b.t).toBeGreaterThan(before.b.t);
  expect(moved.a).toEqual(before.a); // the other anchor did not move
  await page.keyboard.press("Delete");
  await expect(page.locator("[data-kind='trend']")).toHaveCount(0);

  const b = await box(page);
  await page.getByTestId("draw-menu").click();
  await page.getByTestId("tool-ray").click();
  await page.mouse.click(b.x + b.width * 0.4, b.y + b.height * 0.5);
  await page.mouse.move(b.x + b.width * 0.5, b.y + b.height * 0.4, { steps: 3 });
  await expect(page.getByTestId("drawing-draft")).toHaveCount(1);
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("drawing-draft")).toHaveCount(0);
  expect(await stored(page, REPLAY_KEY)).toHaveLength(0);
});

test("a LIVE page and a REPLAY page keep separate drawings", async ({ page }) => {
  await page.evaluate(([live, replay]) => {
    window.localStorage.setItem(live, JSON.stringify([{ id: "live1", kind: "vline", a: { t: 1_700_000_000, p: 4000 }, b: { t: 1_700_000_000, p: 4000 }, label: "LIVE ONLY", color: "#0ea5e9", locked: false, createdAt: 1 }]));
    return replay;
  }, [LIVE_KEY, REPLAY_KEY]);
  await page.reload();
  await page.getByTestId("drawing-manager-btn").click();
  await expect(page.getByTestId("drawing-manager")).not.toContainText("LIVE ONLY"); // this page is REPLAY
});

test("a corrupt or hand-edited drawings value is ignored, never crashes the chart", async ({ page }) => {
  await page.waitForFunction((k) => window.localStorage.getItem(k) !== null, REPLAY_KEY); // the page has loaded its scope and saved
  await page.evaluate((k) => window.localStorage.setItem(k, JSON.stringify([{ id: 1 }, { id: "x", kind: "nope" }, "junk", { id: "ok", kind: "trend", a: { t: 1_700_000_000, p: 4000 }, b: { t: 1_700_003_600, p: 4010 }, label: "ok", color: "red", locked: false, createdAt: 1 }])), REPLAY_KEY);
  await page.reload();
  await expect(page.getByTestId("trade-chart")).toHaveAttribute("data-bars", /\d+/);
  await expect(page.getByTestId("drawing-manager-btn")).toContainText("(1)");
});

test("maximizing and restoring the chart keeps the same bars in view: candles are not squeezed or left stranded", async ({ page }) => {
  const chart = page.getByTestId("trade-chart");
  const range = async () => ((await chart.getAttribute("data-range")) ?? "0:0").split(":").map(Number);
  await page.getByTestId("chart-fit").click();
  await page.waitForTimeout(300);
  const [from0, to0] = await range();
  await page.getByTestId("chart-fullscreen").click();
  await page.waitForTimeout(700);
  const [from1, to1] = await range();
  expect(from1).toBeGreaterThanOrEqual(from0 - 1); // no empty stretch opened on the left
  expect(to1 - from1).toBeLessThanOrEqual(to0 - from0 + 2); // the same bars, now wider (not more, squeezed)
  await page.getByTestId("chart-fullscreen").click();
  await page.waitForTimeout(700);
  const [from2, to2] = await range();
  expect(Math.abs(from2 - from0)).toBeLessThan(2);
  expect(Math.abs(to2 - to0)).toBeLessThan(2);
});

test("previous week high/low and session high/low are drawn from H1 bars when switched on", async ({ page }) => {
  const v = view("wait");
  // three weeks of hourly bars with weekend gaps: the previous week's extremes are known to the test
  const end = Math.floor(anchorMs(v) / 3_600_000) * 3_600_000;
  const hours: { time: string; open: number; high: number; low: number; close: number; tick_volume: number; spread: number; is_closed: boolean }[] = [];
  for (let i = 500; i >= 1; i--) {
    const t = end - i * 3_600_000;
    const day = new Date(t).getUTCDay();
    if (day === 6 || (day === 0 && new Date(t).getUTCHours() < 22) || (day === 5 && new Date(t).getUTCHours() >= 22)) continue; // weekend gap
    const mid = 4200 + Math.sin(i / 9) * 20;
    hours.push({ time: new Date(t).toISOString(), open: mid, high: mid + 3, low: mid - 3, close: mid, tick_volume: 10, spread: 20, is_closed: true });
  }
  await page.route("**/md/XAUUSD/bars**", (route) => {
    const tf = new URL(route.request().url()).searchParams.get("timeframe");
    return tf === "H1" && new URL(route.request().url()).searchParams.get("limit") === "500"
      ? route.fulfill({ json: { symbol: "XAUUSD", timeframe: "H1", source: "test", volume_type: "TICK_VOLUME", closed_only: false, bars: hours } })
      : route.fallback();
  });
  await page.goto("/trade");
  await page.getByTestId("overlay-menu").click();
  await page.getByTestId("toggle-keyLevels").check();
  const legend = page.getByTestId("chart-legend");
  await expect(legend).toContainText("PWH");
  await expect(legend).toContainText("PWL");
  await expect(legend).toContainText("ÂU H");
  await expect(legend).toContainText("MỸ L");
});

test("an existing drawing never steals the click of a new one: a point can be placed right on a Fibonacci line", async ({ page }) => {
  await twoClicks(page, "fib", [0.4, 0.7], [0.7, 0.3]);
  const b = await box(page);
  // the y of the 0.5 line, taken from the DOM
  const y = await page.locator("[data-kind='fib'] g line").nth(6).evaluate((el) => (el as unknown as SVGLineElement).y1.baseVal.value);
  await page.getByTestId("draw-menu").click();
  await page.getByTestId("tool-rr").click();
  await page.mouse.click(b.x + b.width * 0.85, b.y + y);
  await page.mouse.move(b.x + b.width * 0.9, b.y + y + 40, { steps: 3 });
  await page.mouse.click(b.x + b.width * 0.9, b.y + y + 40);
  await expect(page.locator("[data-kind='rr']")).toHaveCount(1);
});

test("upcoming news are vertical lines: red dashed for high with a blocked-window band, amber for medium; switchable", async ({ page }) => {
  const v = view("wait");
  const at = (min: number) => new Date(Math.floor(anchorMs(v) / 300_000) * 300_000 + min * 60_000).toISOString();
  v.news = {
    state: "CLEAR", detail: "no high-impact event inside the news window", warning: false, text: "CLEAR",
    coverage: { from: "2026-10-04T04:00:00Z", to: "2026-10-18T04:00:00Z" }, last_updated_at: at(-60), source: "forexfactory-weekly", blocked_by: null, last_update: null,
    next_events: [
      { time: at(15), title: "CPI m/m", currency: "USD", impact: "high", minutes_to: 15 },
      { time: at(25), title: "Unemployment Claims and a very long extra name", currency: "USD", impact: "medium", minutes_to: 25 },
    ],
  };
  await mock(page, v);
  await page.goto("/trade");
  const markers = page.getByTestId("news-marker");
  await expect(markers).toHaveCount(2);
  await expect(markers.first()).toHaveAttribute("data-impact", "high");
  await expect(markers.first()).toContainText("CPI m/m");
  await expect(markers.nth(1)).toHaveAttribute("data-impact", "medium");
  await expect(markers.nth(1)).toContainText("…"); // a long title is cut, never overflows
  await expect(page.getByTestId("news-window")).toHaveCount(1); // only the high-impact event blocks a window
  await page.getByTestId("overlay-menu").click();
  await page.getByTestId("toggle-news").uncheck();
  await expect(page.getByTestId("news-marker")).toHaveCount(0);
});
