import { expect, test } from "@playwright/test";
import { TFS, bars, barOpen, journalClosedGolden, legend, markersClosedGolden, mock, signalsGolden, view } from "./fixtures/trade";

/**
 * Trade + Journal pages against the production build with the API mocked in the browser. Every served
 * object is a real backend serialization (e2e/fixtures/golden, see fixtures/trade.ts); the real-browser
 * run against a live replay API is e2e-acceptance/desk.spec.ts.
 */

const fixed = (n: number | null | undefined) => (n ?? 0).toFixed(2);

test("WAIT: chart first, blocked-by, Why WAIT stages, waiting-for, six timeframes, status strip", async ({ page }) => {
  const v = view("wait");
  await mock(page, v);
  await page.goto("/trade");
  await expect(page.getByTestId("trade-chart")).toBeVisible();
  await expect(page.getByTestId("hero")).toHaveAttribute("data-hero-state", "WAIT");
  await expect(page.getByTestId("decision")).toHaveText("WAIT");
  await expect(page.getByTestId("blocked-by")).toBeVisible();
  await expect(page.getByTestId("waiting-for")).toContainText("không phải dự báo");
  await expect(page.getByTestId("waiting-for")).toContainText(v.why_wait?.waiting_for ?? "");
  const failed = (v.why_wait?.stages ?? []).find((s) => s.status === "FAIL");
  expect(failed).toBeDefined();
  await expect(page.getByTestId(`stage-${(failed?.stage ?? "").replace(/[^A-Za-z0-9]+/g, "-")}`)).toContainText("FAIL");
  await expect(page.getByTestId("evidence-pill")).toContainText("CHƯA KIỂM CHỨNG");
  await expect(page.getByTestId("news-warning")).toContainText("NEWS NOT VERIFIED");
  await expect(page.getByTestId("paper-only")).toBeVisible();
  await expect(page.getByTestId("plan-card")).toHaveCount(0);
  await expect(legend(page).locator("li")).toHaveCount(0); // no plan lines for a WAIT
  for (const t of TFS) await expect(page.getByTestId(`tf-${t}`)).toBeVisible();
  await expect(page.getByTestId("matrix-M15")).toContainText("SETUP");
  const strip = page.getByTestId("status-strip");
  for (const word of ["DATA", "TRADING CORE", "ACTIVE STRATEGY", "PAPER DESK", "FORWARD", "DEMO", "EDGE"]) await expect(strip).toContainText(word);
  await expect(page.getByTestId("replay-banner")).toContainText("NOT LIVE");
  await page.getByText("Chẩn đoán nâng cao").click();
  await expect(page.getByTestId("demo-lock")).toContainText(v.demo.reasons[0].code);
});

test("BUY: plan lines carry the server values and a paper order needs a confirmation", async ({ page }) => {
  const v = view("buy");
  const plan = v.trade_plan!;
  const chosen = (r: number) => v.risk_plans!.find((p) => p.risk_pct === r)!;
  await mock(page, v);
  let posted: unknown = null;
  await page.route("**/api/trade/paper/open", (route) => {
    posted = route.request().postDataJSON();
    return route.fulfill({ json: view("openPaper").desk!.position });
  });
  await page.goto("/trade");
  await expect(page.getByTestId("decision")).toHaveText("BUY READY");
  await expect(page.getByTestId("line-ENTRY")).toHaveText(`ENTRY ${fixed(plan.planned_entry)}`);
  await expect(page.getByTestId("line-SL")).toHaveText(`SL ${fixed(plan.sl)}`);
  await expect(page.getByTestId("line-TP1")).toHaveText(`TP1 ${fixed(plan.tp1)}`);
  await expect(page.getByTestId("plan-entry")).toHaveText(fixed(plan.planned_entry));
  await expect(page.getByTestId("plan-rr")).toHaveText(fixed(plan.rr_net));
  await expect(page.getByTestId("plan-lots")).toHaveText(fixed(chosen(0.25).lots));
  await expect(page.getByTestId("plan-version")).toContainText(`v${plan.strategy_version}`);
  await expect(page.getByTestId("setup-phase")).toContainText("TRIGGERED");
  await expect(page.getByTestId("expiry")).toBeVisible();
  await page.getByTestId("risk-0.5").click();
  await expect(page.getByTestId("plan-lots")).toHaveText(fixed(chosen(0.5).lots));
  await page.getByTestId("risk-0.25").click();
  await page.getByTestId("take-paper").click();
  expect(posted).toBeNull(); // nothing is sent before the confirmation
  await expect(page.getByTestId("confirm-card")).toContainText("không gửi lệnh thật");
  await page.getByTestId("confirm-paper").click();
  await expect(page.getByTestId("action-message")).toContainText("Đã mở lệnh PAPER BUY");
  expect(posted).toEqual({ setup_id: plan.setup_id, risk_pct: 0.25 });
});

test("SELL is visibly different from BUY (icon, label, text)", async ({ page }) => {
  await mock(page, view("sell"));
  await page.goto("/trade");
  await expect(page.getByTestId("decision")).toHaveText("SELL READY");
  await expect(page.getByTestId("hero")).toContainText("▼");
  await expect(page.getByTestId("plan-side")).toHaveText("SELL");
  await expect(page.getByTestId("take-paper")).toContainText("SELL");
});

test("signal and EXIT markers come from the server objects and snap to their bars", async ({ page }) => {
  const v = view("closedPaper");
  const markers = markersClosedGolden();
  const sig = markers.signals[0];
  const trade = markers.paper_trades[0];
  await mock(page, v, { markers });
  await page.goto("/trade");
  const list = page.getByTestId("chart-markers").locator("li");
  const signal = list.filter({ has: page.locator("xpath=self::*[@data-kind='BUY']") });
  await expect(signal).toHaveCount(1);
  await expect(signal.first()).toHaveAttribute("data-bar-time", new Date(sig.bar_time).toISOString());
  await expect(signal.first()).toContainText(`BUY signal @ ${fixed(sig.entry)}`);
  await expect(signal.first()).toContainText("taken (paper)");
  await expect(signal.first()).toContainText(`v${sig.strategy_version}`);
  const exit = page.getByTestId("chart-markers").locator('li[data-kind="EXIT"]');
  await expect(exit).toHaveCount(1);
  await expect(exit.first()).toContainText(`EXIT ${trade.exit_reason} @ ${fixed(trade.exit_price)}`);
  await expect(exit.first()).toContainText(`${fixed(trade.r_multiple)}R`);
  await expect(exit.first()).toContainText(`P&L ${fixed(trade.net_pnl)}`);
  await page.getByTestId("toggle-signals").uncheck();
  await expect(signal).toHaveCount(0);
});

test("an open paper position draws entry, SL, TP and now, with live R and P&L, and closes by hand", async ({ page }) => {
  const v = view("openPaper");
  const pos = v.desk!.position!;
  await mock(page, v);
  await page.route("**/api/trade/paper/close", (route) => route.fulfill({ json: journalClosedGolden().trades[0] }));
  await page.goto("/trade");
  await expect(page.getByTestId("hero")).toHaveAttribute("data-hero-state", "POSITION_OPEN");
  await expect(page.getByTestId("line-PAPER-ENTRY")).toHaveText(`PAPER ENTRY ${fixed(pos.fill_price)}`);
  await expect(page.getByTestId("line-PAPER-SL")).toHaveText(`PAPER SL ${fixed(pos.sl)}`);
  await expect(page.getByTestId("line-PAPER-TP")).toHaveText(`PAPER TP ${fixed(pos.tp)}`);
  await expect(page.getByTestId("line-NOW")).toHaveText(`NOW ${fixed(pos.current_price)}`);
  await expect(page.getByTestId("position-pnl")).toContainText(fixed(pos.unrealized_pnl));
  await expect(page.getByTestId("position-r")).toHaveText(fixed(pos.unrealized_r));
  await expect(page.getByTestId("position-excursion")).not.toContainText("— / —");
  await page.getByTestId("toggle-paper").uncheck();
  await expect(page.getByTestId("line-PAPER-ENTRY")).toHaveCount(0);
  await page.getByTestId("toggle-paper").check();
  await page.getByTestId("close-paper").click();
  await expect(page.getByTestId("action-message")).toContainText("Đã đóng lệnh paper");
});

test("the exited state names the result and history rows focus the chart", async ({ page }) => {
  const v = view("closedPaper");
  const journal = journalClosedGolden();
  await mock(page, v, { journal, markers: markersClosedGolden(), signals: signalsGolden() });
  await page.goto("/trade");
  await expect(page.getByTestId("hero")).toHaveAttribute("data-hero-state", "EXITED");
  await expect(page.getByTestId("paper-history-row")).toContainText(journal.trades[0].exit_reason ?? "");
  await expect(page.getByTestId("signal-history-row")).toHaveCount(1);
  await page.getByTestId("paper-history-row").first().click();
  await expect(page.getByTestId("trade-chart")).toBeVisible();
});

test("structure overlay is optional and uses the server levels", async ({ page }) => {
  const v = view("buy");
  await mock(page, v);
  await page.goto("/trade");
  const before = await legend(page).locator("li").count();
  await page.getByTestId("toggle-structure").check();
  await expect.poll(() => legend(page).locator("li").count()).toBeGreaterThan(before);
  await expect(page.getByTestId("line-PDH")).toHaveText(`PDH ${fixed(Number(v.structure?.pdh))}`);
});

test("trade-plan overlay can be hidden and the volume panel toggle works", async ({ page }) => {
  await mock(page, view("buy"));
  await page.goto("/trade");
  await expect(page.getByTestId("line-ENTRY")).toBeVisible();
  await page.getByTestId("toggle-plan").uncheck();
  await expect(page.getByTestId("line-ENTRY")).toHaveCount(0);
  await page.getByTestId("toggle-volume").uncheck();
  await expect(page.getByTestId("toggle-volume")).not.toBeChecked();
});

test("clicking a timeframe in the matrix or a Why row switches the chart", async ({ page }) => {
  const requested: string[] = [];
  await mock(page, view("wait"), { onBars: (tf) => requested.push(tf) });
  await page.goto("/trade");
  await expect(page.getByTestId("chart-tf-M5")).toHaveAttribute("aria-pressed", "true");
  await page.getByTestId("matrix-H1").click();
  await expect(page.getByTestId("chart-tf-H1")).toHaveAttribute("aria-pressed", "true");
  await expect.poll(() => requested.includes("H1")).toBe(true);
  const row = page.getByTestId("stages").getByRole("button").filter({ hasText: "M15" }).first();
  await row.click();
  await expect(page.getByTestId("chart-tf-M15")).toHaveAttribute("aria-pressed", "true");
});

test("stale data is STALE (never WAIT), hides the plan and the action", async ({ page }) => {
  await mock(page, view("stale"));
  await page.goto("/trade");
  await expect(page.getByTestId("hero")).toHaveAttribute("data-hero-state", "STALE");
  await expect(page.getByTestId("decision")).toContainText("NOT ACTIONABLE");
  await expect(page.getByTestId("conditions")).toContainText("DATA STALE");
  await expect(page.getByTestId("take-paper")).toHaveCount(0);
  await expect(page.getByTestId("line-ENTRY")).toHaveCount(0);
});

test("an expired setup says EXPIRED SETUP and cannot be taken", async ({ page }) => {
  await mock(page, view("expired"));
  await page.goto("/trade");
  await expect(page.getByTestId("decision")).toHaveText("EXPIRED SETUP");
  await expect(page.getByTestId("take-paper")).toBeDisabled();
});

test("market closed, unavailable engine and a corrupt paper state each have their own state", async ({ page }) => {
  await mock(page, view("marketClosed"));
  await page.goto("/trade");
  await expect(page.getByTestId("hero")).toHaveAttribute("data-hero-state", "MARKET_CLOSED");
  await mock(page, view("writerConflict"));
  await page.goto("/trade");
  await expect(page.getByTestId("hero")).toHaveAttribute("data-hero-state", "UNAVAILABLE");
  await expect(page.getByTestId("conditions")).toContainText("WRITER");
  await expect(page.getByTestId("take-paper")).toHaveCount(0);
  await mock(page, view("paperCorrupt"));
  await page.goto("/trade");
  await expect(page.getByTestId("blockers").locator("[data-code='PAPER_STATE_ERROR']")).toBeVisible();
  await expect(page.getByTestId("take-paper")).toBeDisabled();
});

test("the API refusing a stale setup is shown, not hidden", async ({ page }) => {
  await mock(page, view("buy"));
  await page.route("**/api/trade/paper/open", (route) =>
    route.fulfill({ status: 409, json: { detail: { code: "DECISION_CHANGED", message: "the setup changed" } } }),
  );
  await page.goto("/trade");
  await page.getByTestId("take-paper").click();
  await page.getByTestId("confirm-paper").click();
  await expect(page.getByTestId("action-message")).toContainText("DECISION_CHANGED");
});

test("an unreachable API is API UNAVAILABLE, not WAIT, and blocks entry", async ({ page }) => {
  await page.route("**/trade/**", (route) => route.abort());
  await page.route("**/md/XAUUSD/bars**", (route) => route.abort());
  await page.goto("/trade");
  await expect(page.getByTestId("api-down-banner")).toBeVisible();
  await expect(page.getByTestId("take-paper")).toHaveCount(0);
  await expect(page.getByTestId("decision")).toHaveCount(0);
});

test("journal lists the real closed trade, labels replay, and says it proves nothing", async ({ page }) => {
  const journal = journalClosedGolden();
  const t = journal.trades[0];
  await page.route("**/trade/journal**", (route) => route.fulfill({ json: journal }));
  await page.goto("/journal");
  await expect(page.getByTestId("journal-row")).toHaveCount(journal.trades.length);
  await expect(page.getByTestId("journal-row").first()).toContainText("Chạm TP");
  await expect(page.getByTestId("journal-row").first()).toContainText(fixed(t.tp));
  await expect(page.getByTestId("journal-row").first()).toContainText(`v${t.strategy_version}`);
  await expect(page.getByTestId("journal-replay-banner")).toContainText("KHÔNG PHẢI LIVE");
  await expect(page.getByTestId("journal-note")).toContainText("Chưa có bằng chứng");
  await page.getByTestId("journal-detail-toggle").first().click();
  await expect(page.getByTestId("journal-detail")).toContainText("ACCEPTANCE_REPLAY");
});

test("journal API down is an error, not an empty journal", async ({ page }) => {
  await page.route("**/trade/journal**", (route) => route.abort());
  await page.goto("/journal");
  await expect(page.getByText("chưa có dữ liệu")).toBeVisible();
});

test("the home page opens the trading desk and the legacy page is marked deprecated", async ({ page }) => {
  await mock(page, view("wait"));
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
    await mock(page, view("buy"));
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.goto("/trade");
    await expect(page.getByTestId("trade-chart")).toBeVisible();
    await expect(page.getByTestId("decision")).toBeVisible();
    const chart = await page.getByTestId("trade-chart").boundingBox();
    expect(chart?.width ?? 0).toBeGreaterThan(Math.min(300, vp.width - 40));
    expect(chart?.height ?? 0).toBeGreaterThan(250);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });
}

test("/journal at 390px has no horizontal page scroll", async ({ page }) => {
  await page.route("**/trade/journal**", (route) => route.fulfill({ json: journalClosedGolden() }));
  await page.setViewportSize({ width: 390, height: 800 });
  await page.goto("/journal");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});

test("AUTO_PAPER is visible when it is on and absent when it is off", async ({ page }) => {
  await mock(page, { ...view("wait"), auto_paper: true });
  await page.goto("/trade");
  await expect(page.getByTestId("auto-paper-banner")).toContainText("AUTO_PAPER");
  await mock(page, { ...view("wait"), auto_paper: false });
  await page.goto("/trade");
  await expect(page.getByTestId("auto-paper-banner")).toHaveCount(0);
});

test("a repeated bar time (DST fall-back) does not break the chart series", async ({ page }) => {
  const v = view("buy");
  const markers = markersClosedGolden();
  await mock(page, v, { markers });
  await page.route("**/md/XAUUSD/bars**", (route) => {
    const b = bars(v, "M5");
    b.bars.splice(50, 0, { ...b.bars[50] });
    return route.fulfill({ json: b });
  });
  await page.goto("/trade");
  await expect(page.getByTestId("trade-chart")).toBeVisible();
  await expect(page.getByTestId("chart-markers").locator("li").first()).toHaveAttribute("data-bar-time", barOpen(v, 1));
});
