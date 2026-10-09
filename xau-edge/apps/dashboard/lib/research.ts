/**
 * Typed, GET-only client for the research console API (`/research/*`, `/lifecycle/*`, ADR-0024).
 * Nothing here can run an experiment, open a locked period or write anything. Every call returns a
 * `Result`: when the request fails, the body is not JSON or the API itself says "unknown", the
 * result is `kind: "unknown"` with a reason. There is no implicit OK.
 */
import { API_URL } from "@/lib/api";

export type LifecycleState =
  | "RESEARCH"
  | "REJECTED"
  | "PAPER"
  | "DEMO"
  | "VALIDATED"
  | "FUNDED"
  | "WATCH"
  | "DEGRADED"
  | "DISABLED"
  | "RETIRED";

export const LIFECYCLE_STATES: LifecycleState[] = [
  "RESEARCH",
  "REJECTED",
  "PAPER",
  "DEMO",
  "VALIDATED",
  "FUNDED",
  "WATCH",
  "DEGRADED",
  "DISABLED",
  "RETIRED",
];

export type Result<T> =
  | { kind: "ok"; data: T; fetchedAt: number }
  | { kind: "unknown"; reason: string; source: string | null; partial: T | null; fetchedAt: number };

/** Every API body carries `status` and (when known) the source path of its figures. */
interface Base {
  status: "ok" | "unknown";
  source?: string;
  reason?: string;
  message?: string;
}

export interface Overview extends Base {
  generated_at: string;
  verdict: { status: string; label?: string; source: string; reason?: string };
  v1: {
    status: string;
    source: string;
    runs?: number;
    malformed_rows?: number;
    k?: number | null;
    k_cap?: number | null;
    alpha?: number | null;
    hypotheses_used?: number;
    hypotheses_budget?: number | null;
    reason?: string;
  };
  v2: {
    status: string;
    started: boolean;
    sprint?: string | null;
    k_declared?: number | null;
    k_cap?: number | null;
    hypotheses_used?: number | null;
    hypotheses_budget?: number | null;
    runs?: number;
    message?: string;
    source: string;
  };
  decisions: { id: string; text: string; recommended: string; state: string }[];
  stop_conditions_reached: string[];
  validated_strategies: string[];
  banner: string | null;
  sources: string[];
}

export interface LedgerRun {
  number: number;
  time: string | null;
  variant: string;
  hypothesis: string;
  period: string;
  scenario: string;
  trades: number | null;
  mean_net_r_base: number | null;
  mean_net_r_pessimistic: number | null;
  verdict: string | null;
  registry_id: string;
  note: string;
}

export interface LedgerView extends Base {
  programme: string;
  k: number | null;
  k_cap: number | null;
  alpha: number | null;
  malformed_rows: number;
  total_runs: number;
  shown: number;
  verdicts: Record<string, number>;
  runs: LedgerRun[];
  legacy_k: { baselines: number; programme_1: number | null };
}

export interface PowerView extends Base {
  k: number;
  n: number;
  sd: number;
  alpha: number;
  mde: number;
  underpowered_by_design: boolean;
  underpowered_threshold: number;
  trades_needed: Record<string, number>;
  curve: { n: number; mde: number }[];
  formula: string;
}

export interface Preregistration {
  state: "OK" | "VIOLATION" | "NO_RESULTS" | "UNKNOWN";
  detail: string;
  registered_at?: string;
  first_run_at?: string;
}

export interface HypothesisRow {
  id: string;
  programme: string;
  title: string;
  registered: string | null;
  grid: string | null;
  path: string;
  results: {
    runs: number;
    variants: number;
    any_pass: boolean;
    best_pessimistic_min: { variant: string; value: number } | null;
  };
  preregistration: Preregistration;
}

export interface HypothesesView extends Base {
  hypotheses: HypothesisRow[];
  planned: { id: string; name: string; batch: string }[];
  violations: string[];
}

export type GateState = "PASS" | "FAIL" | "CHƯA CHẠY" | "KHÔNG RÕ";
export type GateMap = Record<string, { state: GateState; detail?: unknown }>;

export interface CandidatePeriodBrief {
  trades: number | null;
  mean_net_r_base: number | null;
  mean_net_r_pessimistic: number | null;
  stage_pass: boolean;
  criteria_passed: number;
  criteria_total: number;
}

export interface CandidatesView extends Base {
  survivors: string[];
  variants: {
    variant: string;
    hypothesis: string | null;
    periods: Record<string, CandidatePeriodBrief>;
    survivor: boolean;
    gates: GateMap;
  }[];
  note: string;
}

export interface Criterion {
  passed: boolean;
  value: number | null;
  threshold: number | null;
}

export interface CandidatePeriod extends CandidatePeriodBrief {
  criteria: Record<string, Criterion>;
  metrics: Record<string, number | null>;
  variants_k: number | null;
  alpha: number | null;
  dataset_ids: Record<string, string> | null;
  registry_id: string | null;
  recorded_at: string | null;
}

export interface CandidateDetail extends Base {
  variant: string;
  hypothesis: string | null;
  periods: Record<string, CandidatePeriod>;
  gates: GateMap;
  gross_mid_r: number | null;
  gross_mid_note: string;
  equity_curve: unknown;
  equity_note: string;
  sources: string[];
}

export interface Issue {
  code: string;
  severity: string;
  count: number;
}

export interface DataView extends Base {
  generated_at: string | null;
  frames: {
    timeframe: string;
    rows: number | null;
    first: string | null;
    last: string | null;
    dataset_id: string | null;
    validation_passed: boolean | null;
    errors: Issue[];
    warnings: Issue[];
  }[];
  clock_certificate: {
    source: string;
    present: boolean;
    years: { year: number; certified: boolean; state: string; offset: number | null }[];
    session_hypotheses_blocked_years: number[];
    message: string;
  };
}

export interface LockRow {
  id: string;
  name: string;
  from: string;
  to: string | null;
  use: string;
  burned: boolean;
  state: string;
}

export interface LocksView extends Base {
  registry_records: number;
  unreadable_records: number;
  locks: LockRow[];
  freeze_records: string[];
}

export interface StrategyRow {
  strategy_id: string;
  state: LifecycleState;
  history: { strategy_id: string; from_state: string; to_state: string; at: string; source: string; reason: string }[];
  web_demotable: boolean;
}

export interface StrategiesView extends Base {
  strategies: StrategyRow[];
  states: LifecycleState[];
  web_rule: string;
}

export interface ForwardView extends Base {
  strategy_id: string;
  n_trades: number;
  min_trades_for_conclusion: number;
  conclusion: "KHÔNG KẾT LUẬN" | "ĐỦ MẪU";
  expected_vs_realised: Record<string, unknown>;
  decay: { suggestion: string; reasons: string[]; window_means: number[]; max_drawdown_r: number | null } | null;
  updated_at: string | null;
}

export interface CalibrationView extends Base {
  assumed: Record<string, number>;
  measured: Record<string, unknown> | null;
}

export interface SoakView extends Base {
  cycles?: number;
  decided_bars?: number;
  duplicate_bars?: number;
  expected_bars?: number | null;
  uptime_m15?: number | null;
  days_covered?: number | null;
  target?: { soak_days: number; uptime_min: number; duplicates_max: number; demo_weeks: number };
  alerts?: { lines: number } | null;
  funded_rules?: { status: string; source: string; pending?: string[]; total?: number; reason?: string };
}

async function get<T extends Base>(path: string, signal?: AbortSignal): Promise<Result<T>> {
  const fetchedAt = Date.now();
  try {
    const res = await fetch(`${API_URL}${path}`, { signal, cache: "no-store" });
    if (!res.ok) {
      return { kind: "unknown", reason: `API trả về lỗi ${res.status}`, source: path, partial: null, fetchedAt };
    }
    const body = (await res.json()) as T | null;
    if (body === null || typeof body !== "object" || body.status !== "ok") {
      const bare = new Set(["status", "source", "reason", "message"]);
      const partial = body !== null && typeof body === "object" && Object.keys(body).some((k) => !bare.has(k)) ? body : null;
      return {
        kind: "unknown",
        reason: body?.reason ?? body?.message ?? "nguồn dữ liệu không rõ",
        source: body?.source ?? path,
        partial,
        fetchedAt,
      };
    }
    return { kind: "ok", data: body, fetchedAt };
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    return { kind: "unknown", reason: "không kết nối được API", source: path, partial: null, fetchedAt };
  }
}

export const research = {
  overview: (s?: AbortSignal) => get<Overview>("/research/overview", s),
  ledger: (programme: "v1" | "v2", s?: AbortSignal) => get<LedgerView>(`/research/ledger?programme=${programme}`, s),
  power: (k: number, n: number, sd: number, s?: AbortSignal) => get<PowerView>(`/research/power?k=${k}&n=${n}&sd=${sd}`, s),
  hypotheses: (s?: AbortSignal) => get<HypothesesView>("/research/hypotheses", s),
  candidates: (s?: AbortSignal) => get<CandidatesView>("/research/candidates", s),
  candidate: (variant: string, s?: AbortSignal) => get<CandidateDetail>(`/research/candidates/${encodeURIComponent(variant)}`, s),
  data: (s?: AbortSignal) => get<DataView>("/research/data", s),
  locks: (s?: AbortSignal) => get<LocksView>("/research/locks", s),
  calibration: (s?: AbortSignal) => get<CalibrationView>("/research/calibration", s),
  soak: (s?: AbortSignal) => get<SoakView>("/research/soak", s),
  strategies: (s?: AbortSignal) => get<StrategiesView>("/lifecycle/strategies", s),
  forward: (id: string, s?: AbortSignal) => get<ForwardView>(`/lifecycle/${encodeURIComponent(id)}/forward`, s),
};

/** Words the console never shows, even if a source file contains them (they are replaced). */
const FORBIDDEN: [RegExp, string][] = [
  [/profit/gi, "lợi nhuận"],
  [/winning/gi, "[ẩn]"],
  [/guaranteed/gi, "[ẩn]"],
  [/will make money/gi, "[ẩn]"],
];

export function clean(text: string): string {
  return FORBIDDEN.reduce((acc, [re, to]) => acc.replace(re, to), text);
}

export function fmt(value: unknown, digits = 3): string {
  if (value === null || value === undefined) return "chưa có";
  if (typeof value === "number") return Number.isFinite(value) ? value.toFixed(digits) : "chưa có";
  if (typeof value === "boolean") return value ? "có" : "không";
  if (typeof value === "string") return clean(value);
  if (typeof value === "object") {
    const o = value as Record<string, unknown>;
    const mid = o.mean ?? o.value ?? o.point ?? o.estimate;
    if (typeof o.lo === "number" && typeof o.hi === "number") {
      const head = typeof mid === "number" ? `${mid.toFixed(digits)} ` : "";
      return `${head}[${o.lo.toFixed(digits)}; ${o.hi.toFixed(digits)}]`;
    }
    if (typeof mid === "number") return mid.toFixed(digits);
    if (typeof o.lo === "number") return `≥ ${o.lo.toFixed(digits)} (cận dưới)`;
  }
  return "chưa có";
}

export type EvidenceLabel = "VALIDATED" | "UNVALIDATED" | "REJECTED";

export function evidenceLabel(state: string | null | undefined): EvidenceLabel {
  if (state === "VALIDATED" || state === "FUNDED") return "VALIDATED";
  if (state === "REJECTED" || state === "RETIRED" || state === "DISABLED") return "REJECTED";
  return "UNVALIDATED";
}

export function ageText(iso: string | null | undefined, now: number): { text: string; stale: boolean } | null {
  if (!iso || now === 0) return null;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return null;
  const sec = Math.max(0, (now - t) / 1000);
  const text =
    sec < 90
      ? `${Math.round(sec)} giây trước`
      : sec < 5400
        ? `${Math.round(sec / 60)} phút trước`
        : sec < 129600
          ? `${(sec / 3600).toFixed(1)} giờ trước`
          : `${Math.round(sec / 86400)} ngày trước`;
  return { text, stale: sec > 86400 };
}
