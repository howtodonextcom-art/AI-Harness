import type { Page } from "@playwright/test";
import type { DecisionCoverage, JournalResponse, MarkersResponse, SetupHistoryResponse, SignalHistoryResponse, TradeView } from "@/lib/trade";
import buyWatch from "./golden/buy_watch.json";
import buyArmed from "./golden/buy_armed.json";
import sellWatch from "./golden/sell_watch.json";
import sellArmed from "./golden/sell_armed.json";
import sellInvalidated from "./golden/sell_invalidated.json";
import buy from "./golden/buy.json";
import closedPaper from "./golden/closed_paper.json";
import coverageIncomplete from "./golden/coverage_incomplete.json";
import expired from "./golden/expired.json";
import journalClosed from "./golden/journal_closed.json";
import marketClosed from "./golden/market_closed.json";
import markersClosed from "./golden/markers_closed.json";
import openPaper from "./golden/open_paper.json";
import paperCorrupt from "./golden/paper_corrupt.json";
import sell from "./golden/sell.json";
import setupsHistory from "./golden/setups_history.json";
import signalsHistory from "./golden/signals_history.json";
import stale from "./golden/stale.json";
import wait from "./golden/wait.json";
import writerConflict from "./golden/writer_conflict.json";

/**
 * Every object served by the mocked API here is a REAL serialization produced by the backend (see
 * `scripts/generate_trade_goldens.py`: TradeEngine / PaperDesk / route handlers over an acceptance
 * replay of burned FTMO bars). Tests only select, clone and (for pure UI states such as "API down")
 * remove things; they never hand-write a BUY, SELL or paper-trade payload.
 */

export const GOLDEN = { buyWatch, buyArmed, sellWatch, sellArmed, sellInvalidated, wait, buy, sell, openPaper, closedPaper, stale, expired, marketClosed, paperCorrupt, writerConflict };
export type GoldenName = keyof typeof GOLDEN;

export const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T;
export const view = (name: GoldenName): TradeView => clone(GOLDEN[name]) as unknown as TradeView;
export const journalClosedGolden = (): JournalResponse => clone(journalClosed) as unknown as JournalResponse;
export const coverageIncompleteGolden = () => clone(coverageIncomplete) as unknown as DecisionCoverage;
export const markersClosedGolden = (): MarkersResponse => clone(markersClosed) as unknown as MarkersResponse;
export const setupsGolden = (): SetupHistoryResponse => clone(setupsHistory) as unknown as SetupHistoryResponse;
export const signalsGolden = (): SignalHistoryResponse => clone(signalsHistory) as unknown as SignalHistoryResponse;

export const TFS = ["H4", "H1", "M30", "M15", "M5", "M1"];

// Bars end at the golden's own server time (so markers and plan lines line up), one grid per timeframe.
export const STEP = 300_000;
const TF_MS: Record<string, number> = { M1: 60_000, M5: 300_000, M15: 900_000, M30: 1_800_000, H1: 3_600_000, H4: 14_400_000 };
export const anchorMs = (v: TradeView) => Date.parse(v.served_at ?? v.generated_at);
export const lastOpen = (v: TradeView, tf = "M5") => Math.floor(anchorMs(v) / TF_MS[tf]) * TF_MS[tf];
export const barOpen = (v: TradeView, back: number, tf = "M5") => new Date(lastOpen(v, tf) - back * TF_MS[tf]).toISOString();

/** Synthetic candles (the chart's data feed, not a trading object) around the golden's quote. */
export function bars(v: TradeView, timeframe: string) {
  const base = v.quote?.bid ?? 4236;
  const out = [];
  for (let i = 120; i >= 0; i--) {
    const mid = base - 6 + (120 - i) * 0.05 + Math.sin(i / 4) * 1.5;
    out.push({ time: barOpen(v, i, timeframe), open: mid, high: mid + 1.5, low: mid - 1.5, close: mid + 0.5, tick_volume: 100 + i, spread: 20, is_closed: i !== 0 });
  }
  return { symbol: "XAUUSD", timeframe, source: "ACCEPTANCE REPLAY (test candles)", volume_type: "TICK_VOLUME", real_volume_policy: "tick volume only", closed_only: false, bars: out };
}

export interface Mocks {
  markers?: MarkersResponse;
  signals?: SignalHistoryResponse;
  journal?: JournalResponse;
  setups?: SetupHistoryResponse;
  onBars?: (tf: string) => void;
}

export async function mock(page: Page, v: TradeView, extra: Mocks = {}) {
  const mode = v.source_mode;
  const markers = extra.markers ?? { simulated: true, source_mode: mode, signals: [], paper_trades: [] };
  const signals = extra.signals ?? { source_mode: mode, signals: [] };
  const journal = extra.journal ?? { simulated: true, source_mode: mode, open: null, trades: [], evidence: v.evidence };
  await page.route("**/trade/decision", (route) => route.fulfill({ json: v }));
  await page.route("**/trade/markers**", (route) => route.fulfill({ json: markers }));
  await page.route("**/trade/signals**", (route) => route.fulfill({ json: signals }));
  await page.route("**/trade/setups**", (route) => route.fulfill({ json: extra.setups ?? { source_mode: mode, setups: [] } }));
  await page.route("**/trade/journal**", (route) => route.fulfill({ json: journal }));
  await page.route("**/md/XAUUSD/bars**", (route) => {
    const tf = new URL(route.request().url()).searchParams.get("timeframe") ?? "M5";
    extra.onBars?.(tf);
    return route.fulfill({ json: bars(v, tf) });
  });
}

export const legend = (page: Page) => page.getByTestId("chart-legend");
