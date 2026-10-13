/** Typed, read-only client for the MT5 market data endpoints (/md/*). No function here can trade. */

import { API_URL } from "@/lib/api";

export const MARKET_TIMEFRAMES = ["M1", "M5", "M15", "M30", "H1", "H4"] as const;
export type MarketTimeframe = (typeof MARKET_TIMEFRAMES)[number];

export interface MarketBar {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  tick_volume: number;
  spread: number;
  is_closed: boolean;
}

export interface BarsResponse {
  symbol: string;
  timeframe: string;
  source: string;
  volume_type: string;
  closed_only: boolean;
  bars: MarketBar[];
}

export interface QuoteResponse {
  available: boolean;
  stale: boolean;
  state?: "FRESH" | "STALE" | "MARKET_CLOSED" | "UNAVAILABLE";
  reason?: string;
  market_status: string;
  bid?: number | null;
  ask?: number | null;
  mid?: number | null;
  spread_price?: number | null;
  spread_points?: number | null;
  timestamp?: string | null;
  last_tick_time?: string | null;
  age_seconds?: number | null;
  collector_age_seconds?: number;
  note?: string;
}

export interface Components {
  terminal: string;
  collector: string;
  api: string;
  market: string;
  quote: string;
  bars: string;
}

export interface MarketStatusResponse {
  health: string;
  reasons?: string[];
  market_status: string;
  collector_running: boolean;
  server?: string | null;
  source?: string;
  volume_type?: string;
  components?: Components;
  recovery_action?: string | null;
  freshness?: Record<string, string>;
  warnings?: string[];
}

export interface MatrixRow {
  timeframe: string;
  last_closed_bar_open: string | null;
  last_close_time: string | null;
  age_seconds: number | null;
}

export interface MatrixResponse {
  symbol: string;
  health: string;
  timeframes: MatrixRow[];
}

export interface DepthRow {
  timeframe: string;
  earliest: string | null;
  latest: string | null;
  rows: number | null;
  freshness: string;
}

export interface QualityResponse {
  history_depth: DepthRow[];
  recent_events: { at: string; kind: string; timeframe?: string; count?: number }[];
  tick_store: { enabled?: boolean; covered_until?: string | null; lag_seconds?: number | null; earliest_covered?: string | null; coverage_windows?: number };
  disk: { level?: string; free_gb?: number; tick_gb?: number; estimated_days_remaining?: number | null };
  warnings: string[];
  collector_health: string;
  ledger_integrity: { ok?: boolean; verified_at?: string } | null;
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return (await response.json()) as T;
}

export const fetchBars = (tf: MarketTimeframe, limit: number, forming: boolean) =>
  get<BarsResponse>(`/md/XAUUSD/bars?timeframe=${tf}&limit=${limit}&include_forming=${forming}`);
export const fetchQuote = () => get<QuoteResponse>("/md/XAUUSD/quote");
export const fetchStatus = () => get<MarketStatusResponse>("/md/status");
export const fetchMatrix = () => get<MatrixResponse>("/md/XAUUSD/matrix");
export const fetchQuality = () => get<QualityResponse>("/md/XAUUSD/quality");
