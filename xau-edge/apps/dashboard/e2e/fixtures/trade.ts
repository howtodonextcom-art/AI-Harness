import type { Page } from "@playwright/test";

/** Mock data for the /trade e2e tests and the screenshot run (server-shaped objects, no real market). */

export const NOW = Date.now();
export const iso = (offsetSeconds: number) => new Date(NOW + offsetSeconds * 1000).toISOString();
export const TFS = ["H4", "H1", "M30", "M15", "M5", "M1"];
export const ROLES: Record<string, string> = {
  H4: "REGIME / BLOCKER", H1: "DIRECTION", M30: "CONTEXT (display only)", M15: "SETUP", M5: "TRIGGER", M1: "EXECUTION TIMING",
};
export const STAGES = ["Market & data", "Spread & regime", "H1 direction", "H4 / M15 alignment", "M15 setup", "M5 trigger", "M1 execution", "Trade plan"];

// 5-minute bars ending a few minutes ago (the chart shows closed bars plus one forming bar)
export const STEP = 300_000;
export const LAST_OPEN = Math.floor(NOW / STEP) * STEP;
export const barOpen = (back: number) => new Date(LAST_OPEN - back * STEP).toISOString();

export function bars(timeframe: string) {
  const out = [];
  for (let i = 120; i >= 0; i--) {
    const base = 2086 + (120 - i) * 0.1 + Math.sin(i / 4) * 1.2;
    out.push({ time: barOpen(i), open: base, high: base + 2, low: base - 2, close: base + 1, tick_volume: 100 + i, spread: 20, is_closed: i !== 0 });
  }
  return { symbol: "XAUUSD", timeframe, source: "FTMO MT5", volume_type: "TICK_VOLUME", closed_only: false, bars: out };
}

export function plan(r: number) {
  return { ok: true, lots: r * 2, risk_pct: r, risk_pct_actual: r, risk_amount: 100 * r, sl_distance: 5, tp_distance: 10, loss_at_sl: 100 * r, gain_at_tp: 200 * r, errors: [] };
}

export function stagesFor(failIndex: number | null) {
  return STAGES.map((stage, i) => ({
    stage,
    status: failIndex === null || i < failIndex ? "PASS" : i === failIndex ? "FAIL" : "NOT_REACHED",
  }));
}

export function view(over: Record<string, unknown> = {}, side: "BUY" | "SELL" | "WAIT" = "BUY", blockers: string[] = []) {
  const wait = side === "WAIT";
  return {
    available: true, generated_at: iso(0), data_as_of: iso(-30), data_age_seconds: 12,
    market: { status: "OPEN", open: true },
    quote: { bid: 2100.1, ask: 2100.5, spread_points: 40, age_seconds: 0.4, stale: false },
    decision: {
      decision: side, decision_id: "d-1", setup_id: "abcdef0123456789", timestamp: iso(0),
      entry_price: wait ? null : 2100.5, stop_loss: wait ? null : 2095.5, take_profit: wait ? null : 2110.5, take_profit_2: wait ? null : 2115.5,
      risk_reward: wait ? null : 1.9, required_win_rate: wait ? null : 0.34, stop_model: wait ? null : "HYBRID",
      risk_pct: null, position_size: null, risk_amount: null, signal_expiry: iso(wait ? 0 : 300), expired: false,
      seconds_to_expiry: wait ? null : 300, refusal_reasons: wait ? ["NO_SETUP"] : [], reasons: [], warnings: [],
      invalidation: wait ? null : "H1 turns bearish", entry_quality: "ACCEPTABLE", evidence_status: "UNVALIDATED_BASELINE",
      strategy_version: "1.2.0", spread_state: "GOOD", volatility_regime: "NORMAL", volume_state: "NORMAL",
      volume_type: "TICK_VOLUME", m1_execution_state: "GOOD",
    },
    actionable: !wait && blockers.length === 0,
    explanation: wait ? ["WAIT because: no M15 pullback setup inside the H1 trend"] : ["BUY: H1 direction is bullish", "M15 setup: pullback"],
    why_wait: { stages: stagesFor(wait ? 4 : null), waiting_for: wait ? "an M15 pullback inside the H1 trend (it then stays armed 6 M5 bars)" : null, blocked_by: wait ? ["NO_SETUP"] : [] },
    setup: { phase: wait ? "NONE" : "TRIGGERED", bars_since_armed: wait ? null : 2, valid_bars: 6, strategy_version: "1.2.0" },
    timeframes: TFS.map((t) => ({ timeframe: t, role: ROLES[t], state: t === "M15" && !wait ? "TRIGGERED (UP / PULLBACK)" : "BULLISH", bias: 1, atr: 3, relative_tick_volume: 1.1, volume_zscore: 0.2, last_closed: iso(-60), freshness: "FRESH" })),
    volume: { type: "TICK_VOLUME", note: "tick volume (number of price changes), not exchange volume", state: "NORMAL", m1_zscore: 0.3, m1_relative: 1.1, m1_percentile: 0.55, m1_acceleration: 0.1 },
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
    telemetry: { day: "2026-10-09", decisions: 10, buy: 1, sell: 0, wait: 9, wait_pct: 90, distinct_setups: 1, top_refusals: [["NO_SETUP", 5]], most_common_blocker: "NO_SETUP", setup_phases: { NONE: 8, ARMED: 1, TRIGGERED: 1 } },
    demo: { status: "LOCKED", reasons: [{ code: "DEMO_DRY_RUN", why: "XAU_EDGE_DEMO_DRY_RUN is true" }], paper_desk_sends_orders: false, how_to_unlock: "See docs." },
    problems: [], ...over,
  };
}

export const EMPTY_MARKERS = { simulated: true, signals: [], paper_trades: [] };

export async function mock(page: Page, body: unknown, markers: unknown = EMPTY_MARKERS, onBars?: (tf: string) => void) {
  await page.route("**/trade/decision", (route) => route.fulfill({ json: body }));
  await page.route("**/trade/markers**", (route) => route.fulfill({ json: markers }));
  await page.route("**/md/XAUUSD/bars**", (route) => {
    const tf = new URL(route.request().url()).searchParams.get("timeframe") ?? "M5";
    onBars?.(tf);
    return route.fulfill({ json: bars(tf) });
  });
}

export const legend = (page: Page) => page.getByTestId("chart-legend");

