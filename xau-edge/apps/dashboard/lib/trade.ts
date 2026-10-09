/**
 * Typed client for the live PAPER trading desk (`/trade/*`). Reads go straight to the API; the two
 * paper actions go through the dashboard's own server route (`/api/trade/*`), which adds the
 * Origin/desk header. No function here can reach MT5 or place a real order.
 */

import { API_URL } from "@/lib/api";

export type Side = "BUY" | "SELL" | "WAIT";

export interface TradeDecisionBody {
  decision: Side;
  decision_id: string;
  setup_id: string;
  timestamp: string;
  entry_price: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  take_profit_2?: number | null;
  risk_reward: number | null;
  required_win_rate: number | null;
  stop_model: string | null;
  risk_pct: number | null;
  position_size: number | null;
  risk_amount: number | null;
  signal_expiry: string | null;
  expired: boolean;
  seconds_to_expiry: number | null;
  refusal_reasons: string[];
  reasons: string[];
  warnings: string[];
  invalidation: string | null;
  entry_quality: string;
  evidence_status: string;
  strategy_version: string;
  spread_state: string;
  volatility_regime: string;
  volume_state: string;
  volume_type: string;
  m1_execution_state: string;
}

export interface WhyWait {
  stages: { stage: string; status: "PASS" | "FAIL" | "NOT_REACHED" }[];
  waiting_for: string | null;
  blocked_by: string[];
}

export interface SetupInfo {
  phase: string | null;
  bars_since_armed: number | null;
  valid_bars: number;
  strategy_version: string;
}

export interface SignalMarker {
  at: string;
  bar_time: string;
  setup_id: string;
  side: "BUY" | "SELL";
  entry: number | null;
  sl: number | null;
  tp1: number | null;
  tp2: number | null;
  rr: number | null;
  lots: number | null;
  expires_at: string | null;
  strategy_version: string;
  taken: boolean;
}

export interface PaperMarker {
  trade_id: string;
  side: "BUY" | "SELL";
  status: string;
  entry_time: string | null;
  entry_price: number | null;
  exit_time: string | null;
  exit_price: number | null;
  exit_reason: string | null;
  net_pnl: number | null;
  r_multiple: number | null;
  duration_minutes: number | null;
  sl: number | null;
  tp: number | null;
}

export interface MarkersResponse {
  simulated: boolean;
  signals: SignalMarker[];
  paper_trades: PaperMarker[];
}

export interface TimeframeRow {
  timeframe: string;
  role: string;
  state: string;
  bias: number | null;
  atr: number | null;
  relative_tick_volume: number | null;
  volume_zscore: number | null;
  last_closed: string | null;
  freshness: string;
}

export interface RiskPlan {
  ok: boolean;
  lots: number;
  risk_pct: number;
  risk_pct_actual: number;
  risk_amount: number;
  sl_distance: number;
  tp_distance: number | null;
  loss_at_sl: number;
  gain_at_tp: number | null;
  errors: string[];
  equity_used?: number;
  equity_source?: string;
}

export interface PaperTrade {
  trade_id: string;
  setup_id: string;
  status: string;
  side: Side;
  created_at: string;
  opened_at: string | null;
  closed_at: string | null;
  fill_price: number;
  sl: number;
  initial_sl: number;
  tp: number;
  lots: number;
  risk_pct: number;
  risk_amount: number | null;
  exit_price?: number | null;
  exit_reason?: string | null;
  net_pnl?: number | null;
  r_multiple?: number | null;
  mfe_r?: number | null;
  mae_r?: number | null;
  duration_minutes?: number | null;
  unrealized_pnl?: number | null;
  unrealized_r?: number | null;
  current_price?: number | null;
  market?: Record<string, string | number | null>;
  decision?: Record<string, unknown>;
  cancel_reason?: string | null;
}

export interface TradeView {
  available: boolean;
  generated_at: string;
  served_at?: string;
  data_as_of?: string | null;
  data_age_seconds?: number | null;
  source?: string;
  market?: { status: string; open: boolean };
  quote?: { bid: number; ask: number; spread_points: number; age_seconds: number; stale: boolean } | null;
  decision?: TradeDecisionBody;
  actionable?: boolean;
  explanation?: string[];
  why_wait?: WhyWait;
  setup?: SetupInfo;
  timeframes?: TimeframeRow[];
  volume?: {
    type: string;
    note: string;
    state: string;
    m1_zscore: number | null;
    m1_relative: number | null;
    m1_percentile: number | null;
    m1_acceleration: number | null;
  };
  structure?: Record<string, string | number | null>;
  risk_plans?: RiskPlan[] | null;
  default_risk_pct?: number;
  risk_choices?: number[];
  news?: { state: string; warning: boolean; text: string };
  evidence: { operational: string; validated_edge: boolean; research: string; label: string };
  desk?: {
    can_open: boolean;
    blockers: string[];
    account: { simulated: boolean; initial_capital: number; balance: number; equity: number; open_positions: number; open_lots: number };
    position: PaperTrade | null;
    today: Record<string, number | string | null>;
  };
  telemetry?: {
    day: string;
    decisions: number;
    buy: number;
    sell: number;
    wait: number;
    wait_pct: number | null;
    distinct_setups: number;
    top_refusals: [string, number][];
    most_common_blocker: string | null;
    setup_phases?: Record<string, number>;
  };
  demo: { status: string; reasons: { code: string; why: string }[]; paper_desk_sends_orders: boolean; how_to_unlock: string };
  problems: string[];
  engine_errors?: string[];
}

export interface JournalResponse {
  simulated: boolean;
  open: PaperTrade | null;
  trades: PaperTrade[];
  evidence: TradeView["evidence"];
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { signal, cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as T;
}

export const fetchDecision = (signal?: AbortSignal) => getJson<TradeView>("/trade/decision", signal);
export const fetchMarkers = (signal?: AbortSignal) => getJson<MarkersResponse>("/trade/markers?days=7", signal);
export const fetchJournal = (signal?: AbortSignal) => getJson<JournalResponse>("/trade/journal?limit=500", signal);

export interface ActionError {
  code: string;
  message: string;
}

async function post<T>(path: string, body: unknown): Promise<{ ok: true; data: T } | { ok: false; error: ActionError }> {
  try {
    const res = await fetch(`/api/trade/${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const json = await res.json();
    if (res.ok) return { ok: true, data: json as T };
    const detail = json?.detail ?? {};
    return { ok: false, error: { code: String(detail.code ?? res.status), message: String(detail.message ?? detail.code ?? "bị từ chối") } };
  } catch {
    return { ok: false, error: { code: "NETWORK", message: "không kết nối được dashboard/API" } };
  }
}

export const openPaperTrade = (setup_id: string, risk_pct: number) =>
  post<PaperTrade>("paper/open", { setup_id, risk_pct });
export const closePaperTrade = (trade_id: string) => post<PaperTrade>("paper/close", { trade_id });
