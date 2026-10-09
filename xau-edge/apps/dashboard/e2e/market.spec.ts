import { expect, test, type Page } from "@playwright/test";

/** Market page e2e against the production build; the /md/* API is mocked in the browser. */

const NOW = Date.now();
const iso = (offsetMinutes: number) => new Date(NOW - offsetMinutes * 60_000).toISOString();

function bars(count: number, forming: boolean) {
  const out = [];
  for (let i = count; i >= 1; i--) {
    const base = 2000 + (count - i) * 0.5;
    out.push({ time: iso(i * 15), open: base, high: base + 2, low: base - 2, close: base + 1, tick_volume: 100 + i, spread: 20, is_closed: true });
  }
  if (forming) out.push({ time: iso(0), open: 2100, high: 2102, low: 2098, close: 2101, tick_volume: 30, spread: 22, is_closed: false });
  return out;
}

async function mock(page: Page, opts: { stale?: boolean; empty?: boolean; running?: boolean } = {}) {
  await page.route("**/md/XAUUSD/bars**", (route) => {
    const forming = new URL(route.request().url()).searchParams.get("include_forming") === "true";
    return route.fulfill({
      json: { symbol: "XAUUSD", timeframe: "M15", source: "FTMO MT5", volume_type: "TICK_VOLUME", closed_only: !forming, bars: opts.empty ? [] : bars(60, forming) },
    });
  });
  await page.route("**/md/XAUUSD/quote", (route) =>
    route.fulfill({
      json: {
        available: true, stale: opts.stale ?? false, market_status: "OPEN", bid: 2100.1, ask: 2100.3,
        mid: 2100.2, spread_price: 0.2, spread_points: 20, timestamp: iso(0), age_seconds: opts.stale ? 400 : 0.5,
      },
    }),
  );
  await page.route("**/md/status", (route) =>
    route.fulfill({
      json: { health: opts.stale ? "STALE" : "GOOD", market_status: "OPEN", collector_running: opts.running ?? true, source: "FTMO MT5", volume_type: "TICK_VOLUME" },
    }),
  );
  await page.route("**/md/XAUUSD/matrix", (route) =>
    route.fulfill({
      json: {
        symbol: "XAUUSD", health: "GOOD",
        timeframes: ["M1", "M5", "M15", "M30", "H1", "H4"].map((t) => ({ timeframe: t, last_closed_bar_open: iso(30), last_close_time: iso(15), age_seconds: 900 })),
      },
    }),
  );
}

test("market page shows quote, chart, matrix and the tick-volume note", async ({ page }) => {
  await mock(page);
  await page.goto("/market");
  await expect(page.getByRole("heading", { name: /XAUUSD · FTMO MT5/ })).toBeVisible();
  await expect(page.getByTestId("quote-Bid")).toHaveText("2100.10");
  await expect(page.getByTestId("quote-Spread (điểm)")).toHaveText("20");
  await expect(page.getByTestId("market-chart")).toBeVisible();
  await expect(page.getByTestId("source-note")).toContainText("tick volume");
  await expect(page.getByTestId("matrix").locator("tbody tr")).toHaveCount(6);
  await expect(page.getByText("Dữ liệu: TỐT")).toBeVisible();
});

test("a stale quote is flagged, never shown as current", async ({ page }) => {
  await mock(page, { stale: true });
  await page.goto("/market");
  await expect(page.getByText("BÁO GIÁ CŨ")).toBeVisible();
  await expect(page.getByText("Dữ liệu: CŨ (STALE)")).toBeVisible();
});

test("no stored bars and a stopped collector are explained", async ({ page }) => {
  await mock(page, { empty: true, running: false });
  await page.goto("/market");
  await expect(page.getByTestId("no-bars")).toContainText("backfill_mt5.py");
  await expect(page.getByRole("status")).toContainText("Collector không chạy");
});

test("timeframe buttons switch the requested timeframe", async ({ page }) => {
  await mock(page);
  const requested: string[] = [];
  page.on("request", (r) => {
    const m = /timeframe=(\w+)/.exec(r.url());
    if (m) requested.push(m[1]);
  });
  await page.goto("/market");
  await page.getByRole("button", { name: "H4", exact: true }).click();
  await expect.poll(() => requested.includes("H4")).toBe(true);
  await expect(page.getByRole("button", { name: "H4", exact: true })).toHaveAttribute("aria-pressed", "true");
});
