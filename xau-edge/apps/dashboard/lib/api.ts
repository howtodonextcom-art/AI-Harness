/** Typed, read-only client for the XAU EDGE API. There is no function here that can place an order. */

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export type Direction = "BUY" | "SELL" | "WAIT";

export interface Signal {
  symbol: string;
  timestamp: string;
  timeframe: string;
  direction: Direction;
  candidate_direction: Direction | null;
  prob_up: number | null;
  prob_down: number | null;
  prob_neutral: number | null;
  probability_source: string;
  expected_return: number | null;
  expected_R: number | null;
  market_regime: string | null;
  higher_timeframe_bias: string | null;
  entry_zone: [number, number] | null;
  stop_loss: number | null;
  take_profit_1: number | null;
  take_profit_2: number | null;
  risk_reward: number | null;
  signal_expiry: string | null;
  explanation: string[];
  historical_matches_count: number;
  similarity_quality: number | null;
  evidence_status: "NONE" | "VALIDATED";
  reasons: string[];
  news_status: "unknown" | "risk" | "clear";
  data_as_of: string;
  inputs_hash: string;
  code_version: string;
}

export interface TimeframeState {
  timestamp: string;
  regime: string | null;
  trend: number;
  bos: number;
  choch: number;
  support: number | null;
  resistance: number | null;
}

export interface RegimeResponse {
  H4: TimeframeState;
  H1: TimeframeState;
  M15: TimeframeState;
  M5: TimeframeState;
}

export interface AnalogueMatch {
  rank: number;
  end_time: string;
  distance: number;
  pattern_path: number[];
  outcome_path: number[];
}

export interface PatternsResponse {
  available: boolean;
  reason?: string;
  at?: string;
  window?: number;
  outcome_bars?: number;
  current_path?: number[];
  candidates?: number;
  best_distance?: number | null;
  median_distance?: number | null;
  matches: AnalogueMatch[];
}

export interface Bar {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  tick_volume: number;
  spread: number;
}

export interface RiskStatus {
  live_trading: boolean;
  kill_switch: { tripped: boolean; note: string };
  limits: Record<string, number | string | boolean | string[]>;
  prop_profile: {
    name: string;
    daily_loss_limit_pct: number;
    max_loss_limit_pct: number;
    max_loss_kind: string;
    verified_on: string;
    ea_restrictions: string;
  };
  evidence_status: "NONE" | "VALIDATED";
}

export interface PaperAccount {
  initial_capital: number;
  balance: number;
  equity: number;
  open_positions: number;
  open_lots: number;
}

export interface RunSummary {
  id: string;
  family: string;
  name: string;
  period: string;
  passed: boolean | null;
  trades: number | null;
}

export interface BotAlert {
  code: string;
  severity: "info" | "warning" | "critical";
  message: string;
}

export interface BotPosition {
  ticket: string;
  symbol: string;
  direction: 1 | -1;
  lots: number;
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  opened_at: string;
  bot_owned: boolean;
}

export interface BotStatusBody {
  updated_at: string;
  mode: "disabled" | "dry-run" | "demo";
  live_trading: false;
  symbol: string;
  connected: boolean;
  account_demo: boolean | null;
  balance: number | null;
  equity: number | null;
  positions: BotPosition[];
  reconcile_clean: boolean | null;
  reconcile_codes: string[];
  last_cycle: {
    decision_time: string | null;
    direction: string;
    accepted: boolean;
    reasons: string[];
    data_age_minutes: number | null;
  } | null;
  news_status: "unknown" | "risk" | "clear";
}

export interface BotStatus {
  configured: boolean;
  live_trading: false;
  status: BotStatusBody | null;
  kill_switch: { tripped: boolean; reason: string; known: boolean };
  alerts: BotAlert[];
  healthy: boolean;
}

export interface BotCycle {
  recorded_at: string;
  decision_time: string | null;
  direction: string;
  accepted: boolean;
  reasons: string[];
  intent_id: string | null;
  dry_run: boolean;
  data_age_minutes: number | null;
}

export interface BotJournalEvent {
  at: string;
  event: string;
  [key: string]: unknown;
}

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { signal, cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${path} failed with ${response.status}`);
  }
  return (await response.json()) as T;
}

export const api = {
  signal: (signal?: AbortSignal) => get<Signal>("/signals/XAUUSD", signal),
  regime: (signal?: AbortSignal) => get<RegimeResponse>("/regime/XAUUSD", signal),
  patterns: (signal?: AbortSignal) => get<PatternsResponse>("/patterns/XAUUSD?k=10", signal),
  bars: (signal?: AbortSignal) =>
    get<{ bars: Bar[] }>("/market/XAUUSD?timeframe=M15&limit=200", signal),
  risk: (signal?: AbortSignal) => get<RiskStatus>("/risk/status", signal),
  runs: (signal?: AbortSignal) => get<{ runs: RunSummary[] }>("/backtests", signal),
  bot: (signal?: AbortSignal) => get<BotStatus>("/bot/status", signal).catch(() => null),
  botCycles: (signal?: AbortSignal) =>
    get<{ cycles: BotCycle[] }>("/bot/cycles?limit=12", signal).then((r) => r.cycles).catch(() => []),
  botJournal: (signal?: AbortSignal) =>
    get<{ events: BotJournalEvent[] }>("/bot/journal?limit=12", signal).then((r) => r.events).catch(() => []),
  paper: (signal?: AbortSignal) =>
    get<PaperAccount>("/paper/account", signal).catch(() => null),
};
