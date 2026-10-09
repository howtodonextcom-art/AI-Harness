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

interface World {
  collector: "RUNNING" | "STOPPED";
  market: "OPEN" | "CLOSED";
  terminal: "CONNECTED" | "DISCONNECTED" | "UNKNOWN";
  empty?: boolean;
  warnings?: string[];
}

const FRESH = { M1: "FRESH", M5: "FRESH", M15: "FRESH", M30: "FRESH", H1: "FRESH", H4: "FRESH" };

function quoteFor(w: World) {
  const running = w.collector === "RUNNING";
  const closed = w.market === "CLOSED";
  const state = closed ? "MARKET_CLOSED" : running ? "FRESH" : "STALE";
  return {
    available: true, stale: !closed && !running, state, market_status: w.market,
    reason: closed ? "market is closed: the last tick is expected to be old" : running ? "last tick is recent" : "the collector stopped publishing 1200s ago",
    bid: 2100.1, ask: 2100.3, mid: 2100.2, spread_price: 0.2, spread_points: 20,
    timestamp: iso(running ? 0 : 20), last_tick_time: iso(running ? 0 : 20), age_seconds: running ? 0.5 : 1200,
  };
}

async function mock(page: Page, world: World) {
  await page.route("**/md/XAUUSD/bars**", (route) => {
    const forming = new URL(route.request().url()).searchParams.get("include_forming") === "true";
    return route.fulfill({
      json: { symbol: "XAUUSD", timeframe: "M15", source: "FTMO MT5", volume_type: "TICK_VOLUME", closed_only: !forming, bars: world.empty ? [] : bars(60, forming) },
    });
  });
  await page.route("**/md/XAUUSD/quote", (route) => route.fulfill({ json: quoteFor(world) }));
  await page.route("**/md/status", (route) => {
    const running = world.collector === "RUNNING";
    return route.fulfill({
      json: {
        health: running ? "GOOD" : "STALE", market_status: world.market, collector_running: running,
        source: "FTMO MT5", volume_type: "TICK_VOLUME", freshness: running ? FRESH : { ...FRESH, M1: "STALE" },
        warnings: world.warnings ?? [],
        components: {
          terminal: running ? world.terminal : "UNKNOWN", collector: world.collector, api: "CONNECTED",
          market: world.market, quote: quoteFor(world).state, bars: running ? (world.market === "OPEN" ? "FRESH" : "MARKET_CLOSED") : "STALE",
        },
        recovery_action: running
          ? world.terminal === "DISCONNECTED" ? "Open the FTMO MT5 terminal and log in; the collector reconnects by itself." : null
          : "Run scripts/start_market_stack.ps1 (status_market_stack.ps1 shows why).",
      },
    });
  });
  await page.route("**/md/XAUUSD/matrix", (route) =>
    route.fulfill({
      json: {
        symbol: "XAUUSD", health: "GOOD",
        timeframes: ["M1", "M5", "M15", "M30", "H1", "H4"].map((t) => ({ timeframe: t, last_closed_bar_open: iso(30), last_close_time: iso(15), age_seconds: 900 })),
      },
    }),
  );
  await page.route("**/md/XAUUSD/quality", (route) =>
    route.fulfill({
      json: {
        history_depth: ["M1", "M5", "M15", "M30", "H1", "H4"].map((t) => ({ timeframe: t, earliest: "2025-05-14T01:10:00+00:00", latest: iso(15), rows: 99000, freshness: "FRESH" })),
        recent_events: [{ at: iso(5), kind: "GAP", timeframe: "M5" }],
        tick_store: { enabled: true, covered_until: iso(0), lag_seconds: 4, coverage_windows: 1 },
        disk: { level: "GOOD", free_gb: 76.8, estimated_days_remaining: 9000 },
        warnings: [], collector_health: "GOOD", ledger_integrity: { ok: true },
      },
    }),
  );
}

const HEALTHY: World = { collector: "RUNNING", market: "OPEN", terminal: "CONNECTED" };

test("market page shows component status, quote, chart, matrix and the tick-volume note", async ({ page }) => {
  await mock(page, { ...HEALTHY });
  await page.goto("/market");
  await expect(page.getByRole("heading", { name: /XAUUSD · FTMO MT5/ })).toBeVisible();
  await expect(page.getByTestId("quote-Bid")).toHaveText("2100.10");
  await expect(page.getByTestId("quote-Spread (điểm)")).toHaveText("20");
  await expect(page.getByTestId("market-chart")).toBeVisible();
  await expect(page.getByTestId("source-note")).toContainText("tick volume");
  await expect(page.getByTestId("matrix").locator("tbody tr")).toHaveCount(6);
  for (const id of ["terminal", "collector", "api", "market", "quote", "bars"]) {
    await expect(page.getByTestId(`pill-${id}`)).toBeVisible();
  }
  await expect(page.getByTestId("pill-collector")).toContainText("ĐANG CHẠY");
  await expect(page.getByTestId("pill-quote")).toContainText("MỚI");
  await expect(page.getByTestId("recovery")).toHaveCount(0);
});

test("owner screenshot scenario: stopped collector is STALE with the recovery action, then recovers without reload", async ({ page }) => {
  const world: World = { collector: "STOPPED", market: "OPEN", terminal: "UNKNOWN" };
  await mock(page, world);
  await page.goto("/market");
  await expect(page.getByTestId("pill-collector")).toContainText("ĐÃ DỪNG");
  await expect(page.getByTestId("pill-quote")).toContainText("CŨ");
  await expect(page.getByTestId("recovery")).toContainText("start_market_stack.ps1");
  await expect(page.getByTestId("quote-detail")).toContainText("collector stopped");
  // the collector is started: the SAME open page must turn fresh by itself (polling, no reload)
  world.collector = "RUNNING";
  world.terminal = "CONNECTED";
  await expect(page.getByTestId("pill-collector")).toContainText("ĐANG CHẠY", { timeout: 10_000 });
  await expect(page.getByTestId("pill-quote")).toContainText("MỚI");
  await expect(page.getByTestId("quote-Tuổi tick")).toHaveText("1s");
  await expect(page.getByTestId("recovery")).toHaveCount(0);
});

test("market closed is shown as closed, not as broken data", async ({ page }) => {
  await mock(page, { collector: "RUNNING", market: "CLOSED", terminal: "CONNECTED" });
  await page.goto("/market");
  await expect(page.getByTestId("pill-market")).toContainText("ĐÓNG");
  await expect(page.getByTestId("pill-quote")).toContainText("THỊ TRƯỜNG ĐÓNG");
  await expect(page.getByTestId("quote-detail")).toContainText("expected to be old");
  await expect(page.getByTestId("pill-collector")).toContainText("ĐANG CHẠY");
});

test("terminal disconnected shows its own recovery instruction", async ({ page }) => {
  await mock(page, { collector: "RUNNING", market: "OPEN", terminal: "DISCONNECTED" });
  await page.goto("/market");
  await expect(page.getByTestId("pill-terminal")).toContainText("MẤT KẾT NỐI");
  await expect(page.getByTestId("recovery")).toContainText("log in");
});

test("no stored bars is explained", async ({ page }) => {
  await mock(page, { ...HEALTHY, empty: true });
  await page.goto("/market");
  await expect(page.getByTestId("no-bars")).toContainText("backfill_mt5.py");
});

test("API outage is a visible error with the start command", async ({ page }) => {
  await page.route("**/md/**", (route) => route.abort());
  await page.goto("/market");
  await expect(page.getByRole("alert").filter({ hasText: "Không đọc được API" })).toContainText("start_market_stack.ps1");
  await expect(page.getByTestId("pill-api")).toContainText("MẤT KẾT NỐI");
});

test("timeframe buttons switch the requested timeframe", async ({ page }) => {
  await mock(page, { ...HEALTHY });
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

test("display zone selector shifts shown times and is remembered", async ({ page }) => {
  await mock(page, { ...HEALTHY });
  await page.goto("/market");
  const first = page.getByTestId("matrix").locator("tbody tr").first().locator("td").nth(1);
  await expect(first).toHaveText(/\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}/);
  const utc = await first.innerText();
  await page.getByTestId("zone-select").selectOption("BROKER");
  const broker = await first.innerText();
  expect(broker).not.toEqual(utc);
  await expect(page.getByTestId("source-note")).toContainText("Giờ broker");
  await page.reload();
  await expect(page.getByTestId("zone-select")).toHaveValue("BROKER");
});

test("data quality panel expands with depth, tick store, disk and events", async ({ page }) => {
  await mock(page, { ...HEALTHY });
  await page.goto("/market");
  await page.getByText("Chất lượng dữ liệu").click();
  await expect(page.getByTestId("depth").locator("tbody tr")).toHaveCount(6);
  await expect(page.getByTestId("tick-store")).toContainText("phủ đến");
  await expect(page.getByTestId("disk")).toContainText("GOOD");
  await expect(page.getByTestId("integrity")).toContainText("sạch");
});

test("consistency warnings are listed", async ({ page }) => {
  await mock(page, { ...HEALTHY, warnings: ["M1: quote is older than the forming bar's open"] });
  await page.goto("/market");
  await expect(page.getByTestId("warnings")).toContainText("quote is older");
});

test("mobile width has no horizontal page scroll", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 800 });
  await mock(page, { ...HEALTHY });
  await page.goto("/market");
  await expect(page.getByTestId("market-chart")).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
