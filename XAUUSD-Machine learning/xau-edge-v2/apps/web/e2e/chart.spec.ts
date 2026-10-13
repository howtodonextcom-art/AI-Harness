import { type Page, type Route, expect, test } from "@playwright/test";

const STEP: Record<string, number> = { M1: 60, M5: 300, M15: 900, M30: 1800, H1: 3600, H4: 14400 };
const END = Date.parse("2026-10-12T18:00:00Z") / 1000;

interface Mock {
  requests: { timeframe: string; limit: number; before: string | null }[];
  served: number[][]; // times served per request, in order
}

/** A deterministic store of `total` bars per timeframe, served with the real endpoint's semantics. */
async function mockBars(page: Page, total: number, delayMs: Record<string, number> = {}): Promise<Mock> {
  const mock: Mock = { requests: [], served: [] };
  await page.route("**/api/v2/market/bars?*", async (route: Route) => {
    const url = new URL(route.request().url());
    const timeframe = url.searchParams.get("timeframe") ?? "M15";
    const limit = Number(url.searchParams.get("limit"));
    const before = url.searchParams.get("before");
    mock.requests.push({ timeframe, limit, before });
    const step = STEP[timeframe] as number;
    const times = Array.from({ length: total }, (_, i) => END - (total - 1 - i) * step);
    const cutoff = before ? Date.parse(before) / 1000 : Number.POSITIVE_INFINITY;
    const pool = times.filter((t) => t < cutoff);
    const served = pool.slice(-limit);
    mock.served.push(served);
    const delay = delayMs[timeframe] ?? 0;
    if (delay) await new Promise((r) => setTimeout(r, delay));
    const first = served[0];
    await route.fulfill({
      json: {
        symbol: "XAUUSD",
        timeframe,
        bars: served.map((t, i) => ({
          time: new Date(t * 1000).toISOString(),
          open: 4000 + (i % 7),
          high: 4010 + (i % 7),
          low: 3990 + (i % 7),
          close: 4003 + (i % 5),
          tick_volume: 10 + (i % 9),
          spread: 30,
          is_closed: true,
        })),
        oldest_available: new Date((times[0] as number) * 1000).toISOString(),
        newest_available: new Date(END * 1000).toISOString(),
        has_more_before: first !== undefined && first > (times[0] as number),
        has_more_after: false,
        data_version: "mock",
      },
    });
  });
  return mock;
}

const meta = (page: Page) => page.getByTestId("chart-meta");

async function dragRight(page: Page, times: number) {
  const box = await page.getByTestId("chart-host").boundingBox();
  if (!box) throw new Error("no chart box");
  const y = box.y + box.height / 2;
  for (let i = 0; i < times; i++) {
    await page.mouse.move(box.x + 60, y);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width - 80, y, { steps: 8 });
    await page.mouse.up();
  }
}

test("the first page is the newest 500 bars; the chart says how many and that there is more", async ({ page }) => {
  const mock = await mockBars(page, 3000);
  await page.goto("/");
  await expect(meta(page)).toHaveAttribute("data-count", "500");
  await expect(meta(page)).toHaveAttribute("data-has-more", "true");
  await expect(meta(page)).toContainText("kéo sang trái");
  expect(mock.requests[0]).toEqual({ timeframe: "M15", limit: 500, before: null });
  await expect(page.getByTestId("chart-host").locator("canvas").first()).toBeVisible();
});

test("scrolling left pages back with before=, no gaps, no duplicates, down to the start of the store", async ({ page }) => {
  const mock = await mockBars(page, 2300);
  await page.goto("/");
  await expect(meta(page)).toHaveAttribute("data-count", "500");
  await expect
    .poll(
      async () => {
        await dragRight(page, 3);
        return meta(page).getAttribute("data-has-more");
      },
      { timeout: 25000, intervals: [300] },
    )
    .toBe("false");
  await expect(meta(page)).toHaveAttribute("data-count", "2300"); // every bar exactly once
  await expect(meta(page)).toContainText("đã tới nến cũ nhất");
  // every older page asked for the bars strictly before the oldest one already loaded
  const older = mock.requests.slice(1);
  expect(older.length).toBeGreaterThanOrEqual(2);
  const all = mock.served.flat();
  expect(new Set(all).size).toBe(all.length); // the server never had to repeat a bar
  let oldestSoFar = (mock.served[0] as number[])[0] as number;
  older.forEach((r, i) => {
    expect(r.before).toBe(new Date(oldestSoFar * 1000).toISOString());
    expect(r.limit).toBe(1000);
    oldestSoFar = (mock.served[i + 1] as number[])[0] ?? oldestSoFar;
  });
});

test("switching timeframe reloads that timeframe; a slow answer for the old one never wins", async ({ page }) => {
  const mock = await mockBars(page, 1200, { M1: 1200 }); // M1 answers late
  await page.goto("/");
  await expect(meta(page)).toHaveAttribute("data-tf", "M15");
  await page.getByTestId("tf-M1").click();
  await page.getByTestId("tf-H1").click(); // the user moves on before M1 arrives
  await expect(meta(page)).toHaveAttribute("data-tf", "H1");
  await expect(meta(page)).toHaveAttribute("data-count", "500");
  await page.waitForTimeout(1600); // the late M1 response has now arrived
  await expect(meta(page)).toHaveAttribute("data-tf", "H1");
  await expect(meta(page)).toHaveAttribute("data-count", "500");
  expect(mock.requests.map((r) => r.timeframe)).toEqual(expect.arrayContaining(["M15", "M1", "H1"]));
  await expect(page.getByTestId("tf-H1")).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("tf-M1")).toHaveAttribute("aria-pressed", "false");
});

test("every timeframe loads", async ({ page }) => {
  await mockBars(page, 800);
  await page.goto("/");
  for (const tf of ["M1", "M5", "M30", "H4", "H1", "M15"]) {
    await page.getByTestId(`tf-${tf}`).click();
    await expect(meta(page)).toHaveAttribute("data-tf", tf);
    await expect(meta(page)).toHaveAttribute("data-count", "500");
  }
});

test("a failed history request is shown, never silent", async ({ page }) => {
  await page.route("**/api/v2/market/bars?*", (route) => route.abort());
  await page.goto("/");
  await expect(page.getByTestId("chart-error")).toBeVisible();
  await expect(page.getByTestId("chart-error")).toContainText("Không tải được nến");
});

test("a new stored bar (data_version change over the socket) merges only the newest bars", async ({ page }) => {
  const mock = await mockBars(page, 1200);
  let version = 0;
  await page.routeWebSocket("**/ws", (route) => {
    const send = (type: string, seq: number) =>
      route.send(
        JSON.stringify({
          type,
          seq,
          ts: new Date().toISOString(),
          schema_version: "2.0.0-g5",
          data_version: `v${version}`,
        }),
      );
    send("hello", 0);
    setTimeout(() => {
      version = 1;
      send("heartbeat", 1);
    }, 700);
  });
  await page.goto("/");
  await expect(meta(page)).toHaveAttribute("data-count", "500");
  await expect.poll(() => mock.requests.filter((r) => r.limit === 10).length).toBe(1); // newest 10 only
  await expect(meta(page)).toHaveAttribute("data-count", "500"); // merged: no duplicates
});

test("a live event puts the quote in the chart header", async ({ page }) => {
  await mockBars(page, 600);
  await page.routeWebSocket("**/ws", (route) => {
    const base = { ts: new Date().toISOString(), schema_version: "2.0.0-g5", data_version: "t" };
    route.send(JSON.stringify({ ...base, type: "hello", seq: 0 }));
    setTimeout(() => {
      route.send(
        JSON.stringify({
          ...base,
          type: "live",
          seq: 1,
          quote: { available: true, state: "FRESH", market_status: "OPEN", reason: "ok", bid: 4321.12, ask: 4321.56 },
          forming: [],
        }),
      );
    }, 500);
  });
  await page.goto("/");
  await expect(page.getByTestId("chart-quote")).toContainText("bid 4321.12 / ask 4321.56");
});
