import { expect, test } from "@playwright/test";
import realTrade from "./fixtures/real_paper_trade.json";
import { EMPTY_MARKERS, LAST_OPEN, STEP, TFS, barOpen, iso, legend, mock, view } from "./fixtures/trade";

/** Trade + Journal pages e2e against the production build; /trade/* and /md/* are mocked in the browser. */

test("WAIT: chart first, blocked-by header, Why WAIT stages, waiting-for and the six timeframes", async ({ page }) => {
  await mock(page, view({}, "WAIT"));
  await page.goto("/trade");
  await expect(page.getByTestId("trade-chart")).toBeVisible();
  await expect(page.getByTestId("decision")).toHaveText("WAIT");
  await expect(page.getByTestId("blocked-by")).toContainText("NO_SETUP");
  await expect(page.getByTestId("stage-M15-setup")).toContainText("FAIL");
  await expect(page.getByTestId("stage-Market-data")).toContainText("PASS");
  await expect(page.getByTestId("stage-M5-trigger")).toContainText("—");
  await expect(page.getByTestId("waiting-for")).toContainText("M15 pullback");
  await expect(page.getByTestId("waiting-for")).toContainText("không phải dự báo");
  await expect(page.getByTestId("explanation")).toContainText("no M15 pullback");
  await expect(page.getByTestId("evidence-pill")).toContainText("CHƯA KIỂM CHỨNG");
  await expect(page.getByTestId("news-warning")).toContainText("NEWS NOT VERIFIED");
  await expect(page.getByTestId("paper-only")).toBeVisible();
  await expect(page.getByTestId("plan-card")).toHaveCount(0);
  await expect(legend(page).locator("li")).toHaveCount(0); // no plan lines for a WAIT
  for (const t of TFS) await expect(page.getByTestId(`tf-${t}`)).toBeVisible();
  await expect(page.getByTestId("tf-M30")).toContainText("CONTEXT");
  await expect(page.getByTestId("matrix-M15")).toContainText("SETUP");
  await expect(page.getByTestId("volume-line")).toContainText("không phải volume sàn");
  await expect(page.getByTestId("volume-line")).toContainText("55%");
  await page.getByText("Chẩn đoán nâng cao").click();
  await expect(page.getByTestId("demo-lock")).toContainText("DEMO_DRY_RUN");
  await expect(page.getByTestId("volume-note")).toContainText("not exchange volume");
  await expect(page.getByTestId("telemetry-card")).toContainText("TRIGGERED:1");
});

test("BUY: plan lines carry the server values and a paper order needs a confirmation", async ({ page }) => {
  await mock(page, view({}, "BUY"));
  let posted: unknown = null;
  await page.route("**/api/trade/paper/open", (route) => {
    posted = route.request().postDataJSON();
    return route.fulfill({ json: { trade_id: "P-1", side: "BUY", lots: 0.5, fill_price: 2100.5, status: "OPEN" } });
  });
  await page.goto("/trade");
  await expect(page.getByTestId("decision")).toHaveText("BUY");
  await expect(page.getByTestId("line-ENTRY")).toHaveText("ENTRY 2100.50");
  await expect(page.getByTestId("line-SL")).toHaveText("SL 2095.50");
  await expect(page.getByTestId("line-TP1")).toHaveText("TP1 2110.50");
  await expect(page.getByTestId("line-TP2")).toHaveText("TP2 2115.50");
  await expect(page.getByTestId("plan-entry")).toHaveText("2100.50");
  await expect(page.getByTestId("plan-lots")).toHaveText("0.50");
  await expect(page.getByTestId("setup-phase")).toContainText("TRIGGERED");
  await page.getByTestId("risk-0.5").click();
  await expect(page.getByTestId("plan-lots")).toHaveText("1.00");
  await page.getByTestId("risk-0.25").click();
  await page.getByTestId("take-paper").click();
  expect(posted).toBeNull(); // nothing is sent before the confirmation
  await page.getByTestId("confirm-paper").click();
  await expect(page.getByTestId("action-message")).toContainText("Đã mở lệnh PAPER BUY");
  expect(posted).toEqual({ setup_id: "abcdef0123456789", risk_pct: 0.25 });
});

test("BUY/SELL markers come from server signals and snap to the bar that contains them", async ({ page }) => {
  const buyAt = new Date(LAST_OPEN - 10 * STEP + 2 * 60_000).toISOString(); // inside a bar
  const sellAt = new Date(LAST_OPEN - 4 * STEP).toISOString();
  const markers = {
    simulated: true,
    signals: [
      { at: buyAt, bar_time: buyAt, setup_id: "s1aaaaaaaa", side: "BUY", entry: 2100.5, sl: 2095.5, tp1: 2110.5, tp2: null, rr: 1.9, lots: 0.5, expires_at: null, strategy_version: "1.2.0", taken: true },
      { at: sellAt, bar_time: sellAt, setup_id: "s2bbbbbbbb", side: "SELL", entry: 2090, sl: 2095, tp1: 2080, tp2: null, rr: 1.8, lots: 0.4, expires_at: null, strategy_version: "1.2.0", taken: false },
    ],
    paper_trades: [],
  };
  await mock(page, view({}, "WAIT"), markers);
  await page.goto("/trade");
  const list = page.getByTestId("chart-markers").locator("li");
  await expect(list).toHaveCount(2);
  await expect(list.nth(0)).toHaveAttribute("data-kind", "BUY");
  await expect(list.nth(0)).toHaveAttribute("data-bar-time", barOpen(10)); // snapped to the containing bar
  await expect(list.nth(0)).toContainText("BUY signal @ 2100.50");
  await expect(list.nth(0)).toContainText("taken (paper)");
  await expect(list.nth(1)).toHaveAttribute("data-kind", "SELL");
  await expect(list.nth(1)).toHaveAttribute("data-bar-time", barOpen(4));
  await page.getByTestId("toggle-signals").uncheck();
  await expect(list).toHaveCount(0);
});

test("EXIT markers show reason, P&L, R and duration; history toggle controls older trades", async ({ page }) => {
  const trade = (id: string, back: number, reason: string, pnl: number, r: number) => ({
    trade_id: id, side: "BUY", status: "CLOSED", entry_time: barOpen(back + 3), entry_price: 2100.5,
    exit_time: barOpen(back), exit_price: 2095.5, exit_reason: reason, net_pnl: pnl, r_multiple: r,
    duration_minutes: 15, sl: 2095.5, tp: 2110.5,
  });
  const markers = { simulated: true, signals: [], paper_trades: [trade("P-1", 30, "TAKE_PROFIT", 52, 2.1), trade("P-2", 10, "STOP_LOSS", -27.5, -1.1)] };
  await mock(page, view({}, "WAIT"), markers);
  await page.goto("/trade");
  const exits = page.getByTestId("chart-markers").locator('li[data-kind="EXIT"]');
  await expect(exits).toHaveCount(1); // only the latest closed trade by default
  await expect(exits.first()).toContainText("EXIT STOP_LOSS @ 2095.50");
  await expect(exits.first()).toContainText("P&L -27.50");
  await expect(exits.first()).toContainText("-1.10R");
  await expect(exits.first()).toContainText("15 min");
  await expect(exits.first()).toHaveAttribute("data-bar-time", barOpen(10));
  await page.getByTestId("toggle-history").check();
  await expect(exits).toHaveCount(2);
});

test("an open paper position draws entry, SL, TP and now, with live R and P&L", async ({ page }) => {
  const position = {
    trade_id: "P-7", setup_id: "x", status: "OPEN", side: "BUY", created_at: iso(-600), opened_at: iso(-600), closed_at: null,
    fill_price: 2100.5, sl: 2095.5, initial_sl: 2095.5, tp: 2110.5, lots: 0.5, risk_pct: 0.25, risk_amount: 25,
    unrealized_pnl: 12.5, unrealized_r: 0.5, current_price: 2103, duration_minutes: 10,
  };
  const v = view({}, "WAIT");
  (v.desk as { position: unknown }).position = position;
  await mock(page, v);
  await page.route("**/api/trade/paper/close", (route) => route.fulfill({ json: { ...position, status: "CLOSED", net_pnl: 12, r_multiple: 0.48 } }));
  await page.goto("/trade");
  await expect(page.getByTestId("line-PAPER-ENTRY")).toHaveText("PAPER ENTRY 2100.50");
  await expect(page.getByTestId("line-PAPER-SL")).toHaveText("PAPER SL 2095.50");
  await expect(page.getByTestId("line-PAPER-TP")).toHaveText("PAPER TP 2110.50");
  await expect(page.getByTestId("line-NOW")).toHaveText("NOW 2103.00");
  await expect(page.getByTestId("position-pnl")).toContainText("$12.50");
  await expect(page.getByTestId("position-r")).toHaveText("0.50");
  await page.getByTestId("toggle-paper").uncheck();
  await expect(page.getByTestId("line-PAPER-ENTRY")).toHaveCount(0);
  await page.getByTestId("toggle-paper").check();
  await page.getByTestId("close-paper").click();
  await expect(page.getByTestId("action-message")).toContainText("Đã đóng lệnh paper");
});

test("structure overlay is optional and uses the server levels", async ({ page }) => {
  await mock(page, view({}, "WAIT"));
  await page.goto("/trade");
  await expect(page.getByTestId("line-RES")).toHaveCount(0);
  await page.getByTestId("toggle-structure").check();
  await expect(page.getByTestId("line-RES")).toHaveText("RES 2120.00");
  await expect(page.getByTestId("line-PDH")).toHaveText("PDH 2125.00");
  await expect(page.getByTestId("line-PDL")).toHaveText("PDL 2080.00");
});

test("trade-plan overlay can be hidden and the volume panel toggle works", async ({ page }) => {
  await mock(page, view({}, "BUY"));
  await page.goto("/trade");
  await expect(page.getByTestId("line-ENTRY")).toBeVisible();
  await page.getByTestId("toggle-plan").uncheck();
  await expect(page.getByTestId("line-ENTRY")).toHaveCount(0);
  await page.getByTestId("toggle-volume").uncheck();
  await expect(page.getByTestId("toggle-volume")).not.toBeChecked();
});

test("clicking a timeframe in the matrix switches the chart to it", async ({ page }) => {
  const requested: string[] = [];
  await mock(page, view({}, "WAIT"), EMPTY_MARKERS, (tf) => requested.push(tf));
  await page.goto("/trade");
  await expect(page.getByTestId("chart-tf-M5")).toHaveAttribute("aria-pressed", "true");
  await page.getByTestId("matrix-H1").click();
  await expect(page.getByTestId("chart-tf-H1")).toHaveAttribute("aria-pressed", "true");
  await expect.poll(() => requested.includes("H1")).toBe(true);
  await page.getByTestId("matrix-M15").click();
  await expect.poll(() => requested.includes("M15")).toBe(true);
});

test("a BUY on stale data is shown as stale, draws no plan and cannot be taken", async ({ page }) => {
  await mock(page, view({ data_age_seconds: 900 }, "BUY"));
  await page.goto("/trade");
  await expect(page.getByTestId("decision")).toContainText("dữ liệu cũ");
  await expect(page.getByTestId("data-stale-banner")).toBeVisible();
  await expect(page.getByTestId("take-paper")).toBeDisabled();
  await expect(page.getByTestId("line-ENTRY")).toHaveCount(0); // the chart disables the stale plan
  await expect(page.getByTestId("chart-card")).toHaveClass(/opacity-60/);
});

test("a blocked desk disables the button and says why", async ({ page }) => {
  await mock(page, view({}, "BUY", ["COOLDOWN"]));
  await page.goto("/trade");
  await expect(page.getByTestId("blockers")).toContainText("nghỉ sau lệnh trước");
  await expect(page.getByTestId("take-paper")).toBeDisabled();
});

test("the API refusing a stale setup is shown, not hidden", async ({ page }) => {
  await mock(page, view({}, "BUY"));
  await page.route("**/api/trade/paper/open", (route) =>
    route.fulfill({ status: 409, json: { detail: { code: "DECISION_CHANGED", message: "the setup changed" } } }),
  );
  await page.goto("/trade");
  await page.getByTestId("take-paper").click();
  await page.getByTestId("confirm-paper").click();
  await expect(page.getByTestId("action-message")).toContainText("DECISION_CHANGED");
});

test("an unreachable API shows a stale banner and blocks entry", async ({ page }) => {
  await page.route("**/trade/decision", (route) => route.abort());
  await page.route("**/trade/markers**", (route) => route.abort());
  await page.route("**/md/XAUUSD/bars**", (route) => route.abort());
  await page.goto("/trade");
  await expect(page.getByTestId("stale-banner")).toBeVisible();
  await expect(page.getByTestId("take-paper")).toHaveCount(0);
});

test("journal lists paper trades with a detail snapshot and says it proves nothing", async ({ page }) => {
  await page.route("**/trade/journal**", (route) =>
    route.fulfill({
      json: {
        simulated: true, open: null,
        evidence: view().evidence,
        trades: [
          { trade_id: "P-1", setup_id: "s", status: "CLOSED", side: "BUY", created_at: iso(-3600), opened_at: iso(-3600), closed_at: iso(-3000), fill_price: 2100.5, sl: 2095.5, initial_sl: 2095.5, tp: 2110.5, lots: 0.5, risk_pct: 0.25, risk_amount: 25, exit_price: 2095.5, exit_reason: "STOP_LOSS", net_pnl: -27.5, r_multiple: -1.1, mfe_r: 0.2, mae_r: -1.0, market: { session: "LONDON" } },
        ],
      },
    }),
  );
  await page.goto("/journal");
  await expect(page.getByTestId("journal-row")).toHaveCount(1);
  await expect(page.getByTestId("journal-row")).toContainText("STOP_LOSS");
  await expect(page.getByTestId("stat-pnl")).toHaveText("-$27.50");
  await expect(page.getByTestId("journal-note")).toContainText("Chưa có bằng chứng");
  await page.getByRole("button", { name: "chi tiết" }).click();
  await expect(page.getByTestId("journal-detail")).toContainText("LONDON");
});

test("the home page opens the trading desk and the legacy page is marked deprecated", async ({ page }) => {
  await mock(page, view({}, "WAIT"));
  await page.goto("/");
  await expect(page).toHaveURL(/\/trade$/);
  await page.goto("/legacy");
  await expect(page.getByTestId("legacy-banner")).toContainText("deprecated");
});

const VIEWPORTS = [
  { name: "1440x900", width: 1440, height: 900 },
  { name: "390x844", width: 390, height: 844 },
  { name: "200% zoom (720x450 CSS px)", width: 720, height: 450 },
];
for (const vp of VIEWPORTS) {
  test(`/trade at ${vp.name}: chart and decision stay usable, no horizontal scroll`, async ({ page }) => {
    await mock(page, view({}, "BUY"));
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.goto("/trade");
    await expect(page.getByTestId("trade-chart")).toBeVisible();
    await expect(page.getByTestId("decision")).toBeVisible();
    const chart = await page.getByTestId("trade-chart").boundingBox();
    expect(chart?.width ?? 0).toBeGreaterThan(Math.min(300, vp.width - 40));
    expect(chart?.height ?? 0).toBeGreaterThan(250);
    const decision = await page.getByTestId("decision").boundingBox();
    expect((decision?.x ?? 0) + (decision?.width ?? 0)).toBeLessThanOrEqual(vp.width + 1);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });
}

test("/journal at 390px has no horizontal page scroll", async ({ page }) => {
  await page.route("**/trade/journal**", (route) => route.fulfill({ json: { simulated: true, open: null, trades: [], evidence: view().evidence } }));
  await page.setViewportSize({ width: 390, height: 800 });
  await page.goto("/journal");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});

test("a REAL desk record (from an acceptance replay) renders its TP/SL, R and markers (no field-name drift)", async ({ page }) => {
  const closed = realTrade as unknown as Record<string, unknown> & { tp: number; sl: number; fill_price: number; exit_reason: string };
  await page.route("**/trade/journal**", (route) =>
    route.fulfill({ json: { simulated: true, open: null, trades: [closed], evidence: view().evidence } }),
  );
  await page.goto("/journal");
  const row = page.getByTestId("journal-row");
  await expect(row).toContainText(closed.tp.toFixed(2)); // TP column is filled (was "—" with a wrong field name)
  await expect(row).toContainText(closed.exit_reason);
  await expect(row).not.toContainText("NaN");

  // the same record, still open, drawn on the chart
  const open = { ...closed, status: "OPEN", closed_at: null, exit_price: null, exit_reason: null, current_price: closed.fill_price + 1, unrealized_pnl: 5, unrealized_r: 0.2 };
  const v = view({}, "WAIT");
  (v.desk as { position: unknown }).position = open;
  await mock(page, v);
  await page.goto("/trade");
  await expect(page.getByTestId("line-PAPER-TP")).toHaveText(`PAPER TP ${closed.tp.toFixed(2)}`);
  await expect(page.getByTestId("line-PAPER-SL")).toHaveText(`PAPER SL ${closed.sl.toFixed(2)}`);
  await expect(page.getByTestId("line-PAPER-ENTRY")).toHaveText(`PAPER ENTRY ${closed.fill_price.toFixed(2)}`);
});
