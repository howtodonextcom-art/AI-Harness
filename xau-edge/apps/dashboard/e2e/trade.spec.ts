import { expect, test, type Page } from "@playwright/test";

/** Trade + Journal pages e2e against the production build; /trade/* is mocked in the browser. */

const iso = (offsetSeconds: number) => new Date(Date.now() + offsetSeconds * 1000).toISOString();
const TFS = ["H4", "H1", "M30", "M15", "M5", "M1"];
const ROLES: Record<string, string> = {
  H4: "REGIME / BLOCKER", H1: "DIRECTION", M30: "CONTEXT (display only)", M15: "SETUP", M5: "TRIGGER", M1: "EXECUTION TIMING",
};

function plan(r: number) {
  return { ok: true, lots: r * 2, risk_pct: r, risk_pct_actual: r, risk_amount: 100 * r, sl_distance: 5, tp_distance: 10, loss_at_sl: 100 * r, gain_at_tp: 200 * r, errors: [] };
}

function view(over: Record<string, unknown> = {}, side: "BUY" | "SELL" | "WAIT" = "BUY", blockers: string[] = []) {
  const wait = side === "WAIT";
  return {
    available: true, generated_at: iso(0), data_as_of: iso(-30), data_age_seconds: 12,
    market: { status: "OPEN", open: true },
    quote: { bid: 2100.1, ask: 2100.5, spread_points: 40, age_seconds: 0.4, stale: false },
    decision: {
      decision: side, decision_id: "d-1", setup_id: "abcdef0123456789", timestamp: iso(0),
      entry_price: wait ? null : 2100.5, stop_loss: wait ? null : 2095.5, take_profit: wait ? null : 2110.5,
      risk_reward: wait ? null : 1.9, required_win_rate: wait ? null : 0.34, stop_model: wait ? null : "STRUCTURE_ATR",
      risk_pct: null, position_size: null, risk_amount: null, signal_expiry: iso(wait ? 0 : 300), expired: false,
      seconds_to_expiry: wait ? null : 300, refusal_reasons: wait ? ["NO_TRIGGER"] : [], reasons: [], warnings: [],
      invalidation: wait ? null : "H1 turns bearish", entry_quality: "OK", evidence_status: "UNVALIDATED_BASELINE",
      strategy_version: "1.1.0", spread_state: "NORMAL", volatility_regime: "NORMAL", volume_state: "NORMAL",
      volume_type: "TICK_VOLUME", m1_execution_state: "GOOD",
    },
    actionable: !wait && blockers.length === 0,
    explanation: wait ? ["WAIT because: M5 has not triggered (or M1 is strongly against the entry)"] : ["BUY: H1 direction is bullish", "M15 setup: pullback"],
    timeframes: TFS.map((t) => ({ timeframe: t, role: ROLES[t], state: "BULLISH", bias: 1, atr: 3, relative_tick_volume: 1.1, volume_zscore: 0.2, last_closed: iso(-60), freshness: "FRESH" })),
    volume: { type: "TICK_VOLUME", note: "tick volume (number of price changes), not exchange volume", state: "NORMAL", m1_zscore: 0.3, m1_relative: 1.1, m1_percentile: 55, m1_acceleration: 0.1 },
    structure: { nearest_resistance: 2120, nearest_support: 2090, pdh: 2125, pdl: 2080, volatility: "NORMAL", session: "LONDON", bos: "NONE", choch: "NONE" },
    risk_plans: wait ? null : [0.1, 0.25, 0.5].map(plan),
    default_risk_pct: 0.25, risk_choices: [0.1, 0.25, 0.5],
    news: { state: "UNKNOWN", warning: true, text: "NEWS NOT VERIFIED: no economic calendar" },
    evidence: { operational: "UNVALIDATED_OPERATIONAL_BASELINE", validated_edge: false, research: "No validated edge.", label: "Not a validated edge." },
    desk: {
      can_open: !wait && blockers.length === 0, blockers,
      account: { simulated: true, initial_capital: 10000, balance: 10000, equity: 10000, open_positions: 0, open_lots: 0 },
      position: null, today: { paper_trades: 0, wins: 0, losses: 0, open: 0, net_pnl: 0, net_r: 0 },
    },
    telemetry: { day: "2026-10-09", decisions: 10, buy: 1, sell: 0, wait: 9, wait_pct: 90, distinct_setups: 1, top_refusals: [["NO_TRIGGER", 5]], most_common_blocker: "NO_TRIGGER" },
    demo: { status: "LOCKED", reasons: [{ code: "DEMO_DRY_RUN", why: "XAU_EDGE_DEMO_DRY_RUN is true" }], paper_desk_sends_orders: false, how_to_unlock: "See docs." },
    problems: [], ...over,
  };
}

async function mock(page: Page, body: unknown | (() => unknown)) {
  await page.route("**/trade/decision", (route) => route.fulfill({ json: typeof body === "function" ? (body as () => unknown)() : body }));
}

test("WAIT shows the exact reason, evidence and news warnings, the demo lock and all six timeframes", async ({ page }) => {
  await mock(page, view({}, "WAIT"));
  await page.goto("/trade");
  await expect(page.getByTestId("decision")).toHaveText("WAIT");
  await expect(page.getByTestId("explanation")).toContainText("M5 has not triggered");
  await expect(page.getByTestId("evidence-pill")).toContainText("CHƯA KIỂM CHỨNG");
  await expect(page.getByTestId("news-warning")).toContainText("NEWS NOT VERIFIED");
  await expect(page.getByTestId("paper-only")).toBeVisible();
  await expect(page.getByTestId("plan-card")).toHaveCount(0);
  await expect(page.getByTestId("demo-lock")).toContainText("DEMO_DRY_RUN");
  await expect(page.getByTestId("volume-note")).toContainText("not exchange volume");
  for (const t of TFS) await expect(page.getByTestId(`tf-${t}`)).toBeVisible();
  await expect(page.getByTestId("tf-M30")).toContainText("CONTEXT");
  await expect(page.getByTestId("main-nav")).toContainText("Trade");
});

test("BUY shows the plan, lot per risk choice, and a paper order needs a confirmation", async ({ page }) => {
  await mock(page, view({}, "BUY"));
  let posted: unknown = null;
  await page.route("**/api/trade/paper/open", (route) => {
    posted = route.request().postDataJSON();
    return route.fulfill({ json: { trade_id: "P-1", side: "BUY", lots: 0.5, fill_price: 2100.5, status: "OPEN" } });
  });
  await page.goto("/trade");
  await expect(page.getByTestId("decision")).toHaveText("BUY");
  await expect(page.getByTestId("plan-entry")).toHaveText("2100.50");
  await expect(page.getByTestId("plan-sl")).toHaveText("2095.50");
  await expect(page.getByTestId("plan-tp")).toHaveText("2110.50");
  await expect(page.getByTestId("plan-lots")).toHaveText("0.50");
  await page.getByTestId("risk-0.5").click();
  await expect(page.getByTestId("plan-lots")).toHaveText("1.00");
  await page.getByTestId("risk-0.25").click();
  await page.getByTestId("take-paper").click();
  expect(posted).toBeNull(); // nothing is sent before the confirmation
  await page.getByTestId("confirm-paper").click();
  await expect(page.getByTestId("action-message")).toContainText("Đã mở lệnh PAPER BUY");
  expect(posted).toEqual({ setup_id: "abcdef0123456789", risk_pct: 0.25 });
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
  await page.goto("/trade");
  await expect(page.getByTestId("stale-banner")).toBeVisible();
  await expect(page.getByTestId("take-paper")).toHaveCount(0);
});

test("an open paper position shows live P&L and can be closed", async ({ page }) => {
  const position = {
    trade_id: "P-7", setup_id: "x", status: "OPEN", side: "BUY", created_at: iso(-600), opened_at: iso(-600), closed_at: null,
    fill_price: 2100.5, initial_sl: 2095.5, initial_tp: 2110.5, lots: 0.5, risk_pct: 0.25, risk_amount: 25,
    unrealized_pnl: 12.5, unrealized_r: 0.5, current_price: 2103, duration_minutes: 10,
  };
  const v = view({}, "WAIT");
  (v.desk as { position: unknown }).position = position;
  await mock(page, v);
  await page.route("**/api/trade/paper/close", (route) =>
    route.fulfill({ json: { ...position, status: "CLOSED", net_pnl: 12, r_multiple: 0.48 } }),
  );
  await page.goto("/trade");
  await expect(page.getByTestId("position-pnl")).toContainText("$12.50");
  await page.getByTestId("close-paper").click();
  await expect(page.getByTestId("action-message")).toContainText("Đã đóng lệnh paper");
});

test("journal lists paper trades with a detail snapshot and says it proves nothing", async ({ page }) => {
  await page.route("**/trade/journal**", (route) =>
    route.fulfill({
      json: {
        simulated: true, open: null,
        evidence: view().evidence,
        trades: [
          { trade_id: "P-1", setup_id: "s", status: "CLOSED", side: "BUY", created_at: iso(-3600), opened_at: iso(-3600), closed_at: iso(-3000), fill_price: 2100.5, initial_sl: 2095.5, initial_tp: 2110.5, lots: 0.5, risk_pct: 0.25, risk_amount: 25, exit_price: 2095.5, exit_reason: "STOP_LOSS", net_pnl: -27.5, r_multiple: -1.1, mfe_r: 0.2, mae_r: -1.0, market: { session: "LONDON" } },
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
