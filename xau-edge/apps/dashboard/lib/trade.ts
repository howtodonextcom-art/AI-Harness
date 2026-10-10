/**
 * Typed client for the live PAPER trading desk (`/trade/*`). Reads go straight to the API; the two
 * paper actions go through the dashboard's own server route (`/api/trade/*`), which adds the
 * Origin/desk header. No function here can reach MT5 or place a real order.
 *
 * These types are the frontend half of the contract: `e2e/fixtures/golden/*.json` are serialized by
 * the real backend and type-checked against them (`tsc`), and the backend test suite fails when the
 * serialized shape drifts from those goldens.
 */

import { API_URL } from "@/lib/api";

export type Side = "BUY" | "SELL" | "WAIT";
export type SourceMode = "LIVE" | "ACCEPTANCE_REPLAY" | "FIXTURE";

export type HeroState =
  | "UNAVAILABLE"
  | "STALE"
  | "MARKET_CLOSED"
  | "POSITION_OPEN"
  | "BUY_READY"
  | "SELL_READY"
  | "NOT_ACTIONABLE"
  | "EXPIRED_SETUP"
  | "SETUP_ARMED"
  | "EXITED"
  | "WAIT";

export interface HeroAction {
  /** the primary action: only BUY and SELL are permission to open a paper trade */
  code: "WAIT" | "BUY" | "SELL" | "HOLD" | "EXIT" | "UNAVAILABLE";
  stage: string;
  side: "BUY" | "SELL" | null;
  /** which way the market leans while the action is still WAIT (a description, never permission) */
  bias: "BUY" | "SELL" | null;
  thesis: "INTACT" | "WEAK" | "UNKNOWN" | null;
  /** the one thing still absent while waiting */
  missing: "SETUP" | "TRIGGER" | null;
  /** READY setup the desk would refuse: the action is WAIT, stage BLOCKED, and this is why (server text). */
  blocked_by?: { code: string; message: string };
}

export interface Hero {
  action: HeroAction;
  state: HeroState;
  label: string;
  tone: "buy" | "sell" | "neutral" | "info" | "warn" | "error";
  detail: string;
  side: "BUY" | "SELL" | null;
}

export interface Condition {
  code: string;
  severity: "ERROR" | "WARN" | "INFO";
  message: string;
}

export interface Blocker {
  code: string;
  message: string;
}

export interface StatusItem {
  state: string;
  detail: string;
}

export interface StatusStrip {
  data: StatusItem;
  trading_core: StatusItem;
  strategy: StatusItem & { label: string };
  paper_desk: StatusItem;
  forward: StatusItem;
  demo: StatusItem;
  edge: StatusItem;
  hero_state: HeroState;
}

export interface StrategyInfo {
  id: string;
  active_version: string;
  label: string;
  evidence: string;
  installed: { version: string; status: "ACTIVE" | "AVAILABLE_INACTIVE"; note: string }[];
}

export interface TradePlan {
  side: "BUY" | "SELL";
  entry_basis: "ask" | "bid";
  planned_entry: number | null;
  sl: number | null;
  tp1: number | null;
  tp2: number | null;
  rr_net: number | null;
  required_win_rate: number | null;
  default_risk_pct: number;
  lots: number | null;
  risk_amount: number | null;
  potential_tp_value: number | null;
  expires_at: string | null;
  seconds_to_expiry: number | null;
  expired: boolean;
  invalidation: string | null;
  strategy_version: string;
  setup_id: string;
  complete: boolean;
  missing: string[];
}

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
  source_mode: SourceMode;
}

export interface WhyStage {
  stage: string;
  status: "PASS" | "FAIL" | "NOT_REACHED";
  timeframe: string;
}

export interface WhyWait {
  stages: WhyStage[];
  waiting_for: string | null;
  waiting_for_code: string | null;
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
  price?: number | null;
  sl: number | null;
  tp1: number | null;
  tp2: number | null;
  rr: number | null;
  lots: number | null;
  expires_at: string | null;
  strategy_version: string;
  source_mode: SourceMode;
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
  strategy_version?: string | null;
}

export interface MarkersResponse {
  simulated: boolean;
  source_mode?: SourceMode;
  signals: SignalMarker[];
  paper_trades: PaperMarker[];
}

export interface SignalHistoryResponse {
  source_mode: SourceMode;
  signals: SignalMarker[];
}

export interface SetupHistoryRow {
  armed_at: string;
  first_seen: string;
  last_seen: string;
  side: "BUY" | "SELL" | null;
  outcome: "TRIGGERED" | "EXPIRED" | "INVALIDATED" | "ARMED";
  actionable: boolean;
  strategy_version: string | null;
}

export interface SetupHistoryResponse {
  source_mode: SourceMode;
  setups: SetupHistoryRow[];
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
  source_mode?: SourceMode;
  created_at: string;
  opened_at: string | null;
  closed_at?: string | null;
  /** the server's single time exit: the paper desk closes the position at this instant at the latest */
  max_hold_until?: string | null;
  planned_entry?: number | null;
  fill_price: number;
  sl: number;
  initial_sl: number;
  tp: number;
  lots: number;
  risk_pct: number;
  risk_amount: number | null;
  strategy_version?: string;
  code_version?: string;
  exit_price?: number | null;
  exit_reason?: string | null;
  net_pnl?: number | null;
  r_multiple?: number | null;
  mfe?: number | null;
  mae?: number | null;
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

export interface Funnel {
  day: string;
  decisions: number;
  armed_setups: number;
  triggered_setups: number;
  expired_setups: number;
  invalidated_setups: number;
  actionable_buy: number;
  actionable_sell: number;
  paper_opens: number;
  paper_exits: number;
  exit_reasons: Record<string, number>;
  refusals: Record<string, number>;
  top_refusals: [string, number][];
}

export interface ForwardAcceptance {
  level: "F0" | "F1" | "F2" | "F3" | "F4";
  text: string;
  live: boolean;
  counts: Record<string, number>;
  /** false when too few of the expected decisions were recorded to trust "no setup seen" */
  evidence_complete: boolean | null;
  coverage_pct: number | null;
}

/** How many of the decisions that should exist (one per closed M1 bar while the engine could see it) were recorded. */
export interface DecisionCoverage {
  window: { from: string; to: string };
  expected_m1_decisions: number;
  recorded_m1_decisions: number;
  coverage_pct: number;
  missing: number;
  missing_intervals: { from: string; to: string; minutes: number }[];
  duplicate_rows: number;
  late_rows: number;
  approx_rows: number;
  outside_expected_rows: number;
  complete: boolean;
  threshold_pct: number;
}

export interface AlertsSummary {
  announced_today: number;
  last: { setup_id: string; side: string; announced_at: string; expires_at: string; closed?: string } | null;
  delivery: "TELEGRAM" | "FILE_FALLBACK";
  telegram_configured: boolean;
  file_fallback_active: boolean;
  last_invalidation: { setup_id: string; side: string; at: string | null } | null;
  this_setup: { announced: boolean; at: string; channel: string } | null;
}

export interface DailyStats {
  day: string;
  is_current_day: boolean;
  open: number;
  high: number;
  low: number;
  range: number;
  prev_close: number | null;
  last: number;
  change: number;
  change_pct: number | null;
  change_basis: "PREV_CLOSE" | "DAY_OPEN";
  range_position: number | null;
}

export interface MarketContext {
  server_time: string;
  session: { code: string; label: string };
  daily: DailyStats | null;
  bar_close: Record<string, string | null>;
  next_open: string | null;
}

export interface TradeView {
  available: boolean;
  source_mode: SourceMode;
  generated_at: string;
  served_at?: string;
  hero: Hero;
  decision_trusted: boolean;
  status_strip: StatusStrip;
  market_context?: MarketContext;
  strategy: StrategyInfo;
  conditions: Condition[];
  forward_acceptance: ForwardAcceptance;
  decision_coverage?: DecisionCoverage | null;
  paper_account_label: string;
  data_as_of?: string | null;
  data_age_seconds?: number | null;
  source?: string;
  market?: { status: string; open: boolean };
  quote?: { bid: number; ask: number; spread_points: number; age_seconds: number; stale: boolean } | null;
  decision?: TradeDecisionBody;
  trade_plan?: TradePlan | null;
  entry_blockers?: Blocker[];
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
  news?: NewsView;
  evidence: { operational: string; validated_edge: boolean; research: string; label: string };
  desk?: {
    can_open: boolean;
    blockers: Blocker[];
    account: { simulated: boolean; initial_capital: number; balance: number; equity: number; open_positions: number; open_lots: number };
    position: PaperTrade | null;
    today: Record<string, number | string | null>;
    closure_policy: string;
    limits: { daily_loss_stop_pct: number; daily_loss_pct: number; max_trades_per_day: number; max_entry_drift_r: number; day_start_equity: number };
    last_exit: { trade_id: string; side: Side; exit_reason: string | null; net_pnl: number | null; r_multiple: number | null; duration_minutes: number | null; closed_at: string } | null;
  };
  funnel?: Funnel;
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
  alerts?: AlertsSummary | null;
  auto_paper?: boolean;
  demo: { status: string; reasons: { code: string; why: string }[]; paper_desk_sends_orders: boolean; how_to_unlock: string };
  problems: string[];
  engine_errors?: string[];
}

export interface JournalResponse {
  simulated: boolean;
  source_mode: SourceMode;
  desk_fault: string | null;
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
export const fetchSignals = (signal?: AbortSignal) => getJson<SignalHistoryResponse>("/trade/signals?limit=20", signal);
export const fetchSetups = (signal?: AbortSignal) => getJson<SetupHistoryResponse>("/trade/setups?days=7", signal);
export const fetchJournal = (signal?: AbortSignal) => getJson<JournalResponse>("/trade/journal?limit=500", signal);

export interface ActionError {
  code: string;
  message: string;
}

async function post<T>(path: string, body: unknown): Promise<{ ok: true; data: T } | { ok: false; error: ActionError }> {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), 12_000); // a hung request must not leave the page busy forever
  try {
    const res = await fetch(`/api/trade/${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: ctl.signal,
    });
    const json = await res.json();
    if (res.ok) return { ok: true, data: json as T };
    const detail = json?.detail ?? {};
    return { ok: false, error: { code: String(detail.code ?? res.status), message: String(detail.message ?? detail.code ?? "bị từ chối") } };
  } catch {
    return { ok: false, error: { code: "NETWORK", message: "mất kết nối khi gửi yêu cầu: hãy kiểm tra vị thế hiện tại trước khi thử lại" } };
  } finally {
    clearTimeout(timer);
  }
}

export const openPaperTrade = (setup_id: string, risk_pct: number) =>
  post<PaperTrade>("paper/open", { setup_id, risk_pct });
export const closePaperTrade = (trade_id: string) => post<PaperTrade>("paper/close", { trade_id });

/** Quick risk calculator (read-only; the same sizing the paper desk uses). Not a signal. */
export const fetchRisk = (entry: number, stopLoss: number, riskPct: number, signal?: AbortSignal) =>
  getJson<RiskPlan>(`/trade/risk?entry=${entry}&stop_loss=${stopLoss}&risk_pct=${riskPct}`, signal);

export interface NewsEventItem {
  time: string;
  title: string;
  currency: string;
  impact: "high" | "medium" | "low";
  minutes_to: number;
}

/** The canonical news state: only CLEAR is green; every other state is "do not assume no news". */
export interface NewsView {
  state: "CLEAR" | "BLOCKED" | "UNKNOWN" | "NOT_CONFIGURED" | "STALE" | "ERROR";
  detail: string | null;
  warning: boolean;
  text: string;
  coverage: { from: string; to: string } | null;
  last_updated_at: string | null;
  source: string | null;
  next_events: NewsEventItem[];
  blocked_by: NewsEventItem | null;
  last_update: { ok: boolean; error: string | null; last_attempt_at: string; last_success_at: string | null } | null;
}
